from langchain_core.runnables import RunnableConfig
from pydantic import SecretStr


def secret_api_key(api_key):
    """Wrap an API key for ``configurable`` so it is not copied into run metadata."""
    return SecretStr(api_key) if api_key else api_key


def extract_api_key(config: RunnableConfig = None):
    """Extract api_key from config"""
    if config and "configurable" in config:
        api_key = config["configurable"].get("api_key")
        if isinstance(api_key, SecretStr):
            return api_key.get_secret_value()
        return api_key
    return None


def extract_api_keys(config: RunnableConfig = None):
    """Extract api_keys dict from config (when admin panel is enabled)"""
    if config and "configurable" in config:
        return config["configurable"].get("api_keys")
    return None


def extract_user_id(config: RunnableConfig = None):
    """Extract user_id from config"""
    if config and "configurable" in config:
        return config["configurable"].get("user_id")
    return None
