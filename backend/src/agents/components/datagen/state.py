import operator
from typing import Annotated, Sequence, TypedDict

from langchain_core.messages import AIMessage, AnyMessage, BaseMessage, HumanMessage
from pydantic import BaseModel, Field


def add_messages_deduplicated(
    left: Sequence[AnyMessage], right: Sequence[AnyMessage]
) -> Sequence[AnyMessage]:
    """
    Custom reducer that deduplicates messages based on their ID.
    Similar to the deduplication logic in stream.py.
    """
    # Convert to lists if needed
    if not isinstance(left, list):
        left = list(left) if left else []
    if not isinstance(right, list):
        right = list(right) if right else []

    # Track existing message IDs
    existing_messages = {}
    result = []

    # Process existing messages first
    for msg in left:
        if isinstance(msg, dict):
            msg_id = msg.get("id")
        else:
            msg_id = getattr(msg, "id", None)

        if msg_id:
            existing_messages[msg_id] = msg
        result.append(msg)

    # Process new messages and deduplicate
    for msg in right:
        if isinstance(msg, dict):
            msg_id = msg.get("id")
        else:
            msg_id = getattr(msg, "id", None)

        # Skip duplicates
        if msg_id and msg_id in existing_messages and msg == existing_messages[msg_id]:
            continue

        # Add new or updated message
        if msg_id:
            existing_messages[msg_id] = msg
        result.append(msg)

    return result


def replace_messages(
    left: Sequence[AnyMessage], right: Sequence[AnyMessage]
) -> Sequence[AnyMessage]:
    """
    Custom reducer that replaces messages entirely with the new ones.
    Used for frontend messages that should be replaced per agent execution.
    """
    # If right is empty, keep left to avoid clearing messages unintentionally
    if not right:
        return left if left else []

    # Convert to list if needed
    if not isinstance(right, list):
        right = list(right)

    return right


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


class State(TypedDict):
    """TypedDict for the entire state structure."""

    # The sequence of messages exchanged in the conversation
    internal_messages: Annotated[Sequence[AnyMessage], add_messages_deduplicated]

    # Messages to be sent to the frontend
    messages: Annotated[Sequence[AnyMessage], add_messages_deduplicated]

    # The complete content of the research hypothesis
    hypothesis: Annotated[str, lambda left, right: right] = ""

    # The complete content of the research process
    process: Annotated[str, lambda left, right: right] = ""

    # next process
    process_decision: Annotated[str, lambda left, right: right] = ""

    # The current state of data visualization planning and execution
    visualization_state: Annotated[str, lambda left, right: right] = ""

    # The current state of the search process, including queries and results
    searcher_state: Annotated[str, lambda left, right: right] = ""

    # The current state of Coder development, including scripts and outputs
    code_state: Annotated[str, lambda left, right: right] = ""

    # The content of the report sections being written
    report_section: Annotated[str, lambda left, right: right] = ""

    # The feedback and comments from the quality review process
    quality_review: Annotated[str, lambda left, right: right] = ""

    # A boolean flag indicating if the current output requires revision
    needs_revision: Annotated[bool, lambda left, right: right] = False

    # The identifier of the agent who sent the last message
    sender: Annotated[str, lambda left, right: right] = ""

    # The areas of the hypothesis that need to be modified
    modification_areas: Annotated[str, lambda left, right: right] = ""


class NoteState(BaseModel):
    """Pydantic model for parsing agent outputs - no state management annotations needed."""

    messages_summary: str = Field(
        default="", description="Summary of the messages exchanged"
    )

    hypothesis: str = Field(default="", description="Current research hypothesis")
    process: str = Field(default="", description="Current research process")
    process_decision: str = Field(
        default="", description="Decision about the next process step"
    )
    visualization_state: str = Field(
        default="", description="Current state of data visualization"
    )
    searcher_state: str = Field(
        default="", description="Current state of the search process"
    )
    code_state: str = Field(default="", description="Current state of code development")
    report_section: str = Field(
        default="", description="Content of the report sections"
    )
    quality_review: str = Field(default="", description="Feedback from quality review")
    needs_revision: bool = Field(
        default=False, description="Flag indicating if revision is needed"
    )

    modification_areas: str = Field(
        default="", description="The areas of the hypothesis that need to be modified"
    )

    class Config:
        arbitrary_types_allowed = (
            True  # Allow BaseMessage type without explicit validator
        )
