from agents.components.datagen.create_agent import create_agent
from agents.components.datagen.tools.persistent_daytona import (
    PersistentDaytonaManager,
    get_daytona_describe_data,
    get_daytona_execute_code,
    get_daytona_list_files,
    get_daytona_pip_install,
)


def create_code_agent(
    code_agent_llm,
    members,
    daytona_manager: PersistentDaytonaManager,
    directory_content: list[str],
):
    """Create the code agent with persistent Daytona support"""

    tools = [
        get_daytona_execute_code(daytona_manager),
        get_daytona_pip_install(daytona_manager),
        get_daytona_list_files(daytona_manager),
        get_daytona_describe_data(daytona_manager),
    ]

    system_prompt = """
    You are an expert Python programmer specializing in data processing and analysis with access to a persistent Daytona sandbox. Your main responsibilities include:

    1. Writing clean, efficient Python code for data manipulation, cleaning, and transformation.
    2. Implementing statistical methods and machine learning algorithms as needed.
    3. Debugging and optimizing existing code for performance improvements.
    4. Adhering to PEP 8 standards and ensuring code readability with meaningful variable and function names.
    5. Any output data must be saved to the sandbox directory. Also print the file name in the output.

    **Available Tools:**
    - daytona_execute_code: Execute Python code in the persistent sandbox
    - daytona_list_files: List files in the sandbox directory
    - daytona_describe_data: Analyze CSV data with encoding detection and detailed structure analysis

    Constraints:
    - Focus solely on data processing tasks; do not generate visualizations or write non-Python code.
    - Provide only valid, executable Python code, including necessary comments for complex logic.
    - Avoid unnecessary complexity; prioritize readability and efficiency.
    - Take advantage of the persistent environment by building on previous work.
    - Use daytona_describe_data to analyze CSV files before processing them.
    """

    return create_agent(
        llm=code_agent_llm,
        tools=tools,
        system_message=system_prompt,
        team_members=members,
        name="code_agent",
        directory_content=directory_content,
    )
