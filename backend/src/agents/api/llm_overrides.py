import json
from typing import Dict, Optional, Tuple

from pydantic import BaseModel


class TaskModelOverride(BaseModel):
    """
    Per-task LLM override.

    Use this to target a specific provider/model/base_url for a single task,
    e.g. deep_research_writer or deep_research_planner.
    """

    provider: Optional[str] = None
    model: Optional[str] = None
    base_url: Optional[str] = None
    provider_type: Optional[str] = None


class LLMOverrides(BaseModel):
    """
    Request-scoped LLM configuration overrides.

    Precedence:
      1) task_models overrides (per task)
      2) top-level overrides (provider/model/base_url/provider_type)
      3) server defaults/config manager

    Notes:
      - api_keys is optional and not required for typical usage.
      - If api_keys is omitted, the Authorization Bearer token is used as
        the fallback key for the selected provider.
      - api_keys is a map of provider name -> key. Provider names must match:
        - top-level provider (provider)
        - any per-task provider in task_models
        - any custom provider names configured in the system
    """

    provider: Optional[str] = None
    model: Optional[str] = None
    base_url: Optional[str] = None
    provider_type: Optional[str] = None
    api_keys: Optional[Dict[str, str]] = None
    task_models: Optional[Dict[str, TaskModelOverride]] = None


def parse_llm_config_json(llm_config_json: Optional[str]) -> Optional[LLMOverrides]:
    """
    Parse llm_config_json (stringified JSON) into LLMOverrides.
    Returns None when not provided.
    """
    if not llm_config_json:
        return None

    data = json.loads(llm_config_json)
    return LLMOverrides.model_validate(data)


def resolve_llm_overrides(
    api_key: str,
    llm_config: Optional[LLMOverrides],
) -> Tuple[Dict[str, str], Optional[dict], str]:
    """
    Resolve request-scoped LLM overrides into api_keys and override maps.

    If api_keys is not provided, the Authorization Bearer token is used as the
    fallback key for the chosen provider and any task-specific providers.
    If api_keys is provided, its keys must match the provider names used in the
    overrides (top-level provider and any task_models providers).
    """
    if not llm_config:
        return {"sambanova": api_key}, None, "sambanova"

    api_keys = dict(llm_config.api_keys or {})
    provider = llm_config.provider or "sambanova"

    if api_key:
        api_keys.setdefault(provider, api_key)
        if llm_config.task_models:
            for task_config in llm_config.task_models.values():
                if task_config.provider:
                    api_keys.setdefault(task_config.provider, api_key)

    overrides = {
        "provider": llm_config.provider,
        "model": llm_config.model,
        "base_url": llm_config.base_url,
        "provider_type": llm_config.provider_type,
        "task_models": (
            {
                task: task_config.model_dump(exclude_none=True)
                for task, task_config in llm_config.task_models.items()
            }
            if llm_config.task_models
            else None
        ),
    }

    return api_keys, overrides, provider
