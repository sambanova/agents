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
        
        # MCP client connections for real tool execution (persistent)
        self.mcp_clients: Dict[str, Any] = {}  # server_id -> MultiServerMCPClient

        # Adaptive health-check backoff per server
        self.health_backoff: Dict[str, int] = {}  # server_id -> seconds to wait before next probe

        # Async tasks that continuously drain MCP subprocess stdout/stderr so pipes
        # never block (keyed by server_id)
        self.output_tasks: Dict[str, asyncio.Task] = {}

        # Optional external orchestrator URL.  If defined, all lifecycle
        # operations are delegated via HTTP rather than spawning locally.  This
        # lets the main API pod remain lightweight while a dedicated
        # orchestrator handles heavy studio binaries.
        self.orchestrator_url: Optional[str] = os.getenv("MCP_ORCHESTRATOR_URL")

        # Lazily-created httpx client session for orchestrator calls
        self._orch_client: Optional["httpx.AsyncClient"] = None


    def _get_or_create_mcp_client(self, server_id: str, config: MCPServerConfig):
        """Return a cached MultiServerMCPClient for the given server, creating one if needed."""
        from langchain_mcp_adapters.client import MultiServerMCPClient

        if server_id in self.mcp_clients:
            return self.mcp_clients[server_id]

        # Build configuration dict once
        if config.transport == "stdio":
            server_config = {
                config.name: {
                    "command": config.command,
                    "args": config.args or [],
                    "transport": "stdio",
                }
            }
        elif config.transport in ["http", "sse"]:
            transport = "streamable_http" if config.transport == "sse" else "http"
            server_config = {
                config.name: {
                    "url": config.url,
                    "transport": transport,
                }
            }
        else:
            raise ValueError(f"Unsupported transport: {config.transport}")

        if config.env_vars:
            server_config[config.name]["env"] = config.env_vars

        client = MultiServerMCPClient(server_config)
        self.mcp_clients[server_id] = client
        return client

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
            if self.orchestrator_url:
                try:
                    await self._delegate("POST", f"/servers/{server_id}/start", user_id)
                    # health monitoring still local (we rely on orch status)
                    # Track remote server locally so subsequent tool calls succeed
                    self.active_servers[server_id] = {
                        "user_id": user_id,
                        "config": config,
                        "transport": config.transport or "stdio",
                        "remote": True,
                        "started_at": time.time(),
                    }
                    await self._start_health_monitoring(user_id, server_id)
                    await self.redis_storage.update_mcp_server_health(
                        user_id, server_id, MCPServerStatus.STARTING.value
                    )
                    return True
                except Exception as e:
                    logger.error("Orchestrator start failed", error=str(e))
                    await self.redis_storage.update_mcp_server_health(
                        user_id, server_id, MCPServerStatus.ERROR.value
                    )
                    return False

            if config.transport == "stdio":
                success = await self._start_stdio_server(user_id, config)
            elif config.transport == "http":
                success = await self._start_http_server(user_id, config)
            elif config.transport == "sse":
                success = await self._start_sse_server(user_id, config)
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
            if self.orchestrator_url:
                try:
                    await self._delegate("POST", f"/servers/{server_id}/stop", user_id)
                    await self.redis_storage.update_mcp_server_health(
                        user_id, server_id, MCPServerStatus.STOPPED.value
                    )
                    # Remove from local active registry
                    if server_id in self.active_servers:
                        self.active_servers.pop(server_id, None)
                    return True
                except Exception as e:
                    logger.error("Orchestrator stop failed", error=str(e))
                    return False

            if not self._is_server_running(server_id):
                logger.info("Server not running", server_id=server_id, user_id=user_id)
                return True

            # Stop health monitoring
            if server_id in self.health_check_tasks:
                self.health_check_tasks[server_id].cancel()
                del self.health_check_tasks[server_id]

            # Stop server process
            if server_id in self.server_processes:
                proc = self.server_processes[server_id]
                try:
                    import signal, os
                    # Terminate the entire process-group (created with start_new_session)
                    os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
                    try:
                        await asyncio.wait_for(proc.wait(), timeout=5)
                    except asyncio.TimeoutError:
                        os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
                        await proc.wait()
                except ProcessLookupError:
                    # Already gone
                    pass
                except Exception as e:
                    logger.warning("Error stopping server process", error=str(e))
                finally:
                    del self.server_processes[server_id]

            # Clean up active server info
            if server_id in self.active_servers:
                del self.active_servers[server_id]

            # Cancel stdout drain task if running
            if server_id in self.output_tasks:
                self.output_tasks[server_id].cancel()
                del self.output_tasks[server_id]

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
            if self.orchestrator_url:
                try:
                    data = await self._delegate("GET", f"/servers/{server_id}/status", user_id)
                    status = MCPServerStatus(data.get("status", "unknown"))
                    return status, data.get("message", "")
                except Exception as e:
                    logger.error("Orchestrator health request failed", error=str(e))
                    return MCPServerStatus.ERROR, str(e)

            config = await self.redis_storage.get_mcp_server_config(user_id, server_id)
            if not config:
                return MCPServerStatus.ERROR, "Server configuration not found"

            if not self._is_server_running(server_id):
                return MCPServerStatus.STOPPED, "Server process not running"

            # TODO: Implement actual MCP health check using langchain-mcp-adapters
            # For stdio transports we inspect the subprocess; for http/sse we
            # currently assume the server is healthy (a more sophisticated ping
            # can be added later).

            if server_id in self.server_processes:
                process = self.server_processes[server_id]
                if process.returncode is None:  # Process still running
                    return MCPServerStatus.HEALTHY, "Server process running"
                else:
                    return MCPServerStatus.ERROR, "Server process terminated"

            # If there's no local subprocess then this is an HTTP/SSE server –
            # treat as healthy for now.
            return MCPServerStatus.HEALTHY, "Remote server assumed healthy"

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
        """Discover available tools from an MCP server using real MCP connection."""
        try:
            # 1) In-memory cache
            if not force_refresh and self._is_cache_valid(server_id):
                cached_tools = self.tool_cache.get(server_id, [])
                return [MCPToolInfo.model_validate(tool) for tool in cached_tools]

            # 2) Redis cache (persistent across processes)
            if not force_refresh:
                redis_cached = await self.redis_storage.get_mcp_server_tools(user_id, server_id)
                if redis_cached:
                    # Re-hydrate local cache with same TTL window
                    self.tool_cache[server_id] = redis_cached
                    self.cache_expiry[server_id] = time.time() + self.cache_ttl
                    return [MCPToolInfo.model_validate(t) for t in redis_cached]

            config = await self.redis_storage.get_mcp_server_config(user_id, server_id)
            if not config:
                logger.error("Server configuration not found", server_id=server_id, user_id=user_id)
                return []

            if not self._is_server_running(server_id):
                logger.warning("Server not running for tool discovery", server_id=server_id, user_id=user_id)
                return []

            # Try to discover tools using real MCP connection
            try:
                discovered_tools = await self._discover_tools_from_mcp(server_id, config)
                if discovered_tools:
                    # Cache the tools
                    self.tool_cache[server_id] = discovered_tools
                    self.cache_expiry[server_id] = time.time() + self.cache_ttl

                    # Store in Redis
                    await self.redis_storage.store_mcp_server_tools(user_id, server_id, discovered_tools)

                    logger.info(
                        "Tools discovered from MCP server",
                        server_id=server_id,
                        user_id=user_id,
                        num_tools=len(discovered_tools),
                    )

                    return [MCPToolInfo.model_validate(tool) for tool in discovered_tools]
            except Exception as mcp_error:
                logger.warning(
                    "Failed to discover tools from MCP server, falling back to mock",
                    server_id=server_id,
                    error=str(mcp_error),
                )

            # Fallback to mock tools if MCP discovery fails
            mock_tools = [
                {
                    "name": f"{config.name}_tool_1",
                    "description": f"Mock tool from {config.name} (MCP connection failed)",
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

            # Cache the mock tools
            self.tool_cache[server_id] = mock_tools
            self.cache_expiry[server_id] = time.time() + self.cache_ttl

            # Store in Redis
            await self.redis_storage.store_mcp_server_tools(user_id, server_id, mock_tools)

            logger.info(
                "Using mock tools for MCP server",
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
        """Check if a server is currently running.

        For ``stdio`` transports we additionally confirm that the underlying
        subprocess has not exited (``returncode`` is ``None``).  Previously we
        only checked membership in ``self.active_servers`` which meant crashed
        processes were still considered alive, leading to misleading health
        reports and restart loops.  For ``http`` and ``sse`` transports we
        keep the original behaviour because there is no local subprocess to
        inspect.
        """
        if server_id not in self.active_servers:
            return False

        server_info = self.active_servers[server_id]
        transport = server_info.get("transport")

        # For stdio-based servers verify the subprocess is still running
        if transport == "stdio":
            proc = self.server_processes.get(server_id)
            if proc is None:
                return False
            return proc.returncode is None  # None ⇒ still running

        # Remote orchestrator-managed server: we treat presence as running
        if server_info.get("remote"):
            return True

        # For http/sse transports we assume running as long as we have the info
        return True

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

            cmd = [config.command] + (config.args or [])

            # Launch asynchronously so we don't block the event loop and ensure we
            # create a new session (process-group) so we can cleanly terminate the
            # whole tree later.
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdin=subprocess.DEVNULL,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                env=env,
                start_new_session=True,  # gives us a dedicated process-group
            )

            # Drain stdout in background to avoid pipe back-pressure deadlocks
            async def _drain_output(proc: asyncio.subprocess.Process, sid: str):
                try:
                    if proc.stdout is None:
                        return
                    async for raw_line in proc.stdout:
                        try:
                            line = raw_line.decode().rstrip()
                        except AttributeError:
                            # Already str
                            line = raw_line.rstrip()
                        logger.info("[mcp:%s] %s", config.name, line)
                except asyncio.CancelledError:
                    # normal on shutdown
                    pass
                except Exception as e:
                    logger.warning("Error reading MCP stdout", server_id=sid, error=str(e))

            drain_task = asyncio.create_task(_drain_output(process, config.server_id))

            # Store process and server info
            self.server_processes[config.server_id] = process
            self.output_tasks[config.server_id] = drain_task
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

    async def _start_sse_server(self, user_id: str, config: MCPServerConfig) -> bool:
        """Start an SSE-based MCP server."""
        try:
            if not config.url:
                logger.error("No URL specified for SSE server", server_id=config.server_id)
                return False

            # TODO: Implement SSE MCP server connection using langchain-mcp-adapters
            # For now, just mark as active (similar to HTTP for now)
            self.active_servers[config.server_id] = {
                "user_id": user_id,
                "config": config,
                "transport": "sse",
                "url": config.url,
                "started_at": time.time(),
            }

            logger.info(
                "Started SSE MCP server",
                server_id=config.server_id,
                url=config.url,
            )
            return True

        except Exception as e:
            logger.error(
                "Error starting SSE MCP server",
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
            interval = self.health_backoff.get(server_id, 30)
            while True:
                await asyncio.sleep(interval)

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
                    # Exponential backoff up to 5 min
                    interval = min(interval * 2, 300)
                    self.health_backoff[server_id] = interval
                else:
                    # Reset backoff on success
                    interval = 30
                    self.health_backoff[server_id] = interval

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
        """Convert an MCP tool to a LangChain tool with real MCP execution."""
        async def tool_func(tool_input, **kwargs) -> str:
            try:
                # Handle both dict and string inputs
                if isinstance(tool_input, str):
                    # Try to parse as JSON if it's a string
                    try:
                        import json
                        arguments = json.loads(tool_input)
                    except:
                        # If not JSON, treat as a simple query parameter
                        arguments = {"query": tool_input}
                elif isinstance(tool_input, dict):
                    arguments = tool_input
                else:
                    arguments = {"input": str(tool_input)}
                
                # Try to execute the tool using real MCP connection
                result = await self._execute_mcp_tool(mcp_tool.server_id, mcp_tool.name, arguments)
                return result
            except Exception as e:
                logger.error(
                    "MCP tool execution failed, returning mock response",
                    tool_name=mcp_tool.name,
                    server_id=mcp_tool.server_id,
                    error=str(e),
                )
                # Fallback to mock response
                return f"Mock response from {mcp_tool.name} for input: {tool_input} (MCP execution failed: {str(e)})"

        def sync_tool_func(tool_input, **kwargs) -> str:
            try:
                # Use asyncio.run for sync execution
                return asyncio.run(tool_func(tool_input, **kwargs))
            except Exception as e:
                logger.error(
                    "Sync MCP tool execution failed",
                    tool_name=mcp_tool.name,
                    error=str(e),
                )
                return f"Mock sync response from {mcp_tool.name} for input: {tool_input} (execution failed)"

        return Tool(
            name=mcp_tool.name,
            description=mcp_tool.description,
            func=sync_tool_func,
            coroutine=tool_func,
        )

    async def _discover_tools_from_mcp(self, server_id: str, config: MCPServerConfig) -> List[Dict[str, Any]]:
        """Discover tools from an MCP server using langchain-mcp-adapters."""
        try:
            # Reuse or create persistent client
            client = self._get_or_create_mcp_client(server_id, config)
            tools = await client.get_tools()
            
            # Convert tools to our format
            discovered_tools = []
            for tool in tools:
                tool_info = {
                    "name": tool.name,
                    "description": tool.description,
                    "server_id": server_id,
                    "server_name": config.name,
                    "input_schema": getattr(tool, 'args_schema', {})
                }
                discovered_tools.append(tool_info)
            
            logger.info(
                "Successfully discovered tools from MCP server",
                server_id=server_id,
                num_tools=len(discovered_tools),
            )
            
            return discovered_tools
                
        except ImportError:
            logger.warning("langchain-mcp-adapters not available, using mock tools")
            raise
        except Exception as e:
            logger.error(
                "Error discovering tools from MCP server",
                server_id=server_id,
                error=str(e),
                exc_info=True,
            )
            raise

    async def _execute_mcp_tool(self, server_id: str, tool_name: str, arguments: Dict[str, Any]) -> str:
        """Execute an MCP tool using langchain-mcp-adapters."""
        try:
            # For now, we'll need to recreate the connection for each tool execution
            # In the future, we could maintain persistent connections
            
            # Get server config
            server_info = self.active_servers.get(server_id)
            if not server_info:
                raise ValueError(f"Server {server_id} not found or not running")
            
            config = server_info["config"]
            
            client = self._get_or_create_mcp_client(server_id, config)

            # Fetch cached tools from the client (await because async)
            tools = await client.get_tools()

            # Find the specific tool
            target_tool = None
            for tool in tools:
                if tool.name == tool_name:
                    target_tool = tool
                    break
            
            if not target_tool:
                raise ValueError(f"Tool {tool_name} not found on server {server_id}")
            
            # Execute the tool
            if hasattr(target_tool, 'ainvoke'):
                result = await target_tool.ainvoke(arguments)
            elif hasattr(target_tool, 'invoke'):
                result = target_tool.invoke(arguments)
            else:
                # Fallback to calling the tool directly
                result = await target_tool(**arguments)
            
            logger.info(
                "Successfully executed MCP tool",
                server_id=server_id,
                tool_name=tool_name,
            )
            
            return str(result)
                
        except ImportError:
            logger.warning("langchain-mcp-adapters not available")
            raise
        except Exception as e:
            logger.error(
                "Error executing MCP tool",
                server_id=server_id,
                tool_name=tool_name,
                error=str(e),
                exc_info=True,
            )
            raise

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

            # Close MCP clients
            for client in self.mcp_clients.values():
                try:
                    await client.aclose() if hasattr(client, "aclose") else None
                except Exception:
                    pass
            self.mcp_clients.clear()
            
            logger.info("MCP server manager cleanup completed")
            
        except Exception as e:
            logger.error("Error during cleanup", error=str(e), exc_info=True) 

    async def _orch(self) -> "httpx.AsyncClient":
        """Return a shared httpx.AsyncClient for orchestrator calls."""
        import httpx
        if self._orch_client is None:
            timeout = httpx.Timeout(30.0)
            self._orch_client = httpx.AsyncClient(base_url=self.orchestrator_url, timeout=timeout)
        return self._orch_client

    async def _delegate(self, method: str, path: str, user_id: str, **kwargs):
        """Send request to orchestrator and return JSON result."""
        client = await self._orch()
        headers = kwargs.pop("headers", {})
        headers["X-User-Id"] = user_id
        resp = await client.request(method, path, headers=headers, **kwargs)
        resp.raise_for_status()
        return resp.json() 