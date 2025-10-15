"""
Message interceptor for CrewAI LLM calls.
Wraps CustomLLM to capture calls and convert them to LangChain AIMessages.
"""

import json
import time
import uuid
from typing import List, Optional, Any, Dict, Union

from langchain_core.messages import AIMessage
from agents.components.crewai_llm import CustomLLM


class CrewAIMessageInterceptor:
    """Intercepts CrewAI LLM calls and captures them as LangChain AIMessages with timing data."""

    def __init__(self):
        self.captured_messages: List[AIMessage] = []
        self.model_timings: List[Dict[str, Any]] = []  # Track per-model timing for breakdown
        self.current_agent_name: Optional[str] = None  # Track which agent is currently executing
        self.agent_call_counts: Dict[str, int] = {}  # Track calls per agent

    def set_agent_context(self, agent_name: str):
        """Set the current agent context for subsequent LLM calls."""
        self.current_agent_name = agent_name

    def wrap_llm(self, llm: CustomLLM, agent_name: Optional[str] = None) -> CustomLLM:
        """Wrap a CustomLLM to intercept its calls."""
        # Store the original call method
        original_call = llm.call
        interceptor = self

        # Create wrapper function
        def intercepted_call(
            messages: Union[str, List[Dict[str, str]]],
            tools: Optional[List[dict]] = None,
            callbacks: Optional[List[Any]] = None,
            available_functions: Optional[Dict[str, Any]] = None,
        ) -> str:
            # Track timing for this LLM call
            start_time = time.time()

            # Call the original method
            response = original_call(messages, tools, callbacks, available_functions)

            # Calculate duration
            end_time = time.time()
            duration = end_time - start_time

            # Extract model name and provider
            model_name = llm.model
            # Split provider/model if present (e.g., "sambanova/Meta-Llama-3.1-8B-Instruct")
            if "/" in model_name:
                provider, model = model_name.split("/", 1)
            else:
                provider = "unknown"
                model = model_name

            # Get agent name from parameter or current context
            agent_name_to_use = agent_name or interceptor.current_agent_name or "Unknown Agent"

            # Track agent call counts
            if agent_name_to_use not in interceptor.agent_call_counts:
                interceptor.agent_call_counts[agent_name_to_use] = 0
            interceptor.agent_call_counts[agent_name_to_use] += 1

            # Store timing data for per-model breakdown including agent info
            timing_entry = {
                "model_name": model,
                "provider": provider,
                "full_model_name": model_name,
                "agent_name": agent_name_to_use,
                "start_time": start_time,
                "end_time": end_time,
                "duration": duration,
                "call_index": interceptor.agent_call_counts[agent_name_to_use]
            }
            interceptor.model_timings.append(timing_entry)

            # Create AIMessage from the response
            # Include timing metadata for downstream processing
            ai_message = AIMessage(
                content=response or "",
                id=str(uuid.uuid4()),
                response_metadata={
                    "model_name": llm.model,
                    "usage": {
                        "total_latency": duration,  # Include per-call latency
                    }
                },
                additional_kwargs={
                    "agent_type": "crewai_llm_call",  # Tag for frontend filtering
                    "timing": timing_entry
                }
            )

            # Capture the message
            interceptor.captured_messages.append(ai_message)

            # Note: We can't publish to Redis in real-time here because:
            # 1. CrewAI runs synchronously in a thread
            # 2. The Redis client is async-only (redis.asyncio)
            # 3. Can't await in sync context
            # Messages will be returned at the end and sent via the graph state stream

            return response

        # Replace the call method
        llm.call = intercepted_call

        return llm

    def clear(self):
        """Clear captured messages and timings."""
        self.captured_messages = []
        self.model_timings = []

    def get_timing_summary(self) -> Dict[str, Any]:
        """Get summary of model timings for waterfall visualization with agent grouping."""
        if not self.model_timings:
            return {
                "total_duration": 0,
                "model_breakdown": [],
                "agent_breakdown": []
            }

        # Calculate total duration (from first start to last end)
        start_times = [t["start_time"] for t in self.model_timings]
        end_times = [t["end_time"] for t in self.model_timings]
        total_duration = max(end_times) - min(start_times) if start_times and end_times else 0
        min_start = min(start_times) if start_times else 0

        # Create model breakdown with agent info and proper start_offset
        model_breakdown = []
        for timing in self.model_timings:
            # Calculate start_offset relative to earliest call
            start_offset = timing["start_time"] - min_start
            model_breakdown.append({
                "model_name": timing["model_name"],
                "provider": timing["provider"],
                "agent_name": timing["agent_name"],
                "duration": timing["duration"],
                "start_offset": start_offset,  # Preserves concurrency in waterfall
                "percentage": (timing["duration"] / total_duration * 100) if total_duration > 0 else 0,
                "call_index": timing.get("call_index", 1)
            })

        # Group by agent for hierarchical view
        agent_groups = {}
        for timing in self.model_timings:
            agent_name = timing["agent_name"]
            if agent_name not in agent_groups:
                agent_groups[agent_name] = {
                    "agent_name": agent_name,
                    "calls": [],
                    "total_duration": 0,
                    "start_time": timing["start_time"],
                    "end_time": timing["end_time"]
                }

            # Calculate start_offset relative to earliest call for concurrency tracking
            call_start_offset = timing["start_time"] - min_start
            agent_groups[agent_name]["calls"].append({
                "model_name": timing["model_name"],
                "provider": timing["provider"],
                "duration": timing["duration"],
                "start_offset": call_start_offset,  # Preserves concurrency in waterfall
                "percentage": (timing["duration"] / total_duration * 100) if total_duration > 0 else 0
            })
            agent_groups[agent_name]["total_duration"] += timing["duration"]
            agent_groups[agent_name]["start_time"] = min(agent_groups[agent_name]["start_time"], timing["start_time"])
            agent_groups[agent_name]["end_time"] = max(agent_groups[agent_name]["end_time"], timing["end_time"])

        # Convert to list and add percentages
        agent_breakdown = []
        for agent_name, group in agent_groups.items():
            agent_breakdown.append({
                "agent_name": agent_name,
                "calls": group["calls"],
                "num_calls": len(group["calls"]),
                "total_duration": group["total_duration"],
                "start_offset": group["start_time"] - min_start,
                "percentage": (group["total_duration"] / total_duration * 100) if total_duration > 0 else 0
            })

        # Sort agents by start time
        agent_breakdown.sort(key=lambda x: x["start_offset"])

        return {
            "total_duration": total_duration,
            "model_breakdown": model_breakdown,
            "agent_breakdown": agent_breakdown
        }
