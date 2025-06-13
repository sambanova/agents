import os
import time
import uuid
from typing import Callable
from urllib.parse import urlparse

import structlog
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware


class LoggingMiddleware(BaseHTTPMiddleware):
    """
    Middleware to log HTTP requests and responses with structured data for OpenSearch/Grafana.
    """

    def __init__(self, app, logger_name: str = "http"):
        super().__init__(app)
        self.logger = structlog.get_logger(logger_name)

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Generate request ID for tracing
        request_id = str(uuid.uuid4())

        # Start timing
        start_time = time.time()

        # Parse URL for better structured logging
        parsed_url = urlparse(str(request.url))

        # Get client information
        client_ip = request.client.host if request.client else None
        user_agent = request.headers.get("user-agent", "")

        # Add request ID to request state for use in other parts of the app
        request.state.request_id = request_id

        # Add structured logging context for this request
        structlog.contextvars.bind_contextvars(
            request_id=request_id,
            operation=f"{request.method} {parsed_url.path}",
            client_ip=client_ip,
        )

        try:
            # Process request
            response = await call_next(request)

            # Calculate duration
            duration = time.time() - start_time

            # Determine response category
            status_category = (
                "success"
                if 200 <= response.status_code < 300
                else (
                    "redirect"
                    if 300 <= response.status_code < 400
                    else (
                        "client_error"
                        if 400 <= response.status_code < 500
                        else "server_error"
                    )
                )
            )

            # Log request completion with all details (SINGLE LOG ENTRY)
            self.logger.info(
                "HTTP request completed",
                request_id=request_id,
                http_method=request.method,
                http_url=str(request.url),
                http_path=parsed_url.path,
                http_status_code=response.status_code,
                http_status_category=status_category,
                duration_seconds=round(duration, 4),
                duration_ms=round(duration * 1000, 2),
                client_ip=client_ip,
                client_user_agent=user_agent,
                operation=f"{request.method} {parsed_url.path}",
                success=status_category == "success",
            )

            # Add request ID to response headers for debugging
            response.headers["X-Request-ID"] = request_id

            return response

        except Exception as exc:
            # Calculate duration
            duration = time.time() - start_time

            # Log error with detailed context (SINGLE ERROR LOG)
            self.logger.error(
                "HTTP request failed",
                request_id=request_id,
                http_method=request.method,
                http_url=str(request.url),
                http_path=parsed_url.path,
                error_type=type(exc).__name__,
                error_message=str(exc),
                duration_seconds=round(duration, 4),
                duration_ms=round(duration * 1000, 2),
                client_ip=client_ip,
                operation=f"{request.method} {parsed_url.path}",
                success=False,
                exc_info=True,
            )

            # Re-raise the exception
            raise exc
        finally:
            # Clear request context
            structlog.contextvars.clear_contextvars()
