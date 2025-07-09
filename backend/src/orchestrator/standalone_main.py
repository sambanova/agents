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
        key = f"orch_mcp_servers:{user_id}:{server_id}"
        config_str = await self.client.get(key)
        if not config_str:
            return None
        
        # Parse the stored JSON config
        try:
            config_data = json.loads(config_str)
            # Map backend field names to our simple format
            return MCPServerConfig(
                id=config_data.get("server_id", server_id),
                name=config_data.get("name", server_id),
                command=config_data.get("command", ""),
                args=config_data.get("args", []),
                env=config_data.get("env_vars", {}),
                enabled=config_data.get("enabled", False),
                status=MCPServerStatus.STOPPED  # Default to stopped, will be updated by process manager
            )
        except Exception as e:
            logger.error(f"Failed to parse server config: {e}")
            return None
    
    async def update_server_status(self, user_id: str, server_id: str, status: MCPServerStatus):
        await self.connect()
        # We can't easily update just the status in the JSON, so we'll skip this for now
        # The backend will handle status updates through its own mechanisms
        pass
    
    async def get_all_enabled_servers(self) -> List[Tuple[str, str, MCPServerConfig]]:
        """Get all enabled MCP servers across all users. Returns (user_id, server_id, config) tuples."""
        await self.connect()
        enabled_servers = []
        
        try:
            # Scan for all orch_user_mcp_servers keys to get user lists
            cursor = 0
            while True:
                cursor, keys = await self.client.scan(cursor, match="orch_user_mcp_servers:*", count=100)
                
                for key in keys:
                    try:
                        # Parse key: orch_user_mcp_servers:user_id
                        parts = key.split(":", 1)
                        if len(parts) != 2:
                            continue
                        
                        user_id = parts[1]
                        
                        # Get all server IDs for this user
                        server_ids = await self.client.smembers(key)
                        
                        for server_id in server_ids:
                            if isinstance(server_id, bytes):
                                server_id = server_id.decode("utf-8")
                            
                            # Get server config
                            config = await self.get_server_config(user_id, server_id)
                            if config and config.enabled:
                                enabled_servers.append((user_id, server_id, config))
                    
                    except Exception as e:
                        logger.warning(f"Error processing user key {key}: {e}")
                        continue
                
                if cursor == 0:
                    break
            
            logger.info(f"Found {len(enabled_servers)} enabled MCP servers across all users")
            return enabled_servers
            
        except Exception as e:
            logger.error(f"Error scanning for enabled servers: {e}")
            return []

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
health_monitor_task: Optional[asyncio.Task] = None

async def health_monitor_loop():
    """Periodic health monitoring to ensure servers stay running."""
    while True:
        try:
            await asyncio.sleep(60)  # Check every minute
            
            # Get all enabled servers
            enabled_servers = await redis_client.get_all_enabled_servers()
            
            for user_id, server_id, config in enabled_servers:
                # Check if process is still running
                is_running = process_manager.is_running(user_id, server_id)
                
                if not is_running:
                    logger.warning(f"Server {server_id} for user {user_id} is not running, restarting...")
                    # Restart the server
                    success = await process_manager.start_server(user_id, server_id, config)
                    status = MCPServerStatus.RUNNING if success else MCPServerStatus.ERROR
                    await redis_client.update_server_status(user_id, server_id, status)
                    
                    if success:
                        logger.info(f"Successfully restarted server {server_id} for user {user_id}")
                    else:
                        logger.error(f"Failed to restart server {server_id} for user {user_id}")
                else:
                    # Update status to running
                    await redis_client.update_server_status(user_id, server_id, MCPServerStatus.RUNNING)
                    
        except asyncio.CancelledError:
            logger.info("Health monitor loop cancelled")
            break
        except Exception as e:
            logger.error(f"Error in health monitor loop: {e}")

@app.on_event("startup")
async def startup_event():
    global redis_client, process_manager, health_monitor_task
    
    redis_host = os.getenv("REDIS_HOST", "localhost")
    redis_port = int(os.getenv("REDIS_PORT", "6379"))
    
    redis_client = SimpleRedisClient(redis_host, redis_port)
    process_manager = ProcessManager()
    
    # Load and start all enabled servers on startup
    enabled_servers = await redis_client.get_all_enabled_servers()
    for user_id, server_id, config in enabled_servers:
        success = await process_manager.start_server(user_id, server_id, config)
        status = MCPServerStatus.RUNNING if success else MCPServerStatus.ERROR
        await redis_client.update_server_status(user_id, server_id, status)
    
    # Start health monitoring
    health_monitor_task = asyncio.create_task(health_monitor_loop())
    
    logger.info("Standalone orchestrator startup complete")

@app.on_event("shutdown")
async def shutdown_event():
    global process_manager, health_monitor_task
    
    # Stop health monitoring
    if health_monitor_task:
        health_monitor_task.cancel()
        try:
            await health_monitor_task
        except asyncio.CancelledError:
            pass
    
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