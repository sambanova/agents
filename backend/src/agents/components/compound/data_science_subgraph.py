from agents.components.datagen.tools.persistent_daytona import PersistentDaytonaManager
from agents.components.datagen.workflow import WorkflowManager
from agents.storage.redis_storage import RedisStorage
from agents.utils.llms import get_sambanova_llm


def setup_language_models(sambanova_api_key: str):
    """Set up the language models needed for the workflow"""

    # Initialize language models
    llm = get_sambanova_llm(sambanova_api_key, "DeepSeek-V3-0324")
    power_llm = get_sambanova_llm(sambanova_api_key, "DeepSeek-V3-0324")
    report_agent_llm = get_sambanova_llm(
        sambanova_api_key, "Meta-Llama-3.3-70B-Instruct"
    )
    code_agent_llm = get_sambanova_llm(sambanova_api_key, "DeepSeek-R1-0528")
    note_agent_llm = get_sambanova_llm(
        sambanova_api_key, "Llama-4-Maverick-17B-128E-Instruct"
    )
    process_agent_llm = get_sambanova_llm(
        sambanova_api_key, "Meta-Llama-3.1-8B-Instruct"
    )
    hypothesis_agent_llm = get_sambanova_llm(sambanova_api_key, "DeepSeek-V3-0324")

    return {
        "llm": llm,
        "power_llm": power_llm,
        "report_agent_llm": report_agent_llm,
        "code_agent_llm": code_agent_llm,
        "note_agent_llm": note_agent_llm,
        "hypothesis_agent_llm": hypothesis_agent_llm,
        "process_agent_llm": process_agent_llm,
    }


def create_data_science_subgraph(
    user_id: str,
    sambanova_api_key: str,
    redis_storage: RedisStorage,
    daytona_manager: PersistentDaytonaManager,
    directory_content: list[str],
):
    language_models = setup_language_models(sambanova_api_key)
    manager = WorkflowManager(
        language_models,
        user_id,
        redis_storage,
        daytona_manager,
        directory_content,
    )

    return manager.graph
