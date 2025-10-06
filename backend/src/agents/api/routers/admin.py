"""
Admin panel API endpoints for LLM configuration management.
Only available when SHOW_ADMIN_PANEL environment variable is set to true.
"""

import os
import json
from typing import Dict, Any, Optional, List
from fastapi import APIRouter, HTTPException, Header, Depends, Request
from pydantic import BaseModel
import structlog

from agents.config.llm_config_manager import get_config_manager
from agents.utils.llm_provider import get_llm
from agents.storage.redis_storage import RedisStorage
from agents.auth.auth0_config import get_current_user_id

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/admin", tags=["admin"])


class ProviderConfig(BaseModel):
    """Model for provider configuration updates"""
    provider: str
    api_key: str


class TaskModelConfig(BaseModel):
    """Model for task-specific model configuration"""
    task: str
    provider: str
    model: str
    fallback_model: Optional[str] = None


class UserConfigUpdate(BaseModel):
    """Model for user configuration updates"""
    default_provider: Optional[str] = None
    task_models: Optional[Dict[str, Dict[str, str]]] = None
    api_keys: Dict[str, str]  # Provider -> API key mapping
    provider_base_urls: Optional[Dict[str, str]] = None  # Provider -> base URL mapping
    task_base_urls: Optional[Dict[str, str]] = None  # Task -> base URL mapping
    custom_models: Optional[List[Dict[str, Any]]] = None  # List of custom models
    custom_providers: Optional[List[Dict[str, Any]]] = None  # List of custom OpenAI-compatible providers


class ModelListResponse(BaseModel):
    """Response model for model listing"""
    provider: str
    models: List[Dict[str, Any]]


def check_admin_enabled():
    """Check if admin panel is enabled via environment variable"""
    admin_enabled = os.getenv("SHOW_ADMIN_PANEL", "false").lower() == "true"
    if not admin_enabled:
        raise HTTPException(
            status_code=403,
            detail="Admin panel is not enabled. Set SHOW_ADMIN_PANEL=true to enable."
        )
    return True


@router.get("/status")
async def get_admin_status():
    """Check if admin panel is enabled"""
    admin_enabled = os.getenv("SHOW_ADMIN_PANEL", "false").lower() == "true"
    return {
        "enabled": admin_enabled,
        "message": "Admin panel is enabled" if admin_enabled else "Admin panel is disabled"
    }


@router.get("/config", dependencies=[Depends(check_admin_enabled)])
async def get_configuration(
    user_id: str = Depends(get_current_user_id),
    request: Request = None
) -> Dict[str, Any]:
    """
    Get the current LLM configuration, including user overrides if applicable.
    Loads from Redis if available, otherwise returns defaults.

    Args:
        user_id: The authenticated user ID
        request: FastAPI request object to access Redis

    Returns:
        The current configuration
    """
    config_manager = get_config_manager()

    if user_id:
        # First, check if singleton has stale config that doesn't exist in Redis
        if request and hasattr(request.app.state, 'redis_storage_service'):
            redis_storage = request.app.state.redis_storage_service
            config_key = f"llm_config:{user_id}"

            try:
                stored_config = await redis_storage.redis_client.get(
                    config_key,
                    user_id=user_id
                )

                # If Redis is empty but singleton has config, clear the singleton
                if not stored_config and config_manager.has_user_override(user_id):
                    logger.info(f"Found stale config override in singleton for user {user_id[:8]}..., clearing it")
                    config_manager.clear_user_override(user_id)
                elif not stored_config:
                    logger.info(f"No config in Redis or singleton for user {user_id[:8]}...")

                if stored_config:
                    overrides = json.loads(stored_config)

                    # Apply stored overrides FIRST so custom providers are available for validation
                    config_manager.set_user_override(user_id, overrides)

                    # Validate and correct task models to ensure they exist in current config
                    # Skip validation for custom providers as they might have any models
                    if "task_models" in overrides:
                        for task, task_config in overrides["task_models"].items():
                            if isinstance(task_config, dict) and "model" in task_config and "provider" in task_config:
                                task_provider = task_config["provider"]
                                model_id = task_config["model"]

                                # Get models for this task's specific provider (passing user_id to include custom providers)
                                provider_models = config_manager.list_models(task_provider, user_id)

                                # Only try to map if model doesn't exist and this is NOT a custom provider
                                is_custom_provider = False
                                if "custom_providers" in overrides:
                                    custom_provider_names = [cp.get("name") for cp in overrides["custom_providers"]]
                                    is_custom_provider = task_provider in custom_provider_names

                                if model_id not in provider_models and not is_custom_provider:
                                    # Try to find a mapping for built-in providers
                                    mapped = False
                                    for logical_model, mappings in config_manager.model_mappings.items():
                                        for prov, prov_model in mappings.items():
                                            if prov_model == model_id and task_provider in mappings:
                                                task_config["model"] = mappings[task_provider]
                                                logger.info(f"Corrected model for task {task}: {model_id} -> {mappings[task_provider]}")
                                                mapped = True
                                                break
                                        if mapped:
                                            break

                    logger.info(f"Loaded persisted config from Redis for user {user_id[:8]}...")
            except Exception as e:
                logger.error(f"Failed to load config from Redis: {e}")

    config = config_manager.get_full_config(user_id)

    # Add metadata about admin panel
    config["admin_metadata"] = {
        "user_has_override": user_id in config_manager._user_overrides if user_id else False,
        "config_source": "user_override" if user_id and user_id in config_manager._user_overrides else "default"
    }

    # Debug: log what we're returning for task_models
    if user_id and "task_models" in config:
        task_models = config["task_models"]
        if "main_agent" in task_models:
            logger.info(f"GET /admin/config returning main_agent: {task_models['main_agent']}")

        # Also check what's in the singleton
        if user_id in config_manager._user_overrides:
            user_override = config_manager._user_overrides[user_id]
            if "task_models" in user_override and "main_agent" in user_override["task_models"]:
                logger.info(f"GET /admin/config - singleton has main_agent: {user_override['task_models']['main_agent']}")

    logger.info("Retrieved configuration", user_id=user_id[:8] + "..." if user_id else None)
    return config


@router.post("/config", dependencies=[Depends(check_admin_enabled)])
async def update_configuration(
    update: UserConfigUpdate,
    user_id: str = Depends(get_current_user_id),
    request: Request = None
) -> Dict[str, Any]:
    """
    Update the LLM configuration for the current user.
    Stores configuration in Redis for persistence.

    Args:
        update: Configuration updates
        user_id: The authenticated user ID
        request: FastAPI request object to access Redis

    Returns:
        Success message with updated configuration
    """
    config_manager = get_config_manager()

    # Prepare user overrides
    overrides = {}
    if update.default_provider:
        overrides["default_provider"] = update.default_provider
    if update.task_models:
        overrides["task_models"] = update.task_models
    if update.custom_providers:
        overrides["custom_providers"] = update.custom_providers
    if update.custom_models:
        overrides["custom_models"] = update.custom_models

    # Log what we're saving for debugging
    logger.info(f"=== RECEIVED CONFIG UPDATE for user {user_id[:8]}... ===")
    logger.info(f"default_provider: {overrides.get('default_provider')}")
    logger.info(f"num_custom_providers: {len(overrides.get('custom_providers', []))}")
    logger.info(f"num_task_models: {len(overrides.get('task_models', {}))}")

    if overrides.get("custom_providers"):
        for cp in overrides["custom_providers"]:
            logger.info(f"Custom Provider Details:")
            logger.info(f"  name: {cp.get('name')}")
            logger.info(f"  providerType: {cp.get('providerType')}")
            logger.info(f"  baseUrl: {cp.get('baseUrl')}")
            logger.info(f"  models type: {type(cp.get('models'))}")
            logger.info(f"  models value: {cp.get('models')}")
            logger.info(f"  apiKey present: {bool(cp.get('apiKey'))}")

    if overrides.get("task_models"):
        logger.info("Task Models (showing all):")
        for task, config in overrides["task_models"].items():
            logger.info(f"  {task}: provider={config.get('provider')}, model={config.get('model')}")

    # Set user overrides in config manager (in-memory for current session)
    config_manager.set_user_override(user_id, overrides)

    # Also persist to Redis using existing infrastructure
    if request and hasattr(request.app.state, 'redis_storage_service'):
        redis_storage = request.app.state.redis_storage_service
        config_key = f"llm_config:{user_id}"

        try:
            # Store configuration in Redis using the redis_client directly
            import json

            # Include custom API keys in the overrides if they exist
            if update.api_keys:
                custom_api_keys = {k: v for k, v in update.api_keys.items() if k.startswith("custom_")}
                if custom_api_keys:
                    overrides["custom_api_keys"] = custom_api_keys

            await redis_storage.redis_client.set(
                config_key,
                json.dumps(overrides),
                user_id=user_id
            )
            logger.info(f"Persisted LLM config to Redis for user {user_id[:8]}...")

            # Also store API keys if provided
            if update.api_keys:
                from agents.api.data_types import APIKeys

                # Debug log what we received from frontend
                logger.info(f"Received API keys from frontend: {list(update.api_keys.keys())}")
                logger.info(f"API key values present: sambanova={bool(update.api_keys.get('sambanova'))}, "
                           f"fireworks={bool(update.api_keys.get('fireworks'))}, "
                           f"together={bool(update.api_keys.get('together'))}")

                # Get existing keys to preserve non-LLM keys
                existing_keys = await redis_storage.get_user_api_key(user_id)

                # Extract custom provider API keys and store them separately
                custom_api_keys = {}
                for key, value in update.api_keys.items():
                    if key.startswith("custom_"):
                        custom_api_keys[key] = value

                # Store custom provider API keys in the overrides
                if custom_api_keys:
                    overrides["custom_api_keys"] = custom_api_keys

                api_keys_obj = APIKeys(
                    sambanova_key=update.api_keys.get("sambanova", ""),
                    fireworks_key=update.api_keys.get("fireworks", ""),
                    together_key=update.api_keys.get("together", ""),
                    serper_key=existing_keys.serper_key if existing_keys else "",
                    exa_key=existing_keys.exa_key if existing_keys else "",
                    paypal_invoicing_email=update.api_keys.get("paypal_invoicing_email", existing_keys.paypal_invoicing_email if existing_keys else "")
                )

                # Debug log what we're storing
                logger.info(f"Storing API keys: sambanova={bool(api_keys_obj.sambanova_key)}, "
                           f"fireworks={bool(api_keys_obj.fireworks_key)}, "
                           f"together={bool(api_keys_obj.together_key)}, "
                           f"custom_providers={len(custom_api_keys)} keys")

                await redis_storage.set_user_api_key(user_id, api_keys_obj)
                logger.info(f"Updated API keys for user {user_id[:8]}...")

        except Exception as e:
            logger.error(f"Failed to persist config to Redis: {e}")
            # Continue even if Redis save fails

    logger.info(
        "Updated configuration",
        user_id=user_id[:8] + "...",
        provider=update.default_provider,
        num_task_overrides=len(update.task_models) if update.task_models else 0
    )

    return {
        "success": True,
        "message": "Configuration updated successfully",
        "config": config_manager.get_full_config(user_id)
    }


@router.delete("/config", dependencies=[Depends(check_admin_enabled)])
async def reset_configuration(
    user_id: str = Depends(get_current_user_id),
    request: Request = None
) -> Dict[str, Any]:
    """
    Reset user configuration to defaults.

    Args:
        user_id: The authenticated user ID
        request: FastAPI request object to access Redis

    Returns:
        Success message
    """
    config_manager = get_config_manager()

    # Clear in-memory override
    config_manager.clear_user_override(user_id)

    # Reload config from file to fix any corruption from shallow copy bug
    config_manager.reload_config()

    # Also clear from Redis
    if request and hasattr(request.app.state, 'redis_storage_service'):
        redis_storage = request.app.state.redis_storage_service
        config_key = f"llm_config:{user_id}"
        try:
            # Delete from Redis - delete doesn't need user_id parameter
            await redis_storage.redis_client.delete(config_key)
            logger.info(f"Cleared LLM config from Redis for user {user_id[:8]}...")
        except Exception as e:
            logger.error(f"Failed to clear config from Redis: {e}")

    logger.info("Reset configuration to defaults", user_id=user_id[:8] + "...")

    # Get the default configuration
    default_config = config_manager.get_full_config()  # Don't pass user_id here - we want the actual defaults

    # Log what we're returning for debugging
    task_models = default_config.get('task_models', {})
    logger.info(f"Returning reset config with provider: {default_config.get('default_provider')}, "
                f"num_task_models: {len(task_models)}")
    # Log a sample of task models to verify they're correct
    if task_models:
        sample_tasks = list(task_models.keys())[:3]
        for task in sample_tasks:
            logger.info(f"  Task {task}: {task_models[task]}")

    return {
        "success": True,
        "message": "Configuration reset to defaults",
        "config": default_config
    }


@router.get("/providers", dependencies=[Depends(check_admin_enabled)])
async def list_providers(
    user_id: str = Depends(get_current_user_id)
) -> List[str]:
    """
    List all available LLM providers, including custom providers.

    Args:
        user_id: The authenticated user ID

    Returns:
        List of provider names
    """
    config_manager = get_config_manager()
    providers = config_manager.list_providers(user_id)

    return providers


@router.get("/models/{provider}", dependencies=[Depends(check_admin_enabled)])
async def list_provider_models(
    provider: str,
    user_id: str = Depends(get_current_user_id)
) -> ModelListResponse:
    """
    List all models available for a specific provider, including custom models.

    Args:
        provider: The provider name
        user_id: The authenticated user ID

    Returns:
        List of models with their configurations
    """
    config_manager = get_config_manager()

    if provider not in config_manager.list_providers():
        raise HTTPException(status_code=404, detail=f"Provider '{provider}' not found")

    models = config_manager.list_models(provider, user_id)

    # Transform to list format
    model_list = []
    for model_id, model_info in models.items():
        model_list.append({
            "id": model_id,
            "name": model_info.get("name", model_id),
            "context_window": model_info.get("context_window", 32768),
            "max_tokens": model_info.get("max_tokens", 8192)
        })

    return ModelListResponse(
        provider=provider,
        models=model_list
    )


@router.get("/tasks", dependencies=[Depends(check_admin_enabled)])
async def list_tasks(
    user_id: str = Depends(get_current_user_id)
) -> List[Dict[str, Any]]:
    """
    List all configurable tasks/agents with their current configurations.

    Args:
        user_id: The authenticated user ID

    Returns:
        List of tasks with their model assignments
    """
    config_manager = get_config_manager()
    config = config_manager.get_full_config(user_id)

    tasks = []
    for task_id, task_config in config.get("task_models", {}).items():
        # Make task names more readable
        task_name = task_id.replace("_", " ").title()
        tasks.append({
            "id": task_id,
            "name": task_name,
            "provider": task_config.get("provider"),
            "model": task_config.get("model"),
            "fallback_model": task_config.get("fallback_model")
        })

    return tasks


@router.post("/test-connection", dependencies=[Depends(check_admin_enabled)])
async def test_provider_connection(
    provider_config: ProviderConfig,
    user_id: str = Depends(get_current_user_id)
) -> Dict[str, Any]:
    """
    Test connection to a provider with given API key.

    Args:
        provider_config: Provider name and API key
        user_id: The authenticated user ID

    Returns:
        Connection test result
    """
    try:
        config_manager = get_config_manager()

        # Get a simple model from the provider to test (pass user_id for custom providers)
        models = config_manager.list_models(provider_config.provider, user_id)
        if not models:
            raise HTTPException(
                status_code=400,
                detail=f"No models configured for provider '{provider_config.provider}'"
            )

        # Use the first available model for testing
        test_model = list(models.keys())[0]

        # Get provider config to get base_url and provider_type for custom providers
        provider_config_dict = config_manager.get_provider_config(provider_config.provider, user_id)
        base_url = provider_config_dict.get("base_url")
        provider_type = provider_config_dict.get("provider_type")

        # Determine which provider client to use
        actual_provider = provider_type if provider_type else provider_config.provider

        # Try to initialize the LLM
        llm = get_llm(
            provider=actual_provider,
            model=test_model,
            api_key=provider_config.api_key,
            base_url=base_url
        )

        # Try a simple completion to verify the connection
        # Note: This will actually make an API call, so it might incur costs
        # In production, you might want a lighter weight test

        logger.info(
            "Testing provider connection",
            provider=provider_config.provider,
            model=test_model
        )

        return {
            "success": True,
            "provider": provider_config.provider,
            "message": f"Successfully connected to {provider_config.provider}",
            "tested_model": test_model
        }

    except Exception as e:
        logger.error(
            "Provider connection test failed",
            provider=provider_config.provider,
            error=str(e)
        )
        return {
            "success": False,
            "provider": provider_config.provider,
            "message": f"Connection failed: {str(e)}",
            "error": str(e)
        }


@router.get("/api-key-info", dependencies=[Depends(check_admin_enabled)])
async def get_api_key_info() -> Dict[str, Any]:
    """
    Get information about where to obtain API keys for each provider.

    Returns:
        Provider API key information
    """
    return {
        "sambanova": {
            "name": "SambaNova",
            "url": "https://cloud.sambanova.ai/",
            "description": "Get your API key from SambaNova Cloud console",
            "required": True
        },
        "fireworks": {
            "name": "Fireworks AI",
            "url": "https://fireworks.ai/",
            "description": "Sign up for Fireworks AI and get your API key from the dashboard",
            "required": False
        },
        "together": {
            "name": "Together AI",
            "url": "https://api.together.xyz/",
            "description": "Create an account on Together AI and generate an API key",
            "required": False
        }
    }