import logging
import os
from logging.handlers import RotatingFileHandler
from typing import Optional

from opentelemetry import metrics, trace
from opentelemetry._logs import set_logger_provider
from opentelemetry.exporter.otlp.proto.grpc._log_exporter import OTLPLogExporter
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor


class UnifiedLogger:
    """
    Unified logging class for FastAPI that combines standard Python logging with OpenTelemetry.
    """
    _instance = None
    _initialized = False
    _file_handler = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(UnifiedLogger, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        # Initialize standard Python logger
        self.logger = logging.getLogger("co-pilot")
        self.logger.setLevel(logging.INFO)

        # Remove existing handlers
        for handler in self.logger.handlers[:]:
            self.logger.removeHandler(handler)

        # Add console handler with formatting
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        console_handler.setFormatter(formatter)
        self.logger.addHandler(console_handler)
        
        # Add file handler for local disk logging
        self._file_handler = self._setup_file_logging()
        
        # Configure uvicorn access logger to use our file handler
        uvicorn_access_logger = logging.getLogger("uvicorn.access")
        if self._file_handler and not any(isinstance(h, RotatingFileHandler) for h in uvicorn_access_logger.handlers):
            uvicorn_access_logger.addHandler(self._file_handler)
        
        self.logger.propagate = False

        self._initialized = True
        
    def _setup_file_logging(self):
        """Set up file logging to store logs on disk."""
        # Get log directory from environment variable or use default
        log_dir = os.getenv("LOG_DIR", "logs")
        log_level = os.getenv("LOG_LEVEL", "INFO")
        max_log_size_mb = int(os.getenv("MAX_LOG_SIZE_MB", "10"))
        backup_count = int(os.getenv("LOG_BACKUP_COUNT", "5"))
        
        # Get pod name from environment if available
        pod_name = os.getenv("POD_NAME", "")
        
        # Create log directory if it doesn't exist
        try:
            os.makedirs(log_dir, exist_ok=True)
        except PermissionError:
            # Fall back to a directory we can write to
            fallback_dir = "/tmp/aiskagents-logs"
            self.logger.warning(f"Cannot create log directory at {log_dir}. Falling back to {fallback_dir}")
            os.makedirs(fallback_dir, exist_ok=True)
            log_dir = fallback_dir
        
        # Set up log file path with pod name if available
        if pod_name:
            log_filename = f"aiskagents-backend-{pod_name}.log"
        else:
            log_filename = "aiskagents-backend.log"
            
        log_file = os.path.join(log_dir, log_filename)
        
        # Create rotating file handler
        try:
            file_handler = RotatingFileHandler(
                log_file,
                maxBytes=max_log_size_mb * 1024 * 1024,  # Convert MB to bytes
                backupCount=backup_count
            )
            
            # Set log level from environment or default to INFO
            level = getattr(logging, log_level.upper(), logging.INFO)
            file_handler.setLevel(level)
            
            # Use the same formatter as console
            formatter = logging.Formatter(
                "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                datefmt='%Y-%m-%d %H:%M:%S'
            )
            file_handler.setFormatter(formatter)
            
            # Add the file handler to our logger
            self.logger.addHandler(file_handler)
            
            # Store the file handler for later use
            self._file_handler = file_handler
            
            # Log that file logging has been set up
            self.logger.info(f"File logging set up at {log_file}")
            
            return file_handler
        except Exception as e:
            self.logger.error(f"Failed to set up file logging: {str(e)}")
            return None

    def configure_otlp(
        self,
        service_name: str = "aiskagents-backend",
        endpoint: str = "http://localhost:4317",
        insecure: bool = True
    ) -> trace.TracerProvider:
        """Configure OpenTelemetry tracing, metrics and logging."""
        resource = Resource(attributes={SERVICE_NAME: service_name})
        
        # Configure Tracing
        tracer_provider = TracerProvider(resource=resource)
        processor = BatchSpanProcessor(OTLPSpanExporter())
        tracer_provider.add_span_processor(processor)
        trace.set_tracer_provider(tracer_provider)

        # Configure Metrics
        reader = PeriodicExportingMetricReader(
            OTLPMetricExporter(endpoint=endpoint, insecure=insecure)
        )
        meter_provider = MeterProvider(resource=resource, metric_readers=[reader])
        metrics.set_meter_provider(meter_provider)

        # Configure OTLP Logging
        logger_provider = LoggerProvider(resource=resource)
        set_logger_provider(logger_provider)

        exporter = OTLPLogExporter(insecure=insecure)
        logger_provider.add_log_record_processor(BatchLogRecordProcessor(exporter))
        handler = LoggingHandler(level=logging.NOTSET, logger_provider=logger_provider)
        
        # Use the same formatter for OTLP handler
        handler.setFormatter(logging.Formatter(
            "[%(asctime)s] %(levelname)s [%(name)s] %(message)s",
            datefmt='%Y-%m-%d %H:%M:%S'
        ))

        # Add OTLP handler to our logger
        self.logger.addHandler(handler)

        return tracer_provider

    def format_message(self, session_id: Optional[str], message: str) -> str:
        """Format log message with session ID if provided."""
        if session_id:
            return f"[{session_id[28:32]}-{session_id[-4:]}] {message}"
        return message

    def debug(self, message: str) -> None:
        """Log debug message."""
        self.logger.debug(message)

    def info(self, message: str) -> None:
        """Log info message."""
        self.logger.info(message)

    def warning(self, message: str) -> None:
        """Log warning message."""
        self.logger.warning(message)

    def error(self, message: str, exc_info: bool = False) -> None:
        """Log error message."""
        self.logger.error(message, exc_info=exc_info)

    def critical(self, message: str) -> None:
        """Log critical message."""
        self.logger.critical(message)

# Create singleton instance
logger = UnifiedLogger()

# Function to configure uvicorn logging to use our file handler
def configure_uvicorn_logging():
    """Configure uvicorn and FastAPI loggers to use our file handler."""
    if logger._file_handler:
        # Get log level from environment or default to INFO
        log_level_name = os.getenv("LOG_LEVEL", "INFO")
        log_level = getattr(logging, log_level_name.upper(), logging.INFO)
        
        # Configure uvicorn loggers
        uvicorn_access_logger = logging.getLogger("uvicorn.access")
        uvicorn_access_logger.setLevel(log_level)
        uvicorn_access_logger.addHandler(logger._file_handler)
        uvicorn_access_logger.propagate = False  # Disable propagation to prevent duplicates
        
        uvicorn_error_logger = logging.getLogger("uvicorn.error")
        uvicorn_error_logger.setLevel(log_level)
        uvicorn_error_logger.addHandler(logger._file_handler)
        uvicorn_error_logger.propagate = False  # Disable propagation to prevent duplicates
        
        # Configure FastAPI logger
        fastapi_logger = logging.getLogger("fastapi")
        fastapi_logger.setLevel(log_level)
        fastapi_logger.addHandler(logger._file_handler)
        fastapi_logger.propagate = False  # Disable propagation to prevent duplicates
        
        # We don't need to configure the root logger since we're handling specific loggers
        # and disabling propagation
        
        logger.info(f"Added file handler to uvicorn and FastAPI loggers with level {log_level_name}")
    else:
        logger.warning("No file handler available. Uvicorn and FastAPI logs will only go to console.") 