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

        # HTTP client for health checks and connection validation
        self._http_client: Optional["httpx.AsyncClient"] = None

    async def _get_http_client(self) -> "httpx.AsyncClient":
        """Get or create HTTP client for health checks and validation."""
        if self._http_client is None:
            import httpx
            self._http_client = httpx.AsyncClient(
                timeout=httpx.Timeout(30.0, connect=10.0, read=20.0),
                limits=httpx.Limits(max_connections=10, max_keepalive_connections=5),
                follow_redirects=True,
            )
        return self._http_client

    def _get_transport_for_langchain(self, config: MCPServerConfig) -> str:
        """
        Map user-provided transport to langchain-mcp-adapters supported transport.
        
        The langchain-mcp-adapters library supports:
        - 'stdio': Local process communication
        - 'sse': Server-sent events
        - 'streamable_http': HTTP with streaming support
        - 'websocket': WebSocket (not used in this implementation)
        
        This function maps various HTTP transport names to the appropriate
        langchain-mcp-adapters transport type.
        """
        transport = config.transport.lower()
        
        if transport == "stdio":
            return "stdio"
        elif transport == "sse":
            return "sse"
        elif transport in ("http", "streamable-http", "streamable_http"):
            return "streamable_http"
        else:
            logger.warning(
                "Unknown transport type, defaulting to streamable_http",
                transport=transport,
                server_id=config.server_id,
            )
            return "streamable_http"

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
            # Use the improved transport mapping
            transport = self._get_transport_for_langchain(config)

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
            mapped_transport=server_config[config.name].get("transport", "unknown"),
            final_config=server_config,
        )
        
        return client

    async def _validate_http_connection(self, config: MCPServerConfig) -> Tuple[bool, Optional[str]]:
        """
        Validate HTTP connection to MCP server.
        
        Returns:
            Tuple of (is_valid, error_message)
        """
        if not config.url:
            return False, "No URL specified"

        try:
            http_client = await self._get_http_client()
            
            # Prepare headers
            headers = {}
            if config.headers:
                headers.update(config.headers)
            
            # Add auth headers from env_vars
            if config.env_vars:
                if "Authorization" in config.env_vars:
                    headers["Authorization"] = config.env_vars["Authorization"]
                elif "AUTHORIZATION" in config.env_vars:
                    headers["Authorization"] = config.env_vars["AUTHORIZATION"]
                elif "AUTH_TOKEN" in config.env_vars:
                    headers["Authorization"] = f"Bearer {config.env_vars['AUTH_TOKEN']}"
                elif "GITHUB_PAT" in config.env_vars:
                    headers["Authorization"] = f"Bearer {config.env_vars['GITHUB_PAT']}"
                elif "GITHUB_TOKEN" in config.env_vars:
                    headers["Authorization"] = f"Bearer {config.env_vars['GITHUB_TOKEN']}"
                elif "authorization_token" in config.env_vars:
                    auth_token = config.env_vars["authorization_token"]
                    if not auth_token.startswith("Bearer "):
                        auth_token = f"Bearer {auth_token}"
                    headers["Authorization"] = auth_token

            # Try to connect to the server
            url = config.url.rstrip("/")
            
            # For MCP servers, we can try a basic HTTP request to check connectivity
            # Most MCP servers will respond with some form of error or info for basic HTTP requests
            try:
                response = await http_client.get(
                    url,
                    headers=headers,
                    timeout=10.0,
                )
                
                # Even if we get 4xx/5xx, the server is reachable
                if response.status_code < 600:
                    logger.debug(
                        "HTTP connection validation successful",
                        server_id=config.server_id,
                        url=url,
                        status_code=response.status_code,
                    )
                    return True, None
                else:
                    return False, f"HTTP error {response.status_code}"
                    
            except Exception as req_error:
                # For MCP servers, connectivity errors are more important than HTTP errors
                error_str = str(req_error).lower()
                if "timeout" in error_str:
                    return False, f"Connection timeout: {req_error}"
                elif "connection refused" in error_str or "connection failed" in error_str:
                    return False, f"Connection refused: {req_error}"
                elif "name resolution" in error_str or "dns" in error_str:
                    return False, f"DNS resolution failed: {req_error}"
                elif "ssl" in error_str or "certificate" in error_str:
                    return False, f"SSL/Certificate error: {req_error}"
                else:
                    return False, f"HTTP request failed: {req_error}"
                    
        except Exception as e:
            logger.error(
                "Error validating HTTP connection",
                server_id=config.server_id,
                url=config.url,
                error=str(e),
                exc_info=True,
            )
            return False, f"Connection validation failed: {str(e)}"

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
                # Validate HTTP connection first
                is_valid, error_msg = await self._validate_http_connection(config)
                if not is_valid:
                    logger.error(
                        "HTTP connection validation failed",
                        server_id=server_id,
                        url=config.url,
                        error=error_msg,
                    )
                    await self.redis_storage.update_mcp_server_health(
                        user_id, server_id, MCPServerStatus.ERROR.value, error_msg
                    )
                    return False

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

            # Perform transport-specific health checks
            if config.transport == "stdio":
                # For stdio, check if subprocess is still running
                if server_id in self.server_processes:
                    process = self.server_processes[server_id]
                    if process.returncode is None:  # Process still running
                        return MCPServerStatus.HEALTHY, "Server process running"
                    else:
                        return MCPServerStatus.ERROR, "Server process terminated"
                else:
                    return MCPServerStatus.ERROR, "Server process not found"
            
            elif config.transport in ("http", "sse", "streamable-http", "streamable_http"):
                # For HTTP/SSE servers, validate the connection
                try:
                    is_valid, error_msg = await self._validate_http_connection(config)
                    if is_valid:
                        # Additional check: try to create MCP client and test basic functionality
                        try:
                            client = self._get_or_create_mcp_client(server_id, config)
                            # Test if we can at least initialize the client
                            # Don't call get_tools() here as it might be expensive
                            return MCPServerStatus.HEALTHY, "HTTP server reachable and MCP client initialized"
                        except Exception as mcp_error:
                            logger.warning(
                                "HTTP server reachable but MCP client failed",
                                server_id=server_id,
                                error=str(mcp_error),
                            )
                            return MCPServerStatus.ERROR, f"MCP client error: {str(mcp_error)}"
                    else:
                        return MCPServerStatus.ERROR, error_msg or "HTTP connection failed"
                except Exception as e:
                    logger.error(
                        "Error during HTTP health check",
                        server_id=server_id,
                        error=str(e),
                    )
                    return MCPServerStatus.ERROR, f"Health check failed: {str(e)}"
            
            else:
                return MCPServerStatus.ERROR, f"Unsupported transport: {config.transport}"

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
                else:
                    # No tools discovered but no error - server might be empty
                    logger.warning(
                        "No tools discovered from MCP server",
                        server_id=server_id,
                        user_id=user_id,
                    )
                    return []
            except Exception as mcp_error:
                error_str = str(mcp_error).lower()
                
                # Log detailed error information
                logger.error(
                    "MCP tool discovery failed",
                    server_id=server_id,
                    user_id=user_id,
                    transport=config.transport,
                    url=config.url,
                    error=str(mcp_error),
                    exc_info=True,
                )
                
                # For HTTP servers, check if it's a connection issue
                if config.transport in ("http", "sse", "streamable-http", "streamable_http"):
                    if any(keyword in error_str for keyword in ["connection", "timeout", "refused", "unreachable"]):
                        logger.error(
                            "HTTP MCP server connection failed during tool discovery",
                            server_id=server_id,
                            url=config.url,
                            error=str(mcp_error),
                        )
                        # Update server status to ERROR
                        await self.redis_storage.update_mcp_server_health(
                            user_id, server_id, MCPServerStatus.ERROR.value, f"Connection failed: {str(mcp_error)}"
                        )
                        return []
                    elif any(keyword in error_str for keyword in ["auth", "unauthorized", "forbidden", "token"]):
                        logger.error(
                            "HTTP MCP server authentication failed during tool discovery",
                            server_id=server_id,
                            url=config.url,
                            error=str(mcp_error),
                        )
                        # Update server status to ERROR
                        await self.redis_storage.update_mcp_server_health(
                            user_id, server_id, MCPServerStatus.ERROR.value, f"Authentication failed: {str(mcp_error)}"
                        )
                        return []
                
                # For other errors, try to provide more specific information
                if "langchain_mcp_adapters" in error_str:
                    logger.error(
                        "MCP adapter library error during tool discovery",
                        server_id=server_id,
                        error=str(mcp_error),
                    )
                elif "transport" in error_str:
                    logger.error(
                        "MCP transport error during tool discovery",
                        server_id=server_id,
                        transport=config.transport,
                        error=str(mcp_error),
                    )
                
                # Don't fallback to mock tools - return empty list to show real issue
                return []

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

            # Validate HTTP connection before marking as active
            is_valid, error_msg = await self._validate_http_connection(config)
            if not is_valid:
                logger.error(
                    "HTTP connection validation failed during startup",
                    server_id=config.server_id,
                    url=config.url,
                    error=error_msg,
                )
                return False

            # Try to create MCP client to test basic functionality
            try:
                client = self._get_or_create_mcp_client(config.server_id, config)
                logger.info(
                    "MCP client created successfully for HTTP server",
                    server_id=config.server_id,
                    url=config.url,
                )
            except Exception as client_error:
                logger.error(
                    "Failed to create MCP client for HTTP server",
                    server_id=config.server_id,
                    url=config.url,
                    error=str(client_error),
                    exc_info=True,
                )
                return False

            # Mark as active
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

            # Validate HTTP connection before marking as active
            # SSE servers typically have HTTP endpoints too
            is_valid, error_msg = await self._validate_http_connection(config)
            if not is_valid:
                logger.error(
                    "HTTP connection validation failed during SSE startup",
                    server_id=config.server_id,
                    url=config.url,
                    error=error_msg,
                )
                return False

            # Try to create MCP client to test basic functionality
            try:
                client = self._get_or_create_mcp_client(config.server_id, config)
                logger.info(
                    "MCP client created successfully for SSE server",
                    server_id=config.server_id,
                    url=config.url,
                )
            except Exception as client_error:
                logger.error(
                    "Failed to create MCP client for SSE server",
                    server_id=config.server_id,
                    url=config.url,
                    error=str(client_error),
                    exc_info=True,
                )
                return False

            # Mark as active
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

                def _requires_structured_input(self, tool) -> bool:
                    """Check if tool requires structured JSON input based on schema."""
                    return (
                        hasattr(tool, 'args_schema') and 
                        tool.args_schema is not None and
                        hasattr(tool.args_schema, 'model_json_schema')
                    )

                def _get_schema_info(self, tool) -> str:
                    """Get helpful schema information for error messages."""
                    try:
                        if hasattr(tool, 'args_schema') and tool.args_schema and hasattr(tool.args_schema, 'model_json_schema'):
                            schema = tool.args_schema.model_json_schema()
                            properties = schema.get('properties', {})
                            required = schema.get('required', [])
                            
                            # Build a helpful format example
                            example_params = {}
                            for prop_name, prop_info in properties.items():
                                prop_type = prop_info.get('type', 'string')
                                if prop_type == 'string':
                                    example_params[prop_name] = f"<{prop_name}_value>"
                                elif prop_type == 'integer':
                                    example_params[prop_name] = 10
                                elif prop_type == 'boolean':
                                    example_params[prop_name] = True
                                else:
                                    example_params[prop_name] = f"<{prop_name}_value>"
                            
                            import json
                            example_json = json.dumps(example_params, indent=2)
                            
                            required_info = f" (required: {required})" if required else ""
                            return f"{example_json}{required_info}"
                        else:
                            return "JSON object with appropriate parameters"
                    except Exception:
                        return "JSON object with appropriate parameters"

                def _parse_structured_input(self, tool_input: str, tool) -> dict:
                    """Intelligently parse string input into structured format for MCP tools."""
                    import json
                    import re
                    from typing import Dict, Any
                    
                    # Clean the input
                    cleaned_input = tool_input.strip()
                    
                    # Strategy 1: Direct JSON parsing
                    if cleaned_input.startswith("{") and cleaned_input.endswith("}"):
                        try:
                            return json.loads(cleaned_input)
                        except json.JSONDecodeError as e:
                            logger.debug(f"Direct JSON parsing failed: {e}")
                    
                    # Strategy 2: Extract JSON from mixed content
                    json_match = re.search(r'\{[^{}]*\}', cleaned_input)
                    if json_match:
                        try:
                            return json.loads(json_match.group())
                        except json.JSONDecodeError:
                            pass
                    
                    # Strategy 3: Parse parameter-style input
                    # Handle formats like: jql="project = 'Cloud'" maxResults=10
                    params = {}
                    
                    # Get expected parameters from schema
                    expected_params = set()
                    if hasattr(tool, 'args_schema') and tool.args_schema and hasattr(tool.args_schema, 'model_json_schema'):
                        schema = tool.args_schema.model_json_schema()
                        expected_params = set(schema.get('properties', {}).keys())
                    
                    # Try to extract key=value pairs
                    # Pattern matches: key="value" or key=value or key: value
                    param_pattern = r'(\w+)\s*[:=]\s*(?:"([^"]*)"|\'([^\']*)\'|([^\s,]+))'
                    matches = re.findall(param_pattern, cleaned_input)
                    
                    for match in matches:
                        key = match[0]
                        # Take the first non-empty group (quoted or unquoted value)
                        value = match[1] or match[2] or match[3]
                        
                        # Only include if it's an expected parameter or we don't have schema info
                        if not expected_params or key in expected_params:
                            # Try to convert to appropriate type
                            if value.lower() in ('true', 'false'):
                                params[key] = value.lower() == 'true'
                            elif value.isdigit():
                                params[key] = int(value)
                            else:
                                params[key] = value
                    
                    if params:
                        return params
                    
                    # Strategy 4: Natural language pattern extraction
                    # Look for common patterns like "search for X" or "find Y"
                    if expected_params:
                        # Try to map common patterns to parameters
                        for param in expected_params:
                            param_lower = param.lower()
                            
                            # Common parameter name patterns
                            if param_lower in ['query', 'q', 'search', 'term']:
                                # Extract quoted strings or the whole input as query
                                quoted_match = re.search(r'["\']([^"\']+)["\']', cleaned_input)
                                if quoted_match:
                                    params[param] = quoted_match.group(1)
                                else:
                                    params[param] = cleaned_input
                                break
                            elif param_lower in ['jql']:
                                # Special handling for JQL queries
                                jql_match = re.search(r'(?:jql[:\s=]+)?["\']?([^"\']+)["\']?', cleaned_input)
                                if jql_match:
                                    params[param] = jql_match.group(1).strip()
                                break
                    
                    # Strategy 4.5: Handle common missing required parameters with defaults
                    if expected_params and hasattr(tool, 'args_schema') and tool.args_schema:
                        schema = tool.args_schema.model_json_schema()
                        required_params_from_schema = schema.get('required', [])
                        properties = schema.get('properties', {})
                        
                        # Add default values for certain common required parameters if missing
                        for required_param in required_params_from_schema:
                            if required_param not in params:
                                param_info = properties.get(required_param, {})
                                param_type = param_info.get('type', 'string')
                                
                                # Handle common cases with sensible defaults
                                if required_param.lower() in ['cloudid', 'cloud_id']:
                                    # For Atlassian tools, cloudId is often needed but can be inferred from org
                                    # This is a placeholder - ideally would be configured per-user
                                    logger.warning(
                                        f"Missing required parameter '{required_param}' for tool {tool.name}. "
                                        f"This parameter needs to be configured for the user."
                                    )
                                    continue  # Don't add a default, let the tool error with proper message
                                elif required_param.lower() in ['maxresults', 'max_results', 'limit']:
                                    # Reasonable default for result limits
                                    params[required_param] = 10
                                elif required_param.lower() in ['offset', 'start', 'skip']:
                                    # Default offset/pagination
                                    params[required_param] = 0
                                elif param_type == 'boolean':
                                    # Default boolean to false
                                    params[required_param] = False
                    
                    if params:
                        return params
                    
                    # Strategy 5: Fallback - try to create a single parameter structure
                    if expected_params and len(expected_params) == 1:
                        # Single parameter tool - use the input as the parameter value
                        param_name = next(iter(expected_params))
                        return {param_name: cleaned_input}
                    
                    # If all strategies fail, raise an informative error
                    raise ValueError(f"Unable to parse input into expected JSON structure. Input: '{cleaned_input}'")
                
                async def ainvoke(self, tool_input, **kwargs):
                    """Delegate to the real MCP tool with intelligent input conversion."""
                    import json, re
                    from typing import Dict, Any

                    # Get the real tool first to check its schema
                    real_tool = await self._get_real_tool()
                    
                    # Check if this tool requires structured input
                    requires_structured_input = self._requires_structured_input(real_tool)
                    
                    if isinstance(tool_input, str):
                        # Clean possible XML tag remnants
                        tool_input = re.sub(r"</?tool_input>?$", "", tool_input.strip())
                        
                        if requires_structured_input:
                            # Tool has JSON schema - attempt intelligent parsing
                            try:
                                parsed_input = self._parse_structured_input(tool_input, real_tool)
                                tool_input = parsed_input
                                logger.debug(
                                    "Successfully parsed structured input for MCP tool",
                                    tool_name=self.name,
                                    original_input=str(tool_input)[:100],
                                    parsed_type=type(parsed_input).__name__,
                                )
                            except Exception as parse_error:
                                # Provide helpful error message with schema info
                                schema_info = self._get_schema_info(real_tool)
                                error_msg = (
                                    f"Tool '{self.name}' requires structured JSON input but failed to parse: {str(parse_error)}. "
                                    f"Expected format: {schema_info}. "
                                    f"Received: {tool_input[:200]}"
                                )
                                logger.error(
                                    "Failed to parse structured input for MCP tool",
                                    tool_name=self.name,
                                    error=str(parse_error),
                                    input_preview=str(tool_input)[:100],
                                    schema_info=schema_info,
                                )
                                raise ValueError(error_msg)
                        else:
                            # Tool doesn't require structured input - try basic JSON parsing for backward compatibility
                            stripped = tool_input.strip()
                            if stripped.startswith("{") and stripped.endswith("}"):
                                try:
                                    tool_input = json.loads(stripped)
                                except json.JSONDecodeError:
                                    pass  # Leave as raw string if parsing fails

                    try:
                        return await real_tool.ainvoke(tool_input, **kwargs)
                    except Exception as e:
                        # Enhanced error handling with context
                        error_str = str(e)
                        if "String tool inputs are not allowed" in error_str:
                            schema_info = self._get_schema_info(real_tool)
                            enhanced_error = (
                                f"Tool '{self.name}' requires JSON input but received string. "
                                f"Expected format: {schema_info}. "
                                f"Input: {str(tool_input)[:200]}"
                            )
                            raise ValueError(enhanced_error)
                        elif "Invalid arguments" in error_str:
                            schema_info = self._get_schema_info(real_tool)
                            enhanced_error = (
                                f"Tool '{self.name}' received invalid arguments. "
                                f"Expected format: {schema_info}. "
                                f"Error: {error_str}"
                            )
                            raise ValueError(enhanced_error)
                        else:
                            # Re-raise original error
                            raise
                
                def invoke(self, tool_input, **kwargs):
                    """Delegate to the real MCP tool (synchronous)."""
                    import asyncio
                    # Use the enhanced async logic for consistency
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
        
        # Add retry logic for HTTP servers
        max_retries = 3 if config.transport in ("http", "sse", "streamable-http", "streamable_http") else 1
        retry_delay = 1  # seconds
        
        for attempt in range(max_retries):
            try:
                # Reuse or create persistent client
                client = self._get_or_create_mcp_client(server_id, config)
                
                # Add timeout for tool discovery
                try:
                    tools = await asyncio.wait_for(client.get_tools(), timeout=30.0)
                except asyncio.TimeoutError:
                    raise Exception(f"Tool discovery timed out after 30 seconds (attempt {attempt + 1}/{max_retries})")
                
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
                    
                    # Extract additional schema metadata for better error messages
                    required_params = []
                    param_types = {}
                    if input_schema and isinstance(input_schema, dict):
                        required_params = input_schema.get('required', [])
                        properties = input_schema.get('properties', {})
                        param_types = {name: prop.get('type', 'string') for name, prop in properties.items()}
                    
                    tool_info = {
                        "name": tool.name,
                        "description": tool.description,
                        "server_id": server_id,
                        "server_name": config.name,
                        "input_schema": input_schema,
                        "required_params": required_params,
                        "param_types": param_types,
                    }
                    discovered_tools.append(tool_info)
                    
                    logger.debug(
                        "Discovered tool",
                        tool_name=tool.name,
                        has_schema=bool(input_schema),
                        required_params=required_params,
                        param_types=param_types,
                    )
                
                logger.info(
                    "Successfully discovered tools from MCP server",
                    server_id=server_id,
                    num_tools=len(discovered_tools),
                    attempt=attempt + 1,
                )
                
                return discovered_tools
                
            except ImportError:
                logger.error("langchain-mcp-adapters not available")
                raise
            except Exception as e:
                error_str = str(e).lower()
                
                # Log the attempt failure
                logger.warning(
                    "Tool discovery attempt failed",
                    server_id=server_id,
                    attempt=attempt + 1,
                    max_retries=max_retries,
                    error=str(e),
                )
                
                # Check if we should retry
                if attempt < max_retries - 1:
                    # Retry for certain types of errors
                    if any(keyword in error_str for keyword in ["timeout", "connection", "temporary", "unavailable"]):
                        logger.info(
                            "Retrying tool discovery after recoverable error",
                            server_id=server_id,
                            attempt=attempt + 1,
                            retry_delay=retry_delay,
                        )
                        await asyncio.sleep(retry_delay)
                        retry_delay *= 2  # Exponential backoff
                        continue
                
                # Final attempt failed or non-retryable error
                logger.error(
                    "Tool discovery failed after all retries",
                    server_id=server_id,
                    transport=config.transport,
                    url=config.url,
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
            
            # Close HTTP clients
            if self._http_client:
                try:
                    await self._http_client.aclose()
                except Exception:
                    pass
                self._http_client = None
            
            if self._orch_client:
                try:
                    await self._orch_client.aclose()
                except Exception:
                    pass
                self._orch_client = None
            
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