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

            # Build kwargs for ChatSambaNovaCloud
            sambanova_kwargs = {
                "model": model,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "sambanova_api_key": api_key,
            }

            # If custom base_url provided, use sambanova_url parameter
            if base_url:
                sambanova_kwargs["sambanova_url"] = base_url
                logger.info(f"[SAMBANOVA_INIT] Using custom SambaNova URL: {base_url}")
            else:
                logger.info(f"[SAMBANOVA_INIT] Using default SambaNova URL (no base_url provided)")

            logger.info(f"[SAMBANOVA_INIT] Initializing with kwargs: model={sambanova_kwargs.get('model')}, has_custom_url={bool(base_url)}, api_key_preview={api_key[:8]}...{api_key[-4:]}")

            llm = ChatSambaNovaCloud(**sambanova_kwargs)

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
            # Assume it's a custom OpenAI-compatible provider
            from langchain_openai import ChatOpenAI

            if max_tokens is None:
                max_tokens = 8192

            if not base_url:
                raise ValueError(f"Custom provider {provider} requires a base_url")

            logger.info(
                f"[CUSTOM_OPENAI] Using custom OpenAI-compatible provider",
                provider=provider,
                base_url=base_url,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
                api_key_preview=f"{api_key[:8]}...{api_key[-4:]}"
            )

            # Don't use max_completion_tokens for custom providers
            # Use model_kwargs to pass max_tokens directly in the request body
            llm = ChatOpenAI(
                model=model,
                temperature=temperature,
                api_key=api_key,
                base_url=base_url,
                timeout=60.0,  # Set explicit timeout
                max_retries=2,  # Limit retries
                model_kwargs={
                    "max_tokens": max_tokens,  # Pass max_tokens directly, not max_completion_tokens
                }
            )

            logger.info(f"[CUSTOM_OPENAI] ChatOpenAI initialized successfully")

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

    # If task config has a specific API key (from custom provider), use it
    task_specific_api_key = task_config.get("api_key")

    # Get model details
    model_info = config_manager.get_model_info(provider, model, user_id)
    max_tokens = model_info.get("max_tokens")

    # For custom providers, use the provider_type to determine which LLM client to use
    # This allows custom SambaNova/Fireworks endpoints with different base URLs
    # Check task_config first (set by get_task_model for custom providers), then provider_config
    provider_type = task_config.get("provider_type") or provider_config.get("provider_type")
    actual_provider = provider_type if provider_type else provider

    logger.info(f"Provider: {provider}, Provider Type: {provider_type}, Actual Provider for LLM: {actual_provider}, Base URL: {base_url}")

    # Get the appropriate API key
    logger.info(f"[API_KEY_DEBUG] api_keys dict type: {type(api_keys)}")
    if isinstance(api_keys, dict):
        logger.info(f"[API_KEY_DEBUG] api_keys dict keys: {list(api_keys.keys())}")
        for key in api_keys:
            if api_keys[key]:
                logger.info(f"[API_KEY_DEBUG] api_keys[{key}] preview: {api_keys[key][:8]}...{api_keys[key][-4:]}")

    # If task has a specific API key (from custom provider), use it first
    if task_specific_api_key:
        api_key = task_specific_api_key
        logger.info(f"[API_KEY_DEBUG] Using task-specific API key for custom provider")
        logger.info(f"[API_KEY_DEBUG] API key value present: {bool(api_key)}")
        logger.info(f"[API_KEY_DEBUG] API key length: {len(api_key) if api_key else 0}")
        logger.info(f"[API_KEY_DEBUG] API key preview: {api_key[:8]}...{api_key[-4:] if len(api_key) > 12 else ''}")
    # For backward compatibility, if only a string key is provided, assume it's for SambaNova
    elif isinstance(api_keys, str):
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
        provider=actual_provider,  # Use provider_type for custom providers
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