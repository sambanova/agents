import json
import os
from typing import Dict, Any, Tuple

class ModelRegistry:
    def __init__(self, config_path: str = None):
        if config_path is None:
            config_path = os.path.join(os.path.dirname(__file__), "model_config.json")
        self.config_path = config_path
        self._config = self._load_config()

    def _load_config(self) -> Dict[str, Any]:
        """Load the configuration from JSON file."""
        try:
            with open(self.config_path, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            raise FileNotFoundError(f"Model configuration file not found at {self.config_path}")

    def get_model_info(self, model_key: str, provider: str) -> str:
        """
        Get the actual model name for the given provider and model key.
        
        Args:
            provider: The LLM provider to use
            model_key: The key of the model in the configuration
            
        Returns:
            str: The actual model name
            
        Raises:
            ValueError: If the provider or model_key is not found in configuration
        """
        provider_config = self._config["providers"].get(provider)
        
        if not provider_config:
            raise ValueError(f"Provider {provider} not found in configuration")

        model_mapping = provider_config["model_mapping"]
        model_name = model_mapping.get(model_key)

        if not model_name:
            raise ValueError(f"No model found for key {model_key} with provider {provider}")

        return model_name

    def get_api_key_env(self, provider: str) -> str:
        """
        Get the environment variable name for the API key of the specified provider.
        
        Args:
            provider: The LLM provider to get the API key environment variable for
            
        Returns:
            str: The name of the environment variable containing the API key
            
        Raises:
            ValueError: If the provider is not found in configuration
        """
        provider_config = self._config["providers"].get(provider)
        
        if not provider_config:
            raise ValueError(f"Provider {provider} not found in configuration")

        return provider_config["api_key_env"]

    def list_available_models(self, provider: str) -> Dict[str, str]:
        """
        List all available models for the specified provider.
        
        Args:
            provider: The LLM provider to list models for
            
        Returns:
            Dict[str, str]: A mapping of model keys to actual model names
            
        Raises:
            ValueError: If the provider is not found in configuration
        """
        provider_config = self._config["providers"].get(provider)
        
        if not provider_config:
            raise ValueError(f"Provider {provider} not found in configuration")

        return provider_config["model_mapping"]

# Global instance
model_registry = ModelRegistry() 