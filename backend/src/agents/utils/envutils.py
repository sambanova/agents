import os
from typing import Optional, Dict, Any
from dotenv import load_dotenv

class EnvUtils:
    """
    Utility class for managing non-sensitive environment variables and configuration
    """
    _instance = None
    _env_loaded = False

    def __new__(cls):
        """
        Singleton implementation to ensure env is loaded only once
        """
        if not cls._instance:
            cls._instance = super(EnvUtils, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        """
        Load environment variables if not already loaded
        """
        if not self._env_loaded:
            load_dotenv()
            self.__class__._env_loaded = True

    def get_env(self, key: str, default: Any = None) -> Optional[str]:
        """Get non-sensitive environment variable"""
        return os.getenv(key, default)

    def get_config(self, config_map: Dict[str, Any]) -> Dict[str, Any]:
        """Get multiple non-sensitive configurations with defaults"""
        return {
            key: self.get_env(key, default) 
            for key, default in config_map.items()
        }

# Example usage
def main():
    # Initialize EnvUtils (will load .env)
    env_utils = EnvUtils()

    # Get a specific environment variable
    api_key = env_utils.get_env('PERPLEXITY_API_KEY')
    print(f"Perplexity API Key: {api_key}")

    # Get a required environment variable (will raise ValueError if not set)
    try:
        required_key = env_utils.get_env('REQUIRED_KEY')
    except ValueError as e:
        print(e)

    # Get multiple configurations with defaults
    config = env_utils.get_config({
        'DATABASE_URL': 'localhost',
        'PORT': 8000,
        'DEBUG': False
    })
    print("Configuration:", config)

if __name__ == "__main__":
    main()