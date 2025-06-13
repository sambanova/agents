import os
from typing import Any, Dict, Optional

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
        return {key: self.get_env(key, default) for key, default in config_map.items()}
