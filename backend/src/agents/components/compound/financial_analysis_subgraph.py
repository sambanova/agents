import os
import time
from datetime import datetime, timezone

import langsmith as ls
import structlog
from agents.components.compound.data_types import LiberalAIMessage
from agents.components.compound.timing_aggregator import WorkflowTimingAggregator
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
            workflow_start_time = time.time()
            result = await crew.execute_financial_analysis(inputs)
            workflow_end_time = time.time()
            workflow_duration = workflow_end_time - workflow_start_time

            # Get timing summary from interceptor
            timing_summary = message_interceptor.get_timing_summary()

            logger.info(
                "Financial analysis crew execution completed",
                workflow_duration_s=round(workflow_duration, 2),
                total_llm_time_s=round(timing_summary.get("total_duration", 0), 2),
                num_llm_calls=len(timing_summary.get("model_breakdown", [])),
                success=True,
            )

            logger.info(
                "Captured LLM messages from crew execution",
                num_messages=len(message_interceptor.captured_messages),
            )

            # Debug: Log the breakdown counts to investigate discrepancy
            logger.info(
                "[COUNT_DEBUG] Timing breakdown analysis",
                captured_messages=len(message_interceptor.captured_messages),
                model_breakdown_count=len(timing_summary.get("model_breakdown", [])),
                agent_breakdown_count=len(timing_summary.get("agent_breakdown", [])),
                agent_breakdown_details=[
                    {
                        "agent": a.get("agent_name"),
                        "num_calls": a.get("num_calls"),
                    }
                    for a in timing_summary.get("agent_breakdown", [])
                ],
            )

            # Create timing aggregator
            timing_aggregator = WorkflowTimingAggregator()
            timing_aggregator.workflow_start_time = workflow_start_time

            # Extract main agent timing from config metadata (if available)
            if config and "metadata" in config and "main_agent_timing" in config["metadata"]:
                main_timing = config["metadata"]["main_agent_timing"]
                logger.info(
                    "Retrieved main agent timing from config metadata",
                    main_timing=main_timing,
                )

                timing_aggregator.add_main_agent_call(
                    node_name=main_timing.get("node_name", "agent_node"),
                    agent_name=main_timing.get("agent_name", "XML Agent"),
                    model_name=main_timing.get("model_name", "unknown"),
                    provider=main_timing.get("model_name", "").split("/")[0] if "/" in main_timing.get("model_name", "") else "sambanova",
                    duration=main_timing.get("duration", 0),
                    start_time=main_timing.get("start_time", workflow_start_time),
                )
            else:
                logger.warning(
                    "Main agent timing not found in config metadata",
                    has_config=config is not None,
                    has_metadata=config and "metadata" in config,
                    metadata_keys=list(config["metadata"].keys()) if config and "metadata" in config else None,
                )

            # Aggregate subgraph timing from interceptor
            agent_breakdown = timing_summary.get("agent_breakdown", [])
            model_breakdown = timing_summary.get("model_breakdown", [])

            # Add subgraph timing to aggregator
            if agent_breakdown or model_breakdown:
                timing_aggregator.add_subgraph_timing(
                    subgraph_name="Financial Analysis",
                    subgraph_duration=workflow_duration,
                    subgraph_start_time=workflow_start_time,
                    agent_breakdown=agent_breakdown,
                    model_breakdown=model_breakdown,
                )

            # Get final hierarchical timing structure
            hierarchical_timing = timing_aggregator.get_hierarchical_timing(workflow_end_time=workflow_end_time)

            logger.info(
                "Created hierarchical timing structure for financial analysis",
                total_llm_calls=hierarchical_timing.get("total_llm_calls", 0),
                num_levels=len(hierarchical_timing.get("levels", [])),
                workflow_duration=round(workflow_duration, 2),
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
                    "workflow_timing": hierarchical_timing,  # Use new hierarchical structure
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
                        "total_latency": workflow_duration,  # Use workflow duration, not LLM sum
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

            # Return both the captured messages AND the final message
            # The captured messages have agent_type="crewai_llm_call" for frontend tracking
            # This ensures they get streamed to frontend and counted correctly
            all_messages = list(message_interceptor.captured_messages) + [final_message]

            logger.info(
                "Returning messages from financial analysis",
                num_captured_messages=len(message_interceptor.captured_messages),
                num_total_messages=len(all_messages),
            )

            return all_messages
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
