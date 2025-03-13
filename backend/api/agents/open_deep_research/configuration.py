########## configuration.py (NEW FILE) ##########
import os
from enum import Enum
from dataclasses import dataclass, field, fields
from typing import Any, Callable, Optional

from langchain_core.runnables import RunnableConfig
from typing_extensions import Annotated
from dataclasses import dataclass

from api.agents.open_deep_research.utils import APIKeyRotator
from config.model_registry import model_registry


DEFAULT_REPORT_STRUCTURE = """The report structure should focus on breaking-down the user-provided topic:

1. Introduction (research needed)
    - Brief overview of the topic area
2. Main Body Sections:
    - Each section should focus on a sub-topic of the user-provided topic
    - Include any key concepts and definitions
    - Provide real-world examples or case studies where applicable
3. Conclusion
    - Aim for 1 structural element (either a list or table) that distills the main body sections
    - Provide a concise summary of the report"""


class SearchAPI(Enum):
    PERPLEXITY = "perplexity"
    TAVILY = "tavily"


@dataclass(kw_only=True)
class Configuration:
    """The configurable fields for the chatbot."""

    report_structure: str = (
        DEFAULT_REPORT_STRUCTURE  # Defaults to the default report structure
    )
    number_of_queries: int = 1  # Number of search queries to generate per iteration
    max_search_depth: int = 1 # Maximum number of reflection + search iterations
    search_api: SearchAPI = SearchAPI.TAVILY  # Default to TAVILY
    api_key_rotator: Optional[APIKeyRotator] = APIKeyRotator(env_var_prefix="TAVILY_API_KEY")
    callback: Optional[Callable] = None  # Callback function for publishing messages
    user_id: Optional[str] = None  # User ID
    conversation_id: Optional[str] = None  # Conversation ID    
    provider: Optional[str] = None  # Provider
    

    @classmethod
    def from_runnable_config(
        cls, config: Optional[RunnableConfig] = None
    ) -> "Configuration":
        """Create a Configuration instance from a RunnableConfig."""
        configurable = (
            config["configurable"] if config and "configurable" in config else {}
        )
        values: dict[str, Any] = {
            f.name: os.environ.get(f.name.upper(), configurable.get(f.name))
            for f in fields(cls)
            if f.init and f.name != "redis_client"  # Skip redis_client from env vars
        }
        # Add redis client if present in configurable
        if configurable and "callback" in configurable:
            values["callback"] = configurable["callback"]
        if configurable and "user_id" in configurable:
            values["user_id"] = configurable["user_id"]
        if configurable and "conversation_id" in configurable:
            values["conversation_id"] = configurable["conversation_id"]
        if configurable and "provider" in configurable:
            values["provider"] = configurable["provider"]

        return cls(**{k: v for k, v in values.items() if v})
