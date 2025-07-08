from typing import Any, Callable, Dict

from agents.utils.message_interceptor import MessageInterceptor
from langchain.output_parsers import OutputFixingParser, PydanticOutputParser
from langchain_core.language_models import LanguageModelLike
from langchain_core.messages import AIMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import Runnable, RunnableLambda


class MessageCaptureAgent(Runnable):
    """
    A manual agent that captures the messages from the LLM response.
    """

    def __init__(
        self,
        prompt: ChatPromptTemplate,
        llm: LanguageModelLike,
        parser: PydanticOutputParser,
        output_mapper: Callable,
    ):
        self.llm = llm
        self.parser = parser
        self.output_mapper = output_mapper
        self.prompt = prompt
        self.llm_interceptor = MessageInterceptor()
        self.llm_fixing_interceptor = MessageInterceptor()

    async def ainvoke(self, state: Dict[str, Any]) -> AIMessage:
        """
        Asynchronously invokes the agent with the given state.
        The logic is now fully encapsulated in _get_llm_response.
        """

        fixing_model = self.llm | RunnableLambda(
            self.llm_fixing_interceptor.capture_and_pass
        )

        return await (
            self.prompt
            | self.llm
            | RunnableLambda(self.llm_interceptor.capture_and_pass)
            | OutputFixingParser.from_llm(
                llm=fixing_model,
                parser=self.parser,
            )
            | self.output_mapper
        ).ainvoke(state)

    def invoke(self, state: Dict[str, Any]) -> AIMessage:
        raise NotImplementedError(
            "This agent is designed for asynchronous invocation. Use ainvoke instead."
        )
