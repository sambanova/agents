from enum import Enum
import functools
from typing import Any, Dict, Literal, Mapping, Optional, Sequence, Union

from agents.api.stream import astream_state_websocket
from agents.api.websocket_interface import WebSocketInterface
from agents.components.compound.data_types import LLMType
from agents.components.compound.xml_agent import get_xml_agent_executor
from langchain_core.messages import AnyMessage
from langchain_core.runnables import (
    ConfigurableField,
    RunnableBinding,
)
from langgraph.graph.message import Messages
from langgraph.pregel import Pregel
from langchain.tools import BaseTool

from langchain_core.language_models.base import LanguageModelLike
from langgraph.checkpoint.redis import RedisSaver
from langchain_core.runnables import RunnableConfig

from agents.utils.llms import (
    get_fireworks_llm,
    get_sambanova_llm,
)

from agents.utils.logging import logger

from agents.tools.langgraph_tools import (
    TOOL_REGISTRY,
    ActionServer,
    Arxiv,
    Connery,
    DallE,
    DDGSearch,
    PressReleases,
    PubMed,
    Retrieval,
    SecFilings,
    Tavily,
    TavilyAnswer,
    Wikipedia,
    YouSearch,
    Daytona,
    validate_tool_config,
)

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


def get_llm(
    llm_type: LLMType,
    api_key: str,
):
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


class ConfigurableAgent(RunnableBinding):
    tools: Sequence[Tool]
    llm_type: LLMType = LLMType.SN_DEEPSEEK_V3
    system_message: str = DEFAULT_SYSTEM_MESSAGE
    subgraphs: Optional[dict] = None

    def __init__(
        self,
        *,
        tools: Sequence[Tool],
        llm_type: LLMType = LLMType.SN_DEEPSEEK_V3,
        system_message: str = DEFAULT_SYSTEM_MESSAGE,
        subgraphs: Optional[dict] = None,
        kwargs: Optional[Mapping[str, Any]] = None,
        config: Optional[Mapping[str, Any]] = None,
        **others: Any,
    ) -> None:
        others.pop("bound", None)
        _tools = []
        for _tool in tools:
            tool_type = _tool["type"]
            tool_config = _tool.get("config", {})

            try:
                validated_config = validate_tool_config(tool_type, tool_config)
            except ValueError as e:
                logger.error(f"Tool validation failed: {e}")
                raise e

            _returned_tools = TOOL_REGISTRY[tool_type]["factory"](**validated_config)
            if isinstance(_returned_tools, list):
                _tools.extend(_returned_tools)
            else:
                _tools.append(_returned_tools)

        llm = functools.partial(get_llm, llm_type)

        _agent = get_xml_agent_executor(
            tools=_tools,
            llm=llm,
            system_message=system_message,
            subgraphs=subgraphs,
            llm_type=llm_type,
        )

        agent_executor = _agent.with_config({"recursion_limit": 50})
        super().__init__(
            tools=tools,
            llm_type=llm_type,
            system_message=system_message,
            subgraphs=subgraphs,
            bound=agent_executor,
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
            import traceback

            print(f"Error: {str(e)}")
            print("Stacktrace:")
            traceback.print_exc()
            raise e


agent: Pregel = (
    ConfigurableAgent(
        llm_type=LLMType.SN_DEEPSEEK_V3,
        tools=[],
        system_message=DEFAULT_SYSTEM_MESSAGE,
    )
    .configurable_fields(
        llm_type=ConfigurableField(id="llm_type", name="LLM Type"),
        system_message=ConfigurableField(id="system_message", name="Instructions"),
        subgraphs=ConfigurableField(id="subgraphs", name="Subgraphs"),
        tools=ConfigurableField(id="tools", name="Tools"),
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

if __name__ == "__main__":
    import asyncio

    from langchain.schema.messages import HumanMessage

    async def run():
        async for m in agent.astream_events(
            HumanMessage(content="whats your name"),
            config={"configurable": {"user_id": "2", "thread_id": "test1"}},
            version="v2",
        ):
            print(m)

    asyncio.run(run())
