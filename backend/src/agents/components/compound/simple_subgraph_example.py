"""
Simple example demonstrating a subgraph with just one node integrated with XML agent.
"""

import asyncio
from datetime import datetime, timezone
from langchain.tools import Tool
from langchain_core.messages import HumanMessage, AIMessage
from agents.components.compound.xml_agent import get_xml_agent_executor
from agents.components.compound.util import extract_api_key
from agents.utils.llms import get_sambanova_llm
from langgraph.graph import END
from langgraph.graph.message import MessageGraph
from langchain_core.runnables import RunnableConfig


def create_simple_calculator_tool():
    """Create a simple calculator tool."""

    def calculator(expression: str) -> str:
        """A simple calculator."""
        try:
            result = eval(expression)
            return f"Result: {result}"
        except Exception as e:
            return f"Error: {str(e)}"

    return Tool(
        name="calculator",
        description="A simple calculator for basic math",
        func=calculator,
    )


def create_simple_greeter_subgraph():
    """Create a simple subgraph with just one node that greets the user."""

    async def greeter_node(messages, *, config: RunnableConfig = None):
        """Single node that creates a friendly greeting using LLM."""
        last_message = messages[-1]
        user_input = last_message.content

        # Get API key from config the same way as XML agent
        api_key = extract_api_key(config)

        llm = get_sambanova_llm(model="DeepSeek-V3-0324", api_key=api_key)
        prompt = f"Create a friendly greeting for: {user_input}"
        result = await llm.ainvoke(prompt)
        result.additional_kwargs["timestamp"] = datetime.now(timezone.utc).isoformat()
        result.additional_kwargs["agent_type"] = "greeter_end"
        return result

    # Create the workflow with just one node
    workflow = MessageGraph()

    # Add the single greeter node
    workflow.add_node("greeter", greeter_node)

    # Set entry point
    workflow.set_entry_point("greeter")

    # Go directly to END after the greeter node
    workflow.add_edge("greeter", END)

    # Compile and return
    return workflow.compile()


def create_simple_analyzer_subgraph():
    """Create another simple subgraph that analyzes text length."""

    def analyzer_node(messages):
        """Single node that analyzes the input text."""
        last_message = messages[-1]
        user_input = last_message.content

        # Simple analysis
        word_count = len(user_input.split())
        char_count = len(user_input)

        analysis_response = f"""📊 Text Analysis:
- Characters: {char_count}
- Words: {word_count}
- Input: "{user_input}" """

        return AIMessage(content=analysis_response)

    # Create the workflow
    workflow = MessageGraph()
    workflow.add_node("analyzer", analyzer_node)
    workflow.set_entry_point("analyzer")
    workflow.add_edge("analyzer", END)

    return workflow.compile()


async def create_and_demonstrate_xml_agent():
    """Actually create the XML agent and demonstrate its workflow structure."""

    print("=== Creating XML Agent with Simple Subgraphs ===\n")

    # Create tools
    tools = [create_simple_calculator_tool()]

    # Create simple subgraphs
    greeter_subgraph = create_simple_greeter_subgraph()
    analyzer_subgraph = create_simple_analyzer_subgraph()

    subgraphs = {"greeter": greeter_subgraph, "analyzer": analyzer_subgraph}

    print("📋 Available Tools:")
    print("- calculator: Basic math operations")
    print("\n📋 Available Subgraphs:")
    print("- greeter: Friendly greeting service")
    print("- analyzer: Text analysis service")
    print("\n" + "=" * 50)

    # Create LLM function (mock for demonstration)
    def mock_llm_function(api_key: str):
        """Mock LLM function for demonstration."""
        return get_sambanova_llm(model="DeepSeek-V3-0324", api_key=api_key)

    # ✅ ACTUALLY CREATE THE XML AGENT!
    print("\n🔧 Creating XML Agent Executor...")
    xml_agent = get_xml_agent_executor(
        tools=tools,
        llm=mock_llm_function,
        system_message="You are a helpful assistant that can use tools and subgraphs.",
        interrupt_before_action=True,  # Will interrupt before ANY action
        subgraphs=subgraphs,
    )

    print("✅ XML Agent created successfully!")

    # Show the agent's internal structure
    print(f"\n📊 Agent Workflow Structure:")
    print(f"- Type: {type(xml_agent)}")
    print(f"- Nodes: {list(xml_agent.nodes.keys())}")

    # Check if subgraph nodes were added
    subgraph_nodes = [
        node for node in xml_agent.nodes.keys() if node.startswith("subgraph_")
    ]
    print(f"- Subgraph nodes: {subgraph_nodes}")

    print(f"\n🔄 Workflow Graph Structure:")
    print("Nodes in the compiled workflow:")
    for node_name in xml_agent.nodes.keys():
        print(f"  - {node_name}")

    print(f"\nEdges in the workflow:")
    # The edges structure might be different in CompiledStateGraph
    if hasattr(xml_agent, "edges"):
        for source, targets in xml_agent.edges.items():
            if isinstance(targets, list):
                for target in targets:
                    print(f"  - {source} → {target}")
            else:
                print(f"  - {source} → {targets}")
    else:
        print("  (Edge structure not directly accessible)")

    # Show interrupt configuration
    interrupt_before = getattr(xml_agent, "interrupt_before", None)
    print(f"\nInterrupt configuration: {interrupt_before}")

    print(f"\n📝 The XML Agent is now ready to:")
    print("1. Route <tool>calculator</tool> calls to 'tool_action' node")
    print("2. Route <subgraph>greeter</subgraph> calls to 'subgraph_greeter' node")
    print("3. Route <subgraph>analyzer</subgraph> calls to 'subgraph_analyzer' node")
    print("4. Interrupt before execution if configured")
    print("5. Share state and configuration across all nodes")

    # Show what would happen with actual usage (without needing API key)
    print(f"\n🎯 Example Usage (would require valid API key):")
    print("```python")
    print("# This would actually work with a real API key:")
    print("result = await xml_agent.ainvoke(")
    print("    {'messages': [HumanMessage(content='What is 5 + 3?')]},")
    print("    config={'configurable': {'api_key': 'your_key_here'}}")
    print(")")
    print("```")

    return xml_agent


async def test_subgraphs_directly():
    """Test the subgraphs directly to show they work."""
    print("\n=== Testing Subgraphs Directly ===")

    # Test greeter subgraph
    greeter = create_simple_greeter_subgraph()
    print("\n🧪 Testing greeter subgraph:")
    test_input = {"messages": [HumanMessage(content="Hello world!")]}
    greeter_result = await greeter.ainvoke(test_input)
    print(f"Input: {test_input['messages'][0].content}")
    print(f"Output: {greeter_result['messages'][-1].content}")

    # Test analyzer subgraph
    analyzer = create_simple_analyzer_subgraph()
    print("\n🧪 Testing analyzer subgraph:")
    test_input2 = {"messages": [HumanMessage(content="This is a test message")]}
    analyzer_result = await analyzer.ainvoke(test_input2)
    print(f"Input: {test_input2['messages'][0].content}")
    print(f"Output: {analyzer_result['messages'][-1].content}")


async def main():
    """Main demonstration function."""

    # Create and show the XML agent
    xml_agent = await create_and_demonstrate_xml_agent()

    # Show success message
    print(f"\n✅ XML Agent Integration Complete!")
    print(f"The agent now has {len(xml_agent.nodes)} nodes including subgraphs.")

    print(f"\n🎉 SUCCESS! The XML agent includes:")
    print(f"   - 1 main agent node")
    print(f"   - 1 tool action node")
    print(
        f"   - {len([n for n in xml_agent.nodes if n.startswith('subgraph_')])} subgraph nodes"
    )
    print(f"   - Built-in start node")

    print(f"\n📋 Ready for:")
    print(f"   - <tool>calculator</tool> → routes to 'tool_action'")
    print(f"   - <subgraph>greeter</subgraph> → routes to 'subgraph_greeter'")
    print(f"   - <subgraph>analyzer</subgraph> → routes to 'subgraph_analyzer'")
    print(f"\n🎯 All with shared state, unified interrupts, and tight integration!")


if __name__ == "__main__":
    asyncio.run(main())
