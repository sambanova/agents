import os
import time
import uuid
from typing import Callable
from urllib.parse import urlparse

import structlog
from fastapi import Request, Response
from starlette.datastructures import Headers
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.types import ASGIApp, Receive, Scope, Send


class LoggingMiddleware:
    """
    Middleware to log HTTP requests/responses and WebSocket connections
    with structured data for OpenSearch/Grafana.
    """

    def __init__(self, app: ASGIApp, logger_name: str = "http"):
        self.app = app
        self.logger = structlog.get_logger(logger_name)

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if scope["type"] not in ["http", "websocket"]:
            await self.app(scope, receive, send)
            return

        request_id = str(uuid.uuid4())

        if "state" not in scope:
            scope["state"] = {}
        scope["state"]["request_id"] = request_id

        structlog.contextvars.bind_contextvars(request_id=request_id)

        try:
            if scope["type"] == "http":
                await self._log_http_request(scope, receive, send, request_id)
            elif scope["type"] == "websocket":
                await self._log_websocket_connection(scope, receive, send, request_id)
        finally:
            structlog.contextvars.clear_contextvars()

    async def _log_http_request(
        self, scope: Scope, receive: Receive, send: Send, request_id: str
    ):
        request = Request(scope)
        start_time = time.time()
        parsed_url = urlparse(str(request.url))
        client_ip = request.client.host if request.client else None
        user_agent = request.headers.get("user-agent", "")

        structlog.contextvars.bind_contextvars(
            operation=f"{request.method} {parsed_url.path}",
            client_ip=client_ip,
        )

        status_code = None

        async def send_wrapper(message):
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
                # Add X-Request-ID header
                headers = Headers(raw=message["headers"])
                headers_list = list(headers.items())
                headers_list.append(("X-Request-ID", request_id))
                message["headers"] = [(k.encode(), v.encode()) for k, v in headers_list]

            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        except Exception as exc:
            duration = time.time() - start_time
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
            # If an exception occurs, we should still try to send a 500 response.
            # This is typically handled by an upstream ExceptionMiddleware.
            # So we re-raise.
            raise exc

        if status_code is not None:
            duration = time.time() - start_time
            status_category = (
                "success"
                if 200 <= status_code < 300
                else (
                    "redirect"
                    if 300 <= status_code < 400
                    else (
                        "client_error" if 400 <= status_code < 500 else "server_error"
                    )
                )
            )

            self.logger.info(
                "HTTP request completed",
                request_id=request_id,
                http_method=request.method,
                http_url=str(request.url),
                http_path=parsed_url.path,
                http_status_code=status_code,
                http_status_category=status_category,
                duration_seconds=round(duration, 4),
                duration_ms=round(duration * 1000, 2),
                client_ip=client_ip,
                client_user_agent=user_agent,
                operation=f"{request.method} {parsed_url.path}",
                success=status_category == "success",
            )

    async def _log_websocket_connection(
        self, scope: Scope, receive: Receive, send: Send, request_id: str
    ):
        start_time = time.time()

        from starlette.datastructures import URL, Headers
        from starlette.websockets import WebSocketDisconnect

        url = URL(scope=scope)
        headers = Headers(scope=scope)
        client_ip = scope.get("client")[0] if scope.get("client") else None
        user_agent = headers.get("user-agent", "")

        structlog.contextvars.bind_contextvars(
            operation=f"WS {url.path}",
            client_ip=client_ip,
        )

        self.logger.info(
            "WebSocket connection opened",
            request_id=request_id,
            ws_url=str(url),
            ws_path=url.path,
            client_ip=client_ip,
            client_user_agent=user_agent,
            operation=f"WS {url.path}",
        )

        try:
            await self.app(scope, receive, send)
        except WebSocketDisconnect as exc:
            # Expected disconnect
            pass
        except Exception as exc:
            self.logger.error(
                "WebSocket connection failed",
                request_id=request_id,
                ws_url=str(url),
                ws_path=url.path,
                error_type=type(exc).__name__,
                error_message=str(exc),
                client_ip=client_ip,
                operation=f"WS {url.path}",
                exc_info=True,
                success=False,
            )
            # Re-raise unless it's a disconnect
            if not isinstance(exc, WebSocketDisconnect):
                raise
        finally:
            duration = time.time() - start_time
            self.logger.info(
                "WebSocket connection closed",
                request_id=request_id,
                ws_url=str(url),
                ws_path=url.path,
                duration_seconds=round(duration, 4),
                duration_ms=round(duration * 1000, 2),
                client_ip=client_ip,
                operation=f"WS {url.path}",
            )
