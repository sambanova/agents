import mimetypes
import re
import uuid
from datetime import datetime

import structlog
from agents.components.datagen.manual_agent import ManualAgent
from agents.components.datagen.message_capture_agent import MessageCaptureAgent
from agents.components.datagen.state import NoteState, State
from agents.components.datagen.tools.persistent_daytona import PersistentDaytonaManager
from agents.storage.redis_storage import RedisStorage
from agents.utils.message_interceptor import MessageInterceptor
from langchain.output_parsers import OutputFixingParser, PydanticOutputParser
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langchain_core.runnables import RunnableLambda, RunnableSequence

# Set up logger
logger = structlog.get_logger(__name__)


async def agent_node(
    state: State, agent: ManualAgent | MessageCaptureAgent, name: str, state_key: str
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

        if isinstance(agent, ManualAgent) and agent.llm_response:
            captured_message = agent.llm_response
            captured_message.additional_kwargs["agent_type"] = f"data_science_{name}"
            captured_messages = [captured_message]
        elif isinstance(agent, MessageCaptureAgent):
            interceptor_messages = agent.llm_interceptor.captured_messages
            fixing_interceptor_messages = agent.llm_fixing_interceptor.captured_messages
            captured_messages = interceptor_messages + fixing_interceptor_messages
            for m in captured_messages:
                m.additional_kwargs["agent_type"] = f"data_science_{name}"
        else:
            pass

        # Return a dictionary to be merged into the state
        return {
            "internal_messages": state["internal_messages"] + [output_message],
            "messages": captured_messages,
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
        messages = []
        current_messages = state.get("internal_messages", [])

        head_messages, tail_messages = [], []

        if len(current_messages) > 6:
            head_messages = current_messages[:2]
            tail_messages = current_messages[-2:]
            state = {**state, "internal_messages": current_messages[2:-2]}
            logger.debug("Trimmed messages for processing")

        result = await agent.ainvoke(state)
        if isinstance(agent, ManualAgent) and agent.llm_response:
            captured_message = agent.llm_response
            captured_message.additional_kwargs["agent_type"] = f"data_science_{name}"
            messages.append(captured_message)

        note_agent_fixing_interceptor = MessageInterceptor()
        fixing_model = agent.llm | RunnableLambda(
            note_agent_fixing_interceptor.capture_and_pass
        )
        node_state_parser = PydanticOutputParser(pydantic_object=NoteState)
        fixing_parser = OutputFixingParser.from_llm(
            llm=fixing_model,
            parser=node_state_parser,
        )
        parsed_output: NoteState = await fixing_parser.aparse(result.content)

        for m in note_agent_fixing_interceptor.captured_messages:
            m.additional_kwargs["agent_type"] = "note_agent_fixed"
            messages.append(m)

        internal_messages = (
            parsed_output.internal_messages
            if parsed_output.internal_messages
            else current_messages
        )
        combined_messages = head_messages + internal_messages + tail_messages

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
            "messages": messages,
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


def parse_and_replace_charts(
    content: str, list_of_files: list[str], user_id: str
) -> tuple[str, dict[str, str]]:
    """
    Parses content to find references to chart files and replaces them with a special markdown link.

    The function identifies filenames for common image formats (png, jpg, jpeg, gif, svg)
    within the text. If a found filename is present in the `list_of_files`, it's
    replaced by a markdown link in the format `[{filename}](redis-chart:{file_id}:{user_id})`.
    A unique file ID is generated for each valid file.

    This process handles filenames that are either plain text or enclosed in backticks.

    Args:
        content: The text content to parse.
        list_of_files: A list of available file names to validate against.
        user_id: The user's ID to be included in the replacement link.

    Returns:
        A tuple containing:
        - The modified content string with chart references replaced.
        - A list of unique file names that were found and replaced.
        - A dictionary mapping the replaced file names to their generated unique file IDs.
    """
    filename_regex = re.compile(r"[\w-]+\.(?:png|jpg|jpeg|gif|svg)")
    found_filenames = set(filename_regex.findall(content))

    modified_content = content
    file_id_mapping = {}

    for filename in found_filenames:
        if filename in list_of_files:
            file_id = str(uuid.uuid4())
            file_id_mapping[filename] = file_id

            replacement_text = f"[{filename}](redis-chart:{file_id}:{user_id})"

            # To handle filenames with optional backticks, create a regex for each filename
            # This ensures we replace `chart.png` and chart.png without affecting other text
            escaped_filename = re.escape(filename)
            pattern_to_replace = re.compile(f"`?{escaped_filename}`?")
            modified_content = pattern_to_replace.sub(
                replacement_text, modified_content
            )

    return modified_content, file_id_mapping


def _create_error_state(
    state: State, error_message: AIMessage, name: str, error_type: str
) -> State:
    """
    Create an error state when an exception occurs.
    """
    logger.info(f"Creating error state for {name}: {error_type}")
    error_state: State = {
        "internal_messages": state.get("internal_messages", []) + [error_message],
        "messages": [],
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


async def refiner_node(
    state: State,
    agent: ManualAgent,
    name: str,
    daytona_manager: PersistentDaytonaManager,
    redis_storage: RedisStorage,
    user_id: str,
) -> tuple[State, dict[str, str]]:
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
            success, content = await daytona_manager.read_file(md_file)
            if success:
                materials.append(f"MD file '{md_file}':\n{content}")

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

        list_of_files = await daytona_manager.list_files()

        # Parse and replace chart references in the result content
        if hasattr(result, "content") and result.content:
            parsed_content, file_id_mapping = parse_and_replace_charts(
                result.content, list_of_files, user_id
            )
            result.content = parsed_content
            logger.info(f"Generated file IDs: {file_id_mapping}")
            for file_name, file_id in file_id_mapping.items():
                success, file_content = await daytona_manager.read_file(file_name)
                if not success:
                    logger.error(content)
                    continue
                mime_type = mimetypes.guess_type(file_name)[0]
                generation_timestamp = datetime.now().isoformat()
                await redis_storage.put_file(
                    user_id,
                    file_id,
                    data=file_content,
                    filename=file_name,
                    format=mime_type,
                    upload_timestamp=generation_timestamp,
                    indexed=False,
                    source="data_science_agent",
                )

        # Update original state - result is now an AIMessage
        # Note: this will be mapped as the last state, we don't need to send this through messages
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
