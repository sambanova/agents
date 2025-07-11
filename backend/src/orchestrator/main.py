"""Standalone MCP-Orchestrator microservice.

This service owns the lifecycle of all MCP Studio servers (spawned as
sub-processes) and exposes a small HTTP API that the main backend uses to
start/stop/query them.  Separating this responsibility keeps heavy/unstable
studio binaries out of the API pod and dramatically improves tail-latency.

Endpoints
---------
POST /servers/{server_id}/start   – spawn or enable server
POST /servers/{server_id}/stop    – terminate server
GET  /servers/{server_id}/status  – return health + tool manifest
POST /servers/{server_id}/discover-tools  – refresh tool cache

All endpoints expect an `X-User-Id` header so the orchestrator can fetch the
correct per-user configuration from Redis.
"""

import asyncio
import os
import sys
from datetime import datetime
from typing import Optional

# Add src to Python path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import httpx
import structlog
from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import JSONResponse

# Re-use existing storage + manager classes
from agents.storage.redis_storage import RedisStorage
from agents.mcp.server_manager import MCPServerManager, MCPServerStatus


logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Service initialisation
# ---------------------------------------------------------------------------

app = FastAPI(title="MCP-Orchestrator", version="0.1.0")


@app.on_event("startup")
async def startup_event():
    """Initialise shared Redis connection and ServerManager."""
    # Here we assume existing SecureRedisService is wired via env-vars
    from agents.storage.global_services import (
        init_global_redis_storage,
        get_global_redis_storage,
    )

    await init_global_redis_storage()
    redis_storage: RedisStorage = get_global_redis_storage()

    # Store on app.state for reuse
    app.state.server_manager = MCPServerManager(redis_storage)
    logger.info("Orchestrator startup complete")


@app.on_event("shutdown")
async def shutdown_event():
    mgr: MCPServerManager = app.state.server_manager  # type: ignore[attr-defined]
    await mgr.cleanup()
    logger.info("Orchestrator shutdown complete")


# ---------------------------------------------------------------------------
# Helper utilities
# ---------------------------------------------------------------------------


async def _ensure_user_header(user_id: Optional[str]) -> str:
    if not user_id:
        raise HTTPException(status_code=400, detail="Missing X-User-Id header")
    return user_id


# ---------------------------------------------------------------------------
# API Routes
# ---------------------------------------------------------------------------


@app.post("/servers/{server_id}/start")
async def start_server(server_id: str, x_user_id: Optional[str] = Header(None)):
    user_id = await _ensure_user_header(x_user_id)
    mgr: MCPServerManager = app.state.server_manager  # type: ignore[attr-defined]

    success = await mgr.start_server(user_id, server_id)
    status = "started" if success else "error"
    return JSONResponse({"server_id": server_id, "status": status})


@app.post("/servers/{server_id}/stop")
async def stop_server(server_id: str, x_user_id: Optional[str] = Header(None)):
    user_id = await _ensure_user_header(x_user_id)
    mgr: MCPServerManager = app.state.server_manager  # type: ignore[attr-defined]
    success = await mgr.stop_server(user_id, server_id)
    status = "stopped" if success else "error"
    return JSONResponse({"server_id": server_id, "status": status})


@app.get("/health")
async def health_check():
    """Health check endpoint for Kubernetes probes."""
    return {"status": "healthy", "service": "mcp-orchestrator"}


@app.get("/servers/{server_id}/status")
async def server_status(server_id: str, x_user_id: Optional[str] = Header(None)):
    user_id = await _ensure_user_header(x_user_id)
    mgr: MCPServerManager = app.state.server_manager  # type: ignore[attr-defined]
    health, message = await mgr.health_check(user_id, server_id)
    tools = await mgr.discover_tools(user_id, server_id)

    return JSONResponse(
        {
            "server_id": server_id,
            "status": health,
            "message": message,
            "checked_at": datetime.utcnow().isoformat(),
            "tools": [t.model_dump(mode="json") for t in tools],
        }
    )


@app.post("/servers/{server_id}/discover-tools")
async def refresh_tools(server_id: str, x_user_id: Optional[str] = Header(None)):
    user_id = await _ensure_user_header(x_user_id)
    mgr: MCPServerManager = app.state.server_manager  # type: ignore[attr-defined]
    tools = await mgr.discover_tools(user_id, server_id, force_refresh=True)
    return {"server_id": server_id, "total": len(tools)} 