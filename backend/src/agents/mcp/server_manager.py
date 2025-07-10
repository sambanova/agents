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
        elif config.transport in ["http", "sse", "streamable-http", "streamable_http"]:
            # Map transport names accepted by langchain-mcp-adapters
            # The library only supports: 'stdio', 'sse', 'websocket', 'streamable_http'
            # Map all HTTP variants to 'streamable_http' since that's the supported HTTP transport
            if config.transport in ("http", "sse", "streamable-http", "streamable_http"):
                transport = "streamable_http"

            server_config = {
                config.name: {
                    "url": config.url.rstrip("/"),
                    "transport": transport,
                }
            }

            # Attach static headers (Option A) or token passed via env (legacy)
            _headers: Dict[str, str] = {}
            # 1) New explicit headers field
            if config.headers:
                _headers.update(config.headers)

            # 2) Legacy AUTH_TOKEN env → Authorization header (Option A shorthand)
            if config.env_vars and "AUTH_TOKEN" in config.env_vars:
                _headers.setdefault("Authorization", f"Bearer {config.env_vars['AUTH_TOKEN']}")

            # 3) Direct Authorization env var support (case sensitive or upper-case)
            if config.env_vars:
                if "Authorization" in config.env_vars:
                    _headers.setdefault("Authorization", config.env_vars["Authorization"])
                elif "AUTHORIZATION" in config.env_vars:
                    _headers.setdefault("Authorization", config.env_vars["AUTHORIZATION"])

            # 4) Convenience mapping for GitHub personal-access tokens supplied as
            #    GITHUB_PAT or GITHUB_TOKEN – widely used variable names.
            if config.env_vars:
                if "GITHUB_PAT" in config.env_vars and "Authorization" not in _headers:
                    _headers["Authorization"] = f"Bearer {config.env_vars['GITHUB_PAT']}"
                elif "GITHUB_TOKEN" in config.env_vars and "Authorization" not in _headers:
                    _headers["Authorization"] = f"Bearer {config.env_vars['GITHUB_TOKEN']}"
                # 5) Direct authorization_token in env_vars (from orchestrator storage)
                elif "authorization_token" in config.env_vars and "Authorization" not in _headers:
                    # The authorization_token might already include "Bearer " prefix
                    auth_token = config.env_vars["authorization_token"]
                    if not auth_token.startswith("Bearer "):
                        auth_token = f"Bearer {auth_token}"
                    _headers["Authorization"] = auth_token

            if _headers:
                server_config[config.name]["headers"] = _headers

            # For HTTP transports, we only need headers, not authorization_token field
            # The langchain-mcp-adapters library handles auth via headers
        else:
            raise ValueError(f"Unsupported transport: {config.transport}")

        # Only add env vars for stdio transport, not for HTTP transports
        if config.transport == "stdio" and config.env_vars:
            server_config[config.name]["env"] = config.env_vars

        client = MultiServerMCPClient(server_config)
        self.mcp_clients[server_id] = client
        
        # Debug: log the final config being passed to the client
        logger.info(
            "Created MCP client",
            server_id=server_id,
            server_name=config.name,
            transport=config.transport,
            final_config=server_config,
        )
        
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

            # Debug: log the config values for remote server detection
            logger.info(
                "Checking server config for remote detection",
                server_id=server_id,
                transport=config.transport,
                url=config.url,
                has_url=bool(config.url),
                is_remote_transport=config.transport in ("http", "sse", "streamable-http", "streamable_http"),
                orchestrator_url=self.orchestrator_url,
            )

            # 1) Purely remote HTTP/SSE servers – no orchestrator, no local process
            if config.url and config.transport in ("http", "sse", "streamable-http", "streamable_http"):
                self.active_servers[server_id] = {
                    "user_id": user_id,
                    "config": config,
                    "transport": config.transport,
                    "remote": True,
                    "started_at": time.time(),
                }
                # Start background health monitor
                await self._start_health_monitoring(user_id, server_id)
                await self.redis_storage.update_mcp_server_health(
                    user_id, server_id, MCPServerStatus.STARTING.value
                )
                logger.info("Registered remote MCP server (no orchestrator)", server_id=server_id)
                return True

            # 2) Local stdio servers managed via external orchestrator
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
                    raw_status = data.get("status", "unknown")
                    # Map orchestrator statuses to backend enum
                    if raw_status in ("running", "healthy"):
                        status = MCPServerStatus.HEALTHY
                    elif raw_status in ("starting",):
                        status = MCPServerStatus.STARTING
                    elif raw_status in ("stopped",):
                        status = MCPServerStatus.STOPPED
                    else:
                        status = MCPServerStatus.ERROR
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
                logger.info("Server not running, attempting to start", server_id=server_id, user_id=user_id)
                # Try to start the server if it's enabled
                if config.enabled:
                    started = await self.start_server(user_id, server_id)
                    if not started:
                        logger.warning("Failed to start server for tool discovery", server_id=server_id, user_id=user_id)
                        return []
                    # Give the server a moment to initialize
                    await asyncio.sleep(1)
                else:
                    logger.warning("Server disabled, cannot discover tools", server_id=server_id, user_id=user_id)
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
        """Get the actual MCP tool from langchain-mcp-adapters directly - no wrapper needed."""
        
        try:
            # Get server config
            server_info = self.active_servers.get(mcp_tool.server_id)
            if not server_info:
                raise ValueError(f"Server {mcp_tool.server_id} not found or not running")
            
            config = server_info["config"]
            client = self._get_or_create_mcp_client(mcp_tool.server_id, config)
            
            # Get the actual MCP tool from the client
            # This is an async operation, but we need to return a tool synchronously
            # So we'll create a cached version that can be called later
            
            # For now, create a simple wrapper that will get the real tool when called
            class MCPToolWrapper(BaseTool):
                # Pydantic configuration to allow arbitrary types on attributes
                class Config:
                    arbitrary_types_allowed = True

                # Static fields required by BaseTool
                name: str = mcp_tool.name
                description: str = mcp_tool.description

                # Extra fields for delegation logic
                tool_info: MCPToolInfo
                server_manager: Any
                _cached_tool: Optional[Any] = None

                def __init__(self, tool_info: MCPToolInfo, server_manager: Any):
                    super().__init__(tool_info=tool_info, server_manager=server_manager)
                    # _cached_tool initialized as None by default
                
                async def _get_real_tool(self):
                    """Get the actual MCP tool from langchain-mcp-adapters."""
                    if self._cached_tool is not None:
                        return self._cached_tool
                        
                    try:
                        server_info = self.server_manager.active_servers.get(self.tool_info.server_id)
                        if not server_info:
                            raise ValueError(f"Server {self.tool_info.server_id} not found")
                        
                        config = server_info["config"]
                        client = self.server_manager._get_or_create_mcp_client(self.tool_info.server_id, config)
                        
                        # Get tools from the client
                        tools = await client.get_tools()
                        
                        # Find our specific tool
                        for tool in tools:
                            if tool.name == self.tool_info.name:
                                self._cached_tool = tool
                                return tool
                                
                        raise ValueError(f"Tool {self.tool_info.name} not found on server")
                        
                    except Exception as e:
                        logger.error(
                            "Error getting real MCP tool",
                            tool_name=self.tool_info.name,
                            error=str(e),
                            exc_info=True,
                        )
                        raise
                
                async def ainvoke(self, tool_input, **kwargs):
                    """Delegate to the real MCP tool."""
                    import json, re

                    # Clean possible XML tag remnants (e.g., trailing '</tool_input')
                    if isinstance(tool_input, str):
                        tool_input = re.sub(r"</?tool_input>?$", "", tool_input.strip())
                        # Try to parse JSON if the string looks like JSON
                        stripped = tool_input.strip()
                        if stripped.startswith("{") and stripped.endswith("}"):
                            try:
                                tool_input = json.loads(stripped)
                            except json.JSONDecodeError:
                                pass  # Leave as raw string if parsing fails

                    real_tool = await self._get_real_tool()
                    return await real_tool.ainvoke(tool_input, **kwargs)
                
                def invoke(self, tool_input, **kwargs):
                    """Delegate to the real MCP tool (synchronous)."""
                    import asyncio, json, re
                    # Clean like in async path
                    if isinstance(tool_input, str):
                        tool_input = re.sub(r"</?tool_input>?$", "", tool_input.strip())
                        stripped = tool_input.strip()
                        if stripped.startswith("{") and stripped.endswith("}"):
                            try:
                                tool_input = json.loads(stripped)
                            except json.JSONDecodeError:
                                pass
                    return asyncio.run(self.ainvoke(tool_input, **kwargs))
                
                def _run(self, *args, **kwargs):
                    """Legacy sync interface."""
                    return self.invoke(*args, **kwargs)
                
                async def _arun(self, *args, **kwargs):
                    """Legacy async interface."""
                    return await self.ainvoke(*args, **kwargs)
            
            return MCPToolWrapper(mcp_tool, self)
            
        except Exception as e:
            logger.error(
                "Error creating MCP tool wrapper",
                tool_name=mcp_tool.name,
                error=str(e),
                exc_info=True,
            )
            # Return a dummy tool that shows the error
            return Tool(
                name=mcp_tool.name,
                description=f"Error: {str(e)}",
                func=lambda x: f"Error: MCP tool {mcp_tool.name} is not available: {str(e)}",
            )

    async def _discover_tools_from_mcp(self, server_id: str, config: MCPServerConfig) -> List[Dict[str, Any]]:
        """Discover tools from an MCP server using langchain-mcp-adapters."""
        logger.info("Discovering tools via MCP", server_id=server_id, transport=config.transport, url=config.url)
        try:
            # Reuse or create persistent client
            client = self._get_or_create_mcp_client(server_id, config)
            tools = await client.get_tools()
            
            # Convert tools to our format
            discovered_tools = []
            for tool in tools:
                # Try to extract the input schema from different possible attributes
                input_schema = {}
                
                # Check for args_schema (most common)
                if hasattr(tool, 'args_schema') and tool.args_schema:
                    if hasattr(tool.args_schema, 'model_json_schema'):
                        # Pydantic v2 style
                        input_schema = tool.args_schema.model_json_schema()
                    elif hasattr(tool.args_schema, 'schema'):
                        # Pydantic v1 style
                        input_schema = tool.args_schema.schema()
                    elif hasattr(tool.args_schema, '__annotations__'):
                        # Simple class with annotations
                        properties = {}
                        for field_name, field_type in tool.args_schema.__annotations__.items():
                            properties[field_name] = {
                                "type": "string",  # Default to string
                                "description": f"Parameter {field_name}"
                            }
                        input_schema = {
                            "type": "object",
                            "properties": properties,
                            "required": list(properties.keys())
                        }
                
                # Check for input_schema attribute directly
                elif hasattr(tool, 'input_schema'):
                    input_schema = tool.input_schema
                
                # Check for description of parameters in the tool description
                elif hasattr(tool, 'description') and tool.description:
                    # Try to extract parameter info from description
                    # This is a fallback for tools that don't have proper schema
                    pass
                
                tool_info = {
                    "name": tool.name,
                    "description": tool.description,
                    "server_id": server_id,
                    "server_name": config.name,
                    "input_schema": input_schema
                }
                discovered_tools.append(tool_info)
                
                logger.debug(
                    "Discovered tool",
                    tool_name=tool.name,
                    has_schema=bool(input_schema),
                    schema_keys=list(input_schema.keys()) if input_schema else []
                )
            
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
            logger.info(
                "Starting MCP tool execution",
                server_id=server_id,
                tool_name=tool_name,
                arguments=arguments,
            )
            
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
            
            logger.info(
                "Found target tool, executing",
                tool_name=tool_name,
                tool_description=target_tool.description,
                tool_args_schema=getattr(target_tool, 'args_schema', None),
                arguments_provided=arguments,
            )
            
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
                result_length=len(str(result)) if result else 0,
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
                arguments=arguments,
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