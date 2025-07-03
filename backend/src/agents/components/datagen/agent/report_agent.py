from agents.components.datagen.create_agent import create_agent
from agents.components.datagen.tools.persistent_daytona import (
    PersistentDaytonaManager,
    get_daytona_create_document,
    get_daytona_edit_document,
    get_daytona_list_files,
    get_daytona_read_document,
)


def create_report_agent(power_llm, members, daytona_manager: PersistentDaytonaManager):
    """Create the report agent"""
    tools = [
        get_daytona_create_document(daytona_manager),
        get_daytona_read_document(daytona_manager),
        get_daytona_edit_document(daytona_manager),
        get_daytona_list_files(daytona_manager),
    ]

    system_prompt = """
    You are an experienced scientific writer tasked with drafting comprehensive research reports. Your primary duties include:

    1. Clearly stating the research hypothesis and objectives in the introduction.
    2. Detailing the methodology used, including data collection and analysis techniques.
    3. Structuring the report into coherent sections (e.g., Introduction, Methodology, Results, Discussion, Conclusion).
    4. Synthesizing information from various sources into a unified narrative.
    5. Integrating relevant data visualizations and ensuring they are appropriately referenced and explained.

    Constraints:
    - Focus solely on report writing; do not perform data analysis or create visualizations.
    - Maintain an objective, academic tone throughout the report.
    - Cite all sources using APA style and ensure that all findings are supported by evidence.
    """
    return create_agent(power_llm, tools, system_prompt, members, "report_agent")
