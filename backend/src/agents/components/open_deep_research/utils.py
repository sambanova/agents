import asyncio
import os
import random
import time
from collections import deque
from typing import Any, Dict, List

import httpx
import requests
import structlog
from agents.components.open_deep_research.state import Section
from langsmith import traceable
from tavily import AsyncTavilyClient, TavilyClient

logger = structlog.get_logger(__name__)

# Initialize clients
tavily_client = TavilyClient()
tavily_async_client = AsyncTavilyClient()


# API key rotation mechanism
class APIKeyRotator:
    def __init__(self, env_var_prefix: str = "TAVILY_API_KEY"):
        """
        Initialize the API key rotator.

        Args:
            env_var_prefix: The prefix for environment variables containing API keys.
                            Will look for TAVILY_API_KEY, TAVILY_API_KEY_1, TAVILY_API_KEY_2, etc.
        """
        self.keys = []
        self.current_index = 0
        self.env_var_prefix = env_var_prefix
        self._load_keys_from_env()

    def _load_keys_from_env(self):
        """Load API keys from environment variables."""
        # First try the base key
        base_key = os.getenv(self.env_var_prefix)
        if base_key:
            self.keys.append(base_key)

        # Then try numbered keys
        i = 1
        while True:
            key = os.getenv(f"{self.env_var_prefix}_{i}")
            if not key:
                break
            self.keys.append(key)
            i += 1

        if not self.keys:
            raise ValueError(f"No API keys found with prefix {self.env_var_prefix}")

        # Shuffle the keys to distribute usage more evenly
        random.shuffle(self.keys)
        self.key_queue = deque(self.keys)

    def get_next_key(self) -> str:
        """Get the next API key in the rotation."""
        if not self.keys:
            raise ValueError("No API keys available")

        # Get the next key and rotate it to the end of the queue
        key = self.key_queue.popleft()
        self.key_queue.append(key)
        return key

    def get_random_key(self) -> str:
        """Get a random API key from the available keys."""
        if not self.keys:
            raise ValueError("No API keys available")
        return random.choice(self.keys)


def deduplicate_and_format_sources(
    search_response, max_tokens_per_source, include_raw_content=True
):
    """
    Takes a list of search responses and formats them into a readable string.
    Limits the raw_content to approximately max_tokens_per_source.
    """
    sources_list = []
    for response in search_response:
        sources_list.extend(response["results"])

    # Deduplicate by URL
    unique_sources = {source["url"]: source for source in sources_list}

    formatted_text = "Sources:\n\n"
    for i, source in enumerate(unique_sources.values(), 1):
        formatted_text += f"Source {source['title']}:\n===\n"
        formatted_text += f"URL: {source['url']}\n===\n"
        formatted_text += (
            f"Most relevant content from source: {source['content']}\n===\n"
        )
        if include_raw_content:
            char_limit = max_tokens_per_source * 4
            raw_content = source.get("raw_content", "")
            if raw_content is None:
                raw_content = ""
                print(f"Warning: No raw_content found for source {source['url']}")
            if len(raw_content) > char_limit:
                raw_content = raw_content[:char_limit] + "... [truncated]"
            formatted_text += f"Full source content limited to {max_tokens_per_source} tokens: {raw_content}\n\n"

    return formatted_text.strip()


def format_sections(sections: list[Section]) -> str:
    """Format a list of sections into a string"""
    formatted_str = ""
    for idx, section in enumerate(sections, 1):
        formatted_str += f"""
{'='*60}
Section {idx}: {section.name}
{'='*60}
Description:
{section.description}
Requires Research:
{section.research}

Content:
{section.content if section.content else '[Not yet written]'}

"""
    return formatted_str


@traceable
async def tavily_search_async(
    search_queries: List[str], key_rotator: APIKeyRotator
) -> List[Dict[str, Any]]:
    """
    Performs concurrent web searches using the Tavily API with key rotation.

    Args:
        search_queries: List of search queries to execute

    Returns:
        List of search results from Tavily
    """
    search_tasks = []

    # Create a new AsyncTavilyClient for each query with a rotated API key
    for query in search_queries:
        # Get the next API key in the rotation
        api_key = key_rotator.get_next_key()

        # Create a new client with the rotated key
        client = AsyncTavilyClient(api_key=api_key)

        # Add the search task with simple retry for 502 errors
        search_tasks.append(_tavily_search_with_retry(query, client, key_rotator))

    # Execute all search tasks concurrently
    search_docs = await asyncio.gather(*search_tasks, return_exceptions=True)

    # Handle any exceptions that occurred during the search
    processed_results = []
    for i, result in enumerate(search_docs):
        if isinstance(result, Exception):
            logger.error(f"Error in search query {i}: {str(result)}")
            # Try fallback to perplexity if tavily fails
            try:
                logger.info(
                    f"Falling back to Perplexity for query: {search_queries[i]}"
                )
                perplexity_result = perplexity_search([search_queries[i]], key_rotator)[
                    0
                ]
                processed_results.append(perplexity_result)
            except Exception:
                # Return an empty result if both fail
                processed_results.append(
                    {
                        "query": search_queries[i],
                        "results": [],
                        "follow_up_questions": [],
                        "answer": None,
                        "images": [],
                    }
                )
        else:
            processed_results.append(result)

    return processed_results


async def _tavily_search_with_retry(
    query: str,
    client: AsyncTavilyClient,
    key_rotator: APIKeyRotator,
    max_retries: int = 2,
):
    """Simple helper function to retry Tavily search on 502 errors"""
    for attempt in range(max_retries + 1):
        try:
            start_time = time.time()
            result = await client.search(
                query, max_results=5, include_raw_content=True, topic="general"
            )
            elapsed_time = time.time() - start_time
            if elapsed_time > 10:
                logger.warning(
                    f"Deep Research - Tavily search took {elapsed_time:.2f} seconds for query: {query}"
                )
            else:
                logger.info(
                    f"Deep Research - Tavily search took {elapsed_time:.2f} seconds for query: {query}"
                )

            return result

        except httpx.HTTPStatusError as e:
            # This will specifically catch HTTP status errors like 502
            status_code = e.response.status_code
            if status_code == 502 and attempt < max_retries:
                logger.warning(
                    f"Tavily 502 Bad Gateway error (attempt {attempt+1}/{max_retries+1}): {e}"
                )
                await asyncio.sleep(attempt + 1)
                # Try with a different API key
                api_key = key_rotator.get_next_key()
                client = AsyncTavilyClient(api_key=api_key)
            else:
                # For other status codes or if we've exhausted retries, raise the exception
                logger.error(f"Tavily HTTP error: {status_code} - {e}")
                raise
        except Exception as e:
            # For all other exceptions, log and raise immediately without retry
            logger.error(f"Tavily error (non-HTTP status error): {str(e)}")
            raise


@traceable
def perplexity_search(search_queries, key_rotator: APIKeyRotator):
    """
    Search the web using the Perplexity API.
    """
    headers = {
        "accept": "application/json",
        "content-type": "application/json",
        "Authorization": f"Bearer {key_rotator.get_next_key()}",
    }

    search_docs = []
    for query in search_queries:
        payload = {
            "model": "sonar-pro",
            "messages": [
                {
                    "role": "system",
                    "content": "Search the web and provide factual information with sources.",
                },
                {"role": "user", "content": query},
            ],
        }

        response = requests.post(
            "https://api.perplexity.ai/chat/completions", headers=headers, json=payload
        )
        response.raise_for_status()

        data = response.json()
        content = data["choices"][0]["message"]["content"]
        citations = data.get("citations", ["https://perplexity.ai"])

        results = []
        # First citation gets the full content
        results.append(
            {
                "title": f"Perplexity Search, Source 1",
                "url": citations[0],
                "content": content,
                "raw_content": content,
                "score": 1.0,
            }
        )
        for i, citation in enumerate(citations[1:], start=2):
            results.append(
                {
                    "title": f"Perplexity Search, Source {i}",
                    "url": citation,
                    "content": "See primary source for full content",
                    "raw_content": None,
                    "score": 0.5,
                }
            )

        search_docs.append(
            {
                "query": query,
                "follow_up_questions": None,
                "answer": None,
                "images": [],
                "results": results,
            }
        )

    return search_docs
