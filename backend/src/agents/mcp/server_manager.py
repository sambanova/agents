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
        self.cache_ttl = 1800  # 30 minutes cache TTL (increased from 5 minutes)
        
        # Persistent MCP client connections for efficient tool execution and discovery
        self.mcp_clients: Dict[str, Any] = {}  # server_id -> MCP client session
        self.client_last_used: Dict[str, float] = {}  # server_id -> last used timestamp
        self.client_cleanup_interval = 3600  # Clean up unused clients after 1 hour

        # Async tasks that continuously drain MCP subprocess stdout/stderr so pipes
        # never block (keyed by server_id)
        self.output_tasks: Dict[str, asyncio.Task] = {}

        # Health check configuration - less aggressive monitoring
        self.health_check_interval = 120  # Check every 2 minutes instead of 30 seconds
        self.restart_failure_count: Dict[str, int] = {}  # Track restart failures per server
        self.max_restart_attempts = 3
        self.restart_backoff_time = 300  # 5 minutes backoff after max attempts reached

        # NEW: Connection management and circuit breaker for robustness
        self.connection_failures: Dict[str, int] = {}  # server_id -> failure count
        self.connection_backoff: Dict[str, float] = {}  # server_id -> next retry time
        self.max_connection_failures = 3  # Max failures before circuit breaker
        self.connection_backoff_time = 30  # Initial backoff time in seconds
        self.max_backoff_time = 300  # Maximum backoff time (5 minutes)
        self.client_validation_cache: Dict[str, float] = {}  # server_id -> last validation time
        self.validation_ttl = 60  # Re-validate clients every minute

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

            # Reset restart failure count on manual start
            self.restart_failure_count.pop(server_id, None)

            # Start server based on transport type
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
                
                # Start health monitoring with less aggressive settings
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

            # Clean up persistent MCP client
            if server_id in self.mcp_clients:
                try:
                    # Try to properly close the client if it has a close method
                    client = self.mcp_clients[server_id]
                    if hasattr(client, 'close'):
                        await client.close()
                except Exception as e:
                    logger.warning("Error closing MCP client", server_id=server_id, error=str(e))
                finally:
                    del self.mcp_clients[server_id]
                    self.client_last_used.pop(server_id, None)

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

            # Clear restart failure tracking
            self.restart_failure_count.pop(server_id, None)

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

            # Check if process is alive for stdio servers
            if server_id in self.server_processes:
                proc = self.server_processes[server_id]
                try:
                    # For subprocess.Popen we have poll(), for asyncio.Process we use returncode
                    if hasattr(proc, "poll"):
                        running = proc.poll() is None
                    else:
                        running = proc.returncode is None
                except Exception:
                    running = False

                if running:
                    # Try a simple MCP connection test if possible
                    try:
                        client = await self._get_or_create_mcp_client(server_id, config)
                        if client:
                            # Simple validation - try to get tools list
                            await asyncio.wait_for(client.get_tools(), timeout=10)
                            return MCPServerStatus.HEALTHY, "Server responding to MCP calls"
                    except asyncio.TimeoutError:
                        return MCPServerStatus.ERROR, "Server not responding to MCP calls (timeout)"
                    except Exception as mcp_error:
                        logger.debug("MCP health check failed", server_id=server_id, error=str(mcp_error))
                        # Don't immediately mark as error - could be temporary
                        return MCPServerStatus.HEALTHY, "Server process running (MCP check failed)"
                    
                    return MCPServerStatus.HEALTHY, "Server process running"
                else:
                    return MCPServerStatus.ERROR, "Server process terminated"

            # For HTTP/SSE servers, just check if marked as active
            return MCPServerStatus.HEALTHY, "Server marked as active"

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
        """Discover available tools from an MCP server using persistent MCP connection."""
        try:
            # Check cache first (now with 30-minute TTL)
            if not force_refresh and self._is_cache_valid(server_id):
                cached_tools = self.tool_cache.get(server_id, [])
                logger.debug("Using cached tools", server_id=server_id, num_tools=len(cached_tools))
                return [MCPToolInfo.model_validate(tool) for tool in cached_tools]

            config = await self.redis_storage.get_mcp_server_config(user_id, server_id)
            if not config:
                logger.error("Server configuration not found", server_id=server_id, user_id=user_id)
                return []

            if not self._is_server_running(server_id):
                logger.warning("Server not running for tool discovery", server_id=server_id, user_id=user_id)
                return []

            # Try to discover tools using persistent MCP connection
            try:
                discovered_tools = await self._discover_tools_from_mcp(server_id, config)
                if discovered_tools:
                    # Cache the tools with longer TTL
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
                    "Failed to discover tools from MCP server, checking cache",
                    server_id=server_id,
                    error=str(mcp_error),
                )
                
                # Try to return cached tools even if expired as fallback
                cached_tools = self.tool_cache.get(server_id, [])
                if cached_tools:
                    logger.info("Using expired cache as fallback", server_id=server_id, num_tools=len(cached_tools))
                    return [MCPToolInfo.model_validate(tool) for tool in cached_tools]

            # Fallback to mock tools for testing
            logger.warning("No tools discovered, using mock tools", server_id=server_id)
            mock_tools = [
                {
                    "name": f"mock_tool_{server_id}",
                    "description": f"Mock tool for server {config.name}",
                    "server_id": server_id,
                    "server_name": config.name,
                    "input_schema": {"type": "object", "properties": {"query": {"type": "string"}}}
                }
            ]
            return [MCPToolInfo.model_validate(tool) for tool in mock_tools]

        except Exception as e:
            logger.error(
                "Error discovering tools",
                server_id=server_id,
                user_id=user_id,
                error=str(e),
                exc_info=True,
            )
            return []

    async def get_user_mcp_tools(self, user_id: str) -> List[BaseTool]:
        """Get all LangChain tools from user's enabled MCP servers. Only use ALREADY RUNNING servers."""
        try:
            # Get all enabled servers for the user
            enabled_servers = await self.redis_storage.get_user_enabled_mcp_servers(user_id)
            
            all_tools = []
            for server_config in enabled_servers:
                # CRITICAL CHANGE: Only get tools from already running servers
                # Do NOT auto-start servers here to prevent constant restarts
                if self._is_server_running(server_config.server_id):
                    # Discover tools from the running server
                    mcp_tools = await self.discover_tools(user_id, server_config.server_id)
                    
                    # Convert MCP tools to LangChain tools
                    for mcp_tool in mcp_tools:
                        langchain_tool = self._convert_mcp_tool_to_langchain(mcp_tool, user_id)
                        all_tools.append(langchain_tool)
                else:
                    logger.debug(
                        "Skipping stopped MCP server for tool loading",
                        server_id=server_config.server_id,
                        user_id=user_id,
                    )
            
            logger.info(
                "Retrieved MCP tools for user",
                user_id=user_id,
                num_servers=len([s for s in enabled_servers if self._is_server_running(s.server_id)]),
                total_enabled_servers=len(enabled_servers),
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
        """Health check loop for a server - IMPROVED: No auto-restart, better error handling."""
        try:
            failure_count = 0
            while True:
                # Wait for health check interval (now 2 minutes)
                await asyncio.sleep(self.health_check_interval)

                # Perform health check
                status, message = await self.health_check(user_id, server_id)

                # Update server health in Redis
                await self.redis_storage.update_mcp_server_health(
                    user_id, server_id, status.value, message
                )

                # CRITICAL CHANGE: Only log errors, do not auto-restart
                # This prevents the restart loops that were causing instability
                if status == MCPServerStatus.ERROR:
                    failure_count += 1
                    logger.warning(
                        "Server health check failed",
                        server_id=server_id,
                        user_id=user_id,
                        error=message,
                        failure_count=failure_count,
                        note="Server will NOT be auto-restarted - manual intervention required"
                    )
                    
                    # Clean up client connection on persistent failures
                    if failure_count >= 3 and server_id in self.mcp_clients:
                        logger.info("Cleaning up MCP client after repeated failures", server_id=server_id)
                        try:
                            client = self.mcp_clients[server_id]
                            if hasattr(client, 'close'):
                                await client.close()
                        except Exception:
                            pass
                        finally:
                            self.mcp_clients.pop(server_id, None)
                            self.client_last_used.pop(server_id, None)
                else:
                    # Reset failure count on successful check
                    failure_count = 0

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

    async def _get_or_create_mcp_client(self, server_id: str, config: MCPServerConfig):
        """Get or create a persistent MCP client for a server with robust error handling."""
        try:
            current_time = time.time()
            
            # Check if we're in backoff mode for this server
            if server_id in self.connection_backoff and current_time < self.connection_backoff[server_id]:
                backoff_remaining = self.connection_backoff[server_id] - current_time
                logger.debug(
                    "Server in connection backoff",
                    server_id=server_id,
                    backoff_remaining=int(backoff_remaining)
                )
                return None

            # Check if we have a cached client that's been validated recently
            if server_id in self.mcp_clients:
                last_validation = self.client_validation_cache.get(server_id, 0)
                if current_time - last_validation < self.validation_ttl:
                    # Update last used time
                    self.client_last_used[server_id] = current_time
                    return self.mcp_clients[server_id]
                
                # Validate existing client
                try:
                    client = self.mcp_clients[server_id]
                    # Quick validation - try to get tools with timeout
                    await asyncio.wait_for(client.get_tools(), timeout=5)
                    self.client_validation_cache[server_id] = current_time
                    self.client_last_used[server_id] = current_time
                    # Reset failure count on successful validation
                    self.connection_failures.pop(server_id, None)
                    return client
                except Exception as e:
                    logger.warning(
                        "Client validation failed, will recreate",
                        server_id=server_id,
                        error=str(e)
                    )
                    await self._cleanup_failed_client(server_id)

            # Create new client
            return await self._create_new_mcp_client(server_id, config)
                
        except Exception as e:
            await self._handle_connection_failure(server_id, e)
            return None

    async def _create_new_mcp_client(self, server_id: str, config: MCPServerConfig):
        """Create a new MCP client with timeout and error handling."""
        try:
            # Import MCP adapters
            from langchain_mcp_adapters.client import MultiServerMCPClient
            
            # Create MCP client configuration
            if config.transport == "stdio":
                if not config.command:
                    raise ValueError("No command specified for stdio server")
                
                server_config = {
                    config.name: {
                        "command": config.command,
                        "args": config.args or [],
                        "transport": "stdio",
                    }
                }
            elif config.transport in ["http", "sse"]:
                if not config.url:
                    raise ValueError("No URL specified for HTTP/SSE server")
                
                # Map our transport types to langchain-mcp-adapters transport types
                transport = "streamable_http" if config.transport == "sse" else "http"
                server_config = {
                    config.name: {
                        "url": config.url,
                        "transport": transport,
                    }
                }
            else:
                raise ValueError(f"Unsupported transport type: {config.transport}")
            
            # Add environment variables if specified
            if config.env_vars:
                server_config[config.name]["env"] = config.env_vars
            
            # Create client with timeout
            logger.info("Creating new MCP client", server_id=server_id, transport=config.transport)
            client = await asyncio.wait_for(
                self._create_client_with_initialization(server_config),
                timeout=30  # 30 second timeout for client creation
            )
            
            # Cache the client
            self.mcp_clients[server_id] = client
            self.client_last_used[server_id] = time.time()
            self.client_validation_cache[server_id] = time.time()
            
            # Reset failure tracking on success
            self.connection_failures.pop(server_id, None)
            self.connection_backoff.pop(server_id, None)
            
            logger.info(
                "Created new persistent MCP client",
                server_id=server_id,
                transport=config.transport,
            )
            
            return client
                
        except ImportError:
            logger.warning("langchain-mcp-adapters not available")
            return None
        except asyncio.TimeoutError:
            logger.error("Timeout creating MCP client", server_id=server_id)
            await self._handle_connection_failure(server_id, Exception("Client creation timeout"))
            return None
        except Exception as e:
            logger.error(
                "Error creating MCP client",
                server_id=server_id,
                error=str(e),
                exc_info=True,
            )
            await self._handle_connection_failure(server_id, e)
            return None

    async def _create_client_with_initialization(self, server_config: Dict[str, Any]):
        """Create and initialize MCP client with proper error handling."""
        from langchain_mcp_adapters.client import MultiServerMCPClient
        
        client = MultiServerMCPClient(server_config)
        
        # Test the client by getting tools (this will initialize the connection)
        await client.get_tools()
        
        return client

    async def _cleanup_failed_client(self, server_id: str):
        """Clean up a failed MCP client connection."""
        try:
            if server_id in self.mcp_clients:
                client = self.mcp_clients[server_id]
                if hasattr(client, 'close'):
                    try:
                        await asyncio.wait_for(client.close(), timeout=5)
                    except:
                        pass  # Ignore close errors
                del self.mcp_clients[server_id]
            
            # Clear related cache entries
            self.client_last_used.pop(server_id, None)
            self.client_validation_cache.pop(server_id, None)
            
            logger.debug("Cleaned up failed MCP client", server_id=server_id)
            
        except Exception as e:
            logger.warning("Error cleaning up failed client", server_id=server_id, error=str(e))

    async def _handle_connection_failure(self, server_id: str, error: Exception):
        """Handle connection failures with exponential backoff."""
        current_time = time.time()
        
        # Increment failure count
        failure_count = self.connection_failures.get(server_id, 0) + 1
        self.connection_failures[server_id] = failure_count
        
        # Calculate backoff time with exponential increase
        if failure_count >= self.max_connection_failures:
            backoff_time = min(
                self.connection_backoff_time * (2 ** (failure_count - self.max_connection_failures)),
                self.max_backoff_time
            )
            self.connection_backoff[server_id] = current_time + backoff_time
            
            logger.warning(
                "Connection failures exceeded threshold, entering backoff",
                server_id=server_id,
                failure_count=failure_count,
                backoff_seconds=int(backoff_time),
                error=str(error)
            )
        else:
            logger.warning(
                "Connection failure recorded",
                server_id=server_id,
                failure_count=failure_count,
                max_failures=self.max_connection_failures,
                error=str(error)
            )
        
        # Clean up the failed client
        await self._cleanup_failed_client(server_id)

    def _convert_mcp_tool_to_langchain(self, mcp_tool: MCPToolInfo, user_id: str) -> BaseTool:
        """Convert an MCP tool to a LangChain tool with efficient MCP execution using persistent connections."""
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
                
                # Try to execute the tool using persistent MCP connection
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
        """Discover tools from an MCP server using persistent client connection with robust error handling."""
        max_retries = 2
        retry_delay = 1
        
        for attempt in range(max_retries + 1):
            try:
                # Use persistent client connection with validation
                client = await self._get_or_create_mcp_client(server_id, config)
                if not client:
                    raise Exception("Could not create MCP client - in backoff or creation failed")
                
                # Get tools using persistent client with timeout
                logger.debug("Discovering tools from MCP server", server_id=server_id, attempt=attempt + 1)
                tools = await asyncio.wait_for(client.get_tools(), timeout=15)
                
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
                    attempt=attempt + 1
                )
                
                return discovered_tools
                    
            except asyncio.TimeoutError:
                error_msg = f"Tool discovery timeout (attempt {attempt + 1})"
                logger.warning(error_msg, server_id=server_id)
                
                if attempt < max_retries:
                    await self._cleanup_failed_client(server_id)
                    await asyncio.sleep(retry_delay)
                    retry_delay *= 2
                    continue
                else:
                    await self._handle_connection_failure(server_id, Exception(error_msg))
                    raise Exception(error_msg)
                    
            except ImportError:
                logger.warning("langchain-mcp-adapters not available, using mock tools")
                raise
            except Exception as e:
                error_msg = str(e)
                logger.warning(
                    "Tool discovery failed",
                    server_id=server_id,
                    attempt=attempt + 1,
                    error=error_msg
                )
                
                # Clean up client on any error during discovery
                await self._cleanup_failed_client(server_id)
                
                if attempt < max_retries:
                    await asyncio.sleep(retry_delay)
                    retry_delay *= 2
                    continue
                else:
                    await self._handle_connection_failure(server_id, e)
                    logger.error(
                        "Error discovering tools from MCP server",
                        server_id=server_id,
                        error=error_msg,
                        exc_info=True,
                    )
                    raise
        
        # Should not reach here
        raise Exception(f"Tool discovery failed after {max_retries + 1} attempts")

    async def _execute_mcp_tool(self, server_id: str, tool_name: str, arguments: Dict[str, Any]) -> str:
        """Execute an MCP tool using persistent client connection with robust error handling."""
        max_retries = 2
        retry_delay = 1
        
        for attempt in range(max_retries + 1):
            try:
                # Get server config
                server_info = self.active_servers.get(server_id)
                if not server_info:
                    raise ValueError(f"Server {server_id} not found or not running")
                
                config = server_info["config"]
                
                # Use persistent client connection with validation
                client = await self._get_or_create_mcp_client(server_id, config)
                if not client:
                    raise Exception("Could not get MCP client - in backoff or creation failed")
                
                # Get tools from client with timeout
                tools = await asyncio.wait_for(client.get_tools(), timeout=10)
                
                # Find the specific tool
                target_tool = None
                for tool in tools:
                    if tool.name == tool_name:
                        target_tool = tool
                        break
                
                if not target_tool:
                    raise ValueError(f"Tool {tool_name} not found on server {server_id}")
                
                # Execute the tool with timeout
                logger.debug(
                    "Executing MCP tool",
                    server_id=server_id,
                    tool_name=tool_name,
                    attempt=attempt + 1
                )
                
                if hasattr(target_tool, 'ainvoke'):
                    result = await asyncio.wait_for(target_tool.ainvoke(arguments), timeout=30)
                elif hasattr(target_tool, 'invoke'):
                    result = await asyncio.wait_for(
                        asyncio.to_thread(target_tool.invoke, arguments),
                        timeout=30
                    )
                else:
                    # Fallback to calling the tool directly
                    result = await asyncio.wait_for(target_tool(**arguments), timeout=30)
                
                logger.info(
                    "Successfully executed MCP tool",
                    server_id=server_id,
                    tool_name=tool_name,
                    attempt=attempt + 1
                )
                
                return str(result)
                    
            except asyncio.TimeoutError:
                error_msg = f"Tool execution timeout (attempt {attempt + 1})"
                logger.warning(error_msg, server_id=server_id, tool_name=tool_name)
                
                if attempt < max_retries:
                    # Clean up client on timeout and retry
                    await self._cleanup_failed_client(server_id)
                    await asyncio.sleep(retry_delay)
                    retry_delay *= 2
                    continue
                else:
                    await self._handle_connection_failure(server_id, Exception(error_msg))
                    raise Exception(error_msg)
                    
            except Exception as e:
                error_msg = str(e)
                logger.warning(
                    "MCP tool execution failed",
                    server_id=server_id,
                    tool_name=tool_name,
                    attempt=attempt + 1,
                    error=error_msg
                )
                
                # Check if this is a connection-related error
                if any(keyword in error_msg.lower() for keyword in [
                    'connection', 'timeout', 'closed', 'broken', 'taskgroup', 'mcp error'
                ]):
                    # Clean up client and retry for connection errors
                    await self._cleanup_failed_client(server_id)
                    
                    if attempt < max_retries:
                        await asyncio.sleep(retry_delay)
                        retry_delay *= 2
                        continue
                    else:
                        await self._handle_connection_failure(server_id, e)
                        raise
                else:
                    # For non-connection errors, don't retry
                    logger.error(
                        "MCP tool execution failed with non-connection error",
                        server_id=server_id,
                        tool_name=tool_name,
                        error=error_msg,
                        exc_info=True,
                    )
                    raise
        
        # Should not reach here
        raise Exception(f"Tool execution failed after {max_retries + 1} attempts")

    async def cleanup_unused_clients(self) -> int:
        """Clean up unused MCP clients to free resources."""
        try:
            current_time = time.time()
            cleanup_count = 0
            
            clients_to_remove = []
            for server_id, last_used in self.client_last_used.items():
                if current_time - last_used > self.client_cleanup_interval:
                    clients_to_remove.append(server_id)
            
            for server_id in clients_to_remove:
                if server_id in self.mcp_clients:
                    try:
                        client = self.mcp_clients[server_id]
                        if hasattr(client, 'close'):
                            await client.close()
                    except Exception as e:
                        logger.warning("Error closing unused MCP client", server_id=server_id, error=str(e))
                    finally:
                        del self.mcp_clients[server_id]
                        del self.client_last_used[server_id]
                        cleanup_count += 1
            
            if cleanup_count > 0:
                logger.info("Cleaned up unused MCP clients", count=cleanup_count)
            
            return cleanup_count
            
        except Exception as e:
            logger.error("Error cleaning up unused MCP clients", error=str(e), exc_info=True)
            return 0

    async def cleanup(self) -> None:
        """Clean up all resources."""
        try:
            # Cancel all health check tasks
            for task in self.health_check_tasks.values():
                task.cancel()
            
            # Wait for tasks to complete
            if self.health_check_tasks:
                await asyncio.gather(*self.health_check_tasks.values(), return_exceptions=True)
            
            # Close all MCP clients
            for server_id, client in self.mcp_clients.items():
                try:
                    if hasattr(client, 'close'):
                        await client.close()
                except Exception as e:
                    logger.warning("Error closing MCP client during cleanup", server_id=server_id, error=str(e))
            
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
            
            # Cancel output drain tasks
            for task in self.output_tasks.values():
                task.cancel()
            
            # Wait for output tasks to complete
            if self.output_tasks:
                await asyncio.gather(*self.output_tasks.values(), return_exceptions=True)
            
            # Clear all data structures
            self.active_servers.clear()
            self.server_processes.clear()
            self.health_check_tasks.clear()
            self.tool_cache.clear()
            self.cache_expiry.clear()
            self.mcp_clients.clear()
            self.client_last_used.clear()
            self.restart_failure_count.clear()
            self.connection_failures.clear()
            self.connection_backoff.clear()
            self.client_validation_cache.clear()
            
            logger.info("MCP server manager cleanup completed")
            
        except Exception as e:
            logger.error("Error during cleanup", error=str(e), exc_info=True) 