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
            # Handle both structured parameters (dict) and simple string input
            if isinstance(action.tool_input, dict):
                # For structured parameters, pass as keyword arguments
                return tool.invoke(action.tool_input)
            else:
                # For simple string input, pass directly
                return tool.invoke(action.tool_input)
        else:
            return f"Tool {action.tool} not found"

    async def ainvoke(self, action: ToolInvocation):
        tool = self.tools_by_name.get(action.tool)
        if tool:
            # Handle both structured parameters (dict) and simple string input
            if isinstance(action.tool_input, dict):
                # For structured parameters, pass as keyword arguments
                return await tool.ainvoke(action.tool_input)
            else:
                # For simple string input, pass directly
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

    def _parse_tool_parameters(self, tool_input_content: str) -> Dict[str, Any]:
        """
        Parse structured XML parameters from tool_input content.

        Converts XML parameter tags like:
        <param1>value1</param1>
        <param2>["item1", "item2"]</param2>
        <param3>dict([(1, "value")])</param3>

        Into a dictionary of parameter names and properly typed values.
        """
        params = {}

        # Find all parameter tags using regex
        param_pattern = r"<(\w+)>(.*?)</\1>"
        matches = re.findall(param_pattern, tool_input_content, re.DOTALL)

        for param_name, param_value in matches:
            param_value = param_value.strip()

            # Try to parse the parameter value as appropriate Python data type
            try:
                # Handle list format: ["item1", "item2", "item3"]
                if param_value.startswith("[") and param_value.endswith("]"):
                    parsed_value = json.loads(param_value)
                    params[param_name] = parsed_value

                # Handle dict format: dict([(1, "value1"), (2, "value2")])
                elif param_value.startswith("dict("):
                    # Use eval for dict() format - this is safe for known patterns
                    parsed_value = eval(param_value)
                    params[param_name] = parsed_value

                # Handle JSON object format: {"key": "value"}
                elif param_value.startswith("{") and param_value.endswith("}"):
                    parsed_value = json.loads(param_value)
                    params[param_name] = parsed_value

                # Handle numeric values
                elif param_value.isdigit():
                    params[param_name] = int(param_value)

                elif param_value.replace(".", "", 1).isdigit():
                    params[param_name] = float(param_value)

                # Handle boolean values
                elif param_value.lower() in ["true", "false"]:
                    params[param_name] = param_value.lower() == "true"

                # Handle None value
                elif param_value.lower() == "none":
                    params[param_name] = None

                # Default to string value
                else:
                    params[param_name] = param_value

            except (json.JSONDecodeError, SyntaxError, ValueError) as e:
                # If parsing fails, treat as string
                logger.warning(
                    f"Failed to parse parameter '{param_name}' with value '{param_value}': {e}. Using as string."
                )
                params[param_name] = param_value

        # If no structured parameters found, check for fallback to old format
        if not params and tool_input_content:
            # Fallback: if content doesn't contain parameter tags, treat as single string input
            logger.info(
                "No structured parameters found, using raw content as string input"
            )
            return tool_input_content

        logger.info(f"Parsed tool parameters: {params}")
        return params

    async def _get_llm_response(self, state: Dict[str, Any]) -> AIMessage:
        """
        Get response from LLM, parse it for tool calls, and return the final AIMessage.
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
                    tool_input_content = tool_input_match.group(1).strip()

                    # Parse structured XML parameters
                    parsed_params = self._parse_tool_parameters(tool_input_content)

                    # Execute the tool with parsed parameters
                    logger.info(
                        f"Executing tool {tool_name} with parameters {parsed_params} in {self.name}"
                    )
                    action = ToolInvocation(tool=tool_name, tool_input=parsed_params)
                    tool_result = await self.tool_executor.ainvoke(action)

                    # Create final response with tool result
                    final_content = f"{response.content}\n<observation>{tool_result}</observation>\n"
                    return AIMessage(content=final_content, sender=self.name)

            # No tool calls, return regular response
            return AIMessage(content=response.content, sender=self.name)
        except Exception as e:
            logger.error(f"Error invoking LLM chain: {e}")
            # Re-raise to be handled by the calling invoke/ainvoke method
            raise

    async def ainvoke(self, state: Dict[str, Any]) -> AIMessage:
        """
        Asynchronously invokes the agent with the given state.
        The logic is now fully encapsulated in _get_llm_response.
        """
        return await self._get_llm_response(state)

    def invoke(self, state: Dict[str, Any]) -> AIMessage:
        raise NotImplementedError(
            "This agent is designed for asynchronous invocation. Use ainvoke instead."
        )
