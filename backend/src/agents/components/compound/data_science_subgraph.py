from agents.components.datagen.tools.persistent_daytona import PersistentDaytonaManager
from agents.components.datagen.workflow import WorkflowManager
from agents.storage.redis_storage import RedisStorage
from agents.utils.llms import get_sambanova_llm


def setup_language_models(sambanova_api_key: str):
    """Set up the language models needed for the workflow"""

    # Initialize language models
    llm = get_sambanova_llm(sambanova_api_key, "DeepSeek-V3-0324")
    power_llm = get_sambanova_llm(sambanova_api_key, "DeepSeek-V3-0324")
    json_llm = get_sambanova_llm(sambanova_api_key, "DeepSeek-V3-0324")

    return {"llm": llm, "power_llm": power_llm, "json_llm": json_llm}


def create_data_science_subgraph(
    user_id: str,
    sambanova_api_key: str,
    redis_storage: RedisStorage,
    daytona_manager: PersistentDaytonaManager,
):
    language_models = setup_language_models(sambanova_api_key)
    manager = WorkflowManager(language_models, user_id, redis_storage, daytona_manager)

    return manager.graph
