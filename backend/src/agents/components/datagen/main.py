import os

from agents.components.datagen.workflow import WorkflowManager
from agents.utils.llms import get_fireworks_llm, get_sambanova_llm
from langchain_core.messages import HumanMessage


def setup_language_models():
    """Set up the language models needed for the workflow"""
    # Get API keys from environment variables
    sambanova_api_key = ""

    # Initialize language models
    llm = get_fireworks_llm(
        sambanova_api_key, "accounts/fireworks/models/llama-v3p1-70b-instruct"
    )
    power_llm = get_fireworks_llm(
        sambanova_api_key, "accounts/fireworks/models/llama-v3p1-70b-instruct"
    )
    json_llm = get_fireworks_llm(
        sambanova_api_key, "accounts/fireworks/models/llama-v3p1-70b-instruct"
    )

    return {"llm": llm, "power_llm": power_llm, "json_llm": json_llm}


def main(user_input: str, working_directory: str = "./data", thread_id: str = "1"):
    """
    Main method to run the datagen workflow

    Args:
        user_input (str): The user's input/query
        working_directory (str): Directory for file operations
        thread_id (str): Thread ID for conversation tracking
    """
    try:
        # Set up language models
        print("Setting up language models...")
        language_models = setup_language_models()

        # Create workflow manager
        print("Creating workflow manager...")
        workflow_manager = WorkflowManager(language_models, working_directory)

        # Get the compiled graph
        graph = workflow_manager.get_graph()

        # Run the workflow
        print(f"Starting workflow with input: {user_input}")
        print("-" * 50)

        events = graph.stream(
            {
                "messages": [HumanMessage(content=user_input)],
                "hypothesis": "",
                "process_decision": "",
                "process": "",
                "visualization_state": "",
                "searcher_state": "",
                "code_state": "",
                "report_section": "",
                "quality_review": "",
                "needs_revision": False,
                "sender": "",
            },
            {"configurable": {"thread_id": thread_id}, "recursion_limit": 3000},
            stream_mode="values",
            debug=False,
        )

        # Process and display events
        for event in events:
            print(f"Event: {event}")
            print("-" * 30)

    except Exception as e:
        print(f"Error running workflow: {e}")
        raise


if __name__ == "__main__":
    # Example usage
    user_input = "Analyze the relationship between customer satisfaction and purchase behavior using machine learning techniques"
    working_directory = "./data"

    # Create working directory if it doesn't exist
    os.makedirs(working_directory, exist_ok=True)

    # Run the workflow
    main(user_input, working_directory)
