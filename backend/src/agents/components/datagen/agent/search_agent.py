from agents.components.datagen.create_agent import create_agent
from agents.components.datagen.tools.FileEdit import (
    collect_data,
    create_document,
    read_document,
)
from agents.tools.langgraph_tools import TOOL_REGISTRY
from langchain.agents import load_tools
from langchain_community.tools import WikipediaQueryRun
from langchain_community.utilities import WikipediaAPIWrapper


def create_search_agent(llm, members, working_directory):
    """Create the search agent"""
    tools = [
        create_document,
        read_document,
        collect_data,
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
    return create_agent(llm, tools, system_prompt, members, working_directory)
