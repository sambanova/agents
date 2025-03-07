########## deep_research_agent.py (NEW CODE) ##########
import asyncio
import json
from typing import Any, Union
import uuid
from redis import Redis

from autogen_core import MessageContext
from autogen_core import (
    DefaultTopicId,
    RoutedAgent,
    message_handler,
    type_subscription,
)

from fastapi import WebSocket
from langgraph.types import Command
from langgraph.checkpoint.memory import MemorySaver

from api.data_types import (
    AgentRequest,
    AgentStructuredResponse,
    APIKeys,
    AgentEnum,
    DeepResearchUserQuestion,
    DeepResearchReport,
    ErrorResponse,
)
from config.model_registry import model_registry
from utils.logging import logger
from api.agents.open_deep_research.graph import create_publish_callback, get_graph


@type_subscription(topic_type="deep_research")
class DeepResearchAgent(RoutedAgent):
    """
    Handles advanced multi-section research with user feedback (interrupt).
    """

    def __init__(
        self, api_keys: APIKeys, redis_client: Redis = None
    ):
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
        self,
        session_id: str,
        llm_provider: str,
        message_id: str
    ) -> dict:
        if session_id not in self._session_threads:
            user_id, conversation_id = session_id.split(":")
            thread_id = str(uuid.uuid4())
            self._session_threads[session_id] = {
                "configurable": {
                    "thread_id": thread_id,
                    "search_api": "tavily",
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
                graph_input = {"topic": message.parameters.deep_research_topic, "document": "\n\n".join(message.docs)}
            else:
                graph_input = {"topic": message.parameters.deep_research_topic}

        memory = self._get_or_create_memory(session_id)
        builder = get_graph(
            getattr(
                self.api_keys, model_registry.get_api_key_env(provider=message.provider)
                
            ),
            provider=message.provider,
        )

        graph = builder.compile(checkpointer=memory)
        thread_config = self._get_or_create_thread_config(session_id, message.provider, message.message_id)

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
                            message_id=message.message_id
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
                message_id=message.message_id
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
            response = AgentStructuredResponse(
                agent_type=AgentEnum.Error,
                data=ErrorResponse(
                    error=f"Unable to assist with deep research, try again later."
                ),
                message=f"Error processing deep research request: {str(e)}",
                message_id=message.message_id
            )
            await self.publish_message(
                response,
                DefaultTopicId(type="user_proxy", source=ctx.topic_id.source),
            )
