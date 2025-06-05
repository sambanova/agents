from datetime import datetime, timezone
from agents.components.compound.util import extract_api_key
from langchain.tools import BaseTool
from langchain.tools.render import render_text_description
from langchain_core.language_models.base import LanguageModelLike
from langchain_core.messages import (
    AIMessage,
    FunctionMessage,
    HumanMessage,
    SystemMessage,
)
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END
from langgraph.graph.message import MessageGraph
from agents.components.compound.prompts import xml_template
from agents.components.compound.message_types import LiberalFunctionMessage
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.redis import RedisSaver


from langgraph.checkpoint.memory import InMemorySaver

memory = InMemorySaver()


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


def get_xml_agent_executor(
    tools: list[BaseTool],
    llm: LanguageModelLike,
    system_message: str,
    subgraphs: dict = None,
):
    """
    Get XML agent executor that can call either tools or subgraphs with tight integration.

    Args:
        tools: List of tools available to the agent
        llm: Language model to use
        system_message: System message for the agent
        interrupt_before_action: Whether to interrupt before action execution
        subgraphs: Dictionary of subgraphs {name: compiled_graph}
    """
    subgraphs = subgraphs or {}

    # Create subgraph section for the template
    if subgraphs:
        subgraph_names = ", ".join(subgraphs.keys())
        subgraph_section = f"""
You also have access to the following subgraphs: {subgraph_names}

In order to use a subgraph, you can use <subgraph></subgraph> and <subgraph_input></subgraph_input> tags. You will then get back a response in the form <observation></observation>
For example, if you have a subgraph called 'research_agent' that could conduct research, in order to research a topic you would respond:

<subgraph>research_agent</subgraph><subgraph_input>Tell me about artificial intelligence</subgraph_input>
<observation>Artificial intelligence (AI) is a field of computer science...</observation>"""
    else:
        subgraph_section = ""

    formatted_system_message = xml_template.format(
        system_message=system_message,
        tools=render_text_description(tools),
        tool_names=", ".join([t.name for t in tools]),
        subgraph_section=subgraph_section,
    )

    async def _get_messages(messages):
        return [
            SystemMessage(content=formatted_system_message)
        ] + await construct_chat_history(messages)

    tool_executor = ToolExecutor(tools)

    # Create agent node that extracts api_key from config
    async def agent_node(messages, *, config: RunnableConfig = None):
        api_key = extract_api_key(config)

        # Call your LLM partial with api_key
        initialised_llm = llm(api_key=api_key)

        llm_with_stop = initialised_llm.bind(
            stop=["</tool_input>", "</subgraph_input>", "<observation>"]
        )

        # Process messages
        processed_messages = await _get_messages(messages)
        result: AIMessage = await llm_with_stop.ainvoke(processed_messages, config)
        result.additional_kwargs["timestamp"] = datetime.now(timezone.utc).isoformat()

        return result

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

        if "</tool>" in content:
            additional_kwargs["agent_type"] = "react_tool"
            # Update the message with action metadata
            last_message.additional_kwargs = additional_kwargs
            return "tool_action"
        elif "</subgraph>" in content:
            additional_kwargs["agent_type"] = "react_subgraph"
            # Update the message with action metadata
            last_message.additional_kwargs = additional_kwargs
            # Extract subgraph name to determine which subgraph node to route to
            subgraph_name = content.split("<subgraph>")[1].split("</subgraph>")[0]
            return f"subgraph_{subgraph_name}"
        else:
            additional_kwargs["agent_type"] = "react_end"
            # Update the message with action metadata
            last_message.additional_kwargs = additional_kwargs
            return "end"

    # Define the function to execute tools
    async def call_tool(messages):
        last_message = messages[-1]
        # Parse tool call
        tool, tool_input = last_message.content.split("</tool>")
        _tool = tool.split("<tool>")[1]
        if "<tool_input>" not in tool_input:
            _tool_input = ""
        else:
            _tool_input = tool_input.split("<tool_input>")[1]
            if "</tool_input>" in _tool_input:
                _tool_input = _tool_input.split("</tool_input>")[0]
        action = ToolInvocation(
            tool=_tool,
            tool_input=_tool_input,
        )
        # Execute tool
        response = await tool_executor.ainvoke(action)
        # Create function message
        function_message = LiberalFunctionMessage(
            content=response,
            name=action.tool,
            additional_kwargs={
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "agent_type": "tool_response",
            },
        )
        return function_message

    # Create subgraph entry nodes
    def create_subgraph_entry_node(subgraph_name: str, subgraph):
        async def subgraph_entry_node(messages, *, config: RunnableConfig = None):
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

            # Prepare input for subgraph - MessageGraph expects messages directly
            subgraph_messages = [HumanMessage(content=subgraph_input)]

            # Execute subgraph with the same config (for proper state management)
            # For MessageGraph, pass messages directly, not wrapped in a dict
            result = await subgraph.ainvoke(subgraph_messages, config)

            return result[-1]

        return subgraph_entry_node

    # Build the workflow
    workflow = MessageGraph()

    # Add main agent node
    workflow.add_node("agent", agent_node)

    # Add tool action node
    workflow.add_node("tool_action", call_tool)

    # Add subgraph nodes dynamically
    subgraph_routing = {}
    for subgraph_name, subgraph in subgraphs.items():
        node_name = f"subgraph_{subgraph_name}"
        workflow.add_node(
            node_name, create_subgraph_entry_node(subgraph_name, subgraph)
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
        workflow.add_edge(f"subgraph_{subgraph_name}", END)

    return workflow.compile(
        checkpointer=memory,
    )


def _collapse_messages(messages):

    # Edge case for financial analysis subgraphs (this one does not return a message after the observation)
    if (
        len(messages) == 2
        and messages[-1].additional_kwargs.get("agent_type") == "financial_analysis_end"
    ):
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


async def construct_chat_history(messages):
    collapsed_messages = []
    temp_messages = []
    for message in messages:
        if isinstance(message, HumanMessage):
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
