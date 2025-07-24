from agents.components.swe.agent.architect.graph import create_swe_architect, swe_architect
from agents.components.swe.agent.common.entities import ImplementationPlan
from agents.components.swe.agent.developer.graph import create_swe_developer, swe_developer
from pydantic import BaseModel, Field
from langchain_core.messages import AnyMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph import add_messages, StateGraph, START, END
from typing import Annotated, Optional

class AgentState(BaseModel):
    implementation_research_scratchpad: Annotated[list[AnyMessage], add_messages]
    implementation_plan: Optional[ImplementationPlan] = Field(None, description="The implementation plan to be executed")


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
    
    # Add nodes
    graph_builder.add_node("swe_architect", architect)
    graph_builder.add_node("swe_developer", developer)
    # Add edges for the workflow
    graph_builder.add_edge(START, "swe_architect")
    graph_builder.add_edge("swe_architect", "swe_developer")
    graph_builder.add_edge("swe_developer", END)

    return graph_builder

def create_swe_agent(daytona_manager=None, github_token=None, *, config: RunnableConfig = None):
    """Create SWE agent with optional Daytona support and config support for API key passing"""
    return create_workflow_graph(daytona_manager, github_token).compile().with_config({
        "tags": ["agent-v1"], 
        "recursion_limit": 200
    })

# For backward compatibility
swe_agent = create_swe_agent()
