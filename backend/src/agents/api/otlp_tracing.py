import structlog

logger = structlog.get_logger(__name__)


def configure_oltp_tracing(
    service_name: str = "aiskagents",
    endpoint: str = "http://localhost:4317",
    insecure: bool = True,
) -> None:
    """Configure OpenTelemetry tracing for the application."""
    return logger.configure_otlp(service_name, endpoint, insecure)
