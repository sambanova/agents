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
import time

import httpx
import structlog
import random
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
        
        # If orchestrator key doesn't exist, try to read from regular encrypted key
        if not config_str:
            logger.info(f"Orchestrator key not found for {server_id}, trying encrypted key")
            regular_key = f"mcp_servers:{user_id}:{server_id}"
            config_str = await self.client.get(regular_key)
            
            if config_str:
                logger.warning(f"Found encrypted data for {server_id} but orchestrator can't decrypt it. Server config unavailable.")
                return None
        
        if not config_str:
            logger.warning(f"No config found for server {server_id} in any location")
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
            logger.error(f"Failed to parse server config for {server_id}: {e}")
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
            logger.info("Starting scan for orchestrator MCP servers...")
            
            # Scan for all orch_user_mcp_servers keys to get user lists
            cursor = 0
            user_keys_found = []
            while True:
                cursor, keys = await self.client.scan(cursor, match="orch_user_mcp_servers:*", count=100)
                user_keys_found.extend(keys)
                
                if cursor == 0:
                    break
            
            logger.info(f"Found {len(user_keys_found)} orchestrator user keys: {user_keys_found}")
            
            # If no orchestrator keys found, try to scan regular user keys as fallback
            if not user_keys_found:
                logger.info("No orchestrator keys found, checking for regular user_mcp_servers keys as fallback...")
                cursor = 0
                while True:
                    cursor, keys = await self.client.scan(cursor, match="user_mcp_servers:*", count=100)
                    for key in keys:
                        # Convert regular key to orchestrator format for processing
                        orch_key = key.replace("user_mcp_servers:", "orch_user_mcp_servers:")
                        user_keys_found.append(orch_key)
                    
                    if cursor == 0:
                        break
                
                logger.info(f"Found {len(user_keys_found)} regular user keys to check")
            
            for key in user_keys_found:
                try:
                    # Parse key: orch_user_mcp_servers:user_id
                    parts = key.split(":", 1)
                    if len(parts) != 2:
                        logger.warning(f"Invalid key format: {key}")
                        continue
                    
                    user_id = parts[1]
                    logger.info(f"Processing user {user_id}")
                    
                    # Get all server IDs for this user (try orchestrator key first, then regular key)
                    server_ids = await self.client.smembers(key)
                    if not server_ids and key.startswith("orch_"):
                        # Try regular key as fallback
                        regular_key = key.replace("orch_user_mcp_servers:", "user_mcp_servers:")
                        server_ids = await self.client.smembers(regular_key)
                        logger.info(f"Using regular key {regular_key} as fallback")
                    
                    logger.info(f"User {user_id} has {len(server_ids)} servers: {server_ids}")
                    
                    for server_id in server_ids:
                        if isinstance(server_id, bytes):
                            server_id = server_id.decode("utf-8")
                        
                        logger.info(f"Checking server {server_id} for user {user_id}")
                        
                        # Get server config
                        config = await self.get_server_config(user_id, server_id)
                        if config:
                            logger.info(f"Server {server_id} config: enabled={config.enabled}, command={config.command}")
                            if config.enabled:
                                enabled_servers.append((user_id, server_id, config))
                                logger.info(f"Added enabled server {server_id} to startup list")
                            else:
                                logger.info(f"Server {server_id} is disabled, skipping")
                        else:
                            logger.warning(f"No config found for server {server_id}")
                
                except Exception as e:
                    logger.warning(f"Error processing user key {key}: {e}")
                    continue
            
            logger.info(f"Scan complete: found {len(enabled_servers)} enabled MCP servers across all users")
            return enabled_servers
            
        except Exception as e:
            logger.error(f"Error scanning for enabled servers: {e}")
            return []

    async def set_running(self, user_id: str, server_id: str):
        await self.connect()
        await self.client.set(f"orch_running:{user_id}:{server_id}", "1")

    async def clear_running(self, user_id: str, server_id: str):
        await self.connect()
        await self.client.delete(f"orch_running:{user_id}:{server_id}")

    async def is_running(self, user_id: str, server_id: str) -> bool:
        await self.connect()
        return await self.client.exists(f"orch_running:{user_id}:{server_id}") == 1

# Simple process manager
class ProcessManager:
    def __init__(self):
        self.processes: Dict[str, subprocess.Popen] = {}
        self.last_used: Dict[str, float] = {}
        self.IDLE_TIMEOUT = int(os.getenv("MCP_IDLE_TIMEOUT", "900"))  # 15 min default
    
    async def start_server(self, user_id: str, server_id: str, config: MCPServerConfig) -> bool:
        try:
            process_key = f"{user_id}:{server_id}"
            
            logger.info(f"ProcessManager starting server {server_id} for user {user_id}")
           # env hidden
            
            # Stop existing process if running
            if process_key in self.processes:
                logger.info(f"Stopping existing process for {server_id}")
                await self.stop_server(user_id, server_id)
            
            # Validate command
            if not config.command:
                logger.error(f"No command specified for server {server_id}")
                return False
            
            # Start new process
            cmd = [config.command] + config.args
            env = {**os.environ, **config.env}
            # Constrain Node.js memory usage if configured
            node_opts = os.getenv("MCP_NODE_OPTIONS")
            if node_opts and "NODE_OPTIONS" not in env:
                env["NODE_OPTIONS"] = node_opts
            
            
            process = subprocess.Popen(
                cmd,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            # Wait a moment to check if process started successfully
            await asyncio.sleep(0.1)
            if process.poll() is not None:
                # Process already exited
                stdout, stderr = process.communicate()
                logger.error(f"Process for {server_id} exited immediately. Exit code: {process.returncode}")
                logger.error(f"Stdout: {stdout}")
                logger.error(f"Stderr: {stderr}")
                return False
            
            self.processes[process_key] = process
            self.last_used[process_key] = time.time()
            await redis_client.set_running(user_id, server_id)
            logger.info(f"Successfully started MCP server {server_id} for user {user_id} (PID: {process.pid})")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start server {server_id}: {e}", exc_info=True)
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
                self.last_used.pop(process_key, None)
                await redis_client.clear_running(user_id, server_id)
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

    def touch(self, user_id: str, server_id: str):
        self.last_used[f"{user_id}:{server_id}"] = time.time()

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
            await asyncio.sleep(60 + random.uniform(0, 15))  # jitter 0-15s
            
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

            # Idle shutdown
            # Stop servers that have been idle beyond timeout
            now = time.time()
            for proc_key in list(process_manager.processes.keys()):
                last = process_manager.last_used.get(proc_key, now)
                if now - last > process_manager.IDLE_TIMEOUT:
                    u_id, s_id = proc_key.split(":", 1)
                    logger.info(f"Stopping idle server {s_id} for user {u_id}")
                    await process_manager.stop_server(u_id, s_id)
                    await redis_client.clear_running(u_id, s_id)
                    await redis_client.update_server_status(u_id, s_id, MCPServerStatus.STOPPED)

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
    
    logger.info(f"Connecting to Redis at {redis_host}:{redis_port}")
    
    redis_client = SimpleRedisClient(redis_host, redis_port)
    process_manager = ProcessManager()
    
    if os.getenv("ORCH_SKIP_AUTOSTART", "false").lower() != "true":
        # Load and start all enabled servers on startup
        logger.info("Scanning for enabled MCP servers...")
        enabled_servers = await redis_client.get_all_enabled_servers()
        logger.info(f"Found {len(enabled_servers)} enabled servers")

        for user_id, server_id, config in enabled_servers:
            if await redis_client.is_running(user_id, server_id):
                logger.info(f"Server {server_id} already running according to Redis flag – skipping autostart")
                continue
            logger.info(f"Starting server {server_id} for user {user_id} (command: {config.command})")
            success = await process_manager.start_server(user_id, server_id, config)
            status = MCPServerStatus.RUNNING if success else MCPServerStatus.ERROR
            await redis_client.update_server_status(user_id, server_id, status)
            
            if success:
                logger.info(f"Successfully started server {server_id}")
            else:
                logger.error(f"Failed to start server {server_id}")
    else:
        logger.info("ORCH_SKIP_AUTOSTART=true → skipping automatic server startup")
    
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
    
    logger.info(f"Received start request for server {server_id} from user {user_id}")
    
    # Get server config from Redis
    config = await redis_client.get_server_config(user_id, server_id)
    if not config:
        logger.error(f"Server config not found for {server_id}")
        return JSONResponse({"server_id": server_id, "status": "error", "message": "Server config not found"})
    
    logger.info(f"Found config for server {server_id}: command={config.command}, args={config.args}, enabled={config.enabled}")
    
    if not config.enabled:
        logger.warning(f"Server {server_id} is disabled")
        return JSONResponse({"server_id": server_id, "status": "disabled"})

    # If the server is already running, simply touch the last-used timestamp and return
    # RUNNING without restarting the process.  This makes the endpoint idempotent and
    # avoids unnecessary restarts that introduce latency.
    if process_manager.is_running(user_id, server_id):
        logger.info(f"Server {server_id} already running for user {user_id} – skipping start")
        process_manager.touch(user_id, server_id)
        await redis_client.update_server_status(user_id, server_id, MCPServerStatus.RUNNING)
        return JSONResponse({"server_id": server_id, "status": MCPServerStatus.RUNNING.value})
    
    # Start the server process (or restart if not running)
    logger.info(f"Starting server process for {server_id}")
    success = await process_manager.start_server(user_id, server_id, config)
    
    # Update status in Redis
    status = MCPServerStatus.RUNNING if success else MCPServerStatus.ERROR
    await redis_client.update_server_status(user_id, server_id, status)
    
    logger.info(f"Server {server_id} start result: success={success}, status={status}")
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
    if is_running:
        process_manager.touch(user_id, server_id)
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