########## data_types.py (FULL, UNCHANGED EXCEPT NEW FIELDS) ##########
from pydantic import BaseModel, model_validator, Field
from enum import Enum
from typing import Any, List, Optional, Union, Dict
from datetime import date
from agents.components.financial_analysis.financial_analysis_crew import (
    FinancialAnalysisResult,
)
from agents.components.samba_research_flow.crews.edu_research.edu_research_crew import (
    Section,
)
from agents.components.lead_generation_crew import OutreachList


# Enum to Define Agent Types
class AgentEnum(str, Enum):
    FinancialAnalysis = "financial_analysis"
    SalesLeads = "sales_leads"
    Assistant = "assistant"
    UserProxy = "user_proxy"
    DeepResearch = "deep_research"  # For advanced research (LangGraph)
    Error = "error"


class Greeter(BaseModel):
    greeting: str


class DeepResearchUserQuestion(BaseModel):
    deep_research_question: str


class UserQuestion(BaseModel):
    agent_question: str


class AssistantMessage(BaseModel):
    query: str


class AssistantResponse(BaseModel):
    response: str


class ErrorResponse(BaseModel):
    error: str


# Base class for messages exchanged between agents and users
class BaseAgentMessage(BaseModel):
    source: str
    timestamp: Optional[date] = None


class TestMessage(BaseAgentMessage):
    content: str


# SubTask Model
class CoPilotSubTask(BaseModel):
    task_details: str
    assigned_agent: AgentEnum

    class Config:
        use_enum_values = True  # To serialize enums as their values


class HandoffMessage(BaseAgentMessage):
    content: str


class APIKeys(BaseModel):
    sambanova_key: str = ""
    fireworks_key: str = ""
    serper_key: str
    exa_key: str


class FinancialAnalysis(BaseModel):
    ticker: Optional[str] = Field(default=None, description="The ticker of the company")
    company_name: str = Field(default="", description="The name of the company")
    query_text: str = Field(default="", description="The query text from the user")


class SalesLeads(BaseModel):
    industry: str = Field(default="", description="The industry of the company")
    company_stage: Optional[str] = Field(
        default=None, description="The stage of the company"
    )
    geography: Optional[str] = Field(
        default=None, description="The geography for the sales leads"
    )
    funding_stage: Optional[str] = Field(
        default=None, description="The funding stage for the sales leads"
    )
    product: Optional[str] = Field(
        default=None, description="The product for the sales leads"
    )


class DeepResearch(BaseModel):
    deep_research_topic: str = Field(
        default="", description="The topic of the research"
    )


class EducationalContent(BaseModel):
    topic: str = Field(
        default="", description="The topic of the research, use a single word"
    )
    audience_level: Optional[str] = Field(
        default=None, description="What level of audience is the research for"
    )
    focus_areas: Optional[str] = Field(
        default=None, description="The focus areas of the research"
    )

    @model_validator(mode="before")
    def convert_focus_areas_list(cls, data):
        if isinstance(data, dict) and "focus_areas" in data:
            if isinstance(data["focus_areas"], list):
                data["focus_areas"] = ", ".join(
                    str(area) for area in data["focus_areas"]
                )
        return data


class EndUserMessage(BaseAgentMessage):
    content: str
    use_planner: bool = False
    docs: Optional[List[str]] = None
    provider: str
    planner_model: str
    message_id: str


class AgentRequest(BaseModel):
    agent_type: AgentEnum
    parameters: Union[
        FinancialAnalysis, SalesLeads, AssistantMessage, UserQuestion, DeepResearch
    ]
    query: str
    docs: Optional[List[str]] = None
    provider: str
    message_id: str

    @model_validator(mode="after")
    def validate_parameters_type(self) -> "AgentRequest":
        expected_type = {
            AgentEnum.FinancialAnalysis: FinancialAnalysis,
            AgentEnum.SalesLeads: SalesLeads,
            AgentEnum.Assistant: AssistantMessage,
            AgentEnum.UserProxy: UserQuestion,
            AgentEnum.DeepResearch: DeepResearch,
        }[self.agent_type]

        if isinstance(self.parameters, expected_type):
            return self
        if isinstance(self.parameters, dict):
            self.parameters = expected_type.model_validate(self.parameters)
        else:
            raise ValueError(
                f"Parameters must be of type {expected_type.__name__} for agent_type {self.agent_type}"
            )
        return self


class ExtendedSection(Section):
    generated_content: str


class EducationalPlanResult(BaseModel):
    sections: List[ExtendedSection] = []


# A single citation data structure
class DeepCitation(BaseModel):
    title: str = Field(default="", description="The descriptive title")
    url: str = Field(default="", description="The link URL")


class DeepResearchSection(BaseModel):
    name: str
    description: str
    content: str
    citations: List[Dict[str, str]] = Field(default_factory=list)


class DeepResearchReport(BaseModel):
    """
    A structured object that collects the final multi-section deep research report,
    plus the raw final text if needed, plus a list of all citations.
    """

    sections: List[DeepResearchSection]
    final_report: str
    citations: List[DeepCitation] = Field(default_factory=list)


class AgentStructuredResponse(BaseModel):
    agent_type: AgentEnum
    data: Union[
        FinancialAnalysisResult,
        EducationalPlanResult,
        OutreachList,
        Greeter,
        AssistantResponse,
        UserQuestion,
        DeepResearchUserQuestion,
        DeepResearchReport,
        ErrorResponse,
    ]
    metadata: Optional[Dict[str, Any]] = None
    message_id: str
    message: Optional[str] = None  # Additional message or notes from the agent
