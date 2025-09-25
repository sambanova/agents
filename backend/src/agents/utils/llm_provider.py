"""
Extended LLM Provider utility that supports multiple providers with dynamic API keys.
"""

from functools import lru_cache
from typing import Optional, Any
import structlog
from langchain_core.language_models.base import LanguageModelLike

logger = structlog.get_logger(__name__)

@lru_cache(maxsize=8)
def get_llm(
    provider: str,
    model: str,
    api_key: str,
    base_url: Optional[str] = None,
    temperature: float = 0.0,
    max_tokens: Optional[int] = None
) -> LanguageModelLike:
    """
    Get an LLM instance for any supported provider.

    Args:
        provider: The provider name ('sambanova', 'fireworks', 'together')
        model: The model identifier
        api_key: The API key for the provider
        base_url: Optional base URL override
        temperature: Temperature for the model
        max_tokens: Maximum tokens for the model

    Returns:
        An initialized LLM instance
    """
    logger.info(
        "Initializing LLM",
        provider=provider,
        model=model,
        has_api_key=bool(api_key),
        base_url=base_url
    )

    try:
        if provider == "sambanova":
            from langchain_sambanova import ChatSambaNovaCloud

            # Adjust max_tokens for specific models
            if max_tokens is None:
                if "Maverick" in model:
                    max_tokens = 7000  # Reduced for Maverick's 16k context
                elif "gpt-oss-120b" in model:
                    max_tokens = 16384  # Higher for GPT OSS
                else:
                    max_tokens = 8192  # Default

            llm = ChatSambaNovaCloud(
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
                sambanova_api_key=api_key,
            )

        elif provider == "fireworks":
            from langchain_fireworks import ChatFireworks

            if max_tokens is None:
                max_tokens = 8192

            # Fireworks requires the base URL to be set
            if not base_url:
                base_url = "https://api.fireworks.ai/inference/v1"

            llm = ChatFireworks(
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
                api_key=api_key,
                base_url=base_url,
            )

        elif provider == "together":
            # Together AI uses OpenAI-compatible API
            from langchain_openai import ChatOpenAI

            if max_tokens is None:
                max_tokens = 8192

            if not base_url:
                base_url = "https://api.together.xyz/v1"

            llm = ChatOpenAI(
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
                api_key=api_key,
                base_url=base_url,
            )

        else:
            raise ValueError(f"Unsupported provider: {provider}")

        logger.info(
            "LLM initialized successfully",
            provider=provider,
            model=model,
            max_tokens=max_tokens
        )

        return llm

    except Exception as e:
        logger.error(
            "Failed to initialize LLM",
            provider=provider,
            model=model,
            error={"type": type(e).__name__, "message": str(e)},
            exc_info=True
        )
        raise e


def get_llm_for_task(
    task: str,
    api_keys: dict,
    config_manager: Any = None,
    user_id: Optional[str] = None
) -> LanguageModelLike:
    """
    Get an LLM instance for a specific task using configuration.

    Args:
        task: The task identifier (e.g., 'main_agent', 'data_science_agent')
        api_keys: Dictionary of API keys by provider name
        config_manager: Optional config manager instance
        user_id: Optional user ID for user-specific overrides

    Returns:
        An initialized LLM instance for the task
    """
    if config_manager is None:
        from agents.config.llm_config_manager import get_config_manager
        config_manager = get_config_manager()

    # Get task configuration
    task_config = config_manager.get_task_model(task, user_id)
    provider = task_config.get("provider", "sambanova")
    model = task_config.get("model")

    logger.info(f"get_llm_for_task: task={task}, provider={provider}, model={model}, available_keys={list(api_keys.keys()) if isinstance(api_keys, dict) else 'string_key'}")

    # Get provider configuration
    provider_config = config_manager.get_provider_config(provider, user_id)
    # Use task-specific base URL if available, otherwise use provider's base URL
    base_url = task_config.get("base_url") or provider_config.get("base_url")

    # Get model details
    model_info = config_manager.get_model_info(provider, model)
    max_tokens = model_info.get("max_tokens")

    # Get the appropriate API key
    # For backward compatibility, if only a string key is provided, assume it's for SambaNova
    if isinstance(api_keys, str):
        api_key = api_keys
        if provider != "sambanova":
            raise ValueError(f"Provider {provider} requires its own API key")
    else:
        api_key = api_keys.get(provider)
        if not api_key:
            # Fall back to sambanova key if that's what we have
            if provider == "sambanova" and "sambanova" in api_keys:
                api_key = api_keys["sambanova"]
            else:
                raise ValueError(f"No API key provided for provider {provider}")

    return get_llm(
        provider=provider,
        model=model,
        api_key=api_key,
        base_url=base_url,
        max_tokens=max_tokens
    )


def get_crewai_llm(
    provider: str,
    model: str,
    api_key: str,
    base_url: Optional[str] = None,
    temperature: float = 0.0,
    max_tokens: int = 8192
):
    """
    Get a CrewAI-compatible LLM instance (using CustomLLM wrapper).

    Args:
        provider: The provider name
        model: The model identifier
        api_key: The API key
        base_url: Optional base URL
        temperature: Temperature setting
        max_tokens: Maximum tokens

    Returns:
        A CustomLLM instance configured for the provider
    """
    from agents.components.crewai_llm import CustomLLM

    # Map provider to CrewAI model string format
    if provider == "sambanova":
        crewai_model = f"sambanova/{model}"
    elif provider == "fireworks":
        crewai_model = f"fireworks_ai/{model}"
    elif provider == "together":
        crewai_model = f"together_ai/{model}"
    else:
        crewai_model = model

    if not base_url:
        if provider == "sambanova":
            base_url = "https://api.sambanova.ai/v1"
        elif provider == "fireworks":
            base_url = "https://api.fireworks.ai/inference/v1"
        elif provider == "together":
            base_url = "https://api.together.xyz/v1"

    return CustomLLM(
        model=crewai_model,
        temperature=temperature,
        max_tokens=max_tokens,
        api_key=api_key,
        base_url=base_url,
    )