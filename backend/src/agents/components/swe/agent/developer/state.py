from typing import Annotated, List, Optional, Literal

from langgraph.graph.message import Messages

from agents.components.swe.agent.common.entities import ImplementationPlan
from pydantic import BaseModel, Field
from langchain_core.messages import AnyMessage
from langgraph.graph import add_messages

class DiffTask(BaseModel):
    original_code_snippet: str = Field(description="The exact code snippet that is being replaced copy to here only the code snippet that going to be change from all of the content")
    task_description: str = Field(description="How the code snippet should be changed give a full and detailed instruction about the how to edit the code in the most concrete way that if developer sees that he can do it without any problem or additional information")


class Diffs(BaseModel):
    diffs: List[DiffTask] = Field(description="Instructions on how to change the file content")


def add_messages_with_clear(
            left: Messages,
            right: Messages
    ) -> Messages:
    if right is None or not right:
        return []
    return add_messages(left, right)

class SoftwareDeveloperState(BaseModel):
    # messages: Annotated[list[AnyMessage], add_messages]
    implementation_plan: Optional[ImplementationPlan] = Field(None, description="The implementation plan to be executed")
    current_task_idx: Optional[int] = Field(0, description="The current task index in the implementation plan")
    current_atomic_task_idx: Optional[int] = Field(0, description="The current atomic task to be implemented")
    diffs: Optional[Diffs] = Field(None, description="The diffs to be applied to the codebase")
    atomic_implementation_research: Annotated[list[AnyMessage], add_messages_with_clear]
    codebase_structure: Optional[str] = Field(None, description="The codebase structure")
    current_file_content: Optional[str] = Field(None, description="The current content of the file being edited")
    working_directory: Optional[str] = Field(".", description="The working directory for the repository (e.g., './repo-name' or '.' for current directory)")