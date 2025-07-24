import json
from typing import List, TypedDict, Optional

from agents.utils.llms import get_sambanova_llm
from agents.components.compound.util import extract_api_key
from langchain_core.messages import HumanMessage, AIMessage, AnyMessage
from langchain_core.output_parsers import JsonOutputParser
from langgraph.constants import END, START
from langgraph.prebuilt import ToolNode
from pydantic import BaseModel, Field
from langgraph.graph import StateGraph
from langchain_core.runnables import RunnableConfig

from agents.components.swe.agent.architect.state import SoftwareArchitectState
from agents.components.swe.agent.tools.search import search_tools
from agents.components.swe.agent.tools.codemap import codemap_tools
from agents.components.swe.agent.tools.github_tools import get_github_tools
from agents.components.swe.agent.tools.write import get_files_structure
from agents.components.swe.agent.tools.daytona_tools import get_swe_daytona_tools
from agents.components.swe.helpers.prompts import markdown_to_prompt_template
from agents.components.swe.agent.common.entities import ImplementationPlan


class ResearchStep(BaseModel):
    reasoning: str = Field(description="The reasoning behind the research step, why research is needed how it going to help the implmentation of the task")
    hypothesis: str = Field(description="The hypothesis that need to be researched")


class ResearchEvaluation(BaseModel):
    reasoning: str = Field(description="The reason why the research step is valid or not 1-3 sentences")
    is_valid: bool = Field(description="Whether the research step is valid")

# prompt
plan_next_step_prompt = markdown_to_prompt_template("agents/components/swe/agent/architect/prompts/plan_next_step_prompt.md")
check_research_prompt = markdown_to_prompt_template("agents/components/swe/agent/architect/prompts/check_research_already_explored.md")
conduct_research_prompt = markdown_to_prompt_template("agents/components/swe/agent/architect/prompts/conduct_research_plan_prompt.md")
extract_implementation_prompt = markdown_to_prompt_template("agents/components/swe/agent/architect/prompts/extract_implementation_plan.md")

# Create LLM factory functions that extract API key from config
def get_swe_llm(*, config: RunnableConfig = None):
    """Get SambaNova LLM with API key from config"""
    api_key = extract_api_key(config)
    return get_sambanova_llm(api_key=api_key, model="DeepSeek-V3-0324")

# runnable - these will be called with config to get the LLM instance
def create_plan_next_step_runnable(config: RunnableConfig = None):
    llm = get_swe_llm(config=config)
    return plan_next_step_prompt | llm.with_structured_output(ResearchStep)

def create_check_research_runnable(config: RunnableConfig = None):
    llm = get_swe_llm(config=config)
    return check_research_prompt | llm.with_structured_output(ResearchEvaluation)

def create_conduct_research_runnable(config: RunnableConfig = None, daytona_tools=None):
    llm = get_swe_llm(config=config)
    all_tools = search_tools + codemap_tools
    if daytona_tools:
        all_tools = all_tools + daytona_tools
    return conduct_research_prompt | llm.bind_tools(all_tools)

def create_extract_implementation_runnable(config: RunnableConfig = None):
    llm = get_swe_llm(config=config)
    return extract_implementation_prompt | llm | JsonOutputParser(pydantic_object=ImplementationPlan)

# Default tool_node for backward compatibility (without Daytona tools)
tool_node = ToolNode(codemap_tools+search_tools, messages_key="implementation_research_scratchpad")

class ComeUpWithResearchNextStepOutput(TypedDict):
    research_next_step: str
    implementation_research_scratchpad: List[AnyMessage]

def come_up_with_research_next_step(state: SoftwareArchitectState, *, config: RunnableConfig = None) -> ComeUpWithResearchNextStepOutput:
    """Generate the next research step based on the current state"""
    plan_next_step_runnable = create_plan_next_step_runnable(config)
    response = plan_next_step_runnable.invoke({
        "implementation_research_scratchpad": state.implementation_research_scratchpad,
        "codebase_structure": get_files_structure.invoke({
            "directory": state.working_directory or "."
        }),
    })
    return {"research_next_step": response.hypothesis,
            "implementation_research_scratchpad": [
                AIMessage(content=f"My next thing i need to check is {response.hypothesis}"
                          f"This is why I think it is useful: {response.reasoning}")]}

class CheckResearchStepOutput(TypedDict):
    is_valid_research_step: bool
    implementation_research_scratchpad: List[AnyMessage]

def check_research_step(state: SoftwareArchitectState, *, config: RunnableConfig = None)-> CheckResearchStepOutput:
    """Check if the proposed research step has already been explored"""
    check_research_runnable = create_check_research_runnable(config)
    response = check_research_runnable.invoke({
        "implementation_research_scratchpad": state.implementation_research_scratchpad
    })
    if not response.is_valid:
        return {
            "is_valid_research_step": False,
            "implementation_research_scratchpad": [HumanMessage(content="The research path is not valid, here is why: " + response.reasoning)]
        }
    else:
        return {
            "is_valid_research_step": True, 
            "implementation_research_scratchpad": [HumanMessage(content=f"The research path is valid, start conducting the research")]
        }

def conduct_research(state: SoftwareArchitectState, *, config: RunnableConfig = None, daytona_tools=None):
    """Conduct research based on the proposed hypothesis"""
    conduct_research_runnable = create_conduct_research_runnable(config, daytona_tools)
    response = conduct_research_runnable.invoke({
        "implementation_research_scratchpad": state.implementation_research_scratchpad,
        "codebase_structure": get_files_structure.invoke({"directory": state.working_directory or "."})
    })
    return {"implementation_research_scratchpad": [response]}

def convert_tools_messages_to_ai_and_human(implementation_research_scratchpad: List[AnyMessage]):
    messages = []
    for message in implementation_research_scratchpad:
        if message.type == "ai":
            if message.tool_calls:
                tool_name = message.tool_calls[0]["name"]
                tool_args = json.dumps(message.tool_calls[0]["args"])
                messages.append(AIMessage(content=f"I want to call the tool {tool_name} with the following arguments: {tool_args}"))
            else:
                messages.append(message)
        elif message.type == "tool":
            messages.append(HumanMessage(content=f"When executing Tool {message.name} \n The result was {message.content} was called"))
        else:
            messages.append(message)
    return messages

def extract_implementation_plan(state: SoftwareArchitectState, *, config: RunnableConfig = None):
    """Extract implementation plan from research findings"""
    extract_implementation_runnable = create_extract_implementation_runnable(config)
    response = extract_implementation_runnable.invoke({
        "research_findings": convert_tools_messages_to_ai_and_human(state.implementation_research_scratchpad),
        "codebase_structure": get_files_structure.invoke({"directory": state.working_directory or "."}),
        "output_format": JsonOutputParser(pydantic_object=ImplementationPlan).get_format_instructions()
    })
    response = ImplementationPlan(**response)
    return {"implementation_plan": response}

def should_call_tool(state: SoftwareArchitectState):
    """Router function to determine if tools should be called"""
    last_message = state.implementation_research_scratchpad[-1]
    
    if last_message.tool_calls:
        return "should_call_tool"
    
    return "implement_plan"

def should_conduct_research(state: SoftwareArchitectState):
    if state.is_valid_research_step:
        return "plan_is_valid"
    else:
        return "plan_is_not_valid"

def call_model(state: SoftwareArchitectState, *, config: RunnableConfig = None):
    plan_next_step_runnable = create_plan_next_step_runnable(config)
    response = plan_next_step_runnable.invoke({"atomic_implementation_research":state.implementation_research_scratchpad,
                                               "codebase_structure": get_files_structure.invoke({"directory": state.working_directory or "."}),
                                               "historical_actions": "No historical actions"})
    return {"implementation_research_scratchpad": [response]}

class SoftwareArchitectInput(TypedDict):
    implementation_research_scratchpad: List[AnyMessage]
    working_directory: Optional[str]

class SoftwareArchitectOutput(TypedDict):
    implementation_plan: Optional[ImplementationPlan]
    working_directory: Optional[str]

workflow = StateGraph(SoftwareArchitectState,
                      input=SoftwareArchitectInput,
                      output=SoftwareArchitectOutput)

# Define all workflow nodes
workflow.add_node("come_up_with_research_next_step", come_up_with_research_next_step)
workflow.add_node("check_research_step", check_research_step)
workflow.add_node("conduct_research", conduct_research)
workflow.add_node("extract_implementation_plan", extract_implementation_plan)
workflow.add_node("tools", tool_node)

workflow.add_edge(START, "come_up_with_research_next_step")
workflow.add_edge("come_up_with_research_next_step", "check_research_step")
workflow.add_conditional_edges(
    "check_research_step", 
    should_conduct_research,
    {
        "plan_is_valid": "conduct_research",
        "plan_is_not_valid": "come_up_with_research_next_step"
    }
)
workflow.add_edge("check_research_step", "conduct_research")
workflow.add_conditional_edges(
    "conduct_research",
    should_call_tool,
    {
        "should_call_tool": "tools",
        "implement_plan": "extract_implementation_plan",
    }
)
workflow.add_edge("tools", "conduct_research")
workflow.add_edge("extract_implementation_plan", END)

def create_swe_architect(daytona_manager=None, github_token=None):
    """Create the SWE architect workflow with optional Daytona tools"""
    from agents.components.datagen.tools.persistent_daytona import PersistentDaytonaManager
    
    # Get Daytona tools if manager is provided
    daytona_tools = []
    if daytona_manager:
        daytona_tools = get_swe_daytona_tools(daytona_manager)
    
    # Get GitHub tools if token is provided
    github_tools = []
    if github_token:
        github_tools = get_github_tools(github_token)
    
    # Create tool node with all tools
    all_tools = codemap_tools + search_tools + daytona_tools + github_tools
    tool_node = ToolNode(all_tools, messages_key="implementation_research_scratchpad")
    
    # Create workflow with Daytona-enhanced functions
    enhanced_workflow = StateGraph(SoftwareArchitectState,
                                 input=SoftwareArchitectInput,
                                 output=SoftwareArchitectOutput)
    
    # Add nodes with partial application for daytona_tools
    from functools import partial
    enhanced_workflow.add_node("come_up_with_research_next_step", come_up_with_research_next_step)
    enhanced_workflow.add_node("check_research_step", check_research_step)
    enhanced_workflow.add_node("conduct_research", partial(conduct_research, daytona_tools=daytona_tools))
    enhanced_workflow.add_node("extract_implementation_plan", extract_implementation_plan)
    enhanced_workflow.add_node("tools", tool_node)
    
    # Add edges (same as original)
    enhanced_workflow.add_edge(START, "come_up_with_research_next_step")
    enhanced_workflow.add_edge("come_up_with_research_next_step", "check_research_step")
    enhanced_workflow.add_conditional_edges(
        "check_research_step", 
        should_conduct_research,
        {
            "plan_is_valid": "conduct_research",
            "plan_is_not_valid": "come_up_with_research_next_step"
        }
    )
    enhanced_workflow.add_edge("check_research_step", "conduct_research")
    enhanced_workflow.add_conditional_edges(
        "conduct_research",
        should_call_tool,
        {
            "should_call_tool": "tools",
            "implement_plan": "extract_implementation_plan",
        }
    )
    enhanced_workflow.add_edge("tools", "conduct_research")
    enhanced_workflow.add_edge("extract_implementation_plan", END)
    
    return enhanced_workflow.compile().with_config({"tags": ["research-agent-v3"]})

# Default architect without Daytona tools for backward compatibility
swe_architect = workflow.compile().with_config({"tags": ["research-agent-v3"]})
