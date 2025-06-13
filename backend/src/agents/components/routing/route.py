import json
import re
import time
from datetime import datetime, timezone

import redis
import structlog
from agents.api.data_types import (
    AgentEnum,
    AgentRequest,
    AgentStructuredResponse,
    APIKeys,
    AssistantMessage,
    DeepResearch,
    EndUserMessage,
    ErrorResponse,
)
from agents.api.registry import AgentRegistry
from agents.api.session_state import SessionStateManager
from agents.api.websocket_interface import WebSocketInterface
from agents.registry.model_registry import model_registry
from agents.services.query_router_service import QueryRouterServiceChat, QueryType
from agents.utils.error_utils import format_api_error_message
from autogen_core import (
    DefaultTopicId,
    MessageContext,
    RoutedAgent,
    message_handler,
    type_subscription,
)
from autogen_core.models import CreateResult, SystemMessage, UserMessage
from autogen_ext.models.openai import OpenAIChatCompletionClient

logger = structlog.get_logger(__name__)

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
        logger.info(
            logger.format_message(
                None, f"Initializing SemanticRouterAgent '{name}' with ID: {self.id}"
            )
        )
        self._name = name
        self.api_keys = api_keys

        _reasoning_model_name = "llama-3.3-70b"

        self._reasoning_model = lambda provider: OpenAIChatCompletionClient(
            model=model_registry.get_model_info(
                provider=provider, model_key=_reasoning_model_name
            )["model"],
            base_url=model_registry.get_model_info(
                provider=provider, model_key=_reasoning_model_name
            )["url"],
            api_key=getattr(
                api_keys, model_registry.get_api_key_env(provider=provider)
            ),
            model_info={
                "json_output": False,
                "function_calling": True,
                "family": "unknown",
                "vision": False,
            },
        )

        self._structure_extraction_model_name = "llama-3.3-70b"
        self._structure_extraction_model = lambda provider: OpenAIChatCompletionClient(
            model=model_registry.get_model_info(
                provider=provider, model_key=self._structure_extraction_model_name
            )["model"],
            base_url=model_registry.get_model_info(
                provider=provider, model_key=self._structure_extraction_model_name
            )["url"],
            api_key=getattr(
                api_keys, model_registry.get_api_key_env(provider=provider)
            ),
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
            model=model_registry.get_model_info(
                provider=provider, model_key=self._context_summary_model_name
            )["model"],
            base_url=model_registry.get_model_info(
                provider=provider, model_key=self._context_summary_model_name
            )["url"],
            api_key=getattr(
                api_keys, model_registry.get_api_key_env(provider=provider)
            ),
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
        logger.info(
            logger.format_message(
                ctx.topic_id.source,
                f"Routing message: '{message.content[:100]}...' (use_planner={message.use_planner})",
            )
        )

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

            logger.info(
                logger.format_message(
                    ctx.topic_id.source,
                    f"Using query router for message: '{message.content[:100]}...'",
                )
            )

            user_id, conversation_id = ctx.topic_id.source.split(":")
            history = self._session_manager.get_history(conversation_id)

            last_content = {}
            if len(history) > 0:
                try:
                    last_content = json.loads(history[-1].content)
                except json.JSONDecodeError:
                    pass

            if "deep_research_question" in last_content:
                logger.info(
                    logger.format_message(
                        ctx.topic_id.source,
                        "Deep research feedback received, routing to deep research",
                    )
                )
                deep_research_request = AgentRequest(
                    agent_type=AgentEnum.DeepResearch,
                    parameters=DeepResearch(deep_research_topic=""),
                    query=message.content,
                    provider=message.provider,
                    docs=message.docs,
                    message_id=message.message_id,
                )
                await self.publish_message(
                    deep_research_request,
                    DefaultTopicId(type="deep_research", source=ctx.topic_id.source),
                )
                return

            api_key = getattr(
                self.api_keys, model_registry.get_api_key_env(message.provider)
            )
            router = QueryRouterServiceChat(
                llm_api_key=api_key,
                provider=message.provider,
                model_name=message.planner_model,
                websocket_manager=self.websocket_manager,
                redis_client=self.redis_client,
                user_id=user_id,
                conversation_id=conversation_id,
                message_id=message.message_id,
            )

            history = self._session_manager.get_history(conversation_id)

            if len(history) > 0:
                start_time = time.time()
                model_response = await self._context_summary_model(
                    message.provider
                ).create(
                    [
                        SystemMessage(
                            content=f"""You are a helpful assistant that summarises conversations for other processes to use as a context. 
                                   Follow the instructions below to create the summary:
                                   - Mention the user has uploaded {len(message.docs) if message.docs else 0} documents, do not mention the content of the documents.
                                   - Include the topics and entities discussed in the conversation.
                                   - Include the main points discussed in the conversation.
                                   - Include the summary of the questions asked by the user.
                                   - Include the summary of the responses provided by the assistant.
                                   - Include the overall summary of the conversation.
                                   """,
                            source="system",
                        )
                    ]
                    + list(history)
                    + [
                        UserMessage(
                            content="Summarize the messages so far in a few sentences including your responses. Focus on including the topics",
                            source="user",
                        )
                    ]
                )
                context_summary = model_response.content
                end_time = time.time()
                context_summary_time = end_time - start_time
                context_summary_log_message = (
                    f"Context summary took {context_summary_time:.2f} seconds"
                )
                if context_summary_time > 10:
                    logger.warning(
                        logger.format_message(
                            ctx.topic_id.source, context_summary_log_message
                        )
                    )
                else:
                    logger.info(
                        logger.format_message(
                            ctx.topic_id.source, context_summary_log_message
                        )
                    )
            else:
                context_summary = ""

            route_result: QueryType = await router.route_query(
                message.content,
                context_summary,
                len(message.docs) if message.docs else 0,
            )

            self._session_manager.add_to_history(
                conversation_id, UserMessage(content=message.content, source="user")
            )

            request_obj = self._create_request(
                route_result.type, route_result.parameters, message
            )
            logger.info(
                logger.format_message(
                    ctx.topic_id.source,
                    f"Routing to {request_obj.agent_type.value} agent with parameters: {route_result.parameters}",
                )
            )
            await self._publish_message(request_obj, ctx)
            logger.info(
                logger.format_message(
                    ctx.topic_id.source,
                    f"Successfully published request to {request_obj.agent_type.value}",
                )
            )

        except Exception as e:
            logger.error(
                logger.format_message(
                    ctx.topic_id.source, f"Error processing request: {str(e)}"
                ),
                exc_info=True,
            )

            error_response = format_api_error_message(e, "routing message")

            # Send response back
            response = AgentStructuredResponse(
                agent_type=AgentEnum.Error,
                data=ErrorResponse(error=error_response),
                message=f"Error processing message routing: {str(e)}",
                message_id=message.message_id,
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
                message_id=request_obj.message_id,
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
