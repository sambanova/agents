import asyncio
from datetime import datetime
import json
from collections import deque
import re
import os

from autogen_core import MessageContext
from autogen_core import (
    DefaultTopicId,
    RoutedAgent,
    message_handler,
    type_subscription,
)
from autogen_core.models import SystemMessage, UserMessage
from autogen_ext.models.openai import OpenAIChatCompletionClient
from fastapi import WebSocket
import redis

from services.query_router_service import QueryRouterService, QueryType

from api.data_types import (
    APIKeys,
    AgentRequest,
    AgentStructuredResponse,
    EndUserMessage,
    HandoffMessage,
    AgentEnum,
)
from api.registry import AgentRegistry
from api.session_state import SessionStateManager
from utils.logging import logger

agent_registry = AgentRegistry()


@type_subscription(topic_type="router")
class SemanticRouterAgent(RoutedAgent):
    """
    The SemanticRouterAgent routes incoming messages to appropriate agents based on the intent.

    Attributes:
        name (str): Name of the agent.
        model_client (OpenAIChatCompletionClient): The model client for agent routing.
        agent_registry (AgentRegistry): The registry containing agent information.
        session_manager (SessionStateManager): Manages the session state for each user.
        connection_manager (WebSocketConnectionManager): Manages WebSocket connections.
    """

    def __init__(
        self,
        name: str,
        session_manager: SessionStateManager,
        websocket: WebSocket,
        redis_client: redis.Redis,
        api_keys: APIKeys,
    ) -> None:
        super().__init__("SemanticRouterAgent")
        logger.info(logger.format_message(None, f"Initializing SemanticRouterAgent '{name}' with ID: {self.id}"))
        self._name = name
        self._reasoning_model_client = OpenAIChatCompletionClient(
            model="DeepSeek-R1-Distill-Llama-70B",
            base_url="https://api.sambanova.ai/v1",
            api_key=api_keys.sambanova_key,
            model_info={
                "json_output": False,
                "function_calling": True,
                "family": "unknown",
                "vision": False,
            },
        )
        self._structure_extraction_model = OpenAIChatCompletionClient(
            model="Meta-Llama-3.1-70B-Instruct",
            base_url="https://api.sambanova.ai/v1",
            api_key=api_keys.sambanova_key,
            model_info={
                "json_output": False,
                "function_calling": True,
                "family": "unknown",
                "vision": False,
            },
        )
        self._session_manager = session_manager
        self.websocket = websocket
        self.redis_client = redis_client

    @message_handler
    async def route_message(self, message: EndUserMessage, ctx: MessageContext) -> None:
        """
        Routes user messages to appropriate agents based on conversation context.

        Args:
            message (EndUserMessage): The incoming user message.
            ctx (MessageContext): Context information for the message.
        """
        logger.info(logger.format_message(
            ctx.topic_id.source,
            f"Routing message: '{message.content[:100]}...' (use_planner={message.use_planner})"
        ))
        if message.use_planner:
            await self._get_agents_to_route(message, ctx)
        else:
            await self.route_message_with_query_router(message, ctx)

    def _create_request(
        self, request_type: str, parameters: dict, message: EndUserMessage
    ) -> AgentRequest:
        """
        Creates the appropriate request object based on the request type.

        Args:
            request_type (str): The type of request to create
            parameters (dict): The parameters for the request
            message (EndUserMessage): The original message containing API keys and document IDs

        Returns:
            AgentRequest: The request object for the agent
        """

        agent_type = AgentEnum(request_type)
        # Create AgentRequest using model_validate
        request = AgentRequest.model_validate(
            {
                "agent_type": agent_type,
                "parameters": parameters,
                "document_ids": message.document_ids,
                "query": message.content,
            }
        )

        return request

    async def route_message_with_query_router(
        self, message: EndUserMessage, ctx: MessageContext
    ) -> None:
        """
        Routes user messages to appropriate agents based on conversation context.

        Args:
            message (EndUserMessage): The incoming user message.
            ctx (MessageContext): Context information for the message.
        """
        logger.info(logger.format_message(
            ctx.topic_id.source,
            f"Using query router for message: '{message.content[:100]}...'"
        ))
        router = QueryRouterService(message.api_keys.sambanova_key)
        route_result: QueryType = router.route_query(message.content)

        try:
            request_obj = self._create_request(
                route_result.type, route_result.parameters, message
            )
            logger.info(logger.format_message(
                ctx.topic_id.source,
                f"Routing to {request_obj.agent_type.value} agent with parameters: {route_result.parameters}"
            ))
            await self.publish_message(
                request_obj,
                DefaultTopicId(
                    type=request_obj.agent_type.value,
                    source=ctx.topic_id.source,
                ),
            )
            logger.info(logger.format_message(
                ctx.topic_id.source,
                f"Successfully published request to {request_obj.agent_type.value}"
            ))

        except ValueError as e:
            logger.error(logger.format_message(
                ctx.topic_id.source,
                f"Error processing request: {str(e)}"
            ), exc_info=True)
            return

    @message_handler
    async def handle_handoff(
        self, message: HandoffMessage, ctx: MessageContext
    ) -> None:
        """
        Handles handoff messages from other agents.

        Args:
            message (HandoffMessage): The handoff message from another agent.
            ctx (MessageContext): Context information for the message.
        """
        session_id = ctx.topic_id.source
        logger.info(logger.format_message(
            session_id,
            f"Received handoff from {message.source} agent"
        ))

        # Clear session if conversation is complete, otherwise continue routing
        if message.original_task and "complete" in message.content.lower():
            logger.info(logger.format_message(
                session_id,
                "Task complete, clearing session"
            ))
            self._session_manager.clear_session(session_id)
        else:
            logger.info(logger.format_message(
                session_id,
                f"Continuing conversation with new message from {message.source}"
            ))
            await self.route_message(
                EndUserMessage(content=message.content, source=message.source), ctx
            )

    async def _get_agents_to_route(
        self, message: EndUserMessage, ctx: MessageContext
    ) -> None:
        """
        Determines the appropriate agents to route the message to based on context.

        Args:
            message (EndUserMessage): The incoming user message.
        """

        logger.info(logger.format_message(
            ctx.topic_id.source,
            f"Determining agents to route message: '{message.content[:100]}...'"
        ))
        system_message = agent_registry.get_planner_prompt()

        try:
            user_id, conversation_id = ctx.topic_id.source.split(":")

            history = self._session_manager.get_history(ctx.topic_id.source)
            planner_response = await self._reasoning_model_client.create(
                [SystemMessage(content=system_message)]
                + list(history)
                + [UserMessage(content=message.content, source="user")]
            )

            self._session_manager.add_to_history(
                ctx.topic_id.source,
                UserMessage(content=message.content, source="user")
            )

            # Send the chunk through WebSocket if connection exists
            if self.websocket:
                message_data = {
                    "event": "reason",
                    "data": {"reasoning": planner_response.content},
                    "user_id": user_id,
                    "conversation_id": conversation_id,
                    "timestamp": datetime.now().isoformat(),
                }

                # Store in Redis
                message_key = f"messages:{user_id}:{conversation_id}"
                self.redis_client.rpush(message_key, json.dumps(message_data))

                # Send through WebSocket
                await self.websocket.send_text(json.dumps(message_data))
                await asyncio.sleep(0.25)

            cleaned_response = re.sub(
                r"<think>.*?</think>",
                "",
                (
                    planner_response.content
                    if isinstance(planner_response.content, str)
                    else str(planner_response.content)
                ),
                flags=re.DOTALL,
            ).strip()
            feature_extractor_response = await self._structure_extraction_model.create(
                [
                    SystemMessage(
                        content=agent_registry.get_strucuted_output_plan_prompt(
                            cleaned_response
                        )
                    )
                ]
            )

            # TODO: add agents working on a set of tasks
            plan = json.loads(feature_extractor_response.content)
            plan = plan if isinstance(plan, list) else [plan]

            for p in plan:
                try:
                    request_obj = self._create_request(
                        p["agent_type"], p["parameters"], message
                    )
                except Exception as e:
                    logger.error(
                        logger.format_message(
                            ctx.topic_id.source,
                            f"SemanticRouterAgent failed to parse plan item {p}: {str(e)}"
                        )
                    )
                    continue

                logger.info(logger.format_message(
                    ctx.topic_id.source,
                    f"Publishing request to {request_obj.agent_type.value} with parameters: {request_obj.parameters}"
                ))

                if request_obj.agent_type == AgentEnum.UserProxy:
                    response = AgentStructuredResponse(
                        agent_type=request_obj.agent_type,
                        data=request_obj.parameters,
                        message=request_obj.parameters.model_dump_json(),
                    )
                    await self.publish_message(
                        response,
                        DefaultTopicId(
                            type=request_obj.agent_type.value,
                            source=ctx.topic_id.source,
                        ),
                    )
                else:
                    await self.publish_message(
                        request_obj,
                        DefaultTopicId(
                            type=request_obj.agent_type.value,
                            source=ctx.topic_id.source,
                        ),
                    )

        except Exception as e:
            logger.error(
                logger.format_message(
                    ctx.topic_id.source,
                    f"SemanticRouterAgent failed to parse activities response: {str(e)}"
                )
            )
            return
