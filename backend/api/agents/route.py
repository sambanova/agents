import asyncio
from datetime import datetime
import json
from collections import deque
import re
import os
import time

from autogen_core import MessageContext
from autogen_core import (
    DefaultTopicId,
    RoutedAgent,
    message_handler,
    type_subscription,
)
from autogen_core.models import SystemMessage, UserMessage, CreateResult
from autogen_core.models import AssistantMessage as AssistantMessageCore
from autogen_ext.models.openai import OpenAIChatCompletionClient
import redis

from api.websocket_interface import WebSocketInterface
from config.model_registry import model_registry
from services.query_router_service import QueryRouterServiceChat, QueryType

from api.data_types import (
    APIKeys,
    AgentRequest,
    AgentStructuredResponse,
    AssistantMessage,
    DeepResearch,
    EndUserMessage,
    ErrorResponse,
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
        websocket_manager: WebSocketInterface,
        redis_client: redis.Redis,
        api_keys: APIKeys,
    ) -> None:
        super().__init__("SemanticRouterAgent")
        logger.info(logger.format_message(None, f"Initializing SemanticRouterAgent '{name}' with ID: {self.id}"))
        self._name = name
        self.api_keys = api_keys

        _reasoning_model_name = "llama-3.3-70b"

        self._reasoning_model = lambda provider: OpenAIChatCompletionClient(
            model=model_registry.get_model_info(provider=provider, model_key=_reasoning_model_name)["model"],
            base_url=model_registry.get_model_info(provider=provider, model_key=_reasoning_model_name)["url"],
            api_key=getattr(api_keys, model_registry.get_api_key_env(provider=provider)),
            default_headers=self.api_keys.extra_headers,
            temperature=0.0,
            model_info={
                "json_output": False,
                "function_calling": True,
                "family": "unknown",
                "vision": False,
            },
        )

        self._structure_extraction_model_name = "llama-3.3-70b"
        self._structure_extraction_model = lambda provider: OpenAIChatCompletionClient(
            model=model_registry.get_model_info(provider=provider, model_key=self._structure_extraction_model_name)["model"],
            base_url=model_registry.get_model_info(provider=provider, model_key=self._structure_extraction_model_name)["url"],
            api_key=getattr(api_keys, model_registry.get_api_key_env(provider=provider)),
            default_headers=self.api_keys.extra_headers,
            temperature=0.0,
            model_info={
                "json_output": False,
                "function_calling": True,
                "family": "unknown",
                "vision": False,
            },
        )

        self._context_summary_model_name = "llama-3.3-70b"
        self._context_summary_model = lambda provider: OpenAIChatCompletionClient(
            model=model_registry.get_model_info(provider=provider, model_key=self._context_summary_model_name)["model"],
            base_url=model_registry.get_model_info(provider=provider, model_key=self._context_summary_model_name)["url"],
            api_key=getattr(api_keys, model_registry.get_api_key_env(provider=provider)),
            default_headers=self.api_keys.extra_headers,
            temperature=0.0,
            model_info={
                "json_output": False,
                "function_calling": True,
                "family": "unknown",
                "vision": False,
            },
        )

        self._session_manager = session_manager
        self.websocket_manager = websocket_manager
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
                "docs": message.docs,
                "query": message.content,
                "provider": message.provider,
                "message_id": message.message_id,
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

        try:

            logger.info(logger.format_message(
                ctx.topic_id.source,
                f"Using query router for message: '{message.content[:100]}...'"
            ))

            user_id, conversation_id = ctx.topic_id.source.split(":")
            history = self._session_manager.get_history(conversation_id)

            last_content = {}
            if len(history) > 0:
                try:
                    last_content = json.loads(history[-1].content)
                except json.JSONDecodeError:
                    pass

            if "deep_research_question" in last_content:
                logger.info(logger.format_message(
                    ctx.topic_id.source,
                    "Deep research feedback received, routing to deep research"
                ))
                deep_research_request = AgentRequest(
                    agent_type=AgentEnum.DeepResearch,
                    parameters=DeepResearch(deep_research_topic=""),
                    query=message.content,
                    provider=message.provider,
                    docs=message.docs,
                    message_id=message.message_id,
                )
                await self.publish_message(
                    deep_research_request, DefaultTopicId(type="deep_research", source=ctx.topic_id.source))
                return

            api_key = getattr(self.api_keys, model_registry.get_api_key_env(message.provider))
            router = QueryRouterServiceChat(
                llm_api_key=api_key,
                extra_headers=self.api_keys.extra_headers,
                provider=message.provider,
                model_name=message.planner_model,
                websocket_manager=self.websocket_manager,
                redis_client=self.redis_client,
                user_id=user_id,
                conversation_id=conversation_id,
                message_id=message.message_id
            )

            history = self._session_manager.get_history(conversation_id)

            if len(history) > 0:
                model_response = await self._context_summary_model(message.provider).create(
                    [SystemMessage(content=f"""You are a helpful assistant that summarises conversations for other processes to use as a context. 
                                   Follow the instructions below to create the summary:
                                   - Mention the user has uploaded {len(message.docs) if message.docs else 0} documents, do not mention the content of the documents.
                                   - Include the topics and entities discussed in the conversation.
                                   - Include the main points discussed in the conversation.
                                   - Include the summary of the questions asked by the user.
                                   - Include the summary of the responses provided by the assistant.
                                   - Include the overall summary of the conversation.
                                   """, source="system")]
                    + list(history)
                    + [UserMessage(content="Summarize the messages so far in a few sentences including your responses. Focus on including the topis", source="user")]
                )
                context_summary = model_response.content
            else:
                context_summary = ""

            route_result: QueryType = await router.route_query(message.content, context_summary, len(message.docs) if message.docs else 0)

            self._session_manager.add_to_history(
                    conversation_id,
                    UserMessage(content=message.content, source="user")
            )

            request_obj = self._create_request(
                route_result.type, route_result.parameters, message
            )
            logger.info(logger.format_message(
                ctx.topic_id.source,
                f"Routing to {request_obj.agent_type.value} agent with parameters: {route_result.parameters}"
            ))
            await self._publish_message(request_obj, ctx)
            logger.info(logger.format_message(
                ctx.topic_id.source,
                f"Successfully published request to {request_obj.agent_type.value}"
            ))

        except Exception as e:
            logger.error(logger.format_message(
                ctx.topic_id.source,
                f"Error processing request: {str(e)}"
            ), exc_info=True)

            # Send response back
            response = AgentStructuredResponse(
                agent_type=AgentEnum.Error,
                data=ErrorResponse(error=f"Unable to route message, try again later."),
                message=f"Error processing message routing: {str(e)}",
                message_id=message.message_id
            )
            await self.publish_message(
                response,
                DefaultTopicId(type="user_proxy", source=ctx.topic_id.source),
            )
            return

    def _reconcile_plans(self, plans: list) -> list:
        """
        Reconciles multiple plans into a single plan.
        """
        user_proxy_plans = []
        assistant_plans = []
        deep_research_plans = []
        for plan in plans:
            if plan["agent_type"] == AgentEnum.UserProxy:
                user_proxy_plans.append(plan)
            elif plan["agent_type"] == AgentEnum.Assistant:
                assistant_plans.append(plan)
            elif plan["agent_type"] == AgentEnum.DeepResearch:
                deep_research_plans.append(plan)

        if len(user_proxy_plans) > 0:
            return [user_proxy_plans[0]]
        elif len(assistant_plans) > 0:
            return [assistant_plans[0]]
        elif len(deep_research_plans) > 0:
            return [deep_research_plans[0]]
        else:
            return [plans[0]]

    async def _publish_message(
        self, request_obj: AgentRequest, ctx: MessageContext
    ) -> None:
        """
        Publishes a message to the appropriate agent.
        """
        if request_obj.agent_type == AgentEnum.UserProxy:
            response = AgentStructuredResponse(
                agent_type=request_obj.agent_type,
                data=request_obj.parameters,
                message=request_obj.parameters.model_dump_json(),
                message_id=request_obj.message_id
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

    async def _get_agents_to_route(
        self, message: EndUserMessage, ctx: MessageContext
    ) -> None:
        """
        Determines the appropriate agents to route the message to based on context.

        Args:
            message (EndUserMessage): The incoming user message.
        """

        # TODO: remove this when fixed route
        user_id, conversation_id = ctx.topic_id.source.split(":")
        history = self._session_manager.get_history(conversation_id)

        last_content = {}
        if len(history) > 0:
            try:
                last_content = json.loads(history[-1].content)
            except json.JSONDecodeError:
                pass

        if "deep_research_question" in last_content:
            logger.info(logger.format_message(
                ctx.topic_id.source,
                "Deep research feedback received, routing to deep research"
            ))
            deep_research_request = AgentRequest(
                agent_type=AgentEnum.DeepResearch,
                parameters=DeepResearch(deep_research_topic=""),
                query=message.content,
            )
            await self.publish_message(
                deep_research_request, DefaultTopicId(type="deep_research", source=ctx.topic_id.source))
            return

        logger.info(logger.format_message(
            ctx.topic_id.source,
            f"Determining agents to route message: '{message.content[:100]}...'"
        ))
        system_message = agent_registry.get_planner_prompt()

        try:
            start_time = time.time()

            planner_response = self._reasoning_model(message.provider).create_stream(
                [SystemMessage(content=system_message, source="system")]
                + list(history)
                + [UserMessage(content=message.content, source="user")]
            )

            self._session_manager.add_to_history(
                conversation_id,
                UserMessage(content=message.content, source="user")
            )

            # Send the chunks through WebSocket if connection exists
            if self.websocket is None:
                logger.error(logger.format_message(
                    ctx.topic_id.source,
                    "No WebSocket connection found"
                ))
                raise ValueError("No WebSocket connection found")

            planner_metadata = {
                "llm_name": self._reasoning_model(message.provider)._resolved_model,
                "llm_provider": message.provider,
                "task": "planning",
            }   
            planner_event = {
                "event": "planner",
                "data": json.dumps({"metadata": planner_metadata}),
                "user_id": user_id,
                "conversation_id": conversation_id,
                "message_id": message.message_id,
                "timestamp": datetime.now().isoformat(),
            }

            await self.websocket.send_text(json.dumps(planner_event))

            planner_final_response = None
            async for chunk in planner_response:
                if isinstance(chunk, str):
                    message_data = {
                        "event": "planner_chunk",
                        "data": chunk,
                        "message_id": message.message_id,
                    }
                    await self.websocket.send_text(json.dumps(message_data))
                elif isinstance(chunk, CreateResult):
                    planner_final_response = chunk.content

            end_time = time.time()
            processing_time = end_time - start_time
            planner_metadata["duration"] = processing_time

            if planner_final_response:
                # Store complete response in Redis
                message_key = f"messages:{user_id}:{conversation_id}"
                final_message_data = {
                    "event": "planner",
                    "data": json.dumps({"response": planner_final_response, "metadata": planner_metadata}),
                    "user_id": user_id,
                    "conversation_id": conversation_id,
                    "message_id": message.message_id,
                    "timestamp": datetime.now().isoformat(),
                }
                self.redis_client.rpush(message_key, json.dumps(final_message_data))
                await self.websocket.send_text(json.dumps(final_message_data))

                cleaned_response = re.sub(
                    r"<think>.*?</think>",
                    "",
                    (
                        planner_final_response
                        if isinstance(planner_final_response, str)
                        else str(planner_final_response)
                    ),
                    flags=re.DOTALL,
                ).strip()
                feature_extractor_response = await self._structure_extraction_model(message.provider).create(
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

                # reconcile multiple plans
                plan = self._reconcile_plans(plan)

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

                    await self._publish_message(request_obj, ctx)
            else:
                logger.error(logger.format_message(
                    ctx.topic_id.source,
                    "No planner response found"
                ))
                raise ValueError("No planner response found")

        except Exception as e:
            logger.error(
                logger.format_message(
                    ctx.topic_id.source,
                    f"SemanticRouterAgent failed to parse activities response: {str(e)}"
                )
            )
            logger.info(logger.format_message(ctx.topic_id.source, "SemanticRouterAgent defaulting to assistant agent"))
            request_obj = AgentRequest(
                provider=message.provider,
                agent_type=AgentEnum.Assistant,
                parameters=AssistantMessage(query=message.content),
                query=message.content,
            )
            await self.publish_message(
                request_obj,
                DefaultTopicId(
                    type=request_obj.agent_type.value,
                    source=ctx.topic_id.source,
                ),
            )
            return
