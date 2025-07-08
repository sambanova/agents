import mimetypes
import os
import re
import time
import uuid
from datetime import datetime

import structlog
from agents.components.datagen.manual_agent import ManualAgent
from agents.components.datagen.message_capture_agent import MessageCaptureAgent
from agents.components.datagen.state import NoteState, Replace, State
from agents.components.datagen.tools.persistent_daytona import PersistentDaytonaManager
from agents.storage.redis_storage import RedisStorage
from agents.utils.message_interceptor import MessageInterceptor
from langchain.output_parsers import OutputFixingParser, PydanticOutputParser
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langchain_core.runnables import RunnableLambda
from langgraph.types import interrupt

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
    logger.info(
        f"Processing agent in agent node: {name} to update state key: '{state_key}'"
    )
    try:
        output_message = await agent.ainvoke(state)

        if output_message is None:
            raise ValueError("Agent output is None.")

        if isinstance(agent, ManualAgent) and agent.llm_response:
            captured_message = agent.llm_response
            captured_message.additional_kwargs["agent_type"] = f"data_science_{name}"
            captured_messages = [captured_message]
            logger.debug(f"Captured {len(captured_messages)} messages from ManualAgent")
        elif isinstance(agent, MessageCaptureAgent):
            interceptor_messages = agent.llm_interceptor.captured_messages
            fixing_interceptor_messages = agent.llm_fixing_interceptor.captured_messages
            captured_messages = interceptor_messages + fixing_interceptor_messages
            for m in captured_messages:
                m.additional_kwargs["agent_type"] = f"data_science_{name}"
            logger.debug(
                f"Captured {len(captured_messages)} messages from MessageCaptureAgent"
            )
        else:
            captured_messages = []
            logger.debug(f"No messages captured from agent type: {type(agent)}")

        logger.info(f"Agent {name} processed successfully")
        return {
            "internal_messages": [output_message],
            "messages": captured_messages,
            state_key: output_message.content,
            "sender": name,
        }

    except Exception as e:
        logger.info(
            f"Error occurred while processing agent in agent_node {name}: {str(e)}"
        )
        # Return an error message to be added to the state
        error_message = AIMessage(
            content=f"Error in {name}: {str(e)}",
            name=name,
            id=str(uuid.uuid4()),
            sender=name,
        )
        return {
            "internal_messages": [error_message],
        }


async def human_choice_node(state: State) -> State:
    """
    Handle human input to choose the next step in the process.
    If regenerating hypothesis, prompt for specific areas to modify.
    """
    logger.info("Processing human choice node")
    current_hypothesis = state.get("hypothesis", "No hypothesis yet.")
    prompt = (
        "Please <b>provide feedback</b> on the following plan or <b>type 'approve'.</b>\n\n"
        + current_hypothesis
    )

    feedback = interrupt(prompt)
    logger.debug(f"Received feedback: {feedback}")

    if isinstance(feedback, str) and feedback == True:
        content = "Continue the research process"
        state["process"] = "Continue the research process"
        state["modification_areas"] = ""
        logger.info("Human approved - continuing research process")
    elif isinstance(feedback, str) and feedback.strip():
        modification_areas = feedback
        content = f"Regenerate hypothesis. Areas to modify: {modification_areas}"
        state["hypothesis"] = ""
        state["modification_areas"] = modification_areas
        logger.info("Human provided feedback - hypothesis cleared for regeneration")
        logger.debug(f"Modification areas: {modification_areas}")
    else:
        # Default to continue if feedback is empty or not a string
        content = "Continue the research process"
        state["process"] = "Continue the research process"
        state["modification_areas"] = ""
        logger.info("No feedback provided - continuing research process")

    human_message = HumanMessage(content=content, id=str(uuid.uuid4()))

    logger.info("Human choice node processing completed")
    return {
        "internal_messages": [human_message],
        "sender": "human",
    }


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

            # Find research hypothesis in the messages
            user_continue_message_index = [
                i
                for i, m in enumerate(current_messages)
                if m.content.startswith("Continue the research process")
            ]

            if len(user_continue_message_index) == 1:
                user_input = current_messages[0]
                continue_message = current_messages[user_continue_message_index[0]]
                research_hypothesis = current_messages[
                    user_continue_message_index[0] - 1
                ]
                head_messages = [user_input, research_hypothesis, continue_message]
                remaining_messages = current_messages[
                    user_continue_message_index[0] + 1 : -2
                ]
            # Fallback to the first message if no continue message is found
            else:
                logger.warning(
                    "No continue message found, falling back to first two messages"
                )
                head_messages = current_messages[:2]
                remaining_messages = current_messages[2:-2]

            tail_messages = current_messages[-2:]
            trimmed_state = {
                **state,
                "internal_messages": remaining_messages,
            }
            logger.debug(
                f"Trimmed messages for processing - keeping {len(head_messages)} head and {len(tail_messages)} tail messages"
            )
        else:
            trimmed_state = state

        result = await agent.ainvoke(trimmed_state)
        if isinstance(agent, ManualAgent) and agent.llm_response:
            captured_message = agent.llm_response
            captured_message.additional_kwargs["agent_type"] = f"data_science_{name}"
            messages.append(captured_message)

        logger.debug("Setting up output fixing parser")
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

        logger.debug(f"Parsed output and captured {len(messages)} messages")

        new_messages = [
            AIMessage(content=msg, name=name, id=str(uuid.uuid4()), sender=name)
            for msg in parsed_output.internal_messages
        ]
        updated_internal_messages = new_messages if new_messages else current_messages
        combined_messages = head_messages + updated_internal_messages + tail_messages

        logger.info(f"Note agent {name} processed successfully")
        return {
            "messages": messages,
            "internal_messages": Replace(value=combined_messages),
        }

    except Exception as e:
        logger.error(f"Error in note_agent_node {name}: {e}", exc_info=True)
        return {}


def parse_and_replace_charts(
    content: str, list_of_files: list[str], user_id: str
) -> tuple[str, dict[str, str]]:
    """
    Parses content to find custom chart placeholders and replaces them with
    a nested markdown structure compatible with the frontend.

    This function looks for two types of placeholders:
    - `[chart: filename.png]` for embedded images.
    - `[chart-link: filename.png]` for links to charts.

    It replaces them with `![description]([filename.png](redis-chart:file_id:user_id))`
    for images and `[description]([filename.png](redis-chart:file_id:user_id))` for links,
    where the description is derived from the context around the placeholder.
    """
    logger.debug(f"Parsing chart references for user {user_id}")

    # Regex to find all chart placeholders, capturing the type (link or chart) and the filename
    placeholder_regex = re.compile(r"\[(chart|chart-link):\s*([^\]]+?)\s*\]")

    modified_content = content
    file_id_mapping = {}

    # Create a list of matches to iterate over, as we'll be modifying the string
    matches = list(placeholder_regex.finditer(content))

    for match in matches:
        placeholder_type, filename = match.groups()

        if filename in list_of_files:
            if filename not in file_id_mapping:
                # Generate a unique file ID only once per file
                file_id = str(uuid.uuid4())
                file_id_mapping[filename] = file_id
            else:
                file_id = file_id_mapping[filename]

            # The inner markdown link is always the same
            inner_link = f"[{filename}](redis-chart:{file_id}:{user_id})"

            # Try to find a descriptive text for the outer markdown.
            # Look for a preceding markdown header or text on the same line.
            # This is a simple heuristic.
            start_pos = match.start()
            line_start = content.rfind("\n", 0, start_pos) + 1
            line = content[line_start:start_pos].strip()

            # Simple check if the line is a header or just text
            if line.startswith("#"):
                description = line.lstrip("# ").strip()
            elif line:
                description = line.strip().rstrip(":")
            else:
                description = os.path.splitext(filename)[0].replace("_", " ").title()

            if placeholder_type == "chart":
                # Create a markdown image
                replacement_text = f"![{description}]({inner_link})"
            else:  # chart-link
                # Create a markdown link
                replacement_text = f"[{description}]({inner_link})"

            # Replace the original placeholder with the final nested markdown
            # We must replace the original match string, in case of multiple identical placeholders
            modified_content = modified_content.replace(
                match.group(0), replacement_text, 1
            )

    logger.debug(f"Replaced {len(matches)} chart references")
    return modified_content, file_id_mapping


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
    logger.info(f"Processing refiner node: {name} for user {user_id}")
    try:
        # Get storage path
        storage_path = await daytona_manager.list_files()
        logger.debug(f"Retrieved {len(storage_path)} files from storage")

        # Collect materials
        materials = []
        md_files = [s for s in storage_path if s.endswith("md")]
        png_files = [s for s in storage_path if s.endswith("png")]
        logger.debug(f"Found {len(md_files)} MD files and {len(png_files)} PNG files")

        # Process MD files
        for md_file in md_files:
            success, content = await daytona_manager.read_file(md_file)
            if success:
                materials.append(f"MD file '{md_file}':\n{content}")
            else:
                logger.warning(f"Failed to read MD file: {md_file}")

        # Process PNG files
        materials.extend(f"Available charts: '{png_file}'" for png_file in png_files)

        # Combine materials
        combined_materials = "\n\n".join(materials)
        report_content = f"Report materials:\n{combined_materials}"

        # Create refiner state
        refiner_state = state.copy()
        refiner_state["internal_messages"] = [AIMessage(content=report_content)]

        try:
            # Attempt to invoke agent with full content
            logger.debug("Attempting to invoke agent with full content")
            result = await agent.ainvoke(refiner_state)
        except Exception as token_error:
            # If token limit is exceeded, retry with only MD file names
            logger.warning(
                f"Token limit exceeded, retrying with file names only: {token_error}"
            )
            md_file_names = [f"MD file: '{md_file}'" for md_file in md_files]
            png_file_names = [f"PNG file: '{png_file}'" for png_file in png_files]

            simplified_materials = "\n".join(md_file_names + png_file_names)
            simplified_report_content = (
                f"Report materials (file names only):\n{simplified_materials}"
            )

            refiner_state["internal_messages"] = [
                AIMessage(
                    content=simplified_report_content,
                    id=str(uuid.uuid4()),
                    sender=name,
                )
            ]
            result = await agent.ainvoke(refiner_state)

        list_of_files = await daytona_manager.list_files()

        # Parse and replace chart references in the result content
        if hasattr(result, "content") and result.content:
            parsed_content, file_id_mapping = parse_and_replace_charts(
                result.content, list_of_files, user_id
            )
            result.content = parsed_content
            logger.debug(f"Generated {len(file_id_mapping)} file ID mappings")

            for file_name, file_id in file_id_mapping.items():
                success, file_content = await daytona_manager.read_file(file_name)
                if not success:
                    logger.error(f"Failed to read file for storage: {file_name}")
                    continue
                mime_type = mimetypes.guess_type(file_name)[0]
                await redis_storage.put_file(
                    user_id,
                    file_id,
                    data=file_content,
                    filename=file_name,
                    format=mime_type,
                    upload_timestamp=time.time(),
                    indexed=False,
                    source="data_science_agent",
                )
                logger.debug(f"Stored file {file_name} with ID {file_id}")

        # Update original state - result is now an AIMessage
        # Note: this will be mapped as the last state, we don't need to send this through messages
        state["internal_messages"].append(
            AIMessage(
                content=result.content,
                id=result.id,
                sender=name,
            )
        )
        state["sender"] = name

        logger.info(f"Refiner node {name} processing completed successfully")
        return state
    except Exception as e:
        logger.error(f"Error in refiner node {name}: {str(e)}", exc_info=True)
        state["internal_messages"].append(
            AIMessage(
                content=f"Error: {str(e)}",
                name=name,
                id=str(uuid.uuid4()),
                sender=name,
            )
        )
        return state
