import asyncio
import os
import subprocess
import time
import uuid
from typing import Any, Dict, List, Optional, Tuple

import structlog
from agents.api.data_types import MCPServerConfig, MCPServerStatus, MCPToolInfo
from agents.storage.redis_storage import RedisStorage
from langchain.tools import BaseTool, Tool

logger = structlog.get_logger(__name__)


class MCPServerManager:
    """
    Manages MCP server lifecycle including starting, stopping, health checks, and tool discovery.
    Handles both stdio and HTTP MCP servers for individual users.
    """

    def __init__(self, redis_storage: RedisStorage):
        self.redis_storage = redis_storage
        self.active_servers: Dict[str, Dict[str, Any]] = {}  # server_id -> server_info
        self.server_processes: Dict[str, subprocess.Popen] = {}  # server_id -> process
        self.health_check_tasks: Dict[str, asyncio.Task] = {}  # server_id -> task
        self.tool_cache: Dict[str, List[Dict[str, Any]]] = {}  # server_id -> tools
        self.cache_expiry: Dict[str, float] = {}  # server_id -> expiry_time
        self.cache_ttl = 300  # 5 minutes cache TTL

    async def start_server(self, user_id: str, server_id: str) -> bool:
        """Start an MCP server for a user."""
        try:
            # Get server configuration
            config = await self.redis_storage.get_mcp_server_config(user_id, server_id)
            if not config:
                logger.error("Server configuration not found", server_id=server_id, user_id=user_id)
                return False

            if not config.enabled:
                logger.info("Server is disabled", server_id=server_id, user_id=user_id)
                return False

            # Check if server is already running
            if self._is_server_running(server_id):
                logger.info("Server already running", server_id=server_id, user_id=user_id)
                return True

            # Start server based on transport type
            if config.transport == "stdio":
                success = await self._start_stdio_server(user_id, config)
            elif config.transport == "http":
                success = await self._start_http_server(user_id, config)
            else:
                logger.error("Unsupported transport type", transport=config.transport, server_id=server_id)
                return False

            if success:
                # Update server status
                await self.redis_storage.update_mcp_server_health(
                    user_id, server_id, MCPServerStatus.STARTING.value
                )
                
                # Start health monitoring
                await self._start_health_monitoring(user_id, server_id)
                
                logger.info("MCP server started successfully", server_id=server_id, user_id=user_id)
                return True
            else:
                await self.redis_storage.update_mcp_server_health(
                    user_id, server_id, MCPServerStatus.ERROR.value
                )
                return False

        except Exception as e:
            logger.error(
                "Error starting MCP server",
                server_id=server_id,
                user_id=user_id,
                error=str(e),
                exc_info=True,
            )
            await self.redis_storage.update_mcp_server_health(
                user_id, server_id, MCPServerStatus.ERROR.value
            )
            return False

    async def stop_server(self, user_id: str, server_id: str) -> bool:
        """Stop an MCP server for a user."""
        try:
            if not self._is_server_running(server_id):
                logger.info("Server not running", server_id=server_id, user_id=user_id)
                return True

            # Stop health monitoring
            if server_id in self.health_check_tasks:
                self.health_check_tasks[server_id].cancel()
                del self.health_check_tasks[server_id]

            # Stop server process
            if server_id in self.server_processes:
                process = self.server_processes[server_id]
                try:
                    process.terminate()
                    # Wait for graceful shutdown
                    await asyncio.sleep(2)
                    if process.poll() is None:
                        process.kill()
                    process.wait()
                except Exception as e:
                    logger.warning("Error stopping server process", error=str(e))
                finally:
                    del self.server_processes[server_id]

            # Clean up active server info
            if server_id in self.active_servers:
                del self.active_servers[server_id]

            # Clear tool cache
            if server_id in self.tool_cache:
                del self.tool_cache[server_id]
                del self.cache_expiry[server_id]

            # Update server status
            await self.redis_storage.update_mcp_server_health(
                user_id, server_id, MCPServerStatus.STOPPED.value
            )

            logger.info("MCP server stopped successfully", server_id=server_id, user_id=user_id)
            return True

        except Exception as e:
            logger.error(
                "Error stopping MCP server",
                server_id=server_id,
                user_id=user_id,
                error=str(e),
                exc_info=True,
            )
            return False

    async def restart_server(self, user_id: str, server_id: str) -> bool:
        """Restart an MCP server for a user."""
        logger.info("Restarting MCP server", server_id=server_id, user_id=user_id)
        
        # Stop the server first
        stop_success = await self.stop_server(user_id, server_id)
        if not stop_success:
            logger.error("Failed to stop server during restart", server_id=server_id)
            return False
            
        # Wait a bit before restarting
        await asyncio.sleep(1)
        
        # Start the server again
        return await self.start_server(user_id, server_id)

    async def health_check(self, user_id: str, server_id: str) -> Tuple[MCPServerStatus, Optional[str]]:
        """Perform health check on an MCP server."""
        try:
            config = await self.redis_storage.get_mcp_server_config(user_id, server_id)
            if not config:
                return MCPServerStatus.ERROR, "Server configuration not found"

            if not self._is_server_running(server_id):
                return MCPServerStatus.STOPPED, "Server process not running"

            # TODO: Implement actual MCP health check using langchain-mcp-adapters
            # For now, just check if process is alive
            if server_id in self.server_processes:
                process = self.server_processes[server_id]
                if process.poll() is None:
                    return MCPServerStatus.HEALTHY, "Server process running"
                else:
                    return MCPServerStatus.ERROR, "Server process terminated"

            return MCPServerStatus.UNKNOWN, "Server status unknown"

        except Exception as e:
            logger.error(
                "Error during health check",
                server_id=server_id,
                user_id=user_id,
                error=str(e),
                exc_info=True,
            )
            return MCPServerStatus.ERROR, str(e)

    async def discover_tools(self, user_id: str, server_id: str, force_refresh: bool = False) -> List[MCPToolInfo]:
        """Discover available tools from an MCP server."""
        try:
            # Check cache first
            if not force_refresh and self._is_cache_valid(server_id):
                cached_tools = self.tool_cache.get(server_id, [])
                return [MCPToolInfo.model_validate(tool) for tool in cached_tools]

            config = await self.redis_storage.get_mcp_server_config(user_id, server_id)
            if not config:
                logger.error("Server configuration not found", server_id=server_id, user_id=user_id)
                return []

            if not self._is_server_running(server_id):
                logger.warning("Server not running for tool discovery", server_id=server_id, user_id=user_id)
                return []

            # TODO: Implement actual tool discovery using langchain-mcp-adapters
            # For now, return mock tools based on server configuration
            mock_tools = [
                {
                    "name": f"{config.name}_tool_1",
                    "description": f"Mock tool 1 from {config.name}",
                    "server_id": server_id,
                    "server_name": config.name,
                    "input_schema": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string", "description": "Query parameter"}
                        },
                        "required": ["query"]
                    }
                }
            ]

            # Cache the tools
            self.tool_cache[server_id] = mock_tools
            self.cache_expiry[server_id] = time.time() + self.cache_ttl

            # Store in Redis
            await self.redis_storage.store_mcp_server_tools(user_id, server_id, mock_tools)

            logger.info(
                "Tools discovered from MCP server",
                server_id=server_id,
                user_id=user_id,
                num_tools=len(mock_tools),
            )

            return [MCPToolInfo.model_validate(tool) for tool in mock_tools]

        except Exception as e:
            logger.error(
                "Error discovering tools from MCP server",
                server_id=server_id,
                user_id=user_id,
                error=str(e),
                exc_info=True,
            )
            return []

    async def get_user_mcp_tools(self, user_id: str) -> List[BaseTool]:
        """Get all LangChain tools from user's enabled MCP servers."""
        try:
            # Get all enabled servers for the user
            enabled_servers = await self.redis_storage.get_user_enabled_mcp_servers(user_id)
            
            all_tools = []
            for server_config in enabled_servers:
                # Ensure server is running
                if not self._is_server_running(server_config.server_id):
                    # Try to start the server
                    await self.start_server(user_id, server_config.server_id)
                
                # Discover tools from the server
                mcp_tools = await self.discover_tools(user_id, server_config.server_id)
                
                # Convert MCP tools to LangChain tools
                for mcp_tool in mcp_tools:
                    langchain_tool = self._convert_mcp_tool_to_langchain(mcp_tool, user_id)
                    all_tools.append(langchain_tool)
            
            logger.info(
                "Retrieved MCP tools for user",
                user_id=user_id,
                num_servers=len(enabled_servers),
                num_tools=len(all_tools),
            )
            
            return all_tools
            
        except Exception as e:
            logger.error(
                "Error getting user MCP tools",
                user_id=user_id,
                error=str(e),
                exc_info=True,
            )
            return []

    async def start_all_user_servers(self, user_id: str) -> int:
        """Start all enabled MCP servers for a user. Returns number of servers started."""
        try:
            enabled_servers = await self.redis_storage.get_user_enabled_mcp_servers(user_id)
            started_count = 0
            
            for server_config in enabled_servers:
                if await self.start_server(user_id, server_config.server_id):
                    started_count += 1
            
            logger.info(
                "Started user MCP servers",
                user_id=user_id,
                started_count=started_count,
                total_enabled=len(enabled_servers),
            )
            
            return started_count
            
        except Exception as e:
            logger.error(
                "Error starting all user servers",
                user_id=user_id,
                error=str(e),
                exc_info=True,
            )
            return 0

    async def stop_all_user_servers(self, user_id: str) -> int:
        """Stop all MCP servers for a user. Returns number of servers stopped."""
        try:
            all_servers = await self.redis_storage.list_user_mcp_servers(user_id)
            stopped_count = 0
            
            for server_config in all_servers:
                if await self.stop_server(user_id, server_config.server_id):
                    stopped_count += 1
            
            logger.info(
                "Stopped user MCP servers",
                user_id=user_id,
                stopped_count=stopped_count,
                total_servers=len(all_servers),
            )
            
            return stopped_count
            
        except Exception as e:
            logger.error(
                "Error stopping all user servers",
                user_id=user_id,
                error=str(e),
                exc_info=True,
            )
            return 0

    def _is_server_running(self, server_id: str) -> bool:
        """Check if a server is currently running."""
        return server_id in self.active_servers

    def _is_cache_valid(self, server_id: str) -> bool:
        """Check if the tool cache is still valid for a server."""
        if server_id not in self.cache_expiry:
            return False
        return time.time() < self.cache_expiry[server_id]

    async def _start_stdio_server(self, user_id: str, config: MCPServerConfig) -> bool:
        """Start a stdio-based MCP server."""
        try:
            if not config.command:
                logger.error("No command specified for stdio server", server_id=config.server_id)
                return False

            # Prepare environment
            env = os.environ.copy()
            if config.env_vars:
                env.update(config.env_vars)

            # Start the process
            cmd = [config.command] + (config.args or [])
            process = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env,
                text=True,
            )

            # Store process and server info
            self.server_processes[config.server_id] = process
            self.active_servers[config.server_id] = {
                "user_id": user_id,
                "config": config,
                "transport": "stdio",
                "process": process,
                "started_at": time.time(),
            }

            logger.info(
                "Started stdio MCP server",
                server_id=config.server_id,
                command=config.command,
                args=config.args,
            )
            return True

        except Exception as e:
            logger.error(
                "Error starting stdio MCP server",
                server_id=config.server_id,
                error=str(e),
                exc_info=True,
            )
            return False

    async def _start_http_server(self, user_id: str, config: MCPServerConfig) -> bool:
        """Start an HTTP-based MCP server."""
        try:
            if not config.url:
                logger.error("No URL specified for HTTP server", server_id=config.server_id)
                return False

            # TODO: Implement HTTP MCP server connection using langchain-mcp-adapters
            # For now, just mark as active
            self.active_servers[config.server_id] = {
                "user_id": user_id,
                "config": config,
                "transport": "http",
                "url": config.url,
                "started_at": time.time(),
            }

            logger.info(
                "Started HTTP MCP server",
                server_id=config.server_id,
                url=config.url,
            )
            return True

        except Exception as e:
            logger.error(
                "Error starting HTTP MCP server",
                server_id=config.server_id,
                error=str(e),
                exc_info=True,
            )
            return False

    async def _start_health_monitoring(self, user_id: str, server_id: str) -> None:
        """Start health monitoring task for a server."""
        try:
            # Cancel existing health check task if any
            if server_id in self.health_check_tasks:
                self.health_check_tasks[server_id].cancel()

            # Start new health check task
            task = asyncio.create_task(self._health_check_loop(user_id, server_id))
            self.health_check_tasks[server_id] = task

        except Exception as e:
            logger.error(
                "Error starting health monitoring",
                server_id=server_id,
                error=str(e),
                exc_info=True,
            )

    async def _health_check_loop(self, user_id: str, server_id: str) -> None:
        """Health check loop for a server."""
        try:
            while True:
                # Wait for health check interval
                await asyncio.sleep(30)  # Check every 30 seconds

                # Perform health check
                status, message = await self.health_check(user_id, server_id)

                # Update server health in Redis
                await self.redis_storage.update_mcp_server_health(
                    user_id, server_id, status.value, message
                )

                # If server is unhealthy, try to restart it
                if status == MCPServerStatus.ERROR:
                    logger.warning(
                        "Server unhealthy, attempting restart",
                        server_id=server_id,
                        user_id=user_id,
                        error=message,
                    )
                    await self.restart_server(user_id, server_id)

        except asyncio.CancelledError:
            logger.info("Health check loop cancelled", server_id=server_id, user_id=user_id)
        except Exception as e:
            logger.error(
                "Error in health check loop",
                server_id=server_id,
                user_id=user_id,
                error=str(e),
                exc_info=True,
            )

    def _convert_mcp_tool_to_langchain(self, mcp_tool: MCPToolInfo, user_id: str) -> BaseTool:
        """Convert an MCP tool to a LangChain tool."""
        async def tool_func(query: str) -> str:
            # TODO: Implement actual MCP tool execution using langchain-mcp-adapters
            # For now, return a mock response
            return f"Mock response from {mcp_tool.name} for query: {query}"

        def sync_tool_func(query: str) -> str:
            # TODO: Implement sync version or use asyncio.run
            return f"Mock sync response from {mcp_tool.name} for query: {query}"

        return Tool(
            name=mcp_tool.name,
            description=mcp_tool.description,
            func=sync_tool_func,
            coroutine=tool_func,
        )

    async def cleanup(self) -> None:
        """Clean up all resources."""
        try:
            # Cancel all health check tasks
            for task in self.health_check_tasks.values():
                task.cancel()
            
            # Wait for tasks to complete
            if self.health_check_tasks:
                await asyncio.gather(*self.health_check_tasks.values(), return_exceptions=True)
            
            # Stop all server processes
            for process in self.server_processes.values():
                try:
                    process.terminate()
                    process.wait(timeout=5)
                except:
                    try:
                        process.kill()
                    except:
                        pass
            
            # Clear all data structures
            self.active_servers.clear()
            self.server_processes.clear()
            self.health_check_tasks.clear()
            self.tool_cache.clear()
            self.cache_expiry.clear()
            
            logger.info("MCP server manager cleanup completed")
            
        except Exception as e:
            logger.error("Error during cleanup", error=str(e), exc_info=True) 