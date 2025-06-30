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
            # StructuredTool expects a single input argument
            return tool.invoke(action.tool_input)
        else:
            return f"Tool {action.tool} not found"

    async def ainvoke(self, action: ToolInvocation):
        tool = self.tools_by_name.get(action.tool)
        if tool:
            # StructuredTool expects a single input argument
            return await tool.ainvoke(action.tool_input)
        else:
            return f"Tool {action.tool} not found"


class ManualAgent(Runnable):
    """
    A manual agent that parses and executes tool calls using XML tags (like xml_agent).
    """

    def __init__(
        self, llm, tools: List[BaseTool], prompt: ChatPromptTemplate, name: str
    ):
        self.llm = llm
        self.tools = {tool.name: tool for tool in tools}
        self.prompt = prompt
        self.tool_executor = ToolExecutor(tools)
        self.name = name
        logger.info(f"ManualAgent initialized with {len(tools)} tools.")

    async def _get_llm_response(self, state: Dict[str, Any]) -> Dict[str, Any]:
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
            # Skip 'sender' as it's not needed by the prompt template
            if key == "sender":
                continue
            # Extract content from AIMessage objects
            if hasattr(value, "content"):
                template_vars[key] = value.content
            # For other types, convert to string
            else:
                str_value = str(value)
                template_vars[key] = str_value

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

        # Debug logging to identify problematic template variables
        for key, value in template_vars.items():
            if isinstance(value, str) and ("{" in value or "}" in value):
                logger.warning(
                    f"Template variable '{key}' contains curly braces: {repr(value)}"
                )

        try:
            response = await chain.ainvoke(template_vars)

            # Check if response contains tool calls and execute them
            if "<tool>" in response.content:
                # Parse tool call from XML
                tool_match = re.search(
                    r"<tool>(.*?)</tool>", response.content, re.DOTALL
                )

                # Handle both closed and unclosed tool_input tags
                tool_input_match = re.search(
                    r"<tool_input>(.*?)(?:</tool_input>|$)", response.content, re.DOTALL
                )

                if tool_match and tool_input_match:
                    tool_name = tool_match.group(1).strip()
                    tool_input = tool_input_match.group(1).strip()

                    # Execute the tool with the raw input
                    action = ToolInvocation(tool=tool_name, tool_input=tool_input)
                    tool_result = await self.tool_executor.ainvoke(action)

                    # Create final response with tool result
                    final_content = f"{response.content}\n<observation>{tool_result}</observation>\n"
                    return {
                        "output": AIMessage(content=final_content, sender=self.name)
                    }

            # No tool calls, return regular response
            return {"output": AIMessage(content=response.content, sender=self.name)}
        except Exception as e:
            logger.error(f"Error invoking LLM chain: {e}")
            # Re-raise to be handled by the calling invoke/ainvoke method
            raise

    async def ainvoke(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Asynchronously invokes the agent with the given state.
        The logic is now fully encapsulated in _get_llm_response.
        """
        return await self._get_llm_response(state)

    def invoke(self, state: Dict[str, Any]) -> Dict[str, Any]:
        raise NotImplementedError(
            "This agent is designed for asynchronous invocation. Use ainvoke instead."
        )
