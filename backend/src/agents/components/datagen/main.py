import asyncio
import os

import redis
import structlog
from agents.components.datagen.state import State
from agents.components.datagen.workflow import WorkflowManager
from agents.storage.redis_storage import RedisStorage
from agents.utils.llms import get_fireworks_llm, get_sambanova_llm
from langchain_core.messages import HumanMessage

logger = structlog.get_logger(__name__)


def setup_language_models():
    """Set up the language models needed for the workflow"""
    # Get API keys from environment variables
    sambanova_api_key = os.getenv("SAMBANOVA_KEY")

    # Initialize language models
    llm = get_sambanova_llm(sambanova_api_key, "DeepSeek-V3-0324")
    power_llm = get_sambanova_llm(sambanova_api_key, "DeepSeek-V3-0324")
    json_llm = get_sambanova_llm(sambanova_api_key, "DeepSeek-V3-0324")

    return {"llm": llm, "power_llm": power_llm, "json_llm": json_llm}


async def main_with_persistent_daytona(
    user_input: str,
    user_id: str,
    thread_id: str,
    redis_storage: RedisStorage,
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
    manager = WorkflowManager(language_models, user_id, redis_storage)
    await manager.initialize()

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
    config = {"configurable": {"thread_id": thread_id}, "recursion_limit": 100}

    try:
        # Run workflow with persistent Daytona

        data_sources = [
            "/Users/tamasj/Downloads/customer_satisfaction_purchase_behavior.csv"
        ]
        async for event in manager.run_workflow(initial_state, config):
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

        print(f"Starting datagen workflow with input: {user_input}")
        print("-" * 50)

        # Run the workflow and process events
        async for event in main_with_persistent_daytona(
            user_input,
            user_id="user1",
            thread_id="1",
            redis_storage=RedisStorage(
                redis_client=redis.Redis(host="localhost", port=6379)
            ),
        ):
            print(f"Event: {event['messages'][-1].content}")
            print("-" * 30)

        print("Workflow completed!")

    # Run the async workflow
    asyncio.run(run_workflow())
