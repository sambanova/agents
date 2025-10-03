"""
Message interceptor for CrewAI LLM calls.
Wraps CustomLLM to capture calls and convert them to LangChain AIMessages.
"""

import uuid
from typing import List, Optional, Any, Dict, Union

from langchain_core.messages import AIMessage
from agents.components.crewai_llm import CustomLLM


class CrewAIMessageInterceptor:
    """Intercepts CrewAI LLM calls and captures them as LangChain AIMessages."""

    def __init__(self):
        self.captured_messages: List[AIMessage] = []

    def wrap_llm(self, llm: CustomLLM) -> CustomLLM:
        """Wrap a CustomLLM to intercept its calls."""
        # Store the original call method
        original_call = llm.call
        interceptor = self

        # Create wrapper function
        def intercepted_call(
            messages: Union[str, List[Dict[str, str]]],
            tools: Optional[List[dict]] = None,
            callbacks: Optional[List[Any]] = None,
            available_functions: Optional[Dict[str, Any]] = None,
        ) -> str:
            # Call the original method
            response = original_call(messages, tools, callbacks, available_functions)

            # Create AIMessage from the response
            # Don't include usage_metadata since we don't have access to token counts here
            # The RedisConversationLogger handles usage tracking separately
            ai_message = AIMessage(
                content=response or "",
                id=str(uuid.uuid4()),
                response_metadata={
                    "model_name": llm.model,
                }
            )

            # Capture the message
            interceptor.captured_messages.append(ai_message)

            return response

        # Replace the call method
        llm.call = intercepted_call

        return llm

    def clear(self):
        """Clear captured messages."""
        self.captured_messages = []
