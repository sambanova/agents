import json
import logging
import os
import time
import warnings
from typing import Any, Dict, List, Optional, Union, cast

import structlog

with warnings.catch_warnings():
    warnings.simplefilter("ignore", UserWarning)
    import litellm
    from litellm import Choices, get_supported_openai_params
    from litellm.types.utils import ModelResponse

from crewai.llm import (
    suppress_warnings,
    DEFAULT_CONTEXT_WINDOW_SIZE,
    LLM_CONTEXT_WINDOW_SIZES,
    CONTEXT_WINDOW_USAGE_RATIO,
)
from crewai.utilities.exceptions.context_window_exceeding_exception import (
    LLMContextLengthExceededException,
)
from crewai import LLM

logger = structlog.get_logger(__name__)


class CustomLLM(LLM):
    def __init__(
        self,
        model: str,
        timeout: Optional[Union[float, int]] = None,
        temperature: Optional[float] = None,
        top_p: Optional[float] = None,
        n: Optional[int] = None,
        stop: Optional[Union[str, List[str]]] = None,
        max_completion_tokens: Optional[int] = None,
        max_tokens: Optional[int] = None,
        presence_penalty: Optional[float] = None,
        frequency_penalty: Optional[float] = None,
        logit_bias: Optional[Dict[int, float]] = None,
        response_format: Optional[Dict[str, Any]] = None,
        seed: Optional[int] = None,
        logprobs: Optional[int] = None,
        top_logprobs: Optional[int] = None,
        base_url: Optional[str] = None,
        api_version: Optional[str] = None,
        api_key: Optional[str] = None,
        callbacks: List[Any] = [],
        extra_headers: Optional[Dict[str, str]] = None,
    ):
        self.model = model
        self.timeout = timeout
        self.temperature = temperature
        self.top_p = top_p
        self.n = n
        self.max_completion_tokens = max_completion_tokens
        self.max_tokens = max_tokens
        self.presence_penalty = presence_penalty
        self.frequency_penalty = frequency_penalty
        self.logit_bias = logit_bias
        self.response_format = response_format
        self.seed = seed
        self.logprobs = logprobs
        self.top_logprobs = top_logprobs
        self.base_url = base_url
        self.api_version = api_version
        self.api_key = api_key
        self.callbacks = callbacks
        self.context_window_size = 0
        self.extra_headers = extra_headers

        litellm.drop_params = True

        # Normalize self.stop to always be a List[str]
        if stop is None:
            self.stop: List[str] = []
        elif isinstance(stop, str):
            self.stop = [stop]
        else:
            self.stop = stop

        self.set_callbacks(callbacks)
        self.set_env_callbacks()

    def call(
        self,
        messages: Union[str, List[Dict[str, str]]],
        tools: Optional[List[dict]] = None,
        callbacks: Optional[List[Any]] = None,
        available_functions: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        High-level llm call method that:
          1) Accepts either a string or a list of messages
          2) Converts string input to the required message format
          3) Calls litellm.completion
          4) Handles function/tool calls if any
          5) Returns the final text response or tool result

        Parameters:
        - messages (Union[str, List[Dict[str, str]]]): The input messages for the LLM.
          - If a string is provided, it will be converted into a message list with a single entry.
          - If a list of dictionaries is provided, each dictionary should have 'role' and 'content' keys.
        - tools (Optional[List[dict]]): A list of tool schemas for function calling.
        - callbacks (Optional[List[Any]]): A list of callback functions to be executed.
        - available_functions (Optional[Dict[str, Any]]): A dictionary mapping function names to actual Python functions.

        Returns:
        - str: The final text response from the LLM or the result of a tool function call.

        Examples:
        ---------
        # Example 1: Using a string input
        response = llm.call("Return the name of a random city in the world.")
        print(response)

        # Example 2: Using a list of messages
        messages = [{"role": "user", "content": "What is the capital of France?"}]
        response = llm.call(messages)
        print(response)
        """
        if isinstance(messages, str):
            messages = [{"role": "user", "content": messages}]

        with suppress_warnings():
            if callbacks and len(callbacks) > 0:
                self.set_callbacks(callbacks)

            try:
                # --- 1) Prepare the parameters for the completion call
                params = {
                    "model": self.model,
                    "messages": messages,
                    "timeout": self.timeout,
                    "temperature": self.temperature,
                    "top_p": self.top_p,
                    "n": self.n,
                    "stop": self.stop,
                    "max_tokens": self.max_tokens or self.max_completion_tokens,
                    "presence_penalty": self.presence_penalty,
                    "frequency_penalty": self.frequency_penalty,
                    "logit_bias": self.logit_bias,
                    "response_format": self.response_format,
                    "seed": self.seed,
                    "logprobs": self.logprobs,
                    "top_logprobs": self.top_logprobs,
                    "api_base": self.base_url,
                    "api_version": self.api_version,
                    "api_key": self.api_key,
                    "stream": False,
                    "tools": tools,
                    "extra_headers": self.extra_headers,
                }

                # Remove None values from params
                params = {k: v for k, v in params.items() if v is not None}

                # --- 2) Make the completion call
                start_time = time.time()

                if "messages" in params:
                    message_headers = str(params["messages"])[0:100]
                else:
                    message_headers = ""

                logger.info(
                    f"CrewAI LLM {self.model} calling litellm.completion with messages: {message_headers}"
                )
                logger.info(f"[LITELLM_PARAMS] model={params.get('model')}, api_base={params.get('api_base')}, api_key={'***' if params.get('api_key') else 'MISSING'}")
                try:
                    response = litellm.completion(**params)
                except litellm.APIError as e:
                    # If it's a Sambanova exception, retry once
                    if "SambanovaException" in str(e):
                        logger.warning(f"Sambanova error occurred, retrying once: {e}")
                        time.sleep(1)  # Brief pause before retry
                        try:
                            response = litellm.completion(**params)
                        except Exception as retry_e:
                            logger.error(f"Retry failed: {retry_e}", exc_info=True)
                            raise
                    else:
                        logger.error(f"Error calling litellm.completion: {e}", exc_info=True)
                        raise
                except Exception as e:
                    logger.error(f"Unexpected error calling litellm.completion: {type(e).__name__}: {e}", exc_info=True)
                    raise
                duration = time.time() - start_time
                if duration > 10:
                    logger.warning(
                        f"CrewAI LLM {self.model} took {duration:.2f} seconds to complete task"
                    )
                else:
                    logger.info(
                        f"CrewAI LLM {self.model} took {duration:.2f} seconds to complete task"
                    )

                response_message = cast(Choices, cast(ModelResponse, response).choices)[
                    0
                ].message
                text_response = response_message.content or ""
                tool_calls = getattr(response_message, "tool_calls", [])

                # --- 3) Handle callbacks with usage info
                if callbacks and len(callbacks) > 0:
                    for callback in callbacks:
                        if hasattr(callback, "log_success_event"):
                            usage_info = getattr(response, "usage", None)
                            if usage_info:
                                callback.log_success_event(
                                    kwargs=params,
                                    response_obj={"usage": usage_info},
                                    start_time=0,
                                    end_time=0,
                                )

                # --- 4) If no tool calls, return the text response
                if not tool_calls or not available_functions:
                    return text_response

                # --- 5) Handle the tool call
                tool_call = tool_calls[0]
                function_name = tool_call.function.name

                if function_name in available_functions:
                    try:
                        function_args = json.loads(tool_call.function.arguments)
                    except json.JSONDecodeError as e:
                        logging.warning(f"Failed to parse function arguments: {e}")
                        return text_response

                    fn = available_functions[function_name]
                    try:
                        # Call the actual tool function
                        result = fn(**function_args)
                        return result

                    except Exception as e:
                        logging.error(
                            f"Error executing function '{function_name}': {e}"
                        )
                        return text_response

                else:
                    logging.warning(
                        f"Tool call requested unknown function '{function_name}'"
                    )
                    return text_response

            except Exception as e:
                if not LLMContextLengthExceededException(
                    str(e)
                )._is_context_limit_error(str(e)):
                    logging.error(f"LiteLLM call failed: {str(e)}")
                raise

    def supports_function_calling(self) -> bool:
        try:
            params = get_supported_openai_params(model=self.model)
            # If litellm doesn't recognize the model, params will be None
            # For custom models with base_url, assume function calling is supported
            if params is None:
                if self.base_url:
                    return True  # Custom OpenAI-compatible endpoints typically support function calling
                return False
            return "response_format" in params
        except Exception as e:
            logging.error(f"Failed to get supported params: {str(e)}")
            return False

    def supports_stop_words(self) -> bool:
        try:
            params = get_supported_openai_params(model=self.model)
            # If litellm doesn't recognize the model, params will be None
            # For custom models with base_url, assume stop words are supported
            if params is None:
                if self.base_url:
                    return True  # Custom OpenAI-compatible endpoints typically support stop words
                return False
            return "stop" in params
        except Exception as e:
            logging.error(f"Failed to get supported params: {str(e)}")
            return False

    def get_context_window_size(self) -> int:
        """
        Returns the context window size, using 75% of the maximum to avoid
        cutting off messages mid-thread.
        """
        if self.context_window_size != 0:
            return self.context_window_size

        self.context_window_size = int(
            DEFAULT_CONTEXT_WINDOW_SIZE * CONTEXT_WINDOW_USAGE_RATIO
        )
        for key, value in LLM_CONTEXT_WINDOW_SIZES.items():
            if self.model.startswith(key):
                self.context_window_size = int(value * CONTEXT_WINDOW_USAGE_RATIO)
        return self.context_window_size

    def set_callbacks(self, callbacks: List[Any]):
        """
        Attempt to keep a single set of callbacks in litellm by removing old
        duplicates and adding new ones.
        """
        with suppress_warnings():
            callback_types = [type(callback) for callback in callbacks]
            for callback in litellm.success_callback[:]:
                if type(callback) in callback_types:
                    litellm.success_callback.remove(callback)

            for callback in litellm._async_success_callback[:]:
                if type(callback) in callback_types:
                    litellm._async_success_callback.remove(callback)

            litellm.callbacks = callbacks

    def set_env_callbacks(self):
        """
        Sets the success and failure callbacks for the LiteLLM library from environment variables.

        This method reads the `LITELLM_SUCCESS_CALLBACKS` and `LITELLM_FAILURE_CALLBACKS`
        environment variables, which should contain comma-separated lists of callback names.
        It then assigns these lists to `litellm.success_callback` and `litellm.failure_callback`,
        respectively.

        If the environment variables are not set or are empty, the corresponding callback lists
        will be set to empty lists.

        Example:
            LITELLM_SUCCESS_CALLBACKS="langfuse,langsmith"
            LITELLM_FAILURE_CALLBACKS="langfuse"

        This will set `litellm.success_callback` to ["langfuse", "langsmith"] and
        `litellm.failure_callback` to ["langfuse"].
        """
        with suppress_warnings():
            success_callbacks_str = os.environ.get("LITELLM_SUCCESS_CALLBACKS", "")
            success_callbacks = []
            if success_callbacks_str:
                success_callbacks = [
                    cb.strip() for cb in success_callbacks_str.split(",") if cb.strip()
                ]

            failure_callbacks_str = os.environ.get("LITELLM_FAILURE_CALLBACKS", "")
            failure_callbacks = []
            if failure_callbacks_str:
                failure_callbacks = [
                    cb.strip() for cb in failure_callbacks_str.split(",") if cb.strip()
                ]

            litellm.success_callback = success_callbacks
            litellm.failure_callback = failure_callbacks
