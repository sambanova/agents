import os
import time
from datetime import datetime, timezone

import langsmith as ls
import structlog
from agents.components.compound.data_types import LiberalAIMessage
from agents.components.compound.util import extract_api_key
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


def create_financial_analysis_graph(redis_client: SecureRedisService):
    """Create a simple subgraph with just one node that greets the user."""
    logger.info("Creating financial analysis subgraph")

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

            # Initialize crew
            logger.info("Initializing FinancialAnalysisCrew")
            crew = FinancialAnalysisCrew(
                llm_api_key=api_key,
                provider="sambanova",
                user_id=config["metadata"]["user_id"],
                run_id=config["metadata"]["thread_id"],
                docs_included=False,
                redis_client=redis_client,
                verbose=False,
                message_id=config["metadata"]["message_id"],
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

            return LiberalAIMessage(
                content=result[0].model_dump(),
                additional_kwargs={
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "agent_type": "financial_analysis_end",
                },
                usage_metadata={
                    "input_tokens": result[1].get("prompt_tokens", None),
                    "output_tokens": result[1].get("completion_tokens", None),
                    "total_tokens": result[1].get("total_tokens", None),
                },
                response_metadata={
                    "usage": {
                        "completion_tokens": result[1].get("completion_tokens", None),
                        "prompt_tokens": result[1].get("prompt_tokens", None),
                        "total_tokens": result[1].get("total_tokens", None),
                    }
                },
            )
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
