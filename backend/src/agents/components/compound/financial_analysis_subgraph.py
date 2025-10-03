import os
import time
from datetime import datetime, timezone

import langsmith as ls
import structlog
from agents.components.compound.data_types import LiberalAIMessage
from agents.components.compound.util import extract_api_key
from agents.components.crewai_message_interceptor import CrewAIMessageInterceptor
from agents.components.financial_analysis.financial_analysis_crew import (
    FinancialAnalysisCrew,
)
from agents.services.financial_user_prompt_extractor_service import (
    FinancialPromptExtractor,
)
from agents.storage.redis_service import SecureRedisService
from agents.utils.logging_utils import setup_logging_context
from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph import END
from langgraph.graph.message import MessageGraph

logger = structlog.get_logger(__name__)


def create_financial_analysis_graph(redis_client: SecureRedisService, user_id: str = None, api_keys: dict = None):
    """Create a simple subgraph with just one node that greets the user."""
    logger.info("Creating financial analysis subgraph", user_id=user_id[:8] if user_id else "None")

    @ls.traceable(
        metadata={"agent_type": "financial_analysis_agent"},
        process_inputs=lambda x: None,
    )
    async def financial_analysis_node(messages, *, config: RunnableConfig = None):
        setup_logging_context(config, node="financial_analysis")

        try:
            api_key = extract_api_key(config)

            logger.info("Extracting financial info from prompt")
            start_time = time.time()
            fextractor = FinancialPromptExtractor(
                llm_api_key=api_key, provider="sambanova"
            )
            extracted_ticker, extracted_company = fextractor.extract_info(
                messages[-1].content
            )
            duration = time.time() - start_time
            logger.info(
                "Financial info extraction completed",
                duration_ms=round(duration * 1000, 2),
                extracted_ticker=extracted_ticker,
                extracted_company=extracted_company,
            )

            # Initialize crew with message interceptor
            logger.info("Initializing FinancialAnalysisCrew with message interceptor")
            logger.info(f"[FINANCIAL_DEBUG] api_keys from closure: {type(api_keys)}, is None: {api_keys is None}")
            if api_keys:
                logger.info(f"[FINANCIAL_DEBUG] api_keys keys: {list(api_keys.keys())}")

            # Create message interceptor
            # Note: Real-time updates via Redis don't work because CrewAI runs sync
            # Messages will be returned at the end and sent via graph state stream
            message_interceptor = CrewAIMessageInterceptor()

            crew = FinancialAnalysisCrew(
                llm_api_key=api_key,
                provider="sambanova",
                user_id=config["metadata"]["user_id"],
                run_id=config["metadata"]["thread_id"],
                docs_included=False,
                redis_client=redis_client,
                verbose=False,
                message_id=config["metadata"]["message_id"],
                admin_api_keys=api_keys,  # Pass api_keys dict for admin panel support
                message_interceptor=message_interceptor,  # Pass interceptor to crew
            )

            inputs = {"ticker": extracted_ticker, "company_name": extracted_company}

            logger.info(
                "Executing financial analysis crew",
                inputs=inputs,
            )
            start_time = time.time()
            result = await crew.execute_financial_analysis(inputs)
            duration = time.time() - start_time
            logger.info(
                "Financial analysis crew execution completed",
                duration_ms=round(duration * 1000, 2),
                success=True,
            )

            logger.info(
                "Captured LLM messages from crew execution",
                num_messages=len(message_interceptor.captured_messages),
            )

            # Create final result message
            # Only include usage_metadata and response_metadata if we have actual values
            # Convert content to JSON string to ensure it's serializable for WebSocket
            import json as json_module
            import uuid
            final_message_kwargs = {
                "content": json_module.dumps(result[0].model_dump(exclude_none=True)),  # JSON string for WebSocket compatibility
                "id": str(uuid.uuid4()),  # Add unique ID for message tracking
                "additional_kwargs": {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "agent_type": "financial_analysis_end",
                },
            }

            # Only add usage_metadata if we have valid token counts
            if result[1].get("prompt_tokens") or result[1].get("completion_tokens") or result[1].get("total_tokens"):
                final_message_kwargs["usage_metadata"] = {
                    "input_tokens": result[1].get("prompt_tokens", 0),
                    "output_tokens": result[1].get("completion_tokens", 0),
                    "total_tokens": result[1].get("total_tokens", 0),
                }
                final_message_kwargs["response_metadata"] = {
                    "usage": {
                        "completion_tokens": result[1].get("completion_tokens", 0),
                        "prompt_tokens": result[1].get("prompt_tokens", 0),
                        "total_tokens": result[1].get("total_tokens", 0),
                    }
                }

            final_message = LiberalAIMessage(**final_message_kwargs)

            # Log the final message to debug WebSocket error
            logger.info(
                "Created final financial analysis message",
                has_usage_metadata="usage_metadata" in final_message_kwargs,
                has_response_metadata="response_metadata" in final_message_kwargs,
                content_type=type(final_message_kwargs.get("content")),
            )

            # Return only the final message
            # The interceptor messages are already sent in real-time via RedisConversationLogger
            return [final_message]
        except Exception as e:
            logger.error(
                "Financial analysis node failed",
                error_type=type(e).__name__,
                error_message=str(e),
                exc_info=True,
            )
            return LiberalAIMessage(
                content=f"Error: {str(e)}",
                additional_kwargs={
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "agent_type": "financial_analysis_end",
                    "error_type": "financial_analysis_error",
                },
            )

    # Create the workflow with just one node
    workflow = MessageGraph()

    # Add the single node
    workflow.add_node("financial_analysis", financial_analysis_node)

    # Set entry point
    workflow.set_entry_point("financial_analysis")

    # Go directly to END after the greeter node
    workflow.add_edge("financial_analysis", END)

    # Compile and return
    return workflow.compile()
