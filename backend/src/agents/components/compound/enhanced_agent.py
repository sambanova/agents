"""
Enhanced ConfigurableAgent with dynamic MCP tool loading support.

This module provides an enhanced version of ConfigurableAgent that can load
user-specific MCP tools in addition to static tools.
"""

import functools
import os
from typing import Any, Dict, Mapping, Optional, Sequence, Union

import structlog
from agents.api.stream import astream_state_websocket
from agents.api.websocket_interface import WebSocketInterface
from agents.components.compound.data_types import LLMType
from agents.components.compound.xml_agent import get_xml_agent_executor

# Import moved to runtime to avoid circular imports
# from agents.tools.dynamic_tool_loader import get_dynamic_tool_loader, load_tools_for_user
from langchain.tools import BaseTool
from langchain_core.runnables import RunnableBinding, RunnableConfig

logger = structlog.get_logger(__name__)

# Import StaticToolConfig from langgraph_tools to avoid circular imports
# This import is done at runtime in the functions that need it

DEFAULT_SYSTEM_MESSAGE = "You are a helpful assistant."

# Try to import new config system for enhanced functionality
try:
    from agents.config.llm_config_manager import get_config_manager
    from agents.utils.llm_provider import get_llm_for_task
    CONFIG_SYSTEM_AVAILABLE = True
except ImportError:
    CONFIG_SYSTEM_AVAILABLE = False


# Local get_llm function to avoid circular imports
def get_llm(
    llm_type: LLMType,
    api_key: str = None,
    user_id: Optional[str] = None,
    api_keys: dict = None,
    llm_overrides: Optional[dict] = None,
):
    """Get LLM instance based on type and API key.

    Note: When called from xml_agent, api_key and optionally api_keys are provided.
    When called from EnhancedConfigurableAgent init, llm_type and user_id are provided.
    """

    # Check if admin panel is enabled and config system is available
    admin_enabled = os.getenv("SHOW_ADMIN_PANEL", "false").lower() == "true"

    if (
        CONFIG_SYSTEM_AVAILABLE
        and user_id
        and (api_keys or api_key)
        and (admin_enabled or llm_overrides)
    ):
        # Use new config system when admin panel is enabled
        config_manager = get_config_manager()

        # Determine which provider the API key is for based on the user's current configuration
        user_config = config_manager.get_full_config(user_id)
        default_provider = user_config.get("default_provider", "sambanova")

        logger.info(f"Admin panel LLM setup: default_provider={default_provider}, user_id={user_id[:8] if user_id else 'None'}...")

        # If api_keys dict was passed (from admin panel), use it directly
        if api_keys and isinstance(api_keys, dict):
            logger.info(f"Using provided API keys dict: providers with keys={list(k for k, v in api_keys.items() if v)}")
            # api_keys is already in the right format
            pass
        else:
            # Fallback to old behavior - create API keys dict
            api_keys = {
                default_provider: api_key,
                # For other providers, we'll let get_llm_for_task handle the error if needed
                "sambanova": api_key if default_provider == "sambanova" else None,
                "fireworks": api_key if default_provider == "fireworks" else None,
                "together": api_key if default_provider == "together" else None,
            }
            logger.info(f"Created API keys dict: providers with keys={list(k for k, v in api_keys.items() if v)}")

        # Map LLMType to task name
        # Handle both enum and string values
        task_map = {
            LLMType.SN_DEEPSEEK_V3: "main_agent",
            LLMType.SN_LLAMA_3_3_70B: "main_agent",
            LLMType.SN_LLAMA_MAVERICK: "vision_agent",
            LLMType.SN_DEEPSEEK_R1_DISTILL_LLAMA: "main_agent",
            LLMType.FIREWORKS_LLAMA_3_3_70B: "main_agent",
            # String values that might come from frontend
            "DeepSeek V3": "main_agent",
            "DeepSeek R1 Distill Llama": "main_agent",
            "Llama 3.3 70B": "main_agent",
            "Llama 4 Maverick": "vision_agent",
            "Fireworks Llama 3.3 70B": "main_agent",
        }

        # Try to get task from map, handle both enum and string
        if isinstance(llm_type, str):
            task = task_map.get(llm_type, "main_agent")
        else:
            task = task_map.get(llm_type, "main_agent")

        # Return the actual LLM instance, not a partial function
        return get_llm_for_task(
            task=task,
            api_keys=api_keys,
            config_manager=config_manager,
            user_id=user_id,
            overrides=llm_overrides,
        )
    else:
        # Use original behavior when admin panel is disabled or api_key is not provided
        if not api_key:
            raise ValueError("API key is required")

        from agents.utils.llms import get_fireworks_llm, get_sambanova_llm

        if llm_type == LLMType.SN_LLAMA_3_3_70B:
            llm = get_sambanova_llm(model="Meta-Llama-3.3-70B-Instruct", api_key=api_key)
        elif llm_type == LLMType.SN_LLAMA_MAVERICK:
            llm = get_sambanova_llm(
                model="Llama-4-Maverick-17B-128E-Instruct", api_key=api_key
            )
        elif llm_type == LLMType.SN_DEEPSEEK_V3:
            llm = get_sambanova_llm(model="DeepSeek-V3-0324", api_key=api_key)
        elif llm_type == LLMType.SN_DEEPSEEK_R1_DISTILL_LLAMA:
            llm = get_sambanova_llm(model="DeepSeek-R1-Distill-Llama-70B", api_key=api_key)
        elif llm_type == LLMType.FIREWORKS_LLAMA_3_3_70B:
            llm = get_fireworks_llm(
                model="accounts/fireworks/models/llama-v3p1-70b-instruct", api_key=api_key
            )
        else:
            # When admin panel is off and we get an unexpected type,
            # default to DeepSeek V3 for backward compatibility
            logger.warning(f"Unexpected agent type: {llm_type}, defaulting to DeepSeek V3")
            llm = get_sambanova_llm(model="DeepSeek-V3-0324", api_key=api_key)

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

        # Store user_id for closure
        init_user_id = user_id

        # Create a wrapper function that xml_agent can call with api_key
        def llm_wrapper(
            api_key: str,
            api_keys: dict = None,
            user_id: str = None,
            llm_overrides: dict = None,
        ):
            # Use the user_id passed from xml_agent if available, otherwise use the one from init
            effective_user_id = user_id if user_id else init_user_id
            return get_llm(
                llm_type,
                api_key=api_key,
                user_id=effective_user_id,
                api_keys=api_keys,
                llm_overrides=llm_overrides,
            )

        llm = llm_wrapper

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
            logger.error(
                f"Error in astream_websocket: {str(e)}",
                exc_info=True,
                error_type=type(e).__name__
            )
            raise e
