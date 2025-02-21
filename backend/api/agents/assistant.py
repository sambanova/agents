from datetime import datetime
import functools
import json
import time
from autogen_agentchat.agents import AssistantAgent, UserProxyAgent

from autogen_core import (
    DefaultTopicId,
    MessageContext,
    RoutedAgent,
    message_handler,
    type_subscription,
)
from autogen_ext.models.openai import OpenAIChatCompletionClient
from autogen_agentchat.messages import TextMessage
from fastapi import WebSocket
import redis
import requests
from api.data_types import (
    APIKeys,
    AgentRequest,
    AgentStructuredResponse,
    AssistantResponse,
)
from exa_py import Exa

from config.model_registry import model_registry
from utils.logging import logger

import asyncio
from typing import Any, Dict, List, Optional


async def get_current_time() -> str:
    """Get the current time."""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def serper_search(api_key: str, query: str, num_results: int = 5):
    """Performs a Google search using Serper API and returns the top results."""
    if not api_key:
        raise ValueError("SERPER_API_KEY environment variable is missing.")

    url = "https://google.serper.dev/search"
    headers = {"X-API-KEY": api_key, "Content-Type": "application/json"}
    payload = {"q": query, "num": num_results}

    response = requests.post(url, json=payload, headers=headers)
    response.raise_for_status()

    data = response.json()

    # Extract relevant search results
    results = []
    for item in data.get("organic", []):
        results.append(
            {
                "title": item.get("title"),
                "link": item.get("link"),
                "snippet": item.get("snippet"),
            }
        )
    return results


def yahoo_finance_search(symbol: str) -> Dict[str, Any]:
    """Get current stock information for a given symbol."""
    try:
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        data = response.json()

        if (
            "chart" in data
            and "result" in data["chart"]
            and len(data["chart"]["result"]) > 0
        ):
            result = data["chart"]["result"][0]
            meta = result.get("meta", {})
            return {
                "symbol": symbol,
                "price": meta.get("regularMarketPrice"),
                "previous_close": meta.get("previousClose"),
                "currency": meta.get("currency"),
                "exchange": meta.get("exchangeName"),
            }
        return {"error": f"No data found for symbol {symbol}"}
    except Exception as e:
        return {"error": f"Failed to fetch data: {str(e)}"}


def exa_news_search(
    api_key: str, query: str, num_results: int = 5
) -> List[Dict[str, str]]:
    """Search for news articles using Exa API."""
    if not api_key:
        raise ValueError("EXA_API_KEY is missing.")

    try:
        exa = Exa(api_key=api_key)
        exa_response = exa.search_and_contents(
            query, num_results=num_results, text=True
        )

        results = []
        for article in exa_response.results:
            results.append(
                {
                    "title": article.title,
                    "url": article.url,
                    "published_date": article.published_date,
                    "text": article.text,
                }
            )
        return results
    except Exception as e:
        return [{"error": f"Failed to fetch news: {str(e)}"}]


@type_subscription(topic_type="assistant")
class AssistantAgentWrapper(RoutedAgent):

    def __init__(
        self,
        websocket: WebSocket,
        api_keys: APIKeys,
        redis_client: redis.Redis,
    ) -> None:
        super().__init__("assistant")
        logger.info(
            logger.format_message(
                None,
                f"Initializing AssistantAgent with ID: {self.id} and tools: [get_current_time, serper_search, yahoo_finance_search, exa_news_search]",
            )
        )
        self.api_keys = api_keys
        self.websocket = websocket
        self.redis_client = redis_client
        self._default_model = "llama-3.1-70b"
        self._current_provider = None
        self._assistant_instance = None

    def get_assistant(self, provider: str) -> AssistantAgent:
        """Get or create an AssistantAgent instance for the given provider.
        Only creates a new instance if the provider changes.
        
        Args:
            provider: The model provider to use
            
        Returns:
            AssistantAgent: The current or new assistant instance
            
        Raises:
            ValueError: If the provider or model configuration is invalid
        """
        if provider == self._current_provider:
            return self._assistant_instance

        try:
            # Get model configuration
            model_info = model_registry.get_model_info(
                model_key=self._default_model, 
                provider=provider
            )
            if not model_info:
                raise ValueError(f"No model configuration found for provider {provider}")

            self._current_provider = provider
            self._assistant_instance = AssistantAgent(
                name="assistant",
                model_client=OpenAIChatCompletionClient(
                    model=model_info["model"],
                    base_url=model_info["url"],
                    api_key=getattr(self.api_keys, model_registry.get_api_key_env(provider=provider)),
                    model_info={
                        "json_output": False,
                        "function_calling": True,
                        "family": "unknown",
                        "vision": False,
                    },
                ),
                tools=[
                    get_current_time,
                    functools.partial(serper_search, self.api_keys.serper_key),
                    yahoo_finance_search,
                    functools.partial(exa_news_search, self.api_keys.exa_key),
                ],
                system_message="You are a helpful AI assistant. You have access to real-time stock data and news information and you should use the company ticker when searching for stock data. For example, if the user asks for Apple's stock price, you should use the ticker 'AAPL' when searching for stock data.",
                reflect_on_tool_use=True,
            )
            return self._assistant_instance

        except Exception as e:
            logger.error(f"Failed to create assistant for provider {provider}: {str(e)}")
            raise ValueError(f"Failed to initialize assistant: {str(e)}")

    @message_handler
    async def handle_text_message(
        self, message: AgentRequest, ctx: MessageContext
    ) -> None:
        try:
            logger.info(
                logger.format_message(
                    ctx.topic_id.source,
                    f"Processing request: '{message.parameters.query[:100]}...'",
                )
            )
            agent_message = TextMessage(content=message.parameters.query, source="user")

            start_time = time.time()
            response = await self.get_assistant(message.provider).on_messages(
                [agent_message], ctx.cancellation_token
            )
            await self.get_assistant(message.provider)._model_context.clear()
            logger.info(
                logger.format_message(
                    ctx.topic_id.source, "Generated response successfully"
                )
            )

            # Handle the response content based on its type
            response_content = (
                response.chat_message.content
                if hasattr(response, "chat_message")
                else (
                    response.response
                    if isinstance(response, AssistantResponse)
                    else "Unable to assist with this request."
                )
            )

            end_time = time.time()
            processing_time = end_time - start_time

            user_id, conversation_id = ctx.topic_id.source.split(":")

            assistant_metadata = {
                "duration": processing_time,
                "llm_name": self.get_assistant(message.provider)._model_client._resolved_model,
                "llm_provider": message.provider,
                "workflow": "General Assistant",
                "agent_name": "General Assistant",
                "task": "assistant",
            }
            assistant_event = {
                "event": "think",
                "data": json.dumps(
                    {
                        "user_id": user_id,
                        "run_id": conversation_id,
                        "agent_name": "General Assistant",
                        "text": response_content,
                        "metadata": assistant_metadata,
                    }
                ),
                "user_id": user_id,
                "conversation_id": conversation_id,
                "timestamp": datetime.now().isoformat(),
            }
            await self.websocket.send_text(json.dumps(assistant_event))
            self.redis_client.rpush(f"messages:{user_id}:{conversation_id}", json.dumps(assistant_event))

        except Exception as e:
            logger.error(
                logger.format_message(
                    ctx.topic_id.source, f"Failed to process request: {str(e)}"
                ),
                exc_info=True,
            )
            await self.get_assistant(message.provider)._model_context.clear()
            response_content = "Unable to assist with this request."

        try:
            # Send response back
            structured_response = AgentStructuredResponse(
                agent_type=self.id.type,
                data=AssistantResponse(response=response_content),
                message=message.parameters.model_dump_json(),
            )
            logger.info(
                logger.format_message(
                    ctx.topic_id.source, "Publishing response to user_proxy"
                )
            )
            await self.publish_message(
                structured_response,
                DefaultTopicId(type="user_proxy", source=ctx.topic_id.source),
            )
        except Exception as e:
            logger.error(
                logger.format_message(
                    ctx.topic_id.source, f"Failed to publish response: {str(e)}"
                ),
                exc_info=True,
            )
