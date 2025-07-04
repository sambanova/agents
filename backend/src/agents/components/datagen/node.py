import json
import os
import re
from pathlib import Path
from typing import Any

import structlog
from agents.components.datagen.manual_agent import ManualAgent
from agents.components.datagen.state import NoteState, State
from agents.components.datagen.tools.persistent_daytona import PersistentDaytonaManager
from langchain.agents import AgentExecutor
from langchain.output_parsers import OutputFixingParser, PydanticOutputParser
from langchain_core.messages import AIMessage, AnyMessage, BaseMessage, HumanMessage
from openai import InternalServerError

# Set up logger
logger = structlog.get_logger(__name__)


async def agent_node(
    state: State, agent: ManualAgent, name: str, state_key: str
) -> dict:
    """
    Invokes the agent and updates the state with the result.

    Args:
        state: The current state of the graph.
        agent: The agent to invoke.
        name: The name of the agent.
        state_key: The key in the state to update with the agent's output.

    Returns:
        A dictionary containing the updated state.
    """
    logger.info(f"Processing agent: {name} to update state key: '{state_key}'")
    try:
        output_message = await agent.ainvoke(state)

        if output_message is None:
            raise ValueError("Agent output is None.")

        # Return a dictionary to be merged into the state
        return {
            "internal_messages": state["internal_messages"] + [output_message],
            state_key: output_message,
            "sender": name,
        }

    except Exception as e:
        logger.error(
            f"Error occurred while processing agent {name}: {str(e)}", exc_info=True
        )
        # Return an error message to be added to the state
        error_message = AIMessage(content=f"Error in {name}: {str(e)}", name=name)
        return {"internal_messages": state["internal_messages"] + [error_message]}


def human_choice_node(state: State) -> State:
    """
    Handle human input to choose the next step in the process.
    If regenerating hypothesis, prompt for specific areas to modify.
    """
    logger.info("Prompting for human choice")
    print("Please choose the next step:")
    print("1. Regenerate hypothesis")
    print("2. Continue the research process")

    while True:
        choice = input("Please enter your choice (1 or 2): ")
        if choice in ["1", "2"]:
            break
        logger.warning(f"Invalid input received: {choice}")
        print("Invalid input, please try again.")

    if choice == "1":
        modification_areas = input(
            "Please specify which parts of the hypothesis you want to modify: "
        )
        content = f"Regenerate hypothesis. Areas to modify: {modification_areas}"
        state["hypothesis"] = ""
        state["modification_areas"] = modification_areas
        logger.info("Hypothesis cleared for regeneration")
        logger.info(f"Areas to modify: {modification_areas}")
    else:
        content = "Continue the research process"
        state["process"] = "Continue the research process"
        logger.info("Continuing research process")

    human_message = HumanMessage(content=content)

    state["internal_messages"].append(human_message)
    state["sender"] = "human"

    logger.info("Human choice processed")
    return state


def create_message(message: dict[str], name: str) -> BaseMessage:
    """
    Create a BaseMessage object based on the message type.
    """
    content = message.get("content", "")
    message_type = message.get("type", "").lower()

    logger.debug(f"Creating message of type {message_type} for {name}")
    return (
        HumanMessage(content=content)
        if message_type == "human"
        else AIMessage(content=content, name=name)
    )


async def note_agent_node(state: State, agent: ManualAgent, name: str) -> State:
    """
    Process the note agent's action and update the entire state.
    """
    logger.info(f"Processing note agent: {name}")
    try:
        current_messages = state.get("internal_messages", [])

        head_messages, tail_messages = [], []

        if len(current_messages) > 6:
            head_messages = current_messages[:2]
            tail_messages = current_messages[-2:]
            state = {**state, "internal_messages": current_messages[2:-2]}
            logger.debug("Trimmed messages for processing")

        result = await agent.ainvoke(state)
        node_state_parser = PydanticOutputParser(pydantic_object=NoteState)
        fixing_parser = OutputFixingParser.from_llm(
            llm=agent.llm,
            parser=node_state_parser,
        )
        parsed_output: NoteState = await fixing_parser.aparse(result.content)
        messages = (
            parsed_output.internal_messages
            if parsed_output.internal_messages
            else current_messages
        )

        combined_messages = head_messages + messages + tail_messages

        updated_state: State = {
            "internal_messages": combined_messages,
            "hypothesis": (
                str(parsed_output.hypothesis)
                if parsed_output.hypothesis
                else state.get("hypothesis", "")
            ),
            "process": (
                str(parsed_output.process)
                if parsed_output.process
                else state.get("process", "")
            ),
            "process_decision": (
                str(parsed_output.process_decision)
                if parsed_output.process_decision
                else state.get("process_decision", "")
            ),
            "visualization_state": (
                str(parsed_output.visualization_state)
                if parsed_output.visualization_state
                else state.get("visualization_state", "")
            ),
            "searcher_state": (
                str(parsed_output.searcher_state)
                if parsed_output.searcher_state
                else state.get("searcher_state", "")
            ),
            "code_state": (
                str(parsed_output.code_state)
                if parsed_output.code_state
                else state.get("code_state", "")
            ),
            "report_section": (
                str(parsed_output.report_section)
                if parsed_output.report_section
                else state.get("report_section", "")
            ),
            "quality_review": (
                str(parsed_output.quality_review)
                if parsed_output.quality_review
                else state.get("quality_review", "")
            ),
            "needs_revision": bool(
                bool(parsed_output.needs_revision)
                if parsed_output.needs_revision
                else state.get("needs_revision", False)
            ),
            "sender": "note_agent",
        }

        logger.info("Updated state successfully")
        return updated_state

    except Exception as e:
        logger.error(f"Unexpected error in note_agent_node: {e}", exc_info=True)
        return _create_error_state(
            state,
            AIMessage(content=f"Unexpected error: {str(e)}", name=name),
            name,
            "Unexpected error",
        )


def _create_error_state(
    state: State, error_message: AIMessage, name: str, error_type: str
) -> State:
    """
    Create an error state when an exception occurs.
    """
    logger.info(f"Creating error state for {name}: {error_type}")
    error_state: State = {
        "internal_messages": state.get("internal_messages", []) + [error_message],
        "hypothesis": str(state.get("hypothesis", "")),
        "process": str(state.get("process", "")),
        "process_decision": str(state.get("process_decision", "")),
        "visualization_state": str(state.get("visualization_state", "")),
        "searcher_state": str(state.get("searcher_state", "")),
        "code_state": str(state.get("code_state", "")),
        "report_section": str(state.get("report_section", "")),
        "quality_review": str(state.get("quality_review", "")),
        "needs_revision": bool(state.get("needs_revision", False)),
        "sender": "note_agent",
    }
    return error_state


def human_review_node(state: State) -> State:
    """
    Display current state to the user and update the state based on user input.
    Includes error handling for robustness.
    """
    try:
        print("\nDo you need additional analysis or modifications?")

        while True:
            user_input = input(
                "Enter 'yes' to continue analysis, or 'no' to end the research: "
            ).lower()
            if user_input in ["yes", "no"]:
                break
            print("Invalid input. Please enter 'yes' or 'no'.")

        if user_input == "yes":
            while True:
                additional_request = input(
                    "Please enter your additional analysis request: "
                ).strip()
                if additional_request:
                    state["internal_messages"].append(
                        HumanMessage(content=additional_request)
                    )
                    state["needs_revision"] = True
                    break
                print("Request cannot be empty. Please try again.")
        else:
            state["needs_revision"] = False

        state["sender"] = "human"
        logger.info("Human review completed successfully.")
        return state

    except KeyboardInterrupt:
        logger.warning("Human review interrupted by user.")
        return None

    except Exception as e:
        logger.error(f"An error occurred during human review: {str(e)}", exc_info=True)
        return None


async def refiner_node(
    state: State,
    agent: ManualAgent,
    name: str,
    daytona_manager: PersistentDaytonaManager,
) -> State:
    """
    Read MD file contents and PNG file names from the specified storage path,
    add them as report materials to a new message,
    then process with the agent and update the original state.
    If token limit is exceeded, use only MD file names instead of full content.
    """
    try:

        # Get storage path
        storage_path = await daytona_manager.list_files()

        # Collect materials
        materials = []
        md_files = [s for s in storage_path if s.endswith("md")]
        png_files = [s for s in storage_path if s.endswith("png")]

        # Process MD files
        for md_file in md_files:
            materials.append(
                f"MD file '{md_file}':\n{await daytona_manager.read_file(md_file)}"
            )

        # Process PNG files
        materials.extend(f"PNG file: '{png_file}'" for png_file in png_files)

        # Combine materials
        combined_materials = "\n\n".join(materials)
        report_content = f"Report materials:\n{combined_materials}"

        # Create refiner state
        refiner_state = state.copy()
        refiner_state["internal_messages"] = [AIMessage(content=report_content)]

        try:
            # Attempt to invoke agent with full content
            result = await agent.ainvoke(refiner_state)
        except Exception as token_error:
            # If token limit is exceeded, retry with only MD file names
            logger.warning("Token limit exceeded. Retrying with MD file names only.")
            md_file_names = [f"MD file: '{md_file}'" for md_file in md_files]
            png_file_names = [f"PNG file: '{png_file}'" for png_file in png_files]

            simplified_materials = "\n".join(md_file_names + png_file_names)
            simplified_report_content = (
                f"Report materials (file names only):\n{simplified_materials}"
            )

            refiner_state["internal_messages"] = [
                AIMessage(content=simplified_report_content)
            ]
            result = await agent.ainvoke(refiner_state)

        # Update original state - result is now an AIMessage
        state["internal_messages"].append(result)
        state["sender"] = name

        logger.info("Refiner node processing completed")
        return state
    except Exception as e:
        logger.error(
            f"Error occurred while processing refiner node: {str(e)}", exc_info=True
        )
        state["internal_messages"].append(
            AIMessage(content=f"Error: {str(e)}", name=name)
        )
        return state


logger.info("Agent processing module initialized")
