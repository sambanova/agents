from __future__ import annotations

from typing import Sequence, Union

import structlog
from agents.components.compound.data_types import LLMType
from agents.components.compound.enhanced_agent import EnhancedConfigurableAgent
from agents.tools.langgraph_tools import (
    ActionServer,
    Arxiv,
    Connery,
    DallE,
    Daytona,
    DDGSearch,
    PressReleases,
    PubMed,
    Retrieval,
    SecFilings,
    Tavily,
    TavilyAnswer,
    Wikipedia,
    YouSearch,
)
from langchain_core.messages import AnyMessage
from langchain_core.runnables import ConfigurableField
from langgraph.graph.message import Messages
from langgraph.pregel import Pregel

logger = structlog.get_logger(__name__)

Tool = Union[
    ActionServer,
    Connery,
    DDGSearch,
    Arxiv,
    YouSearch,
    SecFilings,
    PressReleases,
    PubMed,
    Wikipedia,
    Tavily,
    TavilyAnswer,
    Retrieval,
    DallE,
    Daytona,
]


DEFAULT_SYSTEM_MESSAGE = "You are a helpful assistant."

DEFAULT_API_KEY = "unknown"


enhanced_agent: Pregel = (
    EnhancedConfigurableAgent(
        llm_type=LLMType.SN_DEEPSEEK_V3,
        tools=[],
        system_message=DEFAULT_SYSTEM_MESSAGE,
        user_id=None,
    )
    .configurable_fields(
        llm_type=ConfigurableField(id="llm_type", name="LLM Type"),
        system_message=ConfigurableField(id="system_message", name="Instructions"),
        subgraphs=ConfigurableField(id="subgraphs", name="Subgraphs"),
        tools=ConfigurableField(id="tools", name="Tools"),
        user_id=ConfigurableField(id="user_id", name="User ID"),
    )
    .configurable_alternatives(
        ConfigurableField(id="type", name="Bot Type"),
        default_key="default",
        prefix_keys=True,
    )
    .with_types(
        input_type=Messages,
        output_type=Sequence[AnyMessage],
    )
)
