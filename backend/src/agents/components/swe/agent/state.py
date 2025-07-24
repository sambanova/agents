from typing import Annotated
from langgraph.graph.message import add_messages
from langchain_core.messages import AnyMessage
from pydantic import BaseModel


class State(BaseModel):
    scratchpad: Annotated[list[AnyMessage], add_messages]
    messages: Annotated[list[AnyMessage], add_messages]