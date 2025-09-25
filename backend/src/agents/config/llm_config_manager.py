"""
LLM Configuration Manager
Handles dynamic LLM provider and model configurations
API keys are passed dynamically from frontend, not stored
"""

import json
import os
from typing import Dict, Any, Optional
import yaml
from functools import lru_cache
import structlog

logger = structlog.get_logger(__name__)

class LLMConfigManager:
    """
    Manages LLM provider configurations and model mappings.
    Supports dynamic provider switching without storing API keys.
    """

    # Default configuration that matches current hardcoded setup
    DEFAULT_CONFIG = {
        "default_provider": "sambanova",
        "providers": {
            "sambanova": {
                "base_url": "https://api.sambanova.ai/v1",
                "models": {
                    "Meta-Llama-3.3-70B-Instruct": {"name": "Llama 3.3 70B", "context_window": 32768, "max_tokens": 8192},
                    "Meta-Llama-3.1-70B-Instruct": {"name": "Llama 3.1 70B", "context_window": 32768, "max_tokens": 8192},
                    "Meta-Llama-3.1-8B-Instruct": {"name": "Llama 3.1 8B", "context_window": 32768, "max_tokens": 8192},
                    "DeepSeek-V3-0324": {"name": "DeepSeek V3", "context_window": 32768, "max_tokens": 8192},
                    "DeepSeek-R1-Distill-Llama-70B": {"name": "DeepSeek R1 Distill", "context_window": 32768, "max_tokens": 8192},
                    "DeepSeek-R1-0528": {"name": "DeepSeek R1", "context_window": 32768, "max_tokens": 8192},
                    "Meta-Llama-3.1-405B-Instruct": {"name": "Llama 3.1 405B", "context_window": 32768, "max_tokens": 8192},
                    "Llama-4-Maverick-17B-128E-Instruct": {"name": "Llama 4 Maverick", "context_window": 16384, "max_tokens": 7000},
                    "gpt-oss-120b": {"name": "GPT OSS 120B", "context_window": 128000, "max_tokens": 16384},
                    "Qwen3-32B": {"name": "Qwen3 32B", "context_window": 32768, "max_tokens": 8192}
                }
            },
            "fireworks": {
                "base_url": "https://api.fireworks.ai/inference/v1",
                "models": {
                    "fireworks/llama-v3.3-70b-instruct": {"name": "Llama 3.3 70B", "context_window": 128000, "max_tokens": 8192},
                    "fireworks/llama-v3.1-70b-instruct": {"name": "Llama 3.1 70B", "context_window": 128000, "max_tokens": 8192},
                    "fireworks/llama-v3.1-8b-instruct": {"name": "Llama 3.1 8B", "context_window": 128000, "max_tokens": 8192},
                    "fireworks/llama-v3.1-405b-instruct": {"name": "Llama 3.1 405B", "context_window": 128000, "max_tokens": 8192},
                    "fireworks/deepseek-v3": {"name": "DeepSeek V3", "context_window": 128000, "max_tokens": 8192},
                    "fireworks/deepseek-r1": {"name": "DeepSeek R1", "context_window": 128000, "max_tokens": 8192},
                    "fireworks/qwen2.5-coder-32b-instruct": {"name": "Qwen 2.5 32B", "context_window": 128000, "max_tokens": 8192}
                }
            },
            "together": {
                "base_url": "https://api.together.xyz/v1",
                "models": {
                    "meta-llama/Llama-3.3-70B-Instruct": {"name": "Llama 3.3 70B", "context_window": 128000, "max_tokens": 8192},
                    "meta-llama/Llama-3.1-70B-Instruct-Turbo": {"name": "Llama 3.1 70B Turbo", "context_window": 128000, "max_tokens": 8192},
                    "meta-llama/Llama-3.1-8B-Instruct-Turbo": {"name": "Llama 3.1 8B Turbo", "context_window": 128000, "max_tokens": 8192},
                    "meta-llama/Llama-3.1-405B-Instruct-Turbo": {"name": "Llama 3.1 405B Turbo", "context_window": 128000, "max_tokens": 8192},
                    "deepseek-ai/DeepSeek-V3": {"name": "DeepSeek V3", "context_window": 128000, "max_tokens": 8192},
                    "deepseek-ai/DeepSeek-R1": {"name": "DeepSeek R1", "context_window": 128000, "max_tokens": 8192},
                    "deepseek-ai/DeepSeek-R1-Distill-Llama-70B": {"name": "DeepSeek R1 Distill", "context_window": 128000, "max_tokens": 8192},
                    "Qwen/Qwen2.5-Coder-32B-Instruct": {"name": "Qwen 2.5 32B", "context_window": 128000, "max_tokens": 8192}
                }
            }
        },
        "task_models": {
            "main_agent": {"provider": "sambanova", "model": "DeepSeek-V3-0324", "fallback_model": "gpt-oss-120b"},
            "data_science_agent": {"provider": "sambanova", "model": "DeepSeek-V3-0324"},
            "data_science_report": {"provider": "sambanova", "model": "DeepSeek-V3-0324"},
            "data_science_code": {"provider": "sambanova", "model": "DeepSeek-V3-0324"},
            "data_science_note": {"provider": "sambanova", "model": "Meta-Llama-3.3-70B-Instruct"},
            "data_science_process": {"provider": "sambanova", "model": "Qwen3-32B"},
            "data_science_hypothesis": {"provider": "sambanova", "model": "DeepSeek-V3-0324"},
            "data_science_quality_review": {"provider": "sambanova", "model": "Llama-4-Maverick-17B-128E-Instruct"},
            "data_science_refiner": {"provider": "sambanova", "model": "DeepSeek-R1-0528"},
            "data_science_visualization": {"provider": "sambanova", "model": "DeepSeek-V3-0324"},
            "data_science_searcher": {"provider": "sambanova", "model": "DeepSeek-V3-0324"},
            "data_science_human_choice": {"provider": "sambanova", "model": "DeepSeek-R1-Distill-Llama-70B"},
            "daytona_agent": {"provider": "sambanova", "model": "Meta-Llama-3.3-70B-Instruct"},
            "code_execution_agent": {"provider": "sambanova", "model": "DeepSeek-V3-0324"},
            "research_agent": {"provider": "sambanova", "model": "Meta-Llama-3.3-70B-Instruct"},
            "financial_analysis_agent": {"provider": "sambanova", "model": "Meta-Llama-3.3-70B-Instruct"},
            "vision_agent": {"provider": "sambanova", "model": "Llama-4-Maverick-17B-128E-Instruct"},
            "crewai_default": {"provider": "sambanova", "model": "Meta-Llama-3.1-70B-Instruct"},
            "crewai_competitor_finder": {"provider": "sambanova", "model": "Meta-Llama-3.1-70B-Instruct"},
            "crewai_aggregator": {"provider": "sambanova", "model": "Meta-Llama-3.1-70B-Instruct"},
            "deep_research_planner": {"provider": "sambanova", "model": "Meta-Llama-3.1-70B-Instruct"},
            "deep_research_writer": {"provider": "sambanova", "model": "Meta-Llama-3.3-70B-Instruct"},
            "deep_research_summary": {"provider": "sambanova", "model": "Meta-Llama-3.1-70B-Instruct"}
        }
    }

    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize the configuration manager.

        Args:
            config_path: Optional path to a YAML config file. If not provided,
                        will look for config/llm_config.yaml or use defaults.
        """
        self.config_path = config_path or self._find_config_file()
        self.config = self._load_config()
        self._user_overrides = {}  # Store user-specific overrides
        self._load_model_mappings()  # Load cross-provider model mappings

    def _find_config_file(self) -> Optional[str]:
        """Find the config file in common locations."""
        possible_paths = [
            "src/agents/config/llm_config.yaml",
            "agents/config/llm_config.yaml",
            "config/llm_config.yaml",
            "../config/llm_config.yaml",
            "../../config/llm_config.yaml",
            "/app/src/agents/config/llm_config.yaml",  # Docker path
        ]

        for path in possible_paths:
            if os.path.exists(path):
                logger.info(f"Found config file at: {path}")
                return path

        logger.info("No config file found, using defaults")
        return None

    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from file or use defaults."""
        if self.config_path and os.path.exists(self.config_path):
            try:
                with open(self.config_path, 'r') as f:
                    config = yaml.safe_load(f)
                    logger.info(f"Loaded config from {self.config_path}")
                    return config
            except Exception as e:
                logger.error(f"Error loading config from {self.config_path}: {e}")

        return self.DEFAULT_CONFIG.copy()

    def _load_model_mappings(self):
        """Load model mappings from configuration."""
        self.model_mappings = self.config.get("model_mappings", {})

    def _map_models_to_provider(self, task_models: Dict[str, Any], new_provider: str) -> Dict[str, Any]:
        """
        Map task models to equivalent models for a new provider.

        Args:
            task_models: Current task model configuration
            new_provider: The new provider to map to

        Returns:
            Updated task models with mapped model IDs
        """
        mapped_models = {}

        for task, model_config in task_models.items():
            if isinstance(model_config, dict):
                current_model = model_config.get("model")
                mapped = False

                # Find which logical model this actual model ID corresponds to
                for logical_model, provider_mappings in self.model_mappings.items():
                    # Check each provider's mapping
                    for provider, provider_model_id in provider_mappings.items():
                        if provider_model_id == current_model:
                            # Found the logical model, now get the equivalent for new provider
                            if new_provider in provider_mappings:
                                mapped_models[task] = {
                                    "provider": new_provider,
                                    "model": provider_mappings[new_provider]
                                }
                                mapped = True
                                break
                    if mapped:
                        break

                # If no mapping found, keep the same model config but update provider
                # This handles cases where a model doesn't have an equivalent
                if not mapped:
                    logger.warning(
                        f"No mapping found for model {current_model} to provider {new_provider}, "
                        f"keeping same model ID for task {task}"
                    )
                    mapped_models[task] = {
                        "provider": new_provider,
                        "model": current_model  # Keep same model ID as fallback
                    }

        return mapped_models

    def get_provider_config(self, provider: str, user_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Get configuration for a specific provider, including user overrides.

        Args:
            provider: The provider name
            user_id: Optional user ID for user-specific overrides

        Returns:
            Provider configuration with overrides applied
        """
        base_config = self.config["providers"].get(provider, {}).copy()

        # Apply user-specific base URL override if present
        if user_id and user_id in self._user_overrides:
            user_config = self._user_overrides[user_id]

            # Check for provider-specific base URL override
            if "provider_base_urls" in user_config and provider in user_config["provider_base_urls"]:
                base_config["base_url"] = user_config["provider_base_urls"][provider]
                logger.debug(f"Using custom base URL for {provider}: {base_config['base_url']}")

            # Check for custom models added by the user
            if "custom_models" in user_config and provider in user_config["custom_models"]:
                if "models" not in base_config:
                    base_config["models"] = {}
                # Merge custom models into the provider's model list
                base_config["models"].update(user_config["custom_models"][provider])
                logger.debug(f"Added custom models for {provider}: {list(user_config['custom_models'][provider].keys())}")

        return base_config

    def get_task_model(self, task: str, user_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Get the model configuration for a specific task.

        Args:
            task: The task identifier (e.g., 'main_agent', 'data_science_agent')
            user_id: Optional user ID for user-specific overrides

        Returns:
            Dict with provider, model, and optionally base_url information
        """
        # Check user overrides first
        if user_id and user_id in self._user_overrides:
            user_config = self._user_overrides[user_id].get("task_models", {})
            if task in user_config:
                result = user_config[task].copy()

                # Check for task-specific base URL override
                task_base_urls = self._user_overrides[user_id].get("task_base_urls", {})
                if task in task_base_urls:
                    result["base_url"] = task_base_urls[task]
                    logger.debug(f"Task {task} using custom base URL: {result['base_url']}")

                logger.debug(f"Task {task} for user {user_id[:8]}... using override: provider={result.get('provider')}, model={result.get('model')}")
                return result

        # Fall back to default config
        result = self.config["task_models"].get(task, {
            "provider": self.config["default_provider"],
            "model": list(self.config["providers"][self.config["default_provider"]]["models"].keys())[0]
        }).copy()
        logger.debug(f"Task {task} for user {user_id[:8] if user_id else 'default'}... using default: provider={result.get('provider')}, model={result.get('model')}")
        return result

    def set_user_override(self, user_id: str, overrides: Dict[str, Any]):
        """
        Set user-specific configuration overrides.

        Args:
            user_id: The user identifier
            overrides: Configuration overrides for this user
                     Can include: default_provider, task_models, provider_base_urls, custom_models
        """
        # If provider changed, map models to new provider equivalents
        if "default_provider" in overrides and "task_models" in self.config:
            new_provider = overrides["default_provider"]
            # Only map if we have model mappings configured
            if hasattr(self, 'model_mappings') and self.model_mappings:
                current_task_models = overrides.get("task_models", self.config.get("task_models", {}))
                overrides["task_models"] = self._map_models_to_provider(
                    current_task_models, new_provider
                )

        self._user_overrides[user_id] = overrides
        logger.info(f"Set config overrides for user {user_id[:8]}...")

    def clear_user_override(self, user_id: str):
        """Clear user-specific overrides."""
        if user_id in self._user_overrides:
            # Log what we're clearing for debugging
            logger.info(f"Clearing config overrides for user {user_id[:8]}..., had provider: {self._user_overrides[user_id].get('default_provider', 'none')}")
            del self._user_overrides[user_id]
            logger.info(f"Successfully cleared config overrides for user {user_id[:8]}...")

    def reload_config(self):
        """Reload configuration from file to fix any corruption from shallow copy bug."""
        logger.info("Reloading configuration from file to restore original values")
        self.config = self._load_config()
        self._load_model_mappings()

    def has_user_override(self, user_id: str) -> bool:
        """Check if user has overrides configured."""
        return user_id in self._user_overrides and bool(self._user_overrides[user_id])

    def get_model_info(self, provider: str, model_id: str) -> Dict[str, Any]:
        """Get detailed information about a specific model."""
        provider_config = self.get_provider_config(provider)
        models = provider_config.get("models", {})
        return models.get(model_id, {})

    def list_providers(self) -> list:
        """List all available providers."""
        return list(self.config["providers"].keys())

    def list_models(self, provider: str, user_id: Optional[str] = None) -> Dict[str, Any]:
        """
        List all models available for a provider, including custom models.

        Args:
            provider: The provider name
            user_id: Optional user ID for user-specific custom models

        Returns:
            Dictionary of models with their configurations
        """
        provider_config = self.get_provider_config(provider, user_id)
        return provider_config.get("models", {})

    def get_full_config(self, user_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Get the full configuration, optionally with user overrides applied.

        Args:
            user_id: Optional user ID for user-specific overrides

        Returns:
            The complete configuration
        """
        # Deep copy to avoid modifying the original config
        import copy
        config = copy.deepcopy(self.config)

        # Apply user overrides if available
        if user_id and user_id in self._user_overrides:
            user_config = self._user_overrides[user_id]
            # Deep merge the configurations
            if "task_models" in user_config:
                config["task_models"].update(user_config["task_models"])
            if "default_provider" in user_config:
                config["default_provider"] = user_config["default_provider"]

        return config

    def save_config(self, config: Dict[str, Any], path: Optional[str] = None):
        """
        Save configuration to a YAML file.

        Args:
            config: The configuration to save
            path: Optional path to save to. If not provided, uses the current config_path
        """
        save_path = path or self.config_path or "config/llm_config.yaml"

        # Ensure directory exists
        os.makedirs(os.path.dirname(save_path), exist_ok=True)

        try:
            with open(save_path, 'w') as f:
                yaml.dump(config, f, default_flow_style=False, sort_keys=False)
            logger.info(f"Saved config to {save_path}")
        except Exception as e:
            logger.error(f"Error saving config to {save_path}: {e}")
            raise

# Global instance
_config_manager = None

def get_config_manager() -> LLMConfigManager:
    """Get the global config manager instance."""
    global _config_manager
    if _config_manager is None:
        _config_manager = LLMConfigManager()
    return _config_manager