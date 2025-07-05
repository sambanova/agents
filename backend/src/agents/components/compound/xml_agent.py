import asyncio
import os
import time
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

import structlog
from agents.components.compound.data_types import LiberalFunctionMessage, LLMType
from agents.components.compound.prompts import xml_template
from agents.components.compound.util import extract_api_key
from agents.utils.logging_utils import setup_logging_context
from langchain.tools import BaseTool
from langchain.tools.render import render_text_description
from langchain_core.language_models.base import LanguageModelLike
from langchain_core.messages import (
    AIMessage,
    FunctionMessage,
    HumanMessage,
    SystemMessage,
)
from langchain_core.runnables import Runnable, RunnableConfig
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.checkpoint.redis import AsyncRedisSaver
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
from langgraph.graph import END
from langgraph.graph.message import MessageGraph

logger = structlog.get_logger(__name__)


# TODO: This is a temporary fix to get the checkpoint working. Remove this once we have a proper fix.
try:
    from langgraph.checkpoint.redis.aio import AsyncRedisSaver

    # Store the original method
    original_aload_pending_sends = AsyncRedisSaver._aload_pending_sends

    async def patched_aload_pending_sends(self, *args, **kwargs):
        """Patched version that fixes the blob attribute error"""
        try:
            # Try the original method first
            return await original_aload_pending_sends(self, *args, **kwargs)
        except AttributeError as e:
            if "'Document' object has no attribute 'blob'" in str(e):
                # If we hit the blob error, return empty list to avoid crash
                # This means pending sends won't work perfectly, but the checkpoint will function
                return []
            else:
                # Re-raise other AttributeErrors
                raise

    # Apply the patch
    AsyncRedisSaver._aload_pending_sends = patched_aload_pending_sends
    logger.info("Applied Redis checkpoint bug workaround")

except ImportError:
    # Redis checkpoint not available, no patch needed
    pass
except Exception as e:
    logger.error(f"Warning: Could not apply Redis checkpoint patch: {e}")

# Global checkpointer variable
_global_checkpointer = None


def set_global_checkpointer(checkpointer):
    """Set the global checkpointer instance."""
    global _global_checkpointer
    _global_checkpointer = checkpointer


def get_global_checkpointer():
    """Get the global checkpointer instance."""
    return _global_checkpointer


def create_checkpointer(redis_client=None):
    # Simple approach: use Redis directly without context manager pattern
    try:
        if redis_client is None:
            return None

        # Create a custom serializer that supports our custom namespace
        additional_import_mappings = {
            (
                "agents",
                "components",
                "compound",
                "data_types",
                "LiberalFunctionMessage",
            ): (
                "agents",
                "components",
                "compound",
                "data_types",
                "LiberalFunctionMessage",
            ),
            (
                "agents",
                "components",
                "compound",
                "data_types",
                "LiberalAIMessage",
            ): (
                "agents",
                "components",
                "compound",
                "data_types",
                "LiberalAIMessage",
            ),
        }

        # Create checkpointer and extend its serializer configuration
        redis_checkpointer = AsyncRedisSaver(redis_client=redis_client)

        # Store the original loads method to delegate to it first
        original_loads = redis_checkpointer.serde.loads

        def custom_loads(s: str):
            """
            Extended loads method that supports custom message types.

            First attempts to use the original LangGraph deserializer to preserve
            all standard functionality, then falls back to custom configuration
            for objects that require additional namespaces.
            """
            try:
                # Delegate to original implementation first - this handles all
                # standard LangGraph objects including subgraph states
                return original_loads(s)
            except Exception:
                # Original failed, likely due to custom objects that need
                # additional namespaces. Use extended configuration.
                from langchain_core.load.load import loads

                return loads(
                    s,
                    valid_namespaces=[
                        # LangGraph core namespaces
                        "langchain",
                        "langchain_core",
                        "langgraph",
                        "langgraph.graph",
                        "langgraph.checkpoint",
                        "langgraph.pregel",
                        # Custom namespaces
                        "agents",
                        "components",
                        "compound",
                        "message_types",
                    ],
                    additional_import_mappings=additional_import_mappings,
                )

        redis_checkpointer.serde.loads = custom_loads

        return redis_checkpointer

    except Exception as e:
        logger.error(f"Error initializing Redis checkpointer: {e}")
        return None


checkpointer = create_checkpointer(os.getenv("REDIS_URL"))


class ToolInvocation:
    """Simple ToolInvocation class for compatibility."""

    def __init__(self, tool: str, tool_input: str):
        self.tool = tool
        self.tool_input = tool_input


class ToolExecutor:
    """Simple ToolExecutor class for compatibility."""

    def __init__(self, tools):
        self.tools_by_name = {tool.name: tool for tool in tools}

    async def ainvoke(self, action: ToolInvocation):
        tool = self.tools_by_name.get(action.tool)
        if tool:
            return await tool.ainvoke(action.tool_input)
        else:
            return f"Tool {action.tool} not found"


class DynamicToolExecutor:
    """Enhanced ToolExecutor that can load MCP tools dynamically."""

    def __init__(self, static_tools, user_id: str = None):
        self.static_tools_by_name = {tool.name: tool for tool in static_tools}
        self.user_id = user_id
        self.mcp_tools_cache = {}
        self.cache_expiry = 0
        self.cache_ttl = 300  # 5 minutes

    async def ainvoke(self, action: ToolInvocation):
        # First check static tools
        tool = self.static_tools_by_name.get(action.tool)
        if tool:
            return await tool.ainvoke(action.tool_input)
        
        # If not found in static tools and we have a user_id, try MCP tools
        if self.user_id:
            mcp_tool = await self._get_mcp_tool(action.tool)
            if mcp_tool:
                return await mcp_tool.ainvoke(action.tool_input)
        
        return f"Tool {action.tool} not found"
    
    async def _get_mcp_tool(self, tool_name: str):
        """Get MCP tool by name, with caching."""
        import time
        
        # Check cache validity
        if time.time() > self.cache_expiry:
            await self._refresh_mcp_tools()
        
        return self.mcp_tools_cache.get(tool_name)
    
    async def get_all_tools(self):
        """Get all available tools (static + MCP) for prompt generation."""
        import time
        
        # Refresh MCP tools if cache is expired
        if time.time() > self.cache_expiry:
            await self._refresh_mcp_tools()
        
        # Combine static and MCP tools
        all_tools = list(self.static_tools_by_name.values()) + list(self.mcp_tools_cache.values())
        return all_tools

    async def _refresh_mcp_tools(self):
        """Refresh MCP tools cache."""
        import time
        
        try:
            # Import at runtime to avoid circular imports
            from agents.storage.global_services import get_global_mcp_server_manager
            
            mcp_manager = get_global_mcp_server_manager()
            if mcp_manager:
                mcp_tools = await mcp_manager.get_user_mcp_tools(self.user_id)
                self.mcp_tools_cache = {tool.name: tool for tool in mcp_tools}
                self.cache_expiry = time.time() + self.cache_ttl
                
                logger.debug(
                    "Refreshed MCP tools cache",
                    user_id=self.user_id,
                    num_mcp_tools=len(mcp_tools),
                )
            else:
                logger.debug("MCP manager not available, using empty MCP tools cache")
                self.mcp_tools_cache = {}
                self.cache_expiry = time.time() + self.cache_ttl
                
        except Exception as e:
            logger.warning(
                "Failed to refresh MCP tools cache, using empty cache",
                user_id=self.user_id,
                error=str(e),
            )
            self.mcp_tools_cache = {}
            self.cache_expiry = time.time() + 60  # Shorter retry interval on error


def get_xml_agent_executor(
    tools: list[BaseTool],
    llm: LanguageModelLike,
    llm_type: LLMType,
    system_message: str,
    subgraphs: dict = None,
    checkpointer=None,
    user_id: str = None,
):
    """
    Get XML agent executor that can call either tools or subgraphs with tight integration.

    Args:
        tools: List of tools available to the agent
        llm: Language model to use
        system_message: System message for the agent
        interrupt_before_action: Whether to interrupt before action execution
        subgraphs: Dictionary of subgraphs {name: compiled_graph}
        checkpointer: Optional checkpointer, if None will use global checkpointer
        user_id: Optional user ID for context (used for logging and debugging)
    """
    logger.info(
        "Creating XML agent executor",
        tool_names=[t.name for t in tools],
        llm_type=llm_type.value if hasattr(llm_type, "value") else str(llm_type),
        has_subgraphs=bool(subgraphs),
        subgraph_names=list(subgraphs.keys()) if subgraphs else [],
        has_checkpointer=checkpointer is not None,
        user_id=user_id,
    )
    # Use provided checkpointer or fall back to global checkpointer
    if checkpointer is None:
        checkpointer = get_global_checkpointer()

    subgraphs = subgraphs or {}

    # Create subgraph section for the template
    if subgraphs:
        subgraph_descriptions = "\n".join(
            [f"{name}: {subgraphs[name]['description']}" for name in subgraphs.keys()]
        )
        subgraph_section = f"""
You also have access to the following subgraphs:

{subgraph_descriptions}

In order to use a subgraph, you can use <subgraph></subgraph> and <subgraph_input></subgraph_input> tags. You will then get back a response in the form <observation></observation>
For example, if you have a subgraph called 'research_agent' that could conduct research, in order to research a topic you would respond:

<subgraph>research_agent</subgraph><subgraph_input>Tell me about artificial intelligence</subgraph_input>
<observation>Artificial intelligence (AI) is a field of computer science...</observation>"""
    else:
        subgraph_section = ""

    # Create a function to generate system message dynamically (includes MCP tools)
    async def _get_system_message():
        # Get all available tools (static + MCP if using DynamicToolExecutor)
        if isinstance(tool_executor, DynamicToolExecutor):
            all_tools = await tool_executor.get_all_tools()
        else:
            all_tools = tools
            
        return xml_template.format(
            system_message=system_message,
            tools=render_text_description(all_tools),
            tool_names=", ".join([t.name for t in all_tools]),
            subgraph_section=subgraph_section,
        )

    async def _get_messages(messages):
        dynamic_system_message = await _get_system_message()
        return [
            SystemMessage(content=dynamic_system_message)
        ] + await construct_chat_history(messages, llm_type)

    # Use DynamicToolExecutor if user_id is provided for MCP tool support
    if user_id:
        tool_executor = DynamicToolExecutor(tools, user_id)
        logger.info(
            "Using DynamicToolExecutor for MCP tool support",
            user_id=user_id,
            num_static_tools=len(tools),
        )
    else:
        tool_executor = ToolExecutor(tools)

    # Create agent node that extracts api_key from config
    async def agent_node(messages, *, config: RunnableConfig = None):
        setup_logging_context(config, node="agent")
        logger.info("Agent node execution started", num_messages=len(messages))
        api_key = extract_api_key(config)

        # Call your LLM partial with api_key
        initialised_llm = llm(api_key=api_key)

        llm_with_stop = initialised_llm.bind(
            stop=["</tool_input>", "</subgraph_input>", "<observation>"]
        )

        # Check if the last message indicates a malformed tool call that needs retry
        last_message = messages[-1] if messages else None

        if (
            last_message
            and hasattr(last_message, "additional_kwargs")
            and last_message.additional_kwargs.get("error_type")
            in [
                "malformed_tool_call",
                "parse_error",
                "missing_tool_tag",
                "empty_tool_name",
            ]
        ):
            # Add a helpful system message about proper tool formatting
            retry_instruction = """The previous tool call was malformed. Please ensure you use the correct format:
<tool>tool_name</tool>
<tool_input>
your input here
</tool_input>

Make sure to include both opening and closing tags for both tool and tool_input."""

            # Inject the retry instruction into the message history
            processed_messages = await _get_messages(messages)
            processed_messages.append(AIMessage(content=retry_instruction))
        else:
            # Process messages normally
            processed_messages = await _get_messages(messages)

        try:
            start_time = time.time()
            logger.info("Invoking LLM")
            response = await llm_with_stop.ainvoke(processed_messages, config)
            duration = time.time() - start_time
            logger.info(
                "LLM invocation completed",
                duration_ms=round(duration * 1000, 2),
                model=llm_with_stop.model,
            )

            # Post-process response to catch potential formatting issues
            if hasattr(response, "content") and isinstance(response.content, str):
                content = response.content

                # Check for incomplete tool calls and attempt basic cleanup
                if "<tool>" in content and "</tool>" not in content:
                    # Add missing closing tool tag
                    content += "</tool>"
                    response.content = content
                elif "<tool_input>" in content and "</tool_input>" not in content:
                    # Add missing closing tool_input tag
                    content += "</tool_input>"
                    response.content = content

            return response

        except Exception as e:
            logger.error(
                "LLM invocation failed",
                node="agent",
                error_type=type(e).__name__,
                error_message=str(e),
                exc_info=True,
            )
            # If LLM call fails, return an error message that the system can handle
            error_msg = f"Agent error: {str(e)}"
            return AIMessage(
                content=error_msg,
                additional_kwargs={
                    "error_type": "agent_execution_error",
                    "agent_type": "react_end",
                },
            )

        # Define the function that determines whether to continue or not

    def should_continue(messages):
        last_message = messages[-1]
        content = last_message.content

        # Add action metadata to the last message
        if (
            hasattr(last_message, "additional_kwargs")
            and last_message.additional_kwargs
        ):
            additional_kwargs = last_message.additional_kwargs.copy()
        else:
            additional_kwargs = {}

        # Simple routing logic - let call_tool handle all validation
        if "</tool>" in content:
            additional_kwargs["agent_type"] = "react_tool"
            last_message.additional_kwargs = additional_kwargs
            return "tool_action"
        elif "</subgraph>" in content:
            # Only do basic subgraph name extraction for routing
            try:
                subgraph_name = (
                    content.split("<subgraph>")[1].split("</subgraph>")[0].strip()
                )
                if subgraph_name:
                    additional_kwargs["agent_type"] = "react_subgraph_" + subgraph_name
                    last_message.additional_kwargs = additional_kwargs
                    return f"subgraph_{subgraph_name}"
            except (IndexError, ValueError):
                pass

            # If we can't extract subgraph name, treat as end
            additional_kwargs["agent_type"] = "react_end"
            last_message.additional_kwargs = additional_kwargs
            return "end"
        else:
            additional_kwargs["agent_type"] = "react_end"
            last_message.additional_kwargs = additional_kwargs
            return "end"

    # Define the function to execute tools
    async def call_tool(messages, *, config: RunnableConfig = None):
        setup_logging_context(config, node="tool_action")
        logger.info("Tool action started")
        last_message = messages[-1]
        content = last_message.content

        try:
            # Parse tool call with improved error handling
            if "</tool>" not in content:
                # Malformed tool call - missing closing tool tag
                error_msg = "Error: Malformed tool call - missing </tool> tag"
                logger.warning(
                    "Malformed tool call",
                    error=error_msg,
                    content=content,
                )
                return LiberalFunctionMessage(
                    content=error_msg,
                    name="system_error",
                    additional_kwargs={
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "agent_type": "tool_response",
                        "error_type": "malformed_tool_call",
                    },
                )

            # Split on </tool> to separate tool name and input
            tool_parts = content.split("</tool>", 1)
            if len(tool_parts) < 2:
                error_msg = "Error: Could not parse tool call - invalid format"
                logger.warning(
                    "Could not parse tool call",
                    error=error_msg,
                    content=content,
                )
                return LiberalFunctionMessage(
                    content=error_msg,
                    name="system_error",
                    additional_kwargs={
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "agent_type": "tool_response",
                        "error_type": "parse_error",
                    },
                )

            tool_part, tool_input_part = tool_parts

            # Extract tool name
            if "<tool>" not in tool_part:
                error_msg = "Error: Missing <tool> tag in tool call"
                logger.warning(
                    "Missing tool tag",
                    error=error_msg,
                    content=content,
                )
                return LiberalFunctionMessage(
                    content=error_msg,
                    name="system_error",
                    additional_kwargs={
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "agent_type": "tool_response",
                        "error_type": "missing_tool_tag",
                    },
                )

            _tool = tool_part.split("<tool>")[1].strip()

            # Extract tool input
            if "<tool_input>" not in tool_input_part:
                _tool_input = ""
            else:
                tool_input_content = tool_input_part.split("<tool_input>")[1]
                if "</tool_input>" in tool_input_content:
                    _tool_input = tool_input_content.split("</tool_input>")[0]
                else:
                    # Handle case where </tool_input> is missing (malformed/truncated)
                    _tool_input = tool_input_content.strip()
                    # Note: This allows processing even with malformed input

            # Validate tool name
            if not _tool:
                error_msg = "Error: Empty tool name provided"
                logger.warning(
                    "Empty tool name",
                    error=error_msg,
                    content=content,
                )
                return LiberalFunctionMessage(
                    content=error_msg,
                    name="system_error",
                    additional_kwargs={
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "agent_type": "tool_response",
                        "error_type": "empty_tool_name",
                    },
                )

            action = ToolInvocation(
                tool=_tool,
                tool_input=_tool_input,
            )
            logger.info(
                "Executing tool",
                tool_name=_tool,
                tool_input=_tool_input,
            )
            # Execute tool with error handling
            start_time = time.time()
            try:
                response = await tool_executor.ainvoke(action)
                duration = time.time() - start_time
                logger.info(
                    "Tool execution completed",
                    tool_name=_tool,
                    duration_ms=round(duration * 1000, 2),
                    success=True,
                )

                # Handle cases where response might be malformed or too large
                if isinstance(response, str) and len(response) > 50000:
                    response = (
                        response[:50000] + "\n\n[Response truncated due to length]"
                    )

            except Exception as e:
                duration = time.time() - start_time
                error_msg = f"Error executing tool '{_tool}': {str(e)}"
                logger.error(
                    "Tool execution failed",
                    tool_name=_tool,
                    error_type=type(e).__name__,
                    error_message=str(e),
                    duration_ms=round(duration * 1000, 2),
                    success=False,
                    exc_info=True,
                )
                return LiberalFunctionMessage(
                    content=error_msg,
                    name=_tool,
                    additional_kwargs={
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "agent_type": "tool_response",
                        "error_type": "tool_execution_error",
                    },
                )

            # Create function message
            function_message = LiberalFunctionMessage(
                content=response if len(response) > 0 else "No response from tool",
                response_metadata={"usage": {"total_latency": duration}},
                name=action.tool,
                additional_kwargs={
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "agent_type": "tool_response",
                },
            )
            return function_message

        except Exception as e:
            # Catch-all error handler for unexpected parsing issues
            error_msg = f"Unexpected error parsing tool call: {str(e)}"
            logger.error(
                "Unexpected error parsing tool call",
                error_type=type(e).__name__,
                error_message=str(e),
                exc_info=True,
            )
            return LiberalFunctionMessage(
                content=error_msg,
                name="system_error",
                additional_kwargs={
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "agent_type": "tool_response",
                    "error_type": "unexpected_parse_error",
                },
            )

    # Create subgraph entry nodes
    def create_subgraph_entry_node(
        subgraph_name: str,
        state_input_mapper: Callable,
        state_output_mapper: Callable,
        subgraph,
    ):
        async def subgraph_entry_node(messages, *, config: RunnableConfig = None):
            setup_logging_context(
                config, node=f"subgraph_{subgraph_name}", subgraph_name=subgraph_name
            )
            logger.info("Subgraph node started")
            last_message = messages[-1]
            # Parse subgraph input
            content = last_message.content
            if "<subgraph_input>" not in content:
                subgraph_input = ""
            else:
                subgraph_input_part = content.split("<subgraph_input>")[1]
                if "</subgraph_input>" in subgraph_input_part:
                    subgraph_input = subgraph_input_part.split("</subgraph_input>")[0]
                else:
                    subgraph_input = subgraph_input_part

            subgraph_messages = state_input_mapper(subgraph_input)
            logger.info(
                "Invoking subgraph",
            )
            # Execute subgraph with the same config (for proper state management)
            # For MessageGraph, pass messages directly, not wrapped in a dict
            start_time = time.time()
            result = await subgraph.ainvoke(subgraph_messages, config)
            duration = time.time() - start_time
            logger.info(
                "Subgraph invocation completed",
                duration_ms=round(duration * 1000, 2),
                success=True,
            )

            return state_output_mapper(result)

        return subgraph_entry_node

    # Build the workflow
    workflow = MessageGraph()

    # Add main agent node
    workflow.add_node("agent", agent_node)

    # Add tool action node
    workflow.add_node("tool_action", call_tool)

    # Add subgraph nodes dynamically
    subgraph_routing = {}
    for subgraph_name, subgraph_def in subgraphs.items():
        node_name = f"subgraph_{subgraph_name}"
        workflow.add_node(
            node_name,
            create_subgraph_entry_node(
                subgraph_name,
                subgraph_def["state_input_mapper"],
                subgraph_def["state_output_mapper"],
                subgraph_def["graph"],
            ),
        )
        subgraph_routing[node_name] = node_name

    # Set the entrypoint as `agent`
    workflow.set_entry_point("agent")

    # Add conditional edges from agent
    routing_dict = {"tool_action": "tool_action", "end": END, **subgraph_routing}

    workflow.add_conditional_edges(
        "agent",
        should_continue,
        routing_dict,
    )

    # Add edges back to agent from all action nodes
    workflow.add_edge("tool_action", "agent")
    for subgraph_name in subgraphs.keys():
        # We route the subgraph to the next node specified in the subgraph definition
        workflow.add_edge(
            f"subgraph_{subgraph_name}", subgraphs[subgraph_name]["next_node"]
        )

    return workflow.compile(
        checkpointer=checkpointer,
    )


def _collapse_messages(messages):

    # Edge case for financial analysis subgraphs (this one does not return a message after the observation)
    if len(messages) == 2 and messages[-1].additional_kwargs.get("agent_type") in [
        "financial_analysis_end",
        "deep_research_end",
    ]:
        log = f"{messages[0].content}<observation>{messages[1].content}</observation>"
        return AIMessage(content=log)

    log = ""
    if isinstance(messages[-1], AIMessage):
        scratchpad = messages[:-1]
        final = messages[-1]
    else:
        scratchpad = messages
        final = None
    if len(scratchpad) % 2 != 0:
        raise ValueError("Unexpected")
    for i in range(0, len(scratchpad), 2):
        action = messages[i]
        observation = messages[i + 1]
        log += f"{action.content}<observation>{observation.content}</observation>"
    if final is not None:
        log += final.content
    return AIMessage(content=log)


async def construct_chat_history(messages, llm_type: LLMType):
    collapsed_messages = []
    temp_messages = []
    for message in messages:
        if isinstance(message, HumanMessage):
            # If some of the messages contain images, we need to collapse them into a single message for text based models
            if llm_type != LLMType.SN_LLAMA_MAVERICK and isinstance(
                message.content, list
            ):
                for c in message.content:
                    if "text" in c:
                        message.content = c["text"]
            if temp_messages:
                collapsed_messages.append(_collapse_messages(temp_messages))
                temp_messages = []
            collapsed_messages.append(message)
        elif isinstance(message, LiberalFunctionMessage):
            _dict = message.model_dump()
            _dict["content"] = str(_dict["content"])
            m_c = FunctionMessage(**_dict)
            temp_messages.append(m_c)
        else:
            temp_messages.append(message)

    # Don't forget to add the last non-human message if it exists
    if temp_messages:
        collapsed_messages.append(_collapse_messages(temp_messages))

    return collapsed_messages
