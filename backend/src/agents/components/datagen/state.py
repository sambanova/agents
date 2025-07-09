import operator
import uuid
from dataclasses import dataclass
from typing import Annotated, Sequence, TypedDict

from langchain_core.messages import AIMessage, AnyMessage, BaseMessage, HumanMessage
from pydantic import BaseModel, Field


@dataclass
class Replace:
    """A signal to replace the state value instead of appending."""

    value: str | Sequence[AnyMessage]


def add_messages(
    left: Sequence[AnyMessage], right: Sequence[AnyMessage] | Replace
) -> Sequence[AnyMessage]:
    """
    Custom reducer that adds messages to the state.
    """
    if isinstance(right, Replace):
        return right.value
    return left + right


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


def dynamic_reducer(left: str, right: str | Replace) -> str:
    if isinstance(right, Replace):
        return right.value
    return left + " " + right


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


class QualityReviewDecision(BaseModel):
    """
    Decision about whether the report needs revision.
    """

    passed: bool = Field(
        description="Whether the previous step passed the quality review."
    )
    reason: str = Field(description="The reason for the decision.")


class State(TypedDict):
    """TypedDict for the entire state structure."""

    # The sequence of messages exchanged in the conversation
    internal_messages: Annotated[Sequence[AnyMessage], add_messages]

    # Messages to be sent to the frontend
    messages: Annotated[Sequence[AnyMessage], replace_messages]

    # The complete content of the research hypothesis
    hypothesis: Annotated[str, lambda left, right: right] = ""

    # The complete content of the research process
    process: Annotated[str, lambda left, right: right] = ""

    # next process
    process_decision: Annotated[str, lambda left, right: right] = ""

    # The current state of data visualization planning and execution
    visualization_state: Annotated[str, dynamic_reducer] = ""

    # The current state of the search process, including queries and results
    searcher_state: Annotated[str, dynamic_reducer] = ""

    # The current state of Coder development, including scripts and outputs
    code_state: Annotated[str, dynamic_reducer] = ""

    # The content of the report sections being written
    report_state: Annotated[str, dynamic_reducer] = ""

    # The feedback and comments from the quality review process
    quality_review: Annotated[str, lambda left, right: right] = ""

    # The identifier of the agent who sent the last message
    sender: Annotated[str, lambda left, right: right] = ""

    # The areas of the hypothesis that need to be modified
    modification_areas: Annotated[str, lambda left, right: right] = ""


class NoteState(BaseModel):
    """Pydantic model for parsing agent outputs - no state management annotations needed."""

    internal_messages: list[str] = Field(
        default=[], description="Messages of the current conversation"
    )

    class Config:
        arbitrary_types_allowed = (
            True  # Allow BaseMessage type without explicit validator
        )
