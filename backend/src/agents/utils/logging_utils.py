from typing import Any, Dict, Optional

import structlog
from langchain_core.runnables import RunnableConfig


def setup_logging_context(config: Optional[RunnableConfig], **kwargs: Any) -> None:
    """
    Sets up a structured logging context with common details from the RunnableConfig.

    Clears previous context and binds new context variables. Automatically includes
    'run_id' and 'thread_id' if a RunnableConfig is provided.

    Args:
        config: The RunnableConfig object, which may be None.
        **kwargs: Arbitrary key-value pairs to add to the logging context.
    """
    structlog.contextvars.clear_contextvars()

    log_context: Dict[str, Any] = {}

    if config:
        message_id = config.get("configurable", {}).get("message_id")
        thread_id = config.get("configurable", {}).get("thread_id")
        log_context.update(
            {
                "message_id": str(message_id) if message_id else "N/A",
                "thread_id": thread_id,
            }
        )

    log_context.update(kwargs)
    structlog.contextvars.bind_contextvars(**log_context)
