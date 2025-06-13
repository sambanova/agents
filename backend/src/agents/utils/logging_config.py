import logging
import os
import sys

import structlog
from structlog.dev import ConsoleRenderer
from structlog.stdlib import ProcessorFormatter


def configure_logging(environment: str = "prod"):
    """
    Unified logging configuration using structlog for both stdlib and structlog loggers.
    In development, uses a human-readable console format.
    In production, outputs structured JSON logs compatible with OpenSearch and Grafana.
    """
    is_development = environment == "dev"

    # === Set up a processor chain for standard logging ===
    pre_chain = [
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", key="@timestamp"),
    ]

    # Choose formatter based on environment
    if is_development:
        formatter = ProcessorFormatter(
            processor=structlog.dev.ConsoleRenderer(colors=True),
            foreign_pre_chain=pre_chain,
        )
    else:
        formatter = ProcessorFormatter(
            processor=structlog.processors.JSONRenderer(),
            foreign_pre_chain=pre_chain,
        )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.setLevel(logging.INFO)
    root_logger.addHandler(handler)

    # === Configure structlog ===
    structlog.configure(
        processors=[
            structlog.stdlib.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", key="@timestamp"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    # Intercept uvicorn logs and render them with structlog
    for name in ["uvicorn", "uvicorn.error", "LiteLLM"]:
        logger = logging.getLogger(name)
        logger.handlers.clear()
        logger.propagate = True

    # Silence uvicorn access logs
    access_logger = logging.getLogger("uvicorn.access")
    access_logger.handlers.clear()
    access_logger.propagate = False


def get_logger(name: str = None):
    """Get a structlog logger."""
    return structlog.get_logger(name or "app")


def get_stdlib_logger(name: str):
    """Get a traditional stdlib logger."""
    return logging.getLogger(name)
