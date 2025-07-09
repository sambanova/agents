"""Standalone MCP-Orchestrator microservice.

This is a lightweight service that manages MCP server processes without importing
the heavy backend dependencies. It communicates with Redis directly for configuration
and exposes a simple HTTP API for server lifecycle management.
"""

import asyncio
import json
import os
import subprocess
import sys
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from enum import Enum

import httpx
import structlog
from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import redis.asyncio as aioredis

logger = structlog.get_logger(__name__)

# Simple data types (no heavy imports)
class MCPServerStatus(str, Enum):
    STARTING = "starting"
    RUNNING = "running"
    STOPPED = "stopped"
    ERROR = "error"

class MCPServerConfig(BaseModel):
    id: str
    name: str
    command: str
    args: List[str] = []
    env: Dict[str, str] = {}
    enabled: bool = False
    status: MCPServerStatus = MCPServerStatus.STOPPED

class MCPToolInfo(BaseModel):
    name: str
    description: str
    schema: Dict = {}

# Simple Redis client (no encryption for orchestrator)
class SimpleRedisClient:
    def __init__(self, host: str = "localhost", port: int = 6379):
        self.host = host
        self.port = port
        self.client: Optional[aioredis.Redis] = None
    
    async def connect(self):
        if not self.client:
            self.client = aioredis.Redis(host=self.host, port=self.port, decode_responses=True)
    
    async def get_server_config(self, user_id: str, server_id: str) -> Optional[MCPServerConfig]:
        await self.connect()
        key = f"mcp_server:{user_id}:{server_id}"
        data = await self.client.hgetall(key)
        if not data:
            return None
        
        # Parse the stored config
        try:
            config_data = {
                "id": data.get("id", server_id),
                "name": data.get("name", server_id),
                "command": data.get("command", ""),
                "args": json.loads(data.get("args", "[]")),
                "env": json.loads(data.get("env", "{}")),
                "enabled": data.get("enabled", "false").lower() == "true",
                "status": data.get("status", MCPServerStatus.STOPPED)
            }
            return MCPServerConfig(**config_data)
        except Exception as e:
            logger.error(f"Failed to parse server config: {e}")
            return None
    
    async def update_server_status(self, user_id: str, server_id: str, status: MCPServerStatus):
        await self.connect()
        key = f"mcp_server:{user_id}:{server_id}"
        await self.client.hset(key, "status", status.value)

# Simple process manager
class ProcessManager:
    def __init__(self):
        self.processes: Dict[str, subprocess.Popen] = {}
    
    async def start_server(self, user_id: str, server_id: str, config: MCPServerConfig) -> bool:
        try:
            process_key = f"{user_id}:{server_id}"
            
            # Stop existing process if running
            if process_key in self.processes:
                await self.stop_server(user_id, server_id)
            
            # Start new process
            cmd = [config.command] + config.args
            env = {**os.environ, **config.env}
            
            process = subprocess.Popen(
                cmd,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            self.processes[process_key] = process
            logger.info(f"Started MCP server {server_id} for user {user_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start server {server_id}: {e}")
            return False
    
    async def stop_server(self, user_id: str, server_id: str) -> bool:
        try:
            process_key = f"{user_id}:{server_id}"
            
            if process_key in self.processes:
                process = self.processes[process_key]
                process.terminate()
                
                # Wait for graceful shutdown
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                
                del self.processes[process_key]
                logger.info(f"Stopped MCP server {server_id} for user {user_id}")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to stop server {server_id}: {e}")
            return False
    
    def is_running(self, user_id: str, server_id: str) -> bool:
        process_key = f"{user_id}:{server_id}"
        if process_key not in self.processes:
            return False
        
        process = self.processes[process_key]
        return process.poll() is None

# Service initialization
app = FastAPI(title="MCP-Orchestrator", version="0.1.0")

# Global services
redis_client: Optional[SimpleRedisClient] = None
process_manager: Optional[ProcessManager] = None

@app.on_event("startup")
async def startup_event():
    global redis_client, process_manager
    
    redis_host = os.getenv("REDIS_HOST", "localhost")
    redis_port = int(os.getenv("REDIS_PORT", "6379"))
    
    redis_client = SimpleRedisClient(redis_host, redis_port)
    process_manager = ProcessManager()
    
    logger.info("Standalone orchestrator startup complete")

@app.on_event("shutdown")
async def shutdown_event():
    global process_manager
    
    if process_manager:
        # Stop all running processes
        for process_key in list(process_manager.processes.keys()):
            user_id, server_id = process_key.split(":", 1)
            await process_manager.stop_server(user_id, server_id)
    
    logger.info("Standalone orchestrator shutdown complete")

# Helper utilities
async def _ensure_user_header(user_id: Optional[str]) -> str:
    if not user_id:
        raise HTTPException(status_code=400, detail="Missing X-User-Id header")
    return user_id

# API Routes
@app.post("/servers/{server_id}/start")
async def start_server(server_id: str, x_user_id: Optional[str] = Header(None)):
    user_id = await _ensure_user_header(x_user_id)
    
    # Get server config from Redis
    config = await redis_client.get_server_config(user_id, server_id)
    if not config:
        return JSONResponse({"server_id": server_id, "status": "error", "message": "Server config not found"})
    
    if not config.enabled:
        return JSONResponse({"server_id": server_id, "status": "disabled"})
    
    # Start the server process
    success = await process_manager.start_server(user_id, server_id, config)
    
    # Update status in Redis
    status = MCPServerStatus.RUNNING if success else MCPServerStatus.ERROR
    await redis_client.update_server_status(user_id, server_id, status)
    
    return JSONResponse({"server_id": server_id, "status": status.value})

@app.post("/servers/{server_id}/stop")
async def stop_server(server_id: str, x_user_id: Optional[str] = Header(None)):
    user_id = await _ensure_user_header(x_user_id)
    
    success = await process_manager.stop_server(user_id, server_id)
    
    # Update status in Redis
    status = MCPServerStatus.STOPPED if success else MCPServerStatus.ERROR
    await redis_client.update_server_status(user_id, server_id, status)
    
    return JSONResponse({"server_id": server_id, "status": status.value})

@app.get("/health")
async def health_check():
    """Health check endpoint for Kubernetes probes."""
    return {"status": "healthy", "service": "mcp-orchestrator"}

@app.get("/servers/{server_id}/status")
async def server_status(server_id: str, x_user_id: Optional[str] = Header(None)):
    user_id = await _ensure_user_header(x_user_id)
    
    # Check if process is actually running
    is_running = process_manager.is_running(user_id, server_id)
    status = MCPServerStatus.RUNNING if is_running else MCPServerStatus.STOPPED
    
    # Update Redis with actual status
    await redis_client.update_server_status(user_id, server_id, status)
    
    return JSONResponse({
        "server_id": server_id,
        "status": status.value,
        "message": "Process running" if is_running else "Process stopped",
        "checked_at": datetime.utcnow().isoformat(),
        "tools": []  # Tool discovery can be added later if needed
    })

@app.post("/servers/{server_id}/discover-tools")
async def refresh_tools(server_id: str, x_user_id: Optional[str] = Header(None)):
    user_id = await _ensure_user_header(x_user_id)
    
    # For now, return empty tools list
    # Tool discovery can be implemented later via MCP protocol
    return {"server_id": server_id, "total": 0, "tools": []}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8090) 