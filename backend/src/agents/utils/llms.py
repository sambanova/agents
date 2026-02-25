import os
from functools import lru_cache
from urllib.parse import urlparse

import httpx
import structlog
from langchain_fireworks import ChatFireworks
from langchain_sambanova import ChatSambaNova

logger = structlog.get_logger(__name__)


@lru_cache(maxsize=4)
def get_sambanova_llm(api_key: str, model: str = "Meta-Llama-3.3-70B-Instruct"):
    logger.info("Initializing SambaNova LLM", model=model, llm_provider="sambanova")

    # Adjust max_tokens for Maverick model due to its 16k context limit
    if "Maverick" in model:
        max_tokens = 7000  # Reduced from 8192 to leave room for prompts
    else:
        max_tokens = 8192

    try:
        llm = ChatSambaNova(
            model=model,
            temperature=0,
            max_tokens=max_tokens,
            api_key=api_key,
            stream_options={"include_usage": True},
        )

        logger.info(
            "SambaNova LLM initialized successfully",
            model=model,
            llm_provider="sambanova",
            max_tokens=max_tokens,
        )

    except Exception as e:
        logger.error(
            "Failed to initialize SambaNova LLM",
            model=model,
            llm_provider="sambanova",
            error={"type": type(e).__name__, "message": str(e)},
            exc_info=True,
        )
        raise e
    return llm


@lru_cache(maxsize=4)
def get_fireworks_llm(api_key: str, model: str = "fireworks-llama-3.3-70b"):
    logger.info("Initializing Fireworks LLM", model=model, llm_provider="fireworks")

    try:
        llm = ChatFireworks(
            model=model,
            temperature=0,
            api_key=api_key,
        )

        logger.info(
            "Fireworks LLM initialized successfully",
            model=model,
            llm_provider="fireworks",
        )

    except Exception as e:
        logger.error(
            "Failed to initialize Fireworks LLM",
            model=model,
            llm_provider="fireworks",
            error={"type": type(e).__name__, "message": str(e)},
            exc_info=True,
        )
        raise e
    return llm
