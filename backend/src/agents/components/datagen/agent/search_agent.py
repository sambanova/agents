from agents.components.datagen.create_agent import create_agent
from agents.components.datagen.tools.persistent_daytona import (
    get_daytona_create_document,
    get_daytona_describe_data,
    get_daytona_read_document,
)
from agents.tools.langgraph_tools import TOOL_REGISTRY


def create_search_agent(llm, members, user_id: str):
    """Create the search agent"""
    tools = [
        get_daytona_create_document(user_id),
        get_daytona_read_document(user_id),
        get_daytona_describe_data(user_id),
        TOOL_REGISTRY["wikipedia"]["factory"](),
        TOOL_REGISTRY["search_tavily"]["factory"](),
        TOOL_REGISTRY["arxiv"]["factory"](),
    ]

    system_prompt = """
    You are a skilled research assistant responsible for gathering and summarizing relevant information. Your main tasks include:

    1. Conducting thorough literature reviews using academic databases and reputable online sources.
    2. Summarizing key findings in a clear, concise manner.
    3. Providing citations for all sources, prioritizing peer-reviewed and academically reputable materials.

    Constraints:
    - Focus exclusively on information retrieval and summarization; do not engage in data analysis or processing.
    - Present information in an organized format, with clear attributions to sources.
    - Evaluate the credibility of sources and prioritize high-quality, reliable information.
    """
    return create_agent(llm, tools, system_prompt, members, "search_agent")
