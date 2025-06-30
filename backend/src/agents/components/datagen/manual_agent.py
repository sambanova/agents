import json
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import structlog
from langchain.tools import BaseTool
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

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


class ManualAgent:
    """
    A manual agent that parses and executes tool calls using XML tags (like xml_agent).
    """

    def __init__(self, llm, tools: List[BaseTool], prompt: ChatPromptTemplate):
        self.llm = llm
        self.tools = {tool.name: tool for tool in tools}
        self.prompt = prompt
        self.tool_executor = ToolExecutor(tools)

    def invoke(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process the state and return a result with 'output' field.
        """
        try:
            # Get initial response from LLM
            response = self._get_llm_response(state)

            # Check if the response contains tool calls
            if self._has_tool_call(response):
                # Execute tools and get results
                tool_result = self._execute_tool_call(response)

                # Get final response with tool results
                final_response = self._get_final_response(state, response, tool_result)
                return {"output": final_response}
            else:
                return {"output": response}

        except Exception as e:
            logger.error(f"Error in manual agent: {e}", exc_info=True)
            return {"output": f"Error: {str(e)}"}

    async def ainvoke(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Async version to process the state and return a result with 'output' field.
        """
        try:
            # Get initial response from LLM
            response = self._get_llm_response(state)

            # Check if the response contains tool calls
            if self._has_tool_call(response):
                # Execute tools and get results (async)
                tool_result = await self._execute_tool_call_async(response)

                # Get final response with tool results
                final_response = self._get_final_response(state, response, tool_result)
                return {"output": final_response}
            else:
                return {"output": response}

        except Exception as e:
            logger.error(f"Error in manual agent: {e}", exc_info=True)
            return {"output": f"Error: {str(e)}"}

    def _format_tools(self) -> str:
        """Format tools for inclusion in the prompt."""
        tool_descriptions = []
        for tool_name, tool in self.tools.items():
            # Get tool description and parameters
            description = tool.description or f"Tool: {tool_name}"

            # Format parameters if available
            if hasattr(tool, "args_schema") and tool.args_schema:
                schema = tool.args_schema.schema()
                properties = schema.get("properties", {})
                required = schema.get("required", [])

                params = []
                for param_name, param_info in properties.items():
                    param_type = param_info.get("type", "string")
                    param_desc = param_info.get("description", "")
                    is_required = param_name in required
                    params.append(
                        f"  - {param_name} ({param_type}{'*' if is_required else ''}): {param_desc}"
                    )

                param_str = "\n".join(params) if params else "  No parameters"
            else:
                param_str = "  No parameters"

            tool_descriptions.append(
                f"{tool_name}: {description}\nParameters:\n{param_str}"
            )

        return "\n\n".join(tool_descriptions)

    def _get_llm_response(self, state: Dict[str, Any]) -> str:
        """Get response from LLM with tool descriptions."""
        # Create enhanced prompt with tool information
        system_message = self.prompt.messages[0].prompt.template
        tool_descriptions = self._format_tools()
        tool_names = ", ".join(self.tools.keys())

        enhanced_system_message = f"""{system_message}

You have access to the following tools: {tool_names}

{tool_descriptions}

In order to use a tool, you can use <tool></tool> and <tool_input></tool_input> tags. You will then get back a response in the form <observation></observation>
For example, if you have a tool called 'search' that could search the web, in order to search for something you would respond:

<tool>search</tool><tool_input>your search query here</tool_input>

And you would get back:
<observation>Search results here...</observation>

If you don't need to use a tool, respond normally without any XML tags.
"""

        # Use template placeholder for messages instead of building dynamically
        prompt = ChatPromptTemplate.from_messages(
            [
                ("system", enhanced_system_message),
                MessagesPlaceholder(variable_name="messages"),
            ]
        )

        # Bind stop sequences to prevent over-generation
        llm_with_stop = self.llm.bind(stop=["</tool_input>", "<observation>"])
        chain = prompt | llm_with_stop

        # Prepare template variables from state (with defaults for missing keys)
        template_vars = {
            "messages": state.get("messages", []),
            "hypothesis": state.get("hypothesis", ""),
            "process": state.get("process", ""),
            "process_decision": state.get("process_decision", ""),
            "visualization_state": state.get("visualization_state", ""),
            "searcher_state": state.get("searcher_state", ""),
            "code_state": state.get("code_state", ""),
            "report_section": state.get("report_section", ""),
            "quality_review": state.get("quality_review", ""),
            "needs_revision": state.get("needs_revision", False),
        }

        try:
            response = chain.invoke(template_vars)
        except Exception as e:
            logger.error(f"Error in manual agent: {e}", exc_info=True)
            return {"output": f"Error: {str(e)}"}

        content = response.content if hasattr(response, "content") else str(response)

        # Post-process response to catch potential formatting issues
        if "<tool>" in content and "</tool>" not in content:
            # Add missing closing tool tag
            content += "</tool>"
        elif "<tool_input>" in content and "</tool_input>" not in content:
            # Add missing closing tool_input tag
            content += "</tool_input>"

        return content

    def _has_tool_call(self, response: str) -> bool:
        """Check if response contains a tool call."""
        return "</tool>" in response

    def _execute_tool_call(self, response: str) -> str:
        """Execute tool call from LLM response using XML parsing (similar to xml_agent)."""
        try:
            # Parse tool call with improved error handling (based on xml_agent)
            if "</tool>" not in response:
                error_msg = "Error: Malformed tool call - missing </tool> tag"
                logger.warning("Malformed tool call", error=error_msg, content=response)
                return error_msg

            # Split on </tool> to separate tool name and input
            tool_parts = response.split("</tool>", 1)
            if len(tool_parts) < 2:
                error_msg = "Error: Could not parse tool call - invalid format"
                logger.warning(
                    "Could not parse tool call", error=error_msg, content=response
                )
                return error_msg

            tool_part, tool_input_part = tool_parts

            # Extract tool name
            if "<tool>" not in tool_part:
                error_msg = "Error: Missing <tool> tag in tool call"
                logger.warning("Missing tool tag", error=error_msg, content=response)
                return error_msg

            tool_name = tool_part.split("<tool>")[1].strip()

            # Extract tool input
            if "<tool_input>" not in tool_input_part:
                tool_input = ""
            else:
                tool_input_content = tool_input_part.split("<tool_input>")[1]
                if "</tool_input>" in tool_input_content:
                    tool_input = tool_input_content.split("</tool_input>")[0]
                else:
                    # Handle case where </tool_input> is missing (malformed/truncated)
                    tool_input = tool_input_content.strip()

            # Validate tool name
            if not tool_name:
                error_msg = "Error: Empty tool name provided"
                logger.warning("Empty tool name", error=error_msg, content=response)
                return error_msg

            # Create and execute tool invocation
            action = ToolInvocation(tool=tool_name, tool_input=tool_input)
            logger.info("Executing tool", tool_name=tool_name, tool_input=tool_input)

            try:
                result = self.tool_executor.invoke(action)
                logger.info(
                    "Tool execution completed", tool_name=tool_name, success=True
                )

                # Handle cases where response might be too large
                if isinstance(result, str) and len(result) > 50000:
                    result = result[:50000] + "\n\n[Response truncated due to length]"

                return str(result) if result else "No response from tool"

            except Exception as e:
                error_msg = f"Error executing tool '{tool_name}': {str(e)}"
                logger.error(
                    "Tool execution failed",
                    tool_name=tool_name,
                    error=str(e),
                    exc_info=True,
                )
                return error_msg

        except Exception as e:
            # Catch-all error handler for unexpected parsing issues
            error_msg = f"Unexpected error parsing tool call: {str(e)}"
            logger.error(
                "Unexpected error parsing tool call", error=str(e), exc_info=True
            )
            return error_msg

    async def _execute_tool_call_async(self, response: str) -> str:
        """Execute tool call from LLM response using XML parsing (async version)."""
        try:
            # Parse tool call with improved error handling (based on xml_agent)
            if "</tool>" not in response:
                error_msg = "Error: Malformed tool call - missing </tool> tag"
                logger.warning("Malformed tool call", error=error_msg, content=response)
                return error_msg

            # Split on </tool> to separate tool name and input
            tool_parts = response.split("</tool>", 1)
            if len(tool_parts) < 2:
                error_msg = "Error: Could not parse tool call - invalid format"
                logger.warning(
                    "Could not parse tool call", error=error_msg, content=response
                )
                return error_msg

            tool_part, tool_input_part = tool_parts

            # Extract tool name
            if "<tool>" not in tool_part:
                error_msg = "Error: Missing <tool> tag in tool call"
                logger.warning("Missing tool tag", error=error_msg, content=response)
                return error_msg

            tool_name = tool_part.split("<tool>")[1].strip()

            # Extract tool input
            if "<tool_input>" not in tool_input_part:
                tool_input = ""
            else:
                tool_input_content = tool_input_part.split("<tool_input>")[1]
                if "</tool_input>" in tool_input_content:
                    tool_input = tool_input_content.split("</tool_input>")[0]
                else:
                    # Handle case where </tool_input> is missing (malformed/truncated)
                    tool_input = tool_input_content.strip()

            # Validate tool name
            if not tool_name:
                error_msg = "Error: Empty tool name provided"
                logger.warning("Empty tool name", error=error_msg, content=response)
                return error_msg

            # Create and execute tool invocation (async)
            action = ToolInvocation(tool=tool_name, tool_input=tool_input)
            logger.info(
                "Executing tool async", tool_name=tool_name, tool_input=tool_input
            )

            try:
                result = await self.tool_executor.ainvoke(action)
                logger.info(
                    "Async tool execution completed", tool_name=tool_name, success=True
                )

                # Handle cases where response might be too large
                if isinstance(result, str) and len(result) > 50000:
                    result = result[:50000] + "\n\n[Response truncated due to length]"

                return str(result) if result else "No response from tool"

            except Exception as e:
                error_msg = f"Error executing tool '{tool_name}': {str(e)}"
                logger.error(
                    "Async tool execution failed",
                    tool_name=tool_name,
                    error=str(e),
                    exc_info=True,
                )
                return error_msg

        except Exception as e:
            # Catch-all error handler for unexpected parsing issues
            error_msg = f"Unexpected error parsing tool call: {str(e)}"
            logger.error(
                "Unexpected error parsing tool call", error=str(e), exc_info=True
            )
            return error_msg

    def _get_final_response(
        self, state: Dict[str, Any], initial_response: str, tool_result: str
    ) -> str:
        """Get final response after tool execution."""
        # Create the observation format (like xml_agent)
        response_with_observation = (
            f"{initial_response}<observation>{tool_result}</observation>"
        )

        # Create follow-up prompt for final analysis
        follow_up_messages = [
            (
                "system",
                "You executed a tool and received results. Please provide your final analysis based on the tool results.",
            ),
            ("assistant", response_with_observation),
            (
                "system",
                "Please provide your final response based on the tool results above.",
            ),
        ]

        follow_up_prompt = ChatPromptTemplate.from_messages(follow_up_messages)
        chain = follow_up_prompt | self.llm

        # No template variables needed for this simple prompt
        final_response = chain.invoke({})
        return (
            final_response.content
            if hasattr(final_response, "content")
            else str(final_response)
        )
