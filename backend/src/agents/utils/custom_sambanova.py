"""
Custom extension of SambaNova chat model with timeout functionality.
"""

from typing import List, Dict, Any, Optional
from langchain_sambanova.chat_models import ChatSambaNovaCloud, _create_message_dicts, BaseMessage
from requests import Response
import requests
from pydantic import Field



class CustomChatSambaNovaCloud(ChatSambaNovaCloud):
    """
    Custom extension of ChatSambaNovaCloud that overrides _handle_request 
    to ensure proper timeout handling.
    """
    
    timeout: Optional[float] = Field(default=None)
    """Request timeout in seconds"""
    
    def __init__(self, timeout: Optional[float] = None, **kwargs):
        """
        Initialize the custom chat model with timeout support.
        
        Args:
            timeout: Optional timeout in seconds for API requests
            **kwargs: Additional arguments to pass to the parent class
        """
        super().__init__(**kwargs)
        self.timeout = timeout
    
    def _handle_request(
        self,
        messages_dicts: List[Dict[str, Any]],
        stop: Optional[List[str]] = None,
        streaming: bool = False,
        **kwargs: Any,
    ) -> Response:
        """
        Performs a post request to the LLM API.

        Args:
            messages_dicts: List of role / content dicts to use as input.
            stop: list of stop tokens
            streaming: wether to do a streaming call

        Returns:
            An iterator of response dicts.
        """
        if streaming:
            data = {
                "messages": messages_dicts,
                "max_tokens": self.max_tokens,
                "stop": stop,
                "model": self.model,
                "temperature": self.temperature,
                "top_p": self.top_p,
                "stream": True,
                "stream_options": self.stream_options,
                **kwargs,
                **self.model_kwargs,
            }
        else:
            data = {
                "messages": messages_dicts,
                "max_tokens": self.max_tokens,
                "stop": stop,
                "model": self.model,
                "temperature": self.temperature,
                "top_p": self.top_p,
                **kwargs,
                **self.model_kwargs,
            }
        if self.model == "gpt-oss-120b":
            data["reasoning_effort"]="high"
        http_session = requests.Session()
        response = http_session.post(
            self.sambanova_url,
            headers={
                "Authorization": f"Bearer {self.sambanova_api_key.get_secret_value()}",
                "Content-Type": "application/json",
                **self.additional_headers,
            },
            json=data,
            stream=streaming,
            timeout=self.timeout,
        )
        if response.status_code != 200:
            raise RuntimeError(
                f"Sambanova /complete call failed with status code "
                f"{response.status_code}.",
                f"{response.text}.",
            )
        return response