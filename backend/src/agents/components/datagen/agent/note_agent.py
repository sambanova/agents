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
    You are an expert summarizer for a team of researcher agents. Your task is to distill the provided agent messages into a concise summary that captures the key activities and progress.

**GUIDELINES:**
- **Brevity is key.** Create a short summary of the key events.
- **Focus on meaningful progress.** Identify significant actions, decisions, and outcomes.
- **Capture key artifacts:** Explicitly mention any files that were successfully created or modified.
- **Note completed steps:** List any major tasks or steps that have been finished.
- **Ignore noise:** Filter out verbose logs, tool chatter, and routine system messages.
- **No preamble:** Start your response directly with the summary. Do not add any introductory text like "Here is a summary...".

Agent messages to summarize:
{internal_messages}
"""

    return base_create_note_agent(
        llm=note_agent_llm,
        system_prompt=system_prompt,
    )
