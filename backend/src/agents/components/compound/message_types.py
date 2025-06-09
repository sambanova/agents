from typing import Any, ClassVar

from langchain_core.messages import (
    FunctionMessage,
    MessageLikeRepresentation,
    ToolMessage,
    _message_from_dict,
    AIMessage,
)
from langgraph.graph.message import Messages, add_messages
from pydantic import Field
from langchain_core.load.serializable import Serializable


class LiberalToolMessage(ToolMessage):
    content: Any = Field(default="")


class LiberalFunctionMessage(FunctionMessage, Serializable):
    """A liberal function message that allows any content type and uses custom namespace."""

    @classmethod
    def is_lc_serializable(cls) -> bool:
        return True

    @classmethod
    def get_lc_namespace(cls) -> list[str]:
        """Return the actual namespace where this class can be imported from."""
        return ["agents", "components", "compound", "message_types"]

    content: Any = Field(default="")


class LiberalAIMessage(AIMessage):

    @classmethod
    def is_lc_serializable(cls) -> bool:
        return True

    @classmethod
    def get_lc_namespace(cls) -> list[str]:
        """Return the actual namespace where this class can be imported from."""
        return ["agents", "components", "compound", "message_types"]

    content: Any = Field(default="")


def _convert_pydantic_dict_to_message(
    data: MessageLikeRepresentation,
) -> MessageLikeRepresentation:
    """Convert a dictionary to a message object if it matches message format."""
    if (
        isinstance(data, dict)
        and "content" in data
        and isinstance(data.get("type"), str)
    ):
        _type = data.pop("type")
        return _message_from_dict({"data": data, "type": _type})
    return data


def add_messages_liberal(left: Messages, right: Messages):
    # coerce to list
    if not isinstance(left, list):
        left = [left]
    if not isinstance(right, list):
        right = [right]
    return add_messages(
        [_convert_pydantic_dict_to_message(m) for m in left],
        [_convert_pydantic_dict_to_message(m) for m in right],
    )
