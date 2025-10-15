import os
import re
import time
from datetime import datetime, timezone
from typing import Callable

import httpx
import langsmith as ls
import structlog
from agents.components.compound.data_types import LiberalFunctionMessage, LLMType
from agents.components.compound.prompts import xml_template
from agents.components.compound.timing_aggregator import WorkflowTimingAggregator
from agents.components.compound.util import extract_api_key, extract_api_keys, extract_user_id
from agents.utils.logging_utils import setup_logging_context
from langchain.tools import BaseTool
from langchain_core.language_models.base import LanguageModelLike
from langchain_core.messages import (
    AIMessage,
    FunctionMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.redis import AsyncRedisSaver
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
    """Enhanced ToolExecutor that can load tools dynamically."""

    def __init__(self, static_tools, user_id: str = None):
        self.static_tools_by_name = {tool.name: tool for tool in static_tools}
        self.user_id = user_id

    async def ainvoke(self, action: ToolInvocation):
        # Check static tools
        tool = self.static_tools_by_name.get(action.tool)
        if tool:
            return await tool.ainvoke(action.tool_input)

        return f"Tool {action.tool} not found"

    async def get_all_tools(self):
        """Get all available tools for prompt generation."""
        return list(self.static_tools_by_name.values())


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

    # Create a function to generate system message dynamically
    async def _get_system_message():
        # Get all available tools
        if isinstance(tool_executor, DynamicToolExecutor):
            all_tools = await tool_executor.get_all_tools()
        else:
            all_tools = tools

        def _describe_tool(_tool: BaseTool) -> str:
            """Return a rich, schema-aware description of a tool for the LLM prompt."""
            import inspect
            import json
            import textwrap

            # Start with name + description
            lines: list[str] = [f"{_tool.name}: {_tool.description}"]

            # ------------------------------------------------------------------
            # Try to extract parameter definitions from various schema sources
            # ------------------------------------------------------------------
            schema = None
            if hasattr(_tool, "args_schema") and _tool.args_schema is not None:
                # Pydantic-style schema (preferred)
                try:
                    schema = _tool.args_schema.model_json_schema()
                except Exception:
                    # Fallback for Pydantic v1 or custom objects
                    if hasattr(_tool.args_schema, "schema"):
                        schema = _tool.args_schema.schema()
            elif hasattr(_tool, "input_schema") and _tool.input_schema:
                schema = _tool.input_schema  # Sometimes placed here directly
            elif hasattr(_tool, "tool_info") and getattr(_tool, "tool_info", None):
                # For tool wrappers we stored input_schema earlier
                schema = getattr(_tool.tool_info, "input_schema", None)

            example_json: str | None = None
            if schema and isinstance(schema, dict):
                props = schema.get("properties", {})
                required = set(schema.get("required", []))

                if props:
                    lines.append("Parameters:")
                    for pname, pinfo in props.items():
                        ptype = pinfo.get("type", "string")
                        pdesc = pinfo.get("description", "")
                        req_flag = " (required)" if pname in required else ""
                        lines.append(f"  - {pname} ({ptype}){req_flag}: {pdesc}")

                    # Build concise example JSON with placeholder values
                    example_dict = {}
                    for pname, pinfo in props.items():
                        ptype = pinfo.get("type", "string")
                        if ptype == "integer":
                            example_dict[pname] = 1
                        elif ptype == "boolean":
                            example_dict[pname] = True
                        else:
                            example_dict[pname] = f"<{pname}>"
                    example_json = json.dumps(example_dict, indent=2)

            # Include example usage block with proper formatting
            if example_json:
                lines.append("Example:")
                lines.append("<tool>" + _tool.name + "</tool>")
                lines.append("<tool_input>")
                # Format JSON with proper indentation for readability
                import json

                try:
                    # Parse and reformat to ensure proper JSON structure
                    parsed_example = (
                        json.loads(example_json)
                        if isinstance(example_json, str)
                        else example_json
                    )
                    formatted_json = json.dumps(parsed_example, indent=2)
                    lines.append(formatted_json)
                except (json.JSONDecodeError, TypeError):
                    # Fallback to original if parsing fails
                    lines.append(example_json)
                lines.append("</tool_input>")

                # Add a format reminder for this specific tool
                lines.append(
                    "⚠️  CRITICAL: Use exact JSON format above with proper { } structure"
                )

            return textwrap.dedent("\n".join(lines)).strip()

        detailed_tools_desc = "\n\n".join(_describe_tool(t) for t in all_tools)

        return xml_template.format(
            system_message=system_message,
            tools=detailed_tools_desc,
            tool_names=", ".join([t.name for t in all_tools]),
            subgraph_section=subgraph_section,
        )

    async def _get_messages(messages):
        dynamic_system_message = await _get_system_message()
        return [
            SystemMessage(content=dynamic_system_message)
        ] + await construct_chat_history(messages, llm_type)

    # Use DynamicToolExecutor if user_id is provided for enhanced tool support
    if user_id:
        tool_executor = DynamicToolExecutor(tools, user_id)
        logger.info(
            "Using DynamicToolExecutor for enhanced tool support",
            user_id=user_id,
            num_static_tools=len(tools),
        )
    else:
        tool_executor = ToolExecutor(tools)

    # Create agent node that extracts api_key from config
    @ls.traceable(
        metadata={"agent_type": "xml_agent", "llm_type": LLMType.SN_DEEPSEEK_V3.value},
        process_inputs=lambda x: None,
    )
    async def agent_node(messages, *, config: RunnableConfig = None):
        setup_logging_context(config, node="agent")
        logger.info("Agent node execution started", num_messages=len(messages))
        api_key = extract_api_key(config)
        api_keys = extract_api_keys(config)  # Get all API keys if admin panel is enabled
        user_id = extract_user_id(config)  # Get user_id for admin panel support

        # Call your LLM partial with api_key (and optionally api_keys and user_id)
        # Pass api_keys and user_id if available for admin panel support
        if api_keys:
            initialised_llm = llm(api_key=api_key, api_keys=api_keys, user_id=user_id)
        else:
            initialised_llm = llm(api_key=api_key)

        llm_with_stop = initialised_llm.bind(
            stop=["</subgraph_input>", "<observation>", "\n\nHuman:", "\n\nAssistant:"]
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

            # Get model name - different providers store it differently
            model_name = None
            if hasattr(llm_with_stop, 'model'):
                model_name = llm_with_stop.model
            elif hasattr(llm_with_stop, 'model_name'):
                model_name = llm_with_stop.model_name
            elif hasattr(llm_with_stop, 'bound') and hasattr(llm_with_stop.bound, 'model'):
                model_name = llm_with_stop.bound.model
            elif hasattr(llm_with_stop, 'bound') and hasattr(llm_with_stop.bound, 'model_name'):
                model_name = llm_with_stop.bound.model_name

            logger.info(
                "LLM invocation completed",
                duration_ms=round(duration * 1000, 2),
                model=model_name,
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

            # Add timing metadata to response for hierarchical tracking
            if not hasattr(response, "response_metadata") or response.response_metadata is None:
                response.response_metadata = {}

            if "usage" not in response.response_metadata:
                response.response_metadata["usage"] = {}

            response.response_metadata["usage"]["total_latency"] = duration
            response.response_metadata["model_name"] = model_name

            # Store timing data for workflow aggregation
            if not hasattr(response, "additional_kwargs") or response.additional_kwargs is None:
                response.additional_kwargs = {}

            response.additional_kwargs["main_agent_timing"] = {
                "node_name": "agent_node",
                "agent_name": "XML Agent",
                "model_name": model_name,
                "duration": duration,
                "start_time": start_time,
            }

            return response

        except RuntimeError as e:
            error_str = str(e)
            # Check if it's a context length error
            if "maximum context length" in error_str.lower() and "32768" in error_str:
                logger.warning(
                    "Context length exceeded for DeepSeek model, falling back to gpt-oss-120b",
                    original_error=error_str
                )

                # Switch to using gpt-oss-120b directly with full context
                logger.info("Switching to gpt-oss-120b for this response due to context length")

                # Create a traceable wrapper for the gpt-oss-120b call
                @ls.traceable(
                    name="gpt-oss-120b-fallback",
                    run_type="llm",
                    metadata={
                        "model": "gpt-oss-120b",
                        "fallback_reason": "context_length_exceeded",
                        "original_model": "DeepSeek-V3-0324"
                    }
                )
                async def call_gpt_oss_120b(messages_dict, api_key):
                    """Traceable wrapper for gpt-oss-120b API call"""
                    async with httpx.AsyncClient(timeout=60.0) as client:
                        response = await client.post(
                            "https://api.sambanova.ai/v1/chat/completions",
                            headers={
                                "Authorization": f"Bearer {api_key}",
                                "Content-Type": "application/json"
                            },
                            json={
                                "model": "gpt-oss-120b",
                                "messages": messages_dict,
                                "stream": False,
                                "max_tokens": 16384,
                                "temperature": 0,
                                "reasoning_effort": "medium"
                            }
                        )

                        if response.status_code != 200:
                            raise Exception(f"gpt-oss-120b call failed with status {response.status_code}: {response.text}")

                        return response.json()

                try:
                    # Get ALL messages for context - gpt-oss-120b has 128k context window
                    recent_messages = []

                    # Keep FULL system message if it exists - include ALL tool definitions
                    if processed_messages and isinstance(processed_messages[0], SystemMessage):
                        system_content = processed_messages[0].content

                        # Check what's in the system message for debugging
                        logger.info(
                            "System message for gpt-oss-120b",
                            full_length=len(system_content),
                            has_tools_section="You have access to the following tools:" in system_content,
                            has_tool_tags="<tool>" in system_content,
                            has_confluence="confluence" in system_content.lower(),
                            first_500_chars=system_content[:500] if len(system_content) > 500 else system_content
                        )

                        recent_messages.append({
                            "role": "system",
                            "content": system_content  # Full system message, no truncation
                        })

                    # Include ALL messages in the conversation - no truncation or limiting
                    for msg in processed_messages[1:] if processed_messages and isinstance(processed_messages[0], SystemMessage) else processed_messages:
                        if isinstance(msg, HumanMessage):
                            recent_messages.append({
                                "role": "user",
                                "content": msg.content if msg.content else "Continue with the task"
                            })
                        elif isinstance(msg, AIMessage):
                            # Include FULL AI message content - no truncation
                            content_text = msg.content if msg.content else ""
                            if not content_text and hasattr(msg, "tool_calls"):
                                content_text = f"[Tool calls: {msg.tool_calls}]"
                            if content_text:  # Only add if there's actual content
                                recent_messages.append({
                                    "role": "assistant",
                                    "content": content_text  # Full content, no truncation
                                })
                        elif isinstance(msg, (ToolMessage, FunctionMessage)):
                            # Include FULL tool results - no truncation
                            tool_content = msg.content if msg.content else "[Tool executed]"
                            recent_messages.append({
                                "role": "assistant",
                                "content": f"[Tool result]: {tool_content}"  # Full tool result, no truncation
                            })

                    # Ensure we have at least a user message
                    if not any(msg["role"] == "user" for msg in recent_messages):
                        recent_messages.append({
                            "role": "user",
                            "content": "Please continue with the current task based on the context."
                        })

                    # Add explicit instruction for tool use if this is a continuation
                    if len(recent_messages) > 1 and recent_messages[-1]["role"] == "assistant":
                        # Add a user message to prompt continuation
                        recent_messages.append({
                            "role": "user",
                            "content": (
                                "Continue with the task. If you need to use tools, format them as:\n"
                                "<tool>tool_name</tool>\n<tool_input>{parameters}</tool_input>\n\n"
                                "Otherwise, provide your response directly."
                            )
                        })

                    # Log what we're sending
                    logger.info(
                        "Sending FULL conversation context to gpt-oss-120b",
                        num_messages=len(recent_messages),
                        total_chars=sum(len(msg["content"]) for msg in recent_messages),
                        message_roles=[msg["role"] for msg in recent_messages],
                        has_full_system_message=any(msg["role"] == "system" and "<tool>" in msg["content"] for msg in recent_messages),
                        messages_preview=[
                            {"role": msg["role"], "content": msg["content"][:100] + "..." if len(msg["content"]) > 100 else msg["content"]}
                            for msg in recent_messages[:5]  # Only preview first 5 messages for logging
                        ]
                    )

                    # Make traceable call to gpt-oss-120b
                    result = await call_gpt_oss_120b(recent_messages, api_key)

                    # Log the full response structure for debugging
                    logger.info(
                        "gpt-oss-120b response structure",
                        has_choices="choices" in result,
                        num_choices=len(result.get("choices", [])) if "choices" in result else 0,
                        first_choice=result.get("choices", [{}])[0] if result.get("choices") else None
                    )

                    # Safely extract content
                    content = None
                    if "choices" in result and len(result["choices"]) > 0:
                        choice = result["choices"][0]
                        # Log the choice structure
                        logger.info(
                            "gpt-oss-120b choice structure",
                            choice_keys=list(choice.keys()),
                            has_message="message" in choice,
                            message_content=choice.get("message", {}).get("content", "NO_CONTENT")[:200] if "message" in choice and choice.get("message", {}).get("content") else "NO_MESSAGE",
                            message_reasoning=choice.get("message", {}).get("reasoning", "NO_REASONING")[:200] if "message" in choice and choice.get("message", {}).get("reasoning") else "NO_REASONING"
                        )

                        if "message" in choice and choice["message"] is not None:
                            # Check for content first
                            content = choice["message"].get("content")

                            # If content is None but reasoning exists, extract next action from reasoning
                            # This happens with reasoning_effort="medium" - the model provides reasoning separately
                            if not content and "reasoning" in choice["message"]:
                                reasoning = choice["message"].get("reasoning", "")
                                logger.info(
                                    "gpt-oss-120b provided reasoning, extracting next action",
                                    reasoning=reasoning[:500]  # Log first 500 chars
                                )

                                # When reasoning_effort="medium", the model may provide reasoning without content
                                # In this case, we'll use the reasoning as the response
                                logger.info(
                                    "gpt-oss-120b provided reasoning without content, using reasoning as response"
                                )
                                # Truncate very long reasoning and format as a response
                                if len(reasoning) > 2000:
                                    content = reasoning[:2000] + "..."
                                else:
                                    content = reasoning

                            elif "text" in choice:
                                content = choice["text"]

                        # Fallback if no content
                        if not content:
                            logger.warning(
                                "gpt-oss-120b returned empty content",
                                response_keys=list(result.keys()) if result else None,
                                choices_length=len(result.get("choices", [])),
                                first_choice_keys=list(result["choices"][0].keys()) if result.get("choices") else None
                            )
                            content = "I need more context to continue. Please provide additional information or try a different query."

                    duration = time.time() - start_time
                    logger.info(
                        "Successfully used gpt-oss-120b for full response",
                        duration_ms=round(duration * 1000, 2),
                        model="gpt-oss-120b"
                    )

                    return AIMessage(content=content)

                except Exception as fallback_error:
                    logger.error(
                        "GPT-OSS-120b fallback failed",
                        error_type=type(fallback_error).__name__,
                        error_message=str(fallback_error),
                        exc_info=True
                    )
                    # Re-raise the original error if fallback fails
                    raise e
            else:
                # Not a context length error, re-raise
                raise

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

    def _aggregate_and_attach_workflow_timing(messages, additional_kwargs):
        """
        Aggregate workflow timing from all messages and attach to additional_kwargs.
        This is called from should_continue when routing to "end".
        """
        # Capture workflow end time IMMEDIATELY
        workflow_end_time = time.time()

        # Extract main agent timing from all messages
        main_agent_calls = []
        workflow_start_time = workflow_end_time  # Initialize, will be updated to earliest

        for msg in messages:
            if hasattr(msg, 'additional_kwargs') and msg.additional_kwargs:
                if 'main_agent_timing' in msg.additional_kwargs:
                    timing = msg.additional_kwargs['main_agent_timing']
                    main_agent_calls.append(timing)
                    # Find the earliest agent call start time
                    if timing.get('start_time') and timing['start_time'] < workflow_start_time:
                        workflow_start_time = timing['start_time']

        # If no agent calls found, skip timing aggregation
        if not main_agent_calls:
            logger.debug("No main agent timing data found, skipping workflow timing")
            return

        # Initialize timing aggregator with the correct workflow start time
        aggregator = WorkflowTimingAggregator()
        aggregator.workflow_start_time = workflow_start_time

        # Add main agent calls to aggregator
        for call in main_agent_calls:
            aggregator.add_main_agent_call(
                node_name=call.get('node_name', 'agent_node'),
                agent_name=call.get('agent_name', 'XML Agent'),
                model_name=call.get('model_name', 'unknown'),
                provider=call.get('provider', 'sambanova'),
                duration=call.get('duration', 0),
                start_time=call.get('start_time', workflow_start_time)
            )

        # Get hierarchical timing structure with explicit end time
        hierarchical_timing = aggregator.get_hierarchical_timing(workflow_end_time=workflow_end_time)

        # Attach to additional_kwargs (will be on the final message)
        additional_kwargs['workflow_timing'] = hierarchical_timing

        logger.info(
            "Aggregated workflow timing in should_continue",
            total_llm_calls=hierarchical_timing.get('total_llm_calls', 0),
            workflow_duration=round(hierarchical_timing.get('workflow_duration', 0), 3),
            num_levels=len(hierarchical_timing.get('levels', [])),
        )

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
                if subgraph_name and subgraph_name in subgraphs:
                    additional_kwargs["agent_type"] = "react_subgraph_" + subgraph_name
                    last_message.additional_kwargs = additional_kwargs
                    return f"subgraph_{subgraph_name}"
                else:
                    logger.warning(
                        "Attempted to route to non-existent subgraph",
                        requested_subgraph=subgraph_name,
                        available_subgraphs=list(subgraphs.keys()),
                    )
                    additional_kwargs["agent_type"] = "react_end"
                    additional_kwargs["error_type"] = "non_existent_subgraph"
                    last_message.additional_kwargs = additional_kwargs
                    last_message.content = f"I am not able to route to the {subgraph_name} subgraph as it is not available"
                    # Aggregate timing before returning "end"
                    _aggregate_and_attach_workflow_timing(messages, additional_kwargs)
                    last_message.additional_kwargs = additional_kwargs
                    return "end"
            except (IndexError, ValueError):
                pass

            # If we can't extract subgraph name, treat as end
            additional_kwargs["agent_type"] = "react_end"
            # Aggregate timing before returning "end"
            _aggregate_and_attach_workflow_timing(messages, additional_kwargs)
            last_message.additional_kwargs = additional_kwargs
            return "end"
        else:
            # This is the normal end case - aggregate workflow timing
            additional_kwargs["agent_type"] = "react_end"
            # Aggregate timing before returning "end"
            _aggregate_and_attach_workflow_timing(messages, additional_kwargs)
            last_message.additional_kwargs = additional_kwargs
            return "end"

    # Define the function to execute tools
    async def call_tool(messages, *, config: RunnableConfig = None):
        setup_logging_context(config, node="tool_action")
        logger.info("Tool action started")
        last_message = messages[-1]
        content = last_message.content

        # Check if there are multiple tool calls
        tool_count = content.count("</tool>")

        if tool_count > 1:
            # Multiple tool calls detected - execute in parallel
            logger.info(f"Detected {tool_count} tool calls, executing in parallel")
            return await _execute_parallel_tools(content, tool_executor)

        # Single tool call - continue with existing logic
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

            # Extract tool input with improved parsing
            if "<tool_input>" not in tool_input_part:
                _tool_input = ""
            else:
                tool_input_content = tool_input_part.split("<tool_input>")[1]
                if "</tool_input>" in tool_input_content:
                    _tool_input = tool_input_content.split("</tool_input>")[0]
                else:
                    # Handle case where </tool_input> is missing (malformed/truncated)
                    # Remove any partial closing tags
                    _tool_input = tool_input_content.strip()
                    # Clean up partial XML tags that might be at the end
                    _tool_input = re.sub(r"</?[^>]*$", "", _tool_input).strip()
                    # Note: This allows processing even with malformed input

                # Smart JSON extraction and conversion for structured tools
                _tool_input = _tool_input.strip()

                def smart_json_extract(text):
                    """Extract JSON from text using multiple strategies."""
                    import json
                    import re

                    # Strategy 1: Clean JSON (starts and ends with braces)
                    if text.startswith("{") and text.endswith("}"):
                        try:
                            return json.loads(text)
                        except json.JSONDecodeError:
                            pass

                    # Strategy 2: Find JSON pattern in mixed content
                    json_pattern = r"\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}"
                    json_matches = re.findall(json_pattern, text)
                    for match in json_matches:
                        try:
                            return json.loads(match)
                        except json.JSONDecodeError:
                            continue

                    # Strategy 3: Extract from partial/malformed JSON
                    # Fix common issues like missing quotes, trailing commas
                    if "{" in text and "}" in text:
                        # Extract content between first { and last }
                        start = text.find("{")
                        end = text.rfind("}") + 1
                        if start < end:
                            json_candidate = text[start:end]
                            try:
                                return json.loads(json_candidate)
                            except json.JSONDecodeError:
                                # Try fixing common JSON issues
                                fixed_json = json_candidate
                                # Remove trailing commas
                                fixed_json = re.sub(r",(\s*[}\]])", r"\1", fixed_json)
                                # Add missing quotes to keys
                                fixed_json = re.sub(r"(\w+):", r'"\1":', fixed_json)
                                try:
                                    return json.loads(fixed_json)
                                except json.JSONDecodeError:
                                    pass

                    # Strategy 4: Key-value pair extraction
                    # For formats like: query: "SambaQA", cloudId: "abc123"
                    kv_pattern = r'(\w+):\s*["\']([^"\']*)["\']'
                    matches = re.findall(kv_pattern, text)
                    if matches:
                        return {key: value for key, value in matches}

                    return None

                if _tool_input:
                    extracted_json = smart_json_extract(_tool_input)
                    if extracted_json:
                        _tool_input = extracted_json
                        logger.debug(
                            "Smart extracted JSON for tool",
                            tool_name=_tool,
                            original=(
                                str(_tool_input)[:100]
                                if isinstance(_tool_input, str)
                                else "dict"
                            ),
                            extracted_type=type(_tool_input).__name__,
                        )
                    else:
                        logger.debug(
                            "No JSON structure detected, keeping as string",
                            tool_name=_tool,
                            input_preview=str(_tool_input)[:100],
                        )

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

    # Function to execute multiple tools in parallel
    async def _execute_parallel_tools(content, tool_executor):
        """Execute multiple tool calls in parallel."""
        import asyncio
        import json

        # Extract all tool calls
        tool_calls = []
        remaining_content = content

        # Parse each tool call
        while "</tool>" in remaining_content:
            tool_parts = remaining_content.split("</tool>", 1)
            tool_part, after_tool = tool_parts

            # Extract tool name
            if "<tool>" not in tool_part:
                remaining_content = after_tool
                continue

            tool_name = tool_part.split("<tool>")[-1].strip()

            # Extract tool input
            tool_input = ""
            if "<tool_input>" in after_tool:
                input_parts = after_tool.split("<tool_input>", 1)
                if len(input_parts) > 1:
                    input_content = input_parts[1]
                    if "</tool_input>" in input_content:
                        tool_input = input_content.split("</tool_input>")[0].strip()
                        # Move past this tool call
                        remaining_content = input_content.split("</tool_input>", 1)[1]
                    else:
                        # Malformed, but try to extract what we can
                        tool_input = input_content.strip()
                        remaining_content = ""
            else:
                # No input for this tool
                remaining_content = after_tool

            # Smart JSON extraction (reuse the existing logic from single tool)
            if tool_input:
                # Try to parse as JSON if it looks like JSON
                if tool_input.startswith("{") and tool_input.endswith("}"):
                    try:
                        tool_input = json.loads(tool_input)
                    except json.JSONDecodeError:
                        # Keep as string if not valid JSON
                        pass

            tool_calls.append((tool_name, tool_input))

        if not tool_calls:
            return LiberalFunctionMessage(
                content="Error: Could not parse any tool calls",
                name="system_error",
                additional_kwargs={
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "agent_type": "tool_response",
                    "error_type": "parse_error",
                },
            )

        logger.info(
            f"Executing {len(tool_calls)} tools in parallel",
            tools=[t[0] for t in tool_calls]
        )

        # Create tasks for parallel execution
        tasks = []
        for tool_name, tool_input in tool_calls:
            action = ToolInvocation(tool=tool_name, tool_input=tool_input)
            tasks.append(tool_executor.ainvoke(action))

        # Execute all tools in parallel
        start_time = time.time()
        try:
            results = await asyncio.gather(*tasks, return_exceptions=True)
        except Exception as e:
            logger.error(f"Error during parallel tool execution: {e}")
            results = [str(e) for _ in tasks]

        duration = time.time() - start_time
        logger.info(
            f"Parallel tool execution completed",
            duration_ms=round(duration * 1000, 2),
            num_tools=len(tool_calls)
        )

        # Combine results into separate observation blocks for each tool
        combined_results = []
        for i, (tool_name, tool_input) in enumerate(tool_calls):
            result = results[i]
            if isinstance(result, Exception):
                result_text = f"Error executing {tool_name}: {str(result)}"
            else:
                result_text = str(result) if result else "No response from tool"

            # Format each result as a separate observation
            combined_results.append(f"[Tool: {tool_name}]\n{result_text}")

        # Create a combined function message with all results
        combined_content = "\n\n".join(combined_results)

        return LiberalFunctionMessage(
            content=combined_content,
            name="parallel_tools",
            response_metadata={"usage": {"total_latency": duration}},
            additional_kwargs={
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "agent_type": "tool_response",
                "parallel_tools": [t[0] for t in tool_calls],
                "num_tools": len(tool_calls),
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

            # Extract main agent timing from full message history (available here)
            main_agent_timing = None
            for msg in messages:
                if hasattr(msg, 'additional_kwargs') and msg.additional_kwargs:
                    if 'main_agent_timing' in msg.additional_kwargs:
                        main_agent_timing = msg.additional_kwargs['main_agent_timing']
                        logger.info(
                            "Extracted main agent timing from message history",
                            timing=main_agent_timing,
                        )
                        break

            # Add timing to config metadata for subgraph access
            if main_agent_timing and config and "metadata" in config:
                config["metadata"]["main_agent_timing"] = main_agent_timing
                logger.info("Added main agent timing to config metadata")

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
        "data_science_end",
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
