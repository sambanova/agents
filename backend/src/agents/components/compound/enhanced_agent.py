"""
Enhanced ConfigurableAgent with dynamic MCP tool loading support.

This module provides an enhanced version of ConfigurableAgent that can load
user-specific MCP tools in addition to static tools.
"""

import functools
from typing import Any, Dict, List, Mapping, Optional, Sequence, Union

import structlog
from agents.api.stream import astream_state_websocket
from agents.api.websocket_interface import WebSocketInterface
# Avoid circular import - redefine types locally
from typing import Union
from agents.tools.langgraph_tools import (
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
)
from agents.components.compound.data_types import LLMType
from agents.components.compound.xml_agent import get_xml_agent_executor
# Import moved to runtime to avoid circular imports
# from agents.tools.dynamic_tool_loader import get_dynamic_tool_loader, load_tools_for_user
from langchain.tools import BaseTool
from langchain_core.messages import AnyMessage
from langchain_core.runnables import ConfigurableField, RunnableBinding, RunnableConfig
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
    """
    Enhanced ConfigurableAgent that supports dynamic MCP tool loading per user.
    
    This agent can load both static tools from the TOOL_REGISTRY and user-specific
    MCP tools from their configured MCP servers.
    """
    
    tools: Sequence[StaticToolConfig]
    llm_type: LLMType = LLMType.SN_DEEPSEEK_V3
    system_message: str = DEFAULT_SYSTEM_MESSAGE
    subgraphs: Optional[dict] = None
    user_id: Optional[str] = None

    def __init__(
        self,
        *,
        tools: Sequence[StaticToolConfig],
        llm_type: LLMType = LLMType.SN_DEEPSEEK_V3,
        system_message: str = DEFAULT_SYSTEM_MESSAGE,
        subgraphs: Optional[dict] = None,
        user_id: Optional[str] = None,
        kwargs: Optional[Mapping[str, Any]] = None,
        config: Optional[Mapping[str, Any]] = None,
        **others: Any,
    ) -> None:
        """
        Initialize enhanced agent with dynamic tool loading support.
        
        Args:
            tools: List of static tool configurations
            llm_type: LLM type to use
            system_message: System message for the agent
            subgraphs: Optional subgraphs dictionary
            user_id: Optional user ID for dynamic tool loading
            kwargs: Additional keyword arguments
            config: Configuration dictionary
            **others: Additional arguments
        """
        others.pop("bound", None)
        
        # Create a lazy-loading agent that will load tools when needed
        def create_agent_with_tools():
            return self._create_agent_executor(tools, llm_type, system_message, subgraphs, user_id)
        
        # For now, create the agent with static tools only
        # The dynamic loading will happen when the agent is actually used
        llm = functools.partial(get_llm, llm_type)
        
        # Create initial agent with empty tools - will be replaced during execution
        _agent = get_xml_agent_executor(
            tools=[],
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
            user_id=user_id,
            bound=agent_executor,
            kwargs=kwargs or {},
            config=config or {},
        )

        # Store user_id after initialization to avoid recursion during __setattr__
        self.user_id = user_id

    async def ainvoke(self, input: Any, config: Optional[RunnableConfig] = None) -> Any:
        """
        Invoke the agent with dynamic tool loading.
        
        This method loads user-specific tools before invoking the agent.
        """
        # Extract user_id from config if not provided during initialization
        effective_user_id = self.user_id
        if not effective_user_id and config:
            effective_user_id = config.get("configurable", {}).get("user_id")
            
        if effective_user_id:
            # Load tools dynamically for the user
            agent_executor = await self._get_agent_with_dynamic_tools(effective_user_id)
            return await agent_executor.ainvoke(input, config)
        else:
            # Fall back to static tools only
            logger.warning("No user_id provided, using static tools only")
            return await super().ainvoke(input, config)

    async def astream(self, input: Any, config: Optional[RunnableConfig] = None, **kwargs):
        """
        Stream the agent with dynamic tool loading.
        """
        # Extract user_id from config if not provided during initialization
        effective_user_id = self.user_id
        if not effective_user_id and config:
            effective_user_id = config.get("configurable", {}).get("user_id")
            
        if effective_user_id:
            # Load tools dynamically for the user
            agent_executor = await self._get_agent_with_dynamic_tools(effective_user_id)
            async for chunk in agent_executor.astream(input, config, **kwargs):
                yield chunk
        else:
            # Fall back to static tools only
            logger.warning("No user_id provided, using static tools only")
            async for chunk in super().astream(input, config, **kwargs):
                yield chunk

    async def astream_websocket(
        self,
        input: Union[list, Dict[str, Any]],
        config: RunnableConfig,
        websocket_manager: WebSocketInterface,
        user_id: str,
        conversation_id: str,
        message_id: str,
    ):
        """Stream agent responses directly to WebSocket with dynamic tool loading."""
        try:
            # Load tools dynamically for the user
            agent_executor = await self._get_agent_with_dynamic_tools(user_id)
            
            # Stream using the enhanced agent
            await astream_state_websocket(
                app=agent_executor,
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

    def with_config(self, config: Dict[str, Any]) -> "EnhancedConfigurableAgent":
        """Return a new agent with updated configuration."""
        new_config = {**self.config, **config}
        return EnhancedConfigurableAgent(
            tools=self.tools,
            llm_type=self.llm_type,
            system_message=self.system_message,
            subgraphs=self.subgraphs,
            user_id=self.user_id,
            kwargs=self.kwargs,
            config=new_config,
        )

    async def _get_agent_with_dynamic_tools(self, user_id: str) -> Pregel:
        """Get an agent executor with dynamic tool loading support."""
        try:
            # Load static tools only - MCP tools will be loaded dynamically by DynamicToolExecutor
            from agents.tools.dynamic_tool_loader import load_tools_for_user
            static_tools = await load_tools_for_user(user_id, self.tools, force_refresh=False)
            
            # Create agent executor with static tools + user_id for dynamic MCP tool loading
            return self._create_agent_executor_with_tools(static_tools, user_id)
            
        except Exception as e:
            logger.error(
                "Error creating enhanced agent, falling back to basic agent",
                user_id=user_id,
                error=str(e),
                exc_info=True,
            )
            # Fall back to basic agent with no tools but still with user_id for MCP support
            return self._create_agent_executor_with_tools([], user_id)

    def _create_agent_executor(
        self,
        tools: Sequence[StaticToolConfig],
        llm_type: LLMType,
        system_message: str,
        subgraphs: Optional[dict],
        user_id: Optional[str],
    ) -> Pregel:
        """Create agent executor with static tools (legacy method)."""
        # This is kept for backward compatibility
        llm = functools.partial(get_llm, llm_type)
        
        _agent = get_xml_agent_executor(
            tools=[],  # Will be loaded dynamically
            llm=llm,
            system_message=system_message,
            subgraphs=subgraphs,
            llm_type=llm_type,
            user_id=user_id,
        )
        
        return _agent.with_config({"recursion_limit": 50})

    def _create_agent_executor_with_tools(
        self,
        tools: List[BaseTool],
        user_id: str,
    ) -> Pregel:
        """Create agent executor with loaded tools."""
        llm = functools.partial(get_llm, self.llm_type)
        
        _agent = get_xml_agent_executor(
            tools=tools,
            llm=llm,
            system_message=self.system_message,
            subgraphs=self.subgraphs,
            llm_type=self.llm_type,
            user_id=user_id,
        )
        
        return _agent.with_config({"recursion_limit": 50})


def create_enhanced_agent(
    tools: Sequence[StaticToolConfig],
    llm_type: LLMType = LLMType.SN_DEEPSEEK_V3,
    system_message: str = DEFAULT_SYSTEM_MESSAGE,
    subgraphs: Optional[dict] = None,
    user_id: Optional[str] = None,
) -> EnhancedConfigurableAgent:
    """
    Create an enhanced configurable agent with dynamic MCP tool loading.
    
    Args:
        tools: List of static tool configurations
        llm_type: LLM type to use
        system_message: System message for the agent
        subgraphs: Optional subgraphs dictionary
        user_id: Optional user ID for dynamic tool loading
        
    Returns:
        Enhanced configurable agent
    """
    return EnhancedConfigurableAgent(
        tools=tools,
        llm_type=llm_type,
        system_message=system_message,
        subgraphs=subgraphs,
        user_id=user_id,
    )


# Enhanced agent will be created on-demand to avoid circular imports
# Use create_enhanced_agent() function instead of global variable 