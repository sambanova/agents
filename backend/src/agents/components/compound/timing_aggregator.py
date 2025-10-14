"""
Unified timing aggregator for tracking LLM calls across main agent and subgraphs.
Provides hierarchical timing data matching LangSmith's structure.
"""

import time
from typing import Dict, List, Any, Optional
import structlog

logger = structlog.get_logger(__name__)


class WorkflowTimingAggregator:
    """
    Aggregates timing data from all levels of the workflow:
    - Main agent LLM calls (XML agent with DeepSeek)
    - Subgraph entries and their internal agents
    - Tool executions

    Provides a hierarchical structure for frontend visualization.
    """

    def __init__(self):
        self.workflow_start_time = time.time()
        self.main_agent_calls: List[Dict[str, Any]] = []
        self.subgraph_timings: List[Dict[str, Any]] = []
        self.total_llm_calls = 0

    def add_main_agent_call(
        self,
        node_name: str,
        agent_name: str,
        model_name: str,
        provider: Optional[str] = None,
        duration: float = 0,
        start_time: Optional[float] = None,
    ):
        """Add a main agent (XML agent) LLM call to the timing data."""
        if start_time is None:
            start_offset = time.time() - self.workflow_start_time
        else:
            start_offset = start_time - self.workflow_start_time

        call_data = {
            "node_name": node_name,
            "agent_name": agent_name,
            "model_name": model_name,
            "provider": provider or self._extract_provider(model_name),
            "duration": duration,
            "start_offset": start_offset,
            "timestamp": start_time or time.time(),
        }

        self.main_agent_calls.append(call_data)
        self.total_llm_calls += 1

        logger.debug(
            "Added main agent LLM call",
            node=node_name,
            agent=agent_name,
            model=model_name,
            duration=round(duration, 3),
        )

    def add_subgraph_timing(
        self,
        subgraph_name: str,
        subgraph_duration: float,
        subgraph_start_time: float,
        agent_breakdown: List[Dict[str, Any]],
        model_breakdown: List[Dict[str, Any]],
    ):
        """Add complete subgraph timing data including all internal agents."""
        subgraph_start_offset = subgraph_start_time - self.workflow_start_time

        # Count total LLM calls in this subgraph
        subgraph_llm_count = len(model_breakdown)
        self.total_llm_calls += subgraph_llm_count

        subgraph_data = {
            "subgraph_name": subgraph_name,
            "subgraph_duration": subgraph_duration,
            "subgraph_start_offset": subgraph_start_offset,
            "agent_breakdown": agent_breakdown,
            "model_breakdown": model_breakdown,
            "num_llm_calls": subgraph_llm_count,
        }

        self.subgraph_timings.append(subgraph_data)

        logger.info(
            "Added subgraph timing",
            subgraph=subgraph_name,
            duration=round(subgraph_duration, 3),
            num_agents=len(agent_breakdown),
            num_llm_calls=subgraph_llm_count,
        )

    def get_hierarchical_timing(self) -> Dict[str, Any]:
        """
        Get complete hierarchical timing structure.

        Returns structure matching LangSmith:
        {
            "workflow_duration": float,
            "total_llm_calls": int,
            "levels": [
                {
                    "level": "main_agent",
                    "llm_calls": [...],
                    "num_calls": int,
                },
                {
                    "level": "subgraph",
                    "subgraph_name": str,
                    "subgraph_duration": float,
                    "subgraph_start_offset": float,
                    "agent_breakdown": [...],
                    "model_breakdown": [...],
                    "num_llm_calls": int,
                }
            ]
        }
        """
        workflow_duration = time.time() - self.workflow_start_time

        levels = []

        # Add main agent level if there are calls
        if self.main_agent_calls:
            levels.append({
                "level": "main_agent",
                "llm_calls": self.main_agent_calls,
                "num_calls": len(self.main_agent_calls),
            })

        # Add subgraph levels
        for subgraph in self.subgraph_timings:
            levels.append({
                "level": "subgraph",
                **subgraph,  # Include all subgraph fields
            })

        result = {
            "workflow_duration": workflow_duration,
            "total_llm_calls": self.total_llm_calls,
            "levels": levels,
        }

        logger.info(
            "Generated hierarchical timing",
            workflow_duration=round(workflow_duration, 3),
            total_llm_calls=self.total_llm_calls,
            num_levels=len(levels),
            main_agent_calls=len(self.main_agent_calls),
            num_subgraphs=len(self.subgraph_timings),
        )

        return result

    def _extract_provider(self, model_name: str) -> str:
        """Extract provider from model name if present (e.g., 'sambanova/Model')."""
        if "/" in model_name:
            return model_name.split("/")[0]
        return "unknown"

    def reset(self):
        """Reset all timing data for a new workflow run."""
        self.workflow_start_time = time.time()
        self.main_agent_calls = []
        self.subgraph_timings = []
        self.total_llm_calls = 0
