"""
Enhanced ConfigurableAgent with dynamic MCP tool loading support.

This module provides an enhanced version of ConfigurableAgent that can load
user-specific MCP tools in addition to static tools.
"""

import asyncio
import functools

# Avoid circular import - redefine types locally
from typing import Any, Dict, List, Mapping, Optional, Sequence, Union

import structlog
from agents.api.stream import astream_state_websocket
from agents.api.websocket_interface import WebSocketInterface
from agents.components.compound.data_types import LLMType
from agents.components.compound.xml_agent import get_xml_agent_executor
from agents.tools.dynamic_tool_loader import load_tools_for_user
from agents.tools.langgraph_tools import (
    TOOL_REGISTRY,
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
    validate_tool_config,
)

# Import moved to runtime to avoid circular imports
# from agents.tools.dynamic_tool_loader import get_dynamic_tool_loader, load_tools_for_user
from langchain.tools import BaseTool
from langchain_core.messages import AnyMessage
from langchain_core.runnables import (
    ConfigurableField,
    RunnableBinding,
    RunnableConfig,
    RunnableLambda,
)
from langgraph.graph.message import Messages
from langgraph.pregel import Pregel

logger = structlog.get_logger(__name__)

# Local type definitions to avoid circular imports
StaticToolConfig = Union[
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


# Local get_llm function to avoid circular imports
def get_llm(llm_type: LLMType, api_key: str):
    """Get LLM instance based on type and API key."""
    from agents.utils.llms import get_fireworks_llm, get_sambanova_llm

    if llm_type == LLMType.SN_LLAMA_3_3_70B:
        llm = get_sambanova_llm(model="Meta-Llama-3.3-70B-Instruct", api_key=api_key)
    elif llm_type == LLMType.SN_LLAMA_MAVERICK:
        llm = get_sambanova_llm(
            model="Llama-4-Maverick-17B-128E-Instruct", api_key=api_key
        )
    elif llm_type == LLMType.SN_DEEPSEEK_V3:
        llm = get_sambanova_llm(model="DeepSeek-V3-0324", api_key=api_key)
    elif llm_type == LLMType.DEEPSEEK_R1_DISTILL_LLAMA:
        llm = get_sambanova_llm(model="DeepSeek-R1-Distill-Llama-70B", api_key=api_key)
    elif llm_type == LLMType.FIREWORKS_LLAMA_3_3_70B:
        llm = get_fireworks_llm(
            model="accounts/fireworks/models/llama-v3p1-70b-instruct", api_key=api_key
        )
    else:
        raise ValueError("Unexpected agent type")

    return llm


class EnhancedConfigurableAgent(RunnableBinding):
    tools: Sequence[BaseTool]
    llm_type: LLMType = LLMType.SN_DEEPSEEK_V3
    system_message: str = DEFAULT_SYSTEM_MESSAGE
    subgraphs: Optional[dict] = None
    user_id: Optional[str] = None

    def __init__(
        self,
        *,
        tools: Sequence[BaseTool] = [],
        llm_type: LLMType = LLMType.SN_DEEPSEEK_V3,
        system_message: str = DEFAULT_SYSTEM_MESSAGE,
        subgraphs: Optional[dict] = None,
        user_id: str = None,
        kwargs: Optional[Mapping[str, Any]] = None,
        config: Optional[Mapping[str, Any]] = None,
        **others: Any,
    ) -> None:
        others.pop("bound", None)
        llm = functools.partial(get_llm, llm_type)

        _agent = get_xml_agent_executor(
            tools=tools,
            llm=llm,
            system_message=system_message,
            subgraphs=subgraphs,
            llm_type=llm_type,
            user_id=user_id,
        )

        agent_executor = _agent.with_config({"recursion_limit": 50})
        super().__init__(
            tools=tools,
            llm_type=llm_type,
            system_message=system_message,
            subgraphs=subgraphs,
            bound=agent_executor,
            user_id=user_id,
            kwargs=kwargs or {},
            config=config or {},
        )

    async def astream_websocket(
        self,
        input: Union[list, Dict[str, Any]],
        config: RunnableConfig,
        websocket_manager: WebSocketInterface,
        user_id: str,
        conversation_id: str,
        message_id: str,
    ):
        try:
            """Stream agent responses directly to WebSocket"""
            await astream_state_websocket(
                app=self.bound,  # The compiled agent executor
                input=input,
                config=config,
                websocket_manager=websocket_manager,
                user_id=user_id,
                conversation_id=conversation_id,
                message_id=message_id,
            )
        except Exception as e:
            logger.error(f"Error in astream_websocket: {str(e)}")
            raise e
