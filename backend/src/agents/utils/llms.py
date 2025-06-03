import os
from functools import lru_cache
from urllib.parse import urlparse

import httpx
from langchain_sambanova import ChatSambaNovaCloud
from langchain_fireworks import ChatFireworks
from agents.utils.logging import logger


@lru_cache(maxsize=4)
def get_sambanova_llm(api_key: str, model: str = "Meta-Llama-3.3-70B-Instruct"):
    logger.info("Initializing SambaNova LLM", model=model, llm_provider="sambanova")

    try:
        llm = ChatSambaNovaCloud(
            model=model,
            temperature=0,
            max_tokens=8192,
            sambanova_api_key=api_key,
        )

        logger.info(
            "SambaNova LLM initialized successfully",
            model=model,
            llm_provider="sambanova",
            max_tokens=8192,
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
