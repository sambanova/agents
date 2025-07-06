import os
from typing import List

import structlog

# Import the manual agent
from agents.components.datagen.manual_agent import ManualAgent
from agents.components.datagen.message_capture_agent import MessageCaptureAgent
from agents.components.datagen.state import NoteState, SupervisorDecision
from langchain.agents import AgentExecutor
from langchain.output_parsers import OutputFixingParser, PydanticOutputParser
from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain.tools import tool
from langchain_core.language_models.base import LanguageModelLike
from langchain_core.messages import AIMessage
from langchain_core.tools import BaseTool

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


def _format_tools(tools: List[BaseTool]) -> str:
    """Format tools for inclusion in the prompt."""
    tool_strings = []
    for tool in tools:
        args_schema = "\n".join(
            f"  - {name} ({info.get('type')}{'*' if name in tool.args else ''}): {info.get('description')}"
            for name, info in tool.args.items()
        )
        tool_strings.append(
            f"{tool.name}: {tool.description}\nParameters:\n{args_schema}"
        )
    return "\n\n".join(tool_strings)


def create_agent(
    llm: LanguageModelLike,
    tools: list,
    system_message: str,
    team_members: list[str],
    directory_content: list[str],
    name: str,
) -> ManualAgent:
    """
    Create a manual agent with the given language model, tools, system message, and team members.
    """
    logger.info("Creating manual agent")

    team_members_str = ", ".join(team_members)
    tool_descriptions = _format_tools(tools)

    # This is a static prompt that is fully constructed once.
    final_system_prompt = f"""You are a specialized AI assistant in a data analysis team.
Your role is to complete specific tasks in the research process.
Your specific role is: {system_message}

Work autonomously according to your specialty, using the tools available to you. Do not ask for clarification.
Your other team members (and other teams) will collaborate with you based on their specialties. You are one of the following team members: {team_members_str}.

The initial contents of your working directory are:
{','.join(directory_content)}
Use the daytona_list_files tool to check for updates in the directory contents when needed.

TOOL USAGE INSTRUCTIONS:
You have access to the following tools:
{tool_descriptions}

To use a tool, you MUST respond with a single XML block in the following format:
<tool>tool_name</tool>
<tool_input>
<parameter_name1>value1</parameter_name1>
<parameter_name2>value2</parameter_name2>
</tool_input>

For example, to use daytona_create_document:
<tool>daytona_create_document</tool>
<tool_input>
<points>["Point 1", "Point 2", "Point 3"]</points>
<filename>my_document.md</filename>
</tool_input>

Or for daytona_edit_document:
<tool>daytona_edit_document</tool>
<tool_input>
<filename>document.md</filename>
<inserts>dict([(1, "New first line"), (3, "New third line")])</inserts>
</tool_input>

You will then get back the results in an <observation> tag.
If you do not need to use a tool, respond normally without any XML tags.
"""

    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", final_system_prompt),
            MessagesPlaceholder(variable_name="internal_messages"),
            # The agent's state is now passed in a single, structured human message
            # for clarity and to avoid confusing the LLM.
            (
                "human",
                """
CURRENT STATE:
---
Hypothesis: {hypothesis}
Process: {process}
Process Decision: {process_decision}
Visualization State: {visualization_state}
Searcher State: {searcher_state}
Code State: {code_state}
Report Section: {report_section}
Quality Review: {quality_review}
Needs Revision: {needs_revision}
---
Based on your role and the current state, please proceed with your task.
""",
            ),
        ]
    )

    logger.info("Manual agent created successfully")
    return ManualAgent(llm=llm, tools=tools, prompt=prompt, name=name)


def create_simple_agent(
    llm: LanguageModelLike,
    system_message: str,
) -> ManualAgent:
    """
    Create a manual agent with the given language model, tools, system message, and team members.
    """
    logger.info("Creating refiner agent")

    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", system_message),
            MessagesPlaceholder(variable_name="internal_messages"),
        ]
    )

    logger.info("Manual agent created successfully")
    return prompt | llm


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
            MessagesPlaceholder(variable_name="internal_messages"),
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

    def wrap_supervisor_output(decision):
        # Convert SupervisorDecision to a simple AIMessage with structured content
        decision_content = f"Decision: {decision.next}, Task: {decision.task}"
        return AIMessage(content=decision_content)

    return MessageCaptureAgent(
        llm=llm,
        prompt=prompt,
        parser=supervisor_parser,
        output_mapper=wrap_supervisor_output,
    )


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

    # Format tools for the note agent
    tool_descriptions = _format_tools(tools)

    # Enhanced system prompt for JSON output with tool capabilities
    # Escape curly braces in output_format to prevent f-string conflicts
    escaped_output_format = output_format.replace("{", "{{").replace("}", "}}")

    enhanced_system_prompt = f"""{system_prompt}

You are a meticulous research process note-taker with access to tools for reading documents and gathering information.

IMPORTANT: You must format your response as a JSON object with the following structure:
{escaped_output_format}

TOOL USAGE INSTRUCTIONS:
You have access to the following tools:
{tool_descriptions}

To use a tool, you MUST respond with a single XML block in the following format:
<tool>tool_name</tool>
<tool_input>
<parameter_name1>value1</parameter_name1>
<parameter_name2>value2</parameter_name2>
</tool_input>

For example, to use daytona_create_document:
<tool>daytona_create_document</tool>
<tool_input>
<points>["Point 1", "Point 2", "Point 3"]</points>
<filename>my_document.md</filename>
</tool_input>

You will then get back the results in an <observation> tag.
If you do not need to use a tool, respond normally without any XML tags.

RESPONSE FORMAT:
Always end your response with a valid JSON object that matches the required structure above. Do not include any text after the JSON object.
"""

    # Simple prompt structure for manual agent
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", enhanced_system_prompt),
            MessagesPlaceholder(variable_name="internal_messages"),
            # Note: No state variables needed since note agent processes the full conversation
        ]
    )

    logger.info("Manual note agent created successfully")
    return ManualAgent(llm=llm, tools=tools, prompt=prompt, name="note_agent")
