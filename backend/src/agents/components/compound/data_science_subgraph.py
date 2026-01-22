from agents.components.datagen.tools.persistent_daytona import PersistentDaytonaManager
from agents.components.datagen.workflow import WorkflowManager
from agents.storage.redis_storage import RedisStorage
from agents.utils.llms import get_sambanova_llm
from langgraph.types import Checkpointer
import os
from typing import Optional, Dict

# Import new config system but maintain backward compatibility
try:
    from agents.config.llm_config_manager import get_config_manager
    from agents.utils.llm_provider import get_llm_for_task
    CONFIG_SYSTEM_AVAILABLE = True
except ImportError:
    CONFIG_SYSTEM_AVAILABLE = False


def setup_language_models(
    sambanova_api_key: str,
    user_id: Optional[str] = None,
    api_keys: Optional[Dict] = None,
    llm_overrides: Optional[Dict] = None,
):
    """Set up the language models needed for the workflow"""

    # Check if admin panel is enabled and config system is available
    admin_enabled = os.getenv("SHOW_ADMIN_PANEL", "false").lower() == "true"

    if CONFIG_SYSTEM_AVAILABLE and user_id and (admin_enabled or llm_overrides or api_keys):
        # Use new config system when admin panel is enabled
        config_manager = get_config_manager()
        # Use provided api_keys dict if available, otherwise create from sambanova_api_key
        if api_keys is None:
            api_keys = {"sambanova": sambanova_api_key}

        report_agent_llm = get_llm_for_task(
            "data_science_report", api_keys, config_manager, user_id, overrides=llm_overrides
        )
        code_agent_llm = get_llm_for_task(
            "data_science_code", api_keys, config_manager, user_id, overrides=llm_overrides
        )
        note_agent_llm = get_llm_for_task(
            "data_science_note", api_keys, config_manager, user_id, overrides=llm_overrides
        )
        process_agent_llm = get_llm_for_task(
            "data_science_process", api_keys, config_manager, user_id, overrides=llm_overrides
        )
        hypothesis_agent_llm = get_llm_for_task(
            "data_science_hypothesis", api_keys, config_manager, user_id, overrides=llm_overrides
        )
        quality_review_agent_llm = get_llm_for_task(
            "data_science_quality_review", api_keys, config_manager, user_id, overrides=llm_overrides
        )
        refiner_agent_llm = get_llm_for_task(
            "data_science_refiner", api_keys, config_manager, user_id, overrides=llm_overrides
        )
        visualization_agent_llm = get_llm_for_task(
            "data_science_visualization", api_keys, config_manager, user_id, overrides=llm_overrides
        )
        searcher_agent_llm = get_llm_for_task(
            "data_science_searcher", api_keys, config_manager, user_id, overrides=llm_overrides
        )
        human_choice_llm = get_llm_for_task(
            "data_science_human_choice", api_keys, config_manager, user_id, overrides=llm_overrides
        )
    else:
        # Use default SambaNova configuration (original behavior)
        report_agent_llm = get_sambanova_llm(sambanova_api_key, "DeepSeek-V3-0324")
        code_agent_llm = get_sambanova_llm(sambanova_api_key, "DeepSeek-V3-0324")
        note_agent_llm = get_sambanova_llm(sambanova_api_key, "Meta-Llama-3.3-70B-Instruct")
        process_agent_llm = get_sambanova_llm(sambanova_api_key, "Qwen3-32B")
        hypothesis_agent_llm = get_sambanova_llm(sambanova_api_key, "DeepSeek-V3-0324")
        quality_review_agent_llm = get_sambanova_llm(
            sambanova_api_key, "Llama-4-Maverick-17B-128E-Instruct"
        )
        refiner_agent_llm = get_sambanova_llm(sambanova_api_key, "DeepSeek-R1-0528")
        visualization_agent_llm = get_sambanova_llm(sambanova_api_key, "DeepSeek-V3-0324")
        searcher_agent_llm = get_sambanova_llm(sambanova_api_key, "DeepSeek-V3-0324")
        human_choice_llm = get_sambanova_llm(
            sambanova_api_key, "DeepSeek-R1-Distill-Llama-70B"
        )

    return {
        "report_agent_llm": report_agent_llm,
        "code_agent_llm": code_agent_llm,
        "note_agent_llm": note_agent_llm,
        "hypothesis_agent_llm": hypothesis_agent_llm,
        "process_agent_llm": process_agent_llm,
        "quality_review_agent_llm": quality_review_agent_llm,
        "refiner_agent_llm": refiner_agent_llm,
        "visualization_agent_llm": visualization_agent_llm,
        "searcher_agent_llm": searcher_agent_llm,
        "human_choice_llm": human_choice_llm,
    }


def create_data_science_subgraph(
    user_id: str,
    sambanova_api_key: str,
    redis_storage: RedisStorage,
    daytona_manager: PersistentDaytonaManager,
    directory_content: list[str],
    checkpointer: Checkpointer = None,
    api_keys: Optional[Dict] = None,
    llm_overrides: Optional[Dict] = None,
):
    language_models = setup_language_models(
        sambanova_api_key, user_id, api_keys, llm_overrides
    )
    manager = WorkflowManager(
        language_models,
        user_id,
        redis_storage,
        daytona_manager,
        directory_content,
        checkpointer,
    )

    return manager.graph
