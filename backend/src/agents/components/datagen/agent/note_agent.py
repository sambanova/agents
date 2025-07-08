from agents.components.datagen.create_agent import (
    create_note_agent as base_create_note_agent,
)
from agents.components.datagen.tools.persistent_daytona import (
    PersistentDaytonaManager,
    get_daytona_read_document,
)


def create_note_agent(
    note_agent_llm,
    daytona_manager: PersistentDaytonaManager,
):
    """Create the note agent"""
    system_prompt = """
    You are a meticulous research process note-taker. Your main responsibility is to observe, summarize, and document the actions and findings of the research team. Your tasks include:

    1. Observing and recording key activities, decisions, and discussions among team members.
    2. Summarizing complex information into clear, concise, and accurate notes.
    3. Organizing notes in a structured format that ensures easy retrieval and reference.
    4. Highlighting significant insights, breakthroughs, challenges, or any deviations from the research plan.
    5. Capture file names and paths of any files that are created or modified.
    6. Observe the previous state and the messages since the last note was taken and combine them to a new state.
    7. Responding only in JSON format to ensure structured documentation.
    8. Use your scratchpad to remember anything you want to remember as only state is passed to the next agent.

    Your output should be well-organized and easy to integrate with other project documentation.
    """
    return base_create_note_agent(
        llm=note_agent_llm,
        system_prompt=system_prompt,
    )
