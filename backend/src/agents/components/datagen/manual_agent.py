import asyncio
import json
import random
import re
import string
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Union

import structlog
from langchain.tools import BaseTool
from langchain_core.messages import AIMessage, HumanMessage, ToolCall
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables import Runnable

logger = structlog.get_logger(__name__)


class ToolInvocation:
    """Simple ToolInvocation class for compatibility."""

    def __init__(self, tool: str, tool_input: str):
        self.tool = tool
        self.tool_input = tool_input


class ToolExecutor:
    """Simple ToolExecutor class for compatibility."""

    def __init__(self, tools):
        self.tools_by_name = {tool.name: tool for tool in tools}

    def invoke(self, action: ToolInvocation):
        tool = self.tools_by_name.get(action.tool)
        if tool:
            return tool.invoke(action.tool_input)
        else:
            return f"Tool {action.tool} not found"

    async def ainvoke(self, action: ToolInvocation):
        tool = self.tools_by_name.get(action.tool)
        if tool:
            return await tool.ainvoke(action.tool_input)
        else:
            return f"Tool {action.tool} not found"


class ManualAgent(Runnable):
    """
    A manual agent that parses and executes tool calls using XML tags (like xml_agent).
    """

    def __init__(self, llm, tools: List[BaseTool], prompt: ChatPromptTemplate):
        self.llm = llm
        self.tools = {tool.name: tool for tool in tools}
        self.prompt = prompt
        self.tool_executor = ToolExecutor(tools)
        logger.info(f"ManualAgent initialized with {len(tools)} tools.")

    def _get_llm_response(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Get response from LLM, parse it for tool calls, and return the final output
        dictionary.
        """
        llm_with_stop = self.llm.bind(stop=["</tool_input>", "<observation>"])
        chain = self.prompt | llm_with_stop

        # Prepare template variables from state, ensuring complex objects are
        # converted to simple strings for clean prompt injection.
        template_vars = {}
        for key, value in state.items():
            if key == "messages":
                template_vars[key] = value
                continue

            # Extract content from AIMessage or SupervisorDecision objects
            if hasattr(value, "content"):
                template_vars[key] = value.content
            # Handle SupervisorDecision specifically if it has a 'decision' attribute
            elif hasattr(value, "decision"):
                template_vars[key] = value.decision
            # For other types, convert to string
            else:
                template_vars[key] = str(value)

        # Ensure all expected keys are present, even if empty
        expected_keys = [
            "hypothesis",
            "process",
            "process_decision",
            "visualization_state",
            "searcher_state",
            "code_state",
            "report_section",
            "quality_review",
            "needs_revision",
        ]
        for key in expected_keys:
            if key not in template_vars:
                template_vars[key] = ""

        try:
            response = chain.invoke(template_vars)
            # The _parse_llm_output method will return either a ToolCall or an AIMessage.
            # This is then wrapped in the dictionary structure expected by the graph.
            output = self._parse_llm_output(response.content)
            return {"output": output}
        except Exception as e:
            logger.error(f"Error invoking LLM chain: {e}")
            logger.error(f"Template variables: {template_vars}")
            # Re-raise to be handled by the calling invoke/ainvoke method
            raise

    async def ainvoke(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Asynchronously invokes the agent with the given state.
        The logic is now fully encapsulated in _get_llm_response.
        """
        return await asyncio.to_thread(self._get_llm_response, state)

    def _parse_llm_output(self, response: str) -> Union[ToolCall, AIMessage]:
        """Parse the LLM output to find a tool call."""
        # Post-process response to catch potential formatting issues from the LLM
        if "<tool>" in response and "</tool>" not in response:
            response += "</tool>"
        elif "<tool_input>" in response and "</tool_input>" not in response:
            response += "</tool_input>"

        tool_match = re.search(r"<tool>(.*?)</tool>", response, re.DOTALL)
        tool_input_match = re.search(
            r"<tool_input>(.*?)</tool_input>", response, re.DOTALL
        )

        if tool_match and tool_input_match:
            tool_name = tool_match.group(1).strip()
            tool_input = tool_input_match.group(1).strip()
            # Generate a random ID for the tool call
            tool_call_id = f"call_{''.join(random.choices(string.ascii_letters + string.digits, k=24))}"
            return ToolCall(name=tool_name, args={"query": tool_input}, id=tool_call_id)

        return AIMessage(content=response)

    def invoke(self, state: Dict[str, Any]) -> Dict[str, Any]:
        raise NotImplementedError(
            "This agent is designed for asynchronous invocation. Use ainvoke instead."
        )
