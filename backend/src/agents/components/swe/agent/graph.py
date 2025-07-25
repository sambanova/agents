from agents.components.swe.agent.architect.graph import create_swe_architect, swe_architect
from agents.components.swe.agent.common.entities import ImplementationPlan
from agents.components.swe.agent.developer.graph import create_swe_developer
from agents.components.swe.human_choice import swe_human_choice_node, swe_human_choice_router
from agents.utils.llms import get_sambanova_llm
from agents.components.compound.util import extract_api_key
from pydantic import BaseModel, Field
from langchain_core.messages import AnyMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph import add_messages, StateGraph, START, END
from typing import Annotated, Optional
import structlog

logger = structlog.get_logger(__name__)

class AgentState(BaseModel):
    implementation_research_scratchpad: Annotated[list[AnyMessage], add_messages]
    implementation_plan: Optional[ImplementationPlan] = Field(None, description="The implementation plan to be executed")
    human_feedback: Optional[str] = Field("", description="Feedback from human about the implementation plan")
    plan_approved: Optional[bool] = Field(None, description="Whether the human has approved the implementation plan")
    messages: Annotated[list[AnyMessage], add_messages] = Field([], description="Messages to be sent to the frontend")
    sender: Optional[str] = Field(None, description="The sender of the last message")
    working_directory: Optional[str] = Field(".", description="The working directory for the repository")


def create_swe_agent(daytona_manager=None, github_token=None):
    """Create the main SWE agent with both architect and developer subgraphs"""
    
    # Create the architect and developer with Daytona support
    architect_subgraph = create_swe_architect(daytona_manager=daytona_manager, github_token=github_token)
    developer_subgraph = create_swe_developer(daytona_manager=daytona_manager, github_token=github_token)
    
    # Create human choice node wrapper function that provides LLM
    async def human_choice_node_wrapper(state, *, config: RunnableConfig = None):
        """Human choice node wrapper that provides LLM from config"""
        api_key = extract_api_key(config)
        llm = get_sambanova_llm(api_key=api_key, model="DeepSeek-V3-0324")
        return await swe_human_choice_node(state, llm)
    
    # Create the main workflow
    workflow = StateGraph(AgentState)
    
    # Add nodes
    workflow.add_node("architect", architect_subgraph)
    workflow.add_node("human_choice", human_choice_node_wrapper)
    workflow.add_node("developer", developer_subgraph)
    
    # Add edges
    workflow.add_edge(START, "architect")
    workflow.add_edge("architect", "human_choice")
    workflow.add_conditional_edges("human_choice", swe_human_choice_router, {"developer": "developer", "architect": "architect"})
    workflow.add_edge("developer", END)
    
    return workflow.compile()
