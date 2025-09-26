from enum import Enum
from typing import Any, ClassVar

from langchain_core.load.serializable import Serializable
from langchain_core.messages import (
    AIMessage,
    FunctionMessage,
    MessageLikeRepresentation,
    ToolMessage,
    _message_from_dict,
)
from langgraph.graph.message import Messages, add_messages
from pydantic import Field


class LLMType(str, Enum):
    SN_LLAMA_3_3_70B = "Llama 3.3 70B"
    SN_LLAMA_MAVERICK = "Llama 4 Maverick"
    SN_DEEPSEEK_V3 = "DeepSeek V3"
    SN_DEEPSEEK_R1_DISTILL_LLAMA = "DeepSeek R1 Distill Llama"
    SN_DEEPSEEK_R1 = "DeepSeek R1"
    SN_QWEN3_3_72B = "Qwen3 32B"
    SN_GPT_OSS = "GPT oss 120b"
    FIREWORKS_LLAMA_3_3_70B = "Fireworks Llama 3.3 70B"
    FIREWORKS_GPT_OSS = "Fireworks GPT oss 120b"
    GROQ_GPT_OSS = "Groq GPT oss 120b" 


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
        return ["agents", "components", "compound", "data_types"]

    content: Any = Field(default="")


class LiberalAIMessage(AIMessage):

    @classmethod
    def is_lc_serializable(cls) -> bool:
        return True

    @classmethod
    def get_lc_namespace(cls) -> list[str]:
        """Return the actual namespace where this class can be imported from."""
        return ["agents", "components", "compound", "data_types"]

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
