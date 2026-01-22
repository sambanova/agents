from langchain_core.runnables import RunnableConfig


def extract_api_key(config: RunnableConfig = None):
    """Extract api_key from config"""
    if config and "configurable" in config:
        return config["configurable"].get("api_key")
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


def extract_llm_overrides(config: RunnableConfig = None):
    """Extract request-scoped llm_overrides from config"""
    if config and "configurable" in config:
        return config["configurable"].get("llm_overrides")
    return None
