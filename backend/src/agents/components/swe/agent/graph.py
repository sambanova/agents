from agents.components.swe.agent.architect.graph import create_swe_architect, swe_architect
from agents.components.swe.agent.common.entities import ImplementationPlan
from agents.components.swe.agent.developer.graph import create_swe_developer, swe_developer
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


def architect_router(state: AgentState) -> str:
    """Route from architect: if plan exists, go to human choice; otherwise stay in architect"""
    if getattr(state, "implementation_plan", None):
        logger.info("Implementation plan created, routing to human choice for approval")
        return "human_choice"
    else:
        logger.info("No implementation plan yet, continuing research")
        return "swe_architect"


def create_workflow_graph(daytona_manager=None, github_token=None):
    """Create and return the workflow graph with conditional routing and optional Daytona support"""
    # Initialize graph
    graph_builder = StateGraph(AgentState)
    
    # Create architect and developer with Daytona support if manager is provided
    if daytona_manager:
        architect = create_swe_architect(daytona_manager, github_token)
        developer = create_swe_developer(daytona_manager, github_token)
    else:
        architect = swe_architect
        developer = swe_developer
    
    # Create human choice node function
    async def human_choice_node_async(state, *, config: RunnableConfig = None):
        """Human choice node for SWE workflow"""
        api_key = extract_api_key(config)
        llm = get_sambanova_llm(api_key=api_key, model="DeepSeek-V3-0324")
        return await swe_human_choice_node(state, llm)
    
    # Add nodes
    graph_builder.add_node("swe_architect", architect)
    graph_builder.add_node("human_choice", human_choice_node_async)
    graph_builder.add_node("swe_developer", developer)
    
    # Add edges for the workflow with human choice integration
    graph_builder.add_edge(START, "swe_architect")
    
    # Conditional edge from architect: loop until plan is created, then go to human choice
    graph_builder.add_conditional_edges(
        "swe_architect",
        architect_router,
        {
            "swe_architect": "swe_architect",  # Continue research if no plan
            "human_choice": "human_choice",   # Go to human choice when plan is ready
        }
    )
    
    # Conditional edge from human choice: revise plan or proceed to developer
    graph_builder.add_conditional_edges(
        "human_choice", 
        swe_human_choice_router,
        {
            "architect": "swe_architect",  # Revise plan
            "developer": "swe_developer",  # Proceed with implementation
        }
    )
    
    # Developer completes and ends
    graph_builder.add_edge("swe_developer", END)

    return graph_builder


def create_swe_agent(daytona_manager=None, github_token=None):
    """Create the complete SWE agent with human choice workflow"""
    logger.info("Creating SWE agent with human choice workflow")
    graph_builder = create_workflow_graph(daytona_manager, github_token)
    return graph_builder.compile().with_config({
        "tags": ["swe-agent-v3"],
        "recursion_limit": 200
    })

# For backward compatibility
swe_agent = create_swe_agent()
