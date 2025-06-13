import json
import time
import uuid
from typing import Any, Callable, Union

import structlog
from agents.api.data_types import (
    AgentEnum,
    AgentRequest,
    AgentStructuredResponse,
    APIKeys,
    DeepResearchReport,
    DeepResearchUserQuestion,
    ErrorResponse,
)
from agents.components.open_deep_research.configuration import SearchAPI
from agents.components.open_deep_research.graph import (
    LLMTimeoutError,
    create_deep_research_graph,
)
from agents.components.open_deep_research.utils import APIKeyRotator
from agents.registry.model_registry import model_registry
from agents.storage.redis_service import SecureRedisService
from agents.utils.error_utils import format_api_error_message
from autogen_core import (
    DefaultTopicId,
    MessageContext,
    RoutedAgent,
    message_handler,
    type_subscription,
)
from fastapi import WebSocket
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command

logger = structlog.get_logger(__name__)


def create_publish_callback(
    user_id: str,
    conversation_id: str,
    message_id: str,
    agent_name: str,
    workflow_name: str,
    redis_client: SecureRedisService,
    token_usage_callback: Callable[[dict], None] = None,
):

    def callback(
        message: str,
        llm_name: str,
        task: str,
        usage: dict,
        llm_provider: str,
        duration: float,
    ):
        response_duration = usage.get("end_time", 0) - usage.get("start_time", 0)
        if response_duration > 0:
            duration = response_duration

        # Track token usage if callback provided
        if token_usage_callback and usage:
            token_usage = {
                "total_tokens": usage.get("total_tokens", 0),
                "prompt_tokens": usage.get("prompt_tokens", 0),
                "completion_tokens": usage.get("completion_tokens", 0),
            }
            token_usage_callback(token_usage)

        message_data = {
            "user_id": user_id,
            "run_id": conversation_id,
            "message_id": message_id,
            "agent_name": agent_name,
            "text": message,
            "timestamp": time.time(),
            "metadata": {
                "workflow_name": workflow_name,
                "agent_name": agent_name,
                "llm_name": llm_name,
                "llm_provider": llm_provider,
                "task": task,
                "total_tokens": usage.get("total_tokens", 0),
                "prompt_tokens": usage.get("prompt_tokens", 0),
                "completion_tokens": usage.get("completion_tokens", 0),
                "acceptance_rate": usage.get("acceptance_rate", 0),
                "completion_tokens_after_first_per_sec": usage.get(
                    "completion_tokens_after_first_per_sec", 0
                ),
                "completion_tokens_after_first_per_sec_first_ten": usage.get(
                    "completion_tokens_after_first_per_sec_first_ten", 0
                ),
                "completion_tokens_per_sec": usage.get("completion_tokens_per_sec", 0),
                "time_to_first_token": usage.get("time_to_first_token", 0),
                "total_latency": usage.get("total_latency", 0),
                "total_tokens_per_sec": usage.get("total_tokens_per_sec", 0),
                "duration": duration,
            },
        }
        channel = f"agent_thoughts:{user_id}:{conversation_id}"
        redis_client.publish(channel, json.dumps(message_data))

    return callback


@type_subscription(topic_type="deep_research")
class DeepResearchAgent(RoutedAgent):
    """
    Handles advanced multi-section research with user feedback (interrupt).
    """

    def __init__(self, api_keys: APIKeys, redis_client: SecureRedisService = None):
        super().__init__("DeepResearchAgent")
        self.api_keys = api_keys
        self.redis_client = redis_client
        logger.info(
            logger.format_message(
                None, f"Initializing DeepResearchAgent with ID: {self.id}"
            )
        )
        # memory saver per user session
        self.memory_stores = {}
        self._session_threads = {}

    def _get_or_create_memory(self, session_id: str) -> MemorySaver:
        if session_id not in self.memory_stores:
            self.memory_stores[session_id] = MemorySaver()
        return self.memory_stores[session_id]

    def _get_or_create_thread_config(
        self, session_id: str, llm_provider: str, message_id: str
    ) -> dict:
        if session_id not in self._session_threads:
            user_id, conversation_id = session_id.split(":")
            thread_id = str(uuid.uuid4())
            self._session_threads[session_id] = {
                "configurable": {
                    "thread_id": thread_id,
                    "search_api": SearchAPI.TAVILY,
                    "api_key_rotator": APIKeyRotator(env_var_prefix="TAVILY_API_KEY"),
                    "user_id": user_id,
                    "conversation_id": conversation_id,
                    "provider": llm_provider,
                    "token_usage": {
                        "total_tokens": 0,
                        "prompt_tokens": 0,
                        "completion_tokens": 0,
                    },
                    "callback": create_publish_callback(
                        message_id=message_id,
                        user_id=user_id,
                        conversation_id=conversation_id,
                        agent_name="deep_research",
                        workflow_name="deep_research",
                        redis_client=self.redis_client,
                        token_usage_callback=self._update_token_usage(session_id),
                    ),
                }
            }
        return self._session_threads[session_id]

    def _update_token_usage(self, session_id: str):
        def update(usage: dict):
            if session_id in self._session_threads:
                token_usage = self._session_threads[session_id]["configurable"][
                    "token_usage"
                ]
                token_usage["total_tokens"] += usage.get("total_tokens", 0)
                token_usage["prompt_tokens"] += usage.get("prompt_tokens", 0)
                token_usage["completion_tokens"] += usage.get("completion_tokens", 0)

        return update

    @message_handler
    async def handle_deep_research_request(
        self, message: AgentRequest, ctx: MessageContext
    ) -> None:
        logger.info(
            logger.format_message(
                ctx.topic_id.source, f"DeepResearchAgent received message: {message}"
            )
        )
        session_id = ctx.topic_id.source
        user_text = message.query.strip()

        # Reset token usage for new requests
        if session_id in self._session_threads:
            self._session_threads[session_id]["configurable"]["token_usage"] = {
                "total_tokens": 0,
                "prompt_tokens": 0,
                "completion_tokens": 0,
            }

        # Decide if it's feedback or a brand-new request
        if user_text.lower() == "true":
            graph_input = Command(resume=True)
        elif user_text.lower() == "false":
            graph_input = Command(resume=False)
        elif user_text and (not message.parameters.deep_research_topic):
            # user typed some text, treat it as feedback
            graph_input = Command(resume=user_text)
        else:
            # brand-new request with the entire user query in topic
            if message.docs:
                graph_input = {
                    "topic": message.parameters.deep_research_topic,
                    "document": "\n\n".join(message.docs),
                }
            else:
                graph_input = {"topic": message.parameters.deep_research_topic}

        memory = self._get_or_create_memory(session_id)
        builder = create_deep_research_graph(
            getattr(
                self.api_keys, model_registry.get_api_key_env(provider=message.provider)
            ),
            provider=message.provider,
        )

        graph = builder.compile(checkpointer=memory)
        thread_config = self._get_or_create_thread_config(
            session_id, message.provider, message.message_id
        )

        try:
            async for event in graph.astream(
                graph_input, thread_config, stream_mode="updates"
            ):
                logger.info(
                    logger.format_message(
                        session_id, f"DeepResearchFlow Event: {event}"
                    )
                )
                # if there's an interrupt, we ask user for feedback
                if "__interrupt__" in event:
                    interrupt_data = event["__interrupt__"]
                    if isinstance(interrupt_data, tuple) and interrupt_data:
                        interrupt_msg = interrupt_data[0].value
                        user_question_str = (
                            "Please <b>provide feedback</b> on the following plan or <b>type 'true' to approve it</b>.\n\n"
                            f"{interrupt_msg}\n\n"
                        )
                        token_usage = self._session_threads[session_id]["configurable"][
                            "token_usage"
                        ]
                        response = AgentStructuredResponse(
                            agent_type=AgentEnum.UserProxy,
                            data=DeepResearchUserQuestion(
                                deep_research_question=user_question_str
                            ),
                            message=user_question_str,
                            metadata=token_usage,
                            message_id=message.message_id,
                        )
                        await self.publish_message(
                            response,
                            DefaultTopicId(
                                type="user_proxy", source=ctx.topic_id.source
                            ),
                        )
                    return

            # If we get here => the flow completed
            final_state = graph.get_state(thread_config, subgraphs=True)
            dr_report = final_state.values.get("deep_research_report", None)
            if dr_report is None:
                logger.warning(
                    logger.format_message(
                        session_id, "No deep_research_report found. Fallback."
                    )
                )
                dr_report = {
                    "sections": [],
                    "final_report": final_state.values.get("final_report", ""),
                }

            # Add token usage to the report
            token_usage = self._session_threads[session_id]["configurable"][
                "token_usage"
            ]
            structured_report = DeepResearchReport.model_validate(dr_report)
            response = AgentStructuredResponse(
                agent_type=AgentEnum.DeepResearch,
                data=structured_report,
                message="Deep research flow completed.",
                metadata=token_usage,
                message_id=message.message_id,
            )

            await self.publish_message(
                response,
                DefaultTopicId(type="user_proxy", source=ctx.topic_id.source),
            )

        except LLMTimeoutError as e:
            logger.error(
                logger.format_message(session_id, f"DeepResearch flow error timeout")
            )
            response = AgentStructuredResponse(
                agent_type=AgentEnum.Error,
                data=ErrorResponse(
                    error=f"Deep research flow timed out, please try again later."
                ),
                message=f"Error processing deep research request: {str(e)}",
                message_id=message.message_id,
            )
            await self.publish_message(
                response,
                DefaultTopicId(type="user_proxy", source=ctx.topic_id.source),
            )

        except Exception as e:
            logger.error(
                logger.format_message(session_id, f"DeepResearch flow error: {str(e)}"),
                exc_info=True,
            )

            error_response = format_api_error_message(e, "deep research")

            response = AgentStructuredResponse(
                agent_type=AgentEnum.Error,
                data=ErrorResponse(error=error_response),
                message=f"Error processing deep research request: {str(e)}",
                message_id=message.message_id,
            )
            await self.publish_message(
                response,
                DefaultTopicId(type="user_proxy", source=ctx.topic_id.source),
            )
