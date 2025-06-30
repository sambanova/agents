import asyncio
import os

import structlog
from agents.components.datagen.state import State
from agents.components.datagen.workflow import WorkflowManager
from agents.utils.llms import get_fireworks_llm, get_sambanova_llm
from langchain_core.messages import HumanMessage

logger = structlog.get_logger(__name__)


def setup_language_models():
    """Set up the language models needed for the workflow"""
    # Get API keys from environment variables
    sambanova_api_key = os.getenv("FIREWORKS_KEY")

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


async def main_with_persistent_daytona(
    user_input: str,
    user_id: str = "default_user",
    working_directory: str = "./data",
    thread_id: str = "1",
    redis_storage=None,
    data_sources=None,
):
    """
    Main method to run the datagen workflow with persistent Daytona client

    Args:
        user_input: User's query or request
        user_id: User identifier for the session
        working_directory: Directory for storing workflow data
        thread_id: Thread identifier for the conversation
        redis_storage: Redis storage instance (optional)
        data_sources: List of file paths to upload to sandbox root folder (optional)

    Example usage:
        # Basic usage
        async for event in main_with_persistent_daytona("Analyze the data"):
            print(event)

        # With data upload
        data_sources = ['/path/to/sales_data.csv', '/path/to/customer_data.csv']
        async for event in main_with_persistent_daytona(
            "Analyze the sales data",
            data_sources=data_sources
        ):
            print(event)
    """

    # Initialize language models
    language_models = setup_language_models()

    # Create workflow manager
    manager = WorkflowManager(language_models, working_directory)

    # Create initial state
    initial_state = {
        "messages": [HumanMessage(content=user_input)],
        "hypothesis": "",
        "process": "",
        "process_decision": None,
        "visualization_state": "",
        "searcher_state": "",
        "code_state": "",
        "report_section": "",
        "quality_review": "",
        "needs_revision": False,
        "sender": "",
    }

    # Configuration for the thread
    config = {"configurable": {"thread_id": thread_id}}

    try:
        # Run workflow with persistent Daytona

        data_sources = [
            "/Users/tamasj/Downloads/customer_satisfaction_purchase_behavior.csv.csv"
        ]
        async for event in manager.run_with_persistent_daytona(
            initial_state, config, user_id, redis_storage, data_sources
        ):
            yield event

    except Exception as e:
        logger.error("Error in datagen workflow", error=str(e), exc_info=True)
        error_state = State(messages=[("assistant", f"Error occurred: {str(e)}")])
        yield error_state


if __name__ == "__main__":

    async def run_workflow():
        """Run the workflow and process events"""
        # Example usage
        user_input = "Analyze the relationship between customer satisfaction and purchase behavior using machine learning techniques"
        working_directory = "./data"

        # Create working directory if it doesn't exist
        os.makedirs(working_directory, exist_ok=True)

        print(f"Starting datagen workflow with input: {user_input}")
        print("-" * 50)

        # Run the workflow and process events
        async for event in main_with_persistent_daytona(
            user_input, working_directory=working_directory
        ):
            print(f"Event: {event}")
            print("-" * 30)

        print("Workflow completed!")

    # Run the async workflow
    asyncio.run(run_workflow())
