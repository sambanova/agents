import os
from typing import List, Literal, Optional

import structlog

# Import the manual agent
from agents.components.datagen.manual_agent import ManualAgent
from langchain.agents import AgentExecutor
from langchain.output_parsers import OutputFixingParser, PydanticOutputParser
from langchain.output_parsers.openai_functions import JsonOutputFunctionsParser
from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain.tools import tool
from langchain_core.language_models.base import LanguageModelLike
from pydantic import BaseModel, Field

logger = structlog.get_logger(__name__)


@tool
def list_directory_contents(directory: str = "./data_storage/") -> str:
    """
    List the contents of the specified directory.

    Args:
        directory (str): The path to the directory to list. Defaults to the data storage directory.

    Returns:
        str: A string representation of the directory contents.
    """
    try:
        logger.info(f"Listing contents of directory: {directory}")
        contents = os.listdir(directory)
        logger.debug(f"Directory contents: {contents}")
        return f"Directory contents :\n" + "\n".join(contents)
    except Exception as e:
        logger.error(f"Error listing directory contents: {str(e)}")
        return f"Error listing directory contents: {str(e)}"


def create_agent(
    llm: LanguageModelLike,
    tools: list[tool],
    system_message: str,
    team_members: list[str],
    working_directory: str = "./data_storage/",
) -> ManualAgent:
    """
    Create a manual agent with the given language model, tools, system message, and team members.

    Parameters:
        llm (LanguageModelLike): The language model to use for the agent.
        tools (list[tool]): A list of tools the agent can use.
        system_message (str): A message defining the agent's role and tasks.
        team_members (list[str]): A list of team member roles for collaboration.
        working_directory (str): The directory where the agent's data will be stored.

    Returns:
        ManualAgent: A manual agent that handles tool execution without function calling.
    """

    logger.info("Creating manual agent")

    # Ensure the ListDirectoryContents tool is available
    if list_directory_contents not in tools:
        tools.append(list_directory_contents)

    # Prepare the tool names and team members for the system prompt
    tool_names = ", ".join([tool.name for tool in tools])
    team_members_str = ", ".join(team_members)

    # List the initial contents of the working directory
    initial_directory_contents = list_directory_contents(working_directory)

    # Create the system prompt for the agent
    system_prompt = (
        "You are a specialized AI assistant in a data analysis team. "
        "Your role is to complete specific tasks in the research process. "
        "Use the provided tools to make progress on your task. "
        "If you can't fully complete a task, explain what you've done and what's needed next. "
        "Always aim for accurate and clear outputs. "
        f"You have access to the following tools: {tool_names}. "
        f"Your specific role: {system_message}\n"
        "Work autonomously according to your specialty, using the tools available to you. "
        "Do not ask for clarification. "
        "Your other team members (and other teams) will collaborate with you based on their specialties. "
        f"You are chosen for a reason! You are one of the following team members: {team_members_str}.\n"
        f"The initial contents of your working directory are:\n{initial_directory_contents}\n"
        "Use the ListDirectoryContents tool to check for updates in the directory contents when needed."
    )

    # Define the prompt structure with placeholders for dynamic content
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", system_prompt),
            MessagesPlaceholder(variable_name="messages"),
            ("ai", "hypothesis: {hypothesis}"),
            ("ai", "process: {process}"),
            ("ai", "process_decision: {process_decision}"),
            ("ai", "visualization_state: {visualization_state}"),
            ("ai", "searcher_state: {searcher_state}"),
            ("ai", "code_state: {code_state}"),
            ("ai", "report_section: {report_section}"),
            ("ai", "quality_review: {quality_review}"),
            ("ai", "needs_revision: {needs_revision}"),
        ]
    )

    logger.info("Manual agent created successfully")

    # Return a manual agent that handles tool execution
    return ManualAgent(llm=llm, tools=tools, prompt=prompt)


class SupervisorDecision(BaseModel):
    """
    Decision about which agent should act next and what task they should perform.
    """

    next: str = Field(
        description="The name of the agent that should act next, or 'FINISH' if the task is complete. Must be one of the provided options."
    )
    task: str = Field(
        description="A concise description of the task the selected agent should perform."
    )


def create_supervisor(
    llm: LanguageModelLike, system_prompt: str, members: list[str]
) -> AgentExecutor:
    # Log the start of supervisor creation
    logger.info("Creating supervisor")

    # Define options for routing, including FINISH and team members
    options = ["FINISH"] + members

    supervisor_parser = PydanticOutputParser(pydantic_object=SupervisorDecision)

    format_instructions = supervisor_parser.get_format_instructions()

    # Create the prompt template
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", system_prompt),
            MessagesPlaceholder(variable_name="messages"),
            (
                "system",
                "Given the conversation above, who should act next? "
                "Or should we FINISH? Select one of: {options}. "
                "Additionally, specify the task that the selected role should perform. "
                "Your response MUST be a JSON object conforming to the following schema:\n"
                "```json\n"  # Emphasize JSON block for LLM
                "{format_instructions}\n"
                "```\n"
                "Do NOT include any other text or explanation, only the JSON object.",
            ),
        ]
    ).partial(
        options=str(options),  # Pass options as a string for the prompt
        team_members=", ".join(
            members
        ),  # If system_prompt uses team_members, keep this
        format_instructions=format_instructions,  # Inject the Pydantic schema instructions
    )

    # Log successful creation of supervisor
    logger.info("Supervisor created successfully")

    return (
        prompt
        | llm
        | OutputFixingParser.from_llm(
            llm=llm,
            parser=supervisor_parser,
        )
    )


from agents.components.datagen.state import NoteState
from langchain.output_parsers import PydanticOutputParser


def create_note_agent(
    llm: LanguageModelLike,
    tools: list,
    system_prompt: str,
) -> ManualAgent:
    """
    Create a Note Agent using manual approach that outputs structured JSON.
    """
    logger.info("Creating manual note agent")

    # Get the JSON output format instructions
    parser = PydanticOutputParser(pydantic_object=NoteState)
    output_format = parser.get_format_instructions()

    # Enhanced system prompt for JSON output with tool capabilities
    enhanced_system_prompt = f"""{system_prompt}

You are a meticulous research process note-taker with access to tools for reading documents and gathering information.

IMPORTANT: You must format your response as a JSON object with the following structure:
{output_format}

TOOL USAGE:
You can use tools when you need to read documents or gather information. Use XML tags for tool calls:
<tool>tool_name</tool><tool_input>your input here</tool_input>

After using tools, you'll receive results in <observation></observation> tags. Then provide your final JSON response.

RESPONSE FORMAT:
Always end your response with a valid JSON object that matches the required structure above. Do not include any text after the JSON object.
"""

    # Simple prompt structure for manual agent
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", enhanced_system_prompt),
            MessagesPlaceholder(variable_name="messages"),
            # Note: No state variables needed since note agent processes the full conversation
        ]
    )

    logger.info("Manual note agent created successfully")
    return ManualAgent(llm=llm, tools=tools, prompt=prompt)


logger.info("Agent creation module initialized")
