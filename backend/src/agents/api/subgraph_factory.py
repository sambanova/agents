"""
Factory module for creating and configuring agent subgraphs.
This centralizes subgraph creation to avoid duplication across API endpoints.
"""

import uuid
from datetime import datetime
from typing import Dict, Optional

import structlog
from agents.components.compound.code_execution_subgraph import create_code_execution_graph
from agents.components.compound.data_science_subgraph import create_data_science_subgraph
from agents.components.compound.data_types import LiberalFunctionMessage
from agents.components.compound.financial_analysis_subgraph import create_financial_analysis_graph
from agents.components.datagen.tools.persistent_daytona import PersistentDaytonaManager
from agents.components.open_deep_research.graph import create_deep_research_graph
from agents.storage.redis_storage import RedisStorage
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.graph import END

logger = structlog.get_logger(__name__)


def create_all_subgraphs(
    user_id: str,
    api_key: str,
    redis_storage: RedisStorage,
    provider: str = "sambanova",
    daytona_manager: Optional[PersistentDaytonaManager] = None,
    directory_content: Optional[list] = None,
    enable_data_science: bool = False,
    admin_api_keys: Optional[Dict] = None,
) -> Dict:
    """
    Creates all available subgraphs following the pattern from websocket_manager.py.

    Args:
        user_id: User ID for the session
        api_key: Primary API key to use
        redis_storage: Redis storage instance
        provider: LLM provider (sambanova, fireworks, together)
        daytona_manager: Optional Daytona manager instance (created if None)
        directory_content: List of filenames for data science subgraph
        enable_data_science: Whether to enable data science subgraph
        admin_api_keys: Optional dict of API keys when admin panel is enabled

    Returns:
        Dictionary of configured subgraphs
    """
    subgraphs = {}

    # Create Daytona manager if not provided
    if daytona_manager is None:
        daytona_manager = PersistentDaytonaManager(
            user_id=user_id,
            redis_storage=redis_storage,
            snapshot="data-analysis:0.0.10",
            file_ids=[],
        )

    # 1. Financial Analysis Subgraph
    subgraphs["financial_analysis"] = {
        "description": "This subgraph is used to analyze financial data and return a comprehensive report. KEY TRIGGER TERMS: Use this when the user says 'get financials' or 'analyze financials' for a single company.",
        "next_node": END,
        "graph": create_financial_analysis_graph(
            redis_client=redis_storage,
            user_id=user_id,
            api_keys=admin_api_keys,
        ),
        "state_input_mapper": lambda x: [HumanMessage(content=x)],
        "state_output_mapper": lambda x: x[-1],
    }

    # 2. Deep Research Subgraph
    subgraphs["deep_research"] = {
        "description": "This subgraph generates comprehensive research reports with multiple perspectives, sources, and analysis. KEY TRIGGER TERM: Use this when the user says 'deep research'. Also use when the user requests: detailed research, in-depth analysis, comprehensive reports, market research, academic research, or thorough investigation of any topic. IMPORTANT: Pass the user's specific research question or topic as a clear, focused query.",
        "next_node": END,
        "graph": create_deep_research_graph(
            api_key=api_key,
            provider=provider,
            request_timeout=120,
            redis_storage=redis_storage,
            user_id=user_id,
            api_keys=admin_api_keys,
        ),
        "state_input_mapper": lambda x: {"topic": x},
        "state_output_mapper": lambda x: AIMessage(
            content=x["final_report"],
            name="DeepResearch",
            additional_kwargs={
                "agent_type": "deep_research_end",
                "pdf_report": x.get("pdf_report", ""),
                "workflow_timing": x.get("workflow_timing", {}),
            },
        ),
    }

    # 3. DaytonaCodeSandbox Subgraph (Coding Agent)
    subgraphs["DaytonaCodeSandbox"] = {
        "description": "This subgraph executes Python code in a secure sandbox environment. Use for: data exploration, basic analysis, code debugging, file operations, simple calculations, data visualization, multi-file analysis, report generation, and any general programming tasks. Perfect for examining datasets, creating plots, running straightforward code snippets, and combining data from multiple uploaded files.",
        "next_node": "agent",
        "graph": create_code_execution_graph(
            user_id=user_id,
            sambanova_api_key=api_key,
            redis_storage=redis_storage,
            daytona_manager=daytona_manager,
            api_keys=admin_api_keys,
        ),
        "state_input_mapper": lambda x: {
            "code": x,
            "current_retry": 0,
            "max_retries": 5,
            "steps_taken": [],
            "error_detected": False,
            "final_result": "",
            "corrections_proposed": [],
            "files": [],
        },
        "state_output_mapper": lambda x: LiberalFunctionMessage(
            name="DaytonaCodeSandbox",
            content="\n".join(x["steps_taken"]),
            additional_kwargs={
                "agent_type": "tool_response",
                "timestamp": datetime.now().isoformat(),
                "files": x["files"],
                "workflow_timing": x.get("workflow_timing", {}),
            },
            result={"usage": {"total_latency": 0.0}},
        ),
    }

    # 4. Data Science Subgraph (conditional)
    if enable_data_science and directory_content:
        subgraphs["data_science"] = {
            "description": "This subgraph performs comprehensive end-to-end data science workflows with multiple specialized agents. Use ONLY for complex projects requiring: machine learning model development, predictive analytics, statistical modeling, hypothesis testing, or multi-step data science pipelines. IMPORTANT: Pass the user's natural language request, NOT code. Do NOT use for simple data exploration - use DaytonaCodeSandbox instead.",
            "next_node": END,
            "graph": create_data_science_subgraph(
                user_id=user_id,
                sambanova_api_key=api_key,
                redis_storage=redis_storage,
                daytona_manager=daytona_manager,
                directory_content=directory_content,
                api_keys=admin_api_keys,
            ),
            "state_input_mapper": lambda x: {
                "internal_messages": [HumanMessage(content=x, id=str(uuid.uuid4()))],
                "hypothesis": "",
                "process": "",
                "process_decision": None,
                "visualization_state": "",
                "searcher_state": "",
                "code_state": "",
                "report_section": "",
                "quality_review": "",
                "needs_revision": False,
                "sender": "",
            },
            "state_output_mapper": lambda x: x["internal_messages"][-1].model_copy(
                update={
                    "additional_kwargs": {
                        **(x["internal_messages"][-1].additional_kwargs or {}),
                        "agent_type": "data_science_end",
                        "workflow_timing": x.get("workflow_timing", {}),
                    }
                }
            ),
        }

    logger.info(
        "Created subgraphs for main agent",
        user_id=user_id[:8] if user_id else "None",
        num_subgraphs=len(subgraphs),
        subgraph_names=list(subgraphs.keys()),
    )

    return subgraphs
