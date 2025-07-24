from typing import Annotated, Optional
from pydantic import BaseModel, Field
from langchain_core.messages import AnyMessage
from langgraph.graph import add_messages
from agents.components.swe.agent.common.entities import ImplementationPlan


class SoftwareArchitectState(BaseModel):
    research_next_step: Optional[str] = Field(None, description="The next research step to be conducted")
    implementation_plan: Optional[ImplementationPlan] = Field(None, description="The implementation plan to be executed")
    implementation_research_scratchpad: Annotated[list[AnyMessage], add_messages] = Field([], description="The scratchpad for implementation research")
    is_valid_research_step: Optional[bool] = Field(None, description="Whether the research step is valid")
    working_directory: Optional[str] = Field(".", description="The working directory for the repository (e.g., './repo-name' or '.' for current directory)")
    human_feedback: Optional[str] = Field("", description="Feedback from human about the implementation plan")
    plan_approved: Optional[bool] = Field(None, description="Whether the human has approved the implementation plan")
    messages: Annotated[list[AnyMessage], add_messages] = Field([], description="Messages to be sent to the frontend")
    sender: Optional[str] = Field(None, description="The sender of the last message")
