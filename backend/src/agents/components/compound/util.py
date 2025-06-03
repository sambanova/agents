from langchain_core.runnables import RunnableConfig


def extract_api_key(config: RunnableConfig = None):
    """Extract api_key from config"""
    if config and "configurable" in config:
        return config["configurable"].get("api_key")
    return None
