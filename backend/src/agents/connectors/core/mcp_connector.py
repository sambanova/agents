"""
MCP (Model Context Protocol) Connector Base Class

Provides integration with MCP servers using SSE/Streamable HTTP transport.
This allows us to leverage existing MCP servers for various services
(Atlassian, GitHub, etc.) without reimplementing their APIs.
"""

import asyncio
import json
import secrets
from abc import abstractmethod
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlencode

import httpx
import structlog
from agents.connectors.core.base_connector import (
    BaseOAuthConnector,
    ConnectorMetadata,
    ConnectorStatus,
    ConnectorTool,
    OAuthConfig,
    OAuthVersion,
    UserOAuthToken,
)
from agents.storage.redis_storage import RedisStorage
from authlib.common.security import generate_token
from authlib.oauth2.rfc7636 import create_s256_code_challenge
from langchain.tools import BaseTool
from dataclasses import dataclass, field

logger = structlog.get_logger(__name__)

@dataclass
class MCPConfig(OAuthConfig):
    """Configuration for MCP-based connectors
    
    IMPORTANT: Only SSE/HTTP-based MCP servers are supported.
    No local MCP server installations are allowed.
    All configurations are user-specific.
    
    MCP servers act as OAuth resource servers (RFC 9728) and handle
    their own OAuth discovery through /.well-known/oauth-protected-resource
    """
    
    mcp_server_url: str = ""  # URL of the remote MCP server (SSE/HTTP endpoint only)
    transport_type: str = "sse"  # Transport type: sse or streamable-http
    
    # OAuth handled by MCP server discovery - no client credentials needed at this level
    use_discovery: bool = True  # Use OAuth discovery from MCP server metadata
    discovered_auth_server: Optional[str] = None  # Discovered from MCP server
    discovered_token_url: Optional[str] = None  # Discovered from MCP server


class MCPConnector(BaseOAuthConnector):
    """
    Base class for MCP-based connectors.
    
    Handles communication with MCP servers via Streamable HTTP or SSE transport,
    and manages OAuth through the MCP protocol when available.
    """
    
    def __init__(self, config: MCPConfig, redis_storage: RedisStorage):
        super().__init__(config, redis_storage)
        self.mcp_config = config
        self.mcp_client = None
        self._sse_connections = {}  # user_id -> SSE connection
    
    @abstractmethod
    def _get_mcp_server_info(self) -> Dict[str, Any]:
        """
        Get MCP server information including URL and supported features.
        Subclasses should provide server-specific details.
        """
        pass
    
    async def test_mcp_connection(self, user_id: str) -> bool:
        """Test if MCP server is accessible"""
        try:
            token = await self.get_user_token(user_id)
            if not token:
                logger.warning("No token for MCP connection test", user_id=user_id)
                return False
            
            # For Atlassian MCP, we need to use the OAuth token properly
            headers = {
                "Authorization": f"Bearer {token.access_token}",
                "Accept": "application/json"
            }
            
            async with httpx.AsyncClient() as client:
                # Try different endpoints based on the server
                # Atlassian MCP server might have a different structure
                test_urls = [
                    f"{self.mcp_config.mcp_server_url}/mcp/v1/capabilities",
                    f"{self.mcp_config.mcp_server_url}/capabilities",
                    self.mcp_config.mcp_server_url  # Try the base URL
                ]
                
                for url in test_urls:
                    try:
                        logger.debug(
                            "Testing MCP endpoint",
                            provider=self.mcp_config.provider_id,
                            url=url,
                            is_base_url=(url == self.mcp_config.mcp_server_url)
                        )
                        
                        # For PayPal SSE endpoint, just check if we can connect
                        if self.mcp_config.provider_id == "paypal" and url == self.mcp_config.mcp_server_url:
                            # SSE endpoint - just check if we can connect
                            response = await client.get(url, headers=headers, timeout=3.0)
                            logger.info(
                                "PayPal MCP SSE endpoint test result",
                                user_id=user_id,
                                status_code=response.status_code,
                                url=url
                            )
                            if response.status_code == 200:
                                logger.info("PayPal MCP SSE endpoint accessible", user_id=user_id)
                                return True
                        else:
                            # Regular endpoints - check for capabilities
                            response = await client.get(url, headers=headers, timeout=5.0)
                            if response.status_code in [200, 204]:
                                return True
                        # If we get 401, token might be invalid
                        if response.status_code == 401:
                            logger.warning(
                                "MCP server returned 401 - token may be invalid",
                                user_id=user_id,
                                url=url
                            )
                    except Exception as e:
                        logger.debug(
                            "MCP endpoint test failed",
                            provider=self.mcp_config.provider_id,
                            url=url,
                            error=str(e)
                        )
                        continue
                
                return False
                
        except Exception as e:
            logger.error(
                "MCP connection test failed",
                user_id=user_id,
                error=str(e)
            )
            return False
    
    async def execute_mcp_tool(
        self,
        user_id: str,
        tool_name: str,
        arguments: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Execute a tool via MCP protocol.
        
        Uses the JSON-RPC format specified by MCP.
        """
        token = await self.get_user_token(user_id, auto_refresh=True)
        if not token:
            raise ValueError("No valid token for MCP execution")
        
        # Prepare JSON-RPC request
        request_id = f"{user_id}_{tool_name}_{secrets.token_hex(8)}"
        request_body = {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": arguments
            },
            "id": request_id
        }
        
        logger.info(
            "Executing MCP tool",
            user_id=user_id,
            tool_name=tool_name,
            request_id=request_id
        )
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                # Use appropriate endpoint based on transport type
                if self.mcp_config.transport_type == "streamable-http":
                    endpoint = f"{self.mcp_config.mcp_server_url}/mcp/v1/invoke"
                else:
                    endpoint = f"{self.mcp_config.mcp_server_url}/execute"
                
                # Build headers with proper authorization
                headers = {
                    "Authorization": f"Bearer {token.access_token}",
                    "Content-Type": "application/json",
                    "Accept": "application/json"
                }
                
                logger.debug(
                    "Sending MCP request",
                    endpoint=endpoint,
                    tool_name=tool_name,
                    has_token=bool(token.access_token)
                )
                
                response = await client.post(
                    endpoint,
                    json=request_body,
                    headers=headers
                )
                
                response.raise_for_status()
                result = response.json()
                
                # Check for JSON-RPC error
                if "error" in result:
                    logger.error(
                        "MCP tool execution error",
                        user_id=user_id,
                        tool_name=tool_name,
                        error=result["error"]
                    )
                    return {
                        "success": False,
                        "error": result["error"].get("message", "Unknown error")
                    }
                
                logger.info(
                    "MCP tool executed successfully",
                    user_id=user_id,
                    tool_name=tool_name
                )
                
                return {
                    "success": True,
                    "result": result.get("result", {})
                }
                
        except httpx.HTTPStatusError as e:
            logger.error(
                "MCP HTTP error",
                user_id=user_id,
                tool_name=tool_name,
                status_code=e.response.status_code,
                error=str(e)
            )
            return {
                "success": False,
                "error": f"HTTP {e.response.status_code}: {e.response.text}"
            }
        except Exception as e:
            logger.error(
                "MCP execution failed",
                user_id=user_id,
                tool_name=tool_name,
                error=str(e)
            )
            return {
                "success": False,
                "error": str(e)
            }
    
    async def discover_oauth_metadata(self) -> Dict[str, Any]:
        """
        Discover OAuth metadata from MCP server.
        
        Following RFC 9728, MCP servers publish metadata at:
        /.well-known/oauth-protected-resource
        
        This tells us which authorization server to use.
        """
        try:
            # Build discovery URL based on MCP server URL
            from urllib.parse import urlparse, urlunparse
            parsed = urlparse(self.mcp_config.mcp_server_url)
            
            # Determine well-known path based on server path
            if parsed.path and parsed.path != '/':
                well_known_path = f"/.well-known/oauth-protected-resource{parsed.path}"
            else:
                well_known_path = "/.well-known/oauth-protected-resource"
            
            discovery_url = urlunparse((
                parsed.scheme,
                parsed.netloc,
                well_known_path,
                '', '', ''
            ))
            
            logger.info(
                "Discovering OAuth metadata",
                mcp_server=self.mcp_config.mcp_server_url,
                discovery_url=discovery_url
            )
            
            async with httpx.AsyncClient() as client:
                # First try without auth to get WWW-Authenticate header
                response = await client.get(discovery_url)
                
                if response.status_code == 200:
                    metadata = response.json()
                    
                    # Store discovered auth server info
                    if "authorization_servers" in metadata:
                        auth_servers = metadata["authorization_servers"]
                        if auth_servers and len(auth_servers) > 0:
                            # Use first authorization server
                            auth_server = auth_servers[0]
                            self.mcp_config.discovered_auth_server = auth_server
                            
                            # Now discover the auth server's metadata
                            auth_metadata = await self._discover_auth_server_metadata(auth_server)
                            if auth_metadata:
                                self.mcp_config.authorize_url = auth_metadata.get("authorization_endpoint")
                                self.mcp_config.token_url = auth_metadata.get("token_endpoint")
                                self.mcp_config.discovered_token_url = auth_metadata.get("token_endpoint")
                    
                    logger.info(
                        "Discovered OAuth metadata",
                        auth_servers=metadata.get("authorization_servers"),
                        resource=metadata.get("resource")
                    )
                    
                    return metadata
                
                elif response.status_code == 401:
                    # Parse WWW-Authenticate header for discovery URL
                    www_auth = response.headers.get("WWW-Authenticate")
                    if www_auth:
                        logger.info(
                            "Got WWW-Authenticate header",
                            header=www_auth
                        )
                        # Parse and follow the header
                        # This is simplified - real implementation would parse properly
                        return {"www_authenticate": www_auth}
                
                return {}
                
        except Exception as e:
            logger.error(
                "Failed to discover OAuth metadata",
                server_url=self.mcp_config.mcp_server_url,
                error=str(e)
            )
            return {}
    
    async def _discover_auth_server_metadata(self, issuer: str) -> Dict[str, Any]:
        """
        Discover authorization server metadata.
        
        Tries both OAuth 2.0 and OpenID Connect discovery endpoints.
        """
        try:
            async with httpx.AsyncClient() as client:
                # Try OAuth 2.0 discovery first
                oauth_url = f"{issuer}/.well-known/oauth-authorization-server"
                try:
                    response = await client.get(oauth_url)
                    if response.status_code == 200:
                        return response.json()
                except:
                    pass
                
                # Try OpenID Connect discovery
                oidc_url = f"{issuer}/.well-known/openid-configuration"
                try:
                    response = await client.get(oidc_url)
                    if response.status_code == 200:
                        return response.json()
                except:
                    pass
                
            return {}
        except Exception as e:
            logger.error(
                "Failed to discover auth server metadata",
                issuer=issuer,
                error=str(e)
            )
            return {}
    
    async def get_mcp_tools(self) -> List[Dict[str, Any]]:
        """
        Get available tools from MCP server.
        
        This queries the MCP server for its tool definitions.
        """
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.mcp_config.mcp_server_url}/mcp/v1/tools",
                    headers={
                        "Accept": "application/json"
                    }
                )
                response.raise_for_status()
                tools_data = response.json()
                
                return tools_data.get("tools", [])
                
        except Exception as e:
            logger.error(
                "Failed to get MCP tools",
                server_url=self.mcp_config.mcp_server_url,
                error=str(e)
            )
            return []
    
    async def get_authorization_url(
        self,
        user_id: str,
        state: Optional[str] = None,
        **kwargs
    ) -> Tuple[str, str]:
        """
        Generate OAuth authorization URL.
        
        For MCP connectors, we need to discover the OAuth endpoints first,
        then generate the authorization URL.
        """
        # For MCP connectors with discovery, we need to discover OAuth endpoints first
        if self.mcp_config.use_discovery and not self.mcp_config.authorize_url:
            # Discover OAuth metadata from MCP server
            metadata = await self.discover_oauth_metadata()
            if not self.mcp_config.authorize_url:
                logger.error(
                    "Could not discover OAuth authorization URL",
                    mcp_server=self.mcp_config.mcp_server_url
                )
                raise ValueError("OAuth authorization URL not discovered from MCP server")
        
        # Check if we have a discovered auth server to use
        if hasattr(self.mcp_config, 'discovered_auth_server') and self.mcp_config.discovered_auth_server:
            # Use MCP OAuth 2.1 spec with resource indicators
            code_verifier = generate_token(48)
            code_challenge = create_s256_code_challenge(code_verifier)
            state = state or secrets.token_urlsafe(32)
            
            params = {
                "client_id": self.config.client_id or "mcp-client",  # MCP servers may provide this
                "redirect_uri": self.config.redirect_uri,
                "response_type": "code",
                "scope": " ".join(self.config.scopes) if self.config.scopes else "read write",
                "state": state,
                "code_challenge": code_challenge,
                "code_challenge_method": "S256",
                # MCP spec requires resource indicators (RFC 8707)
                "resource": self.mcp_config.mcp_server_url
            }
            
            # Add any additional params
            params.update(kwargs)
            
            # Store state with code_verifier
            await self._store_oauth_state(state, user_id, code_verifier)
            
            auth_url = f"{self.mcp_config.authorize_url}?" + urlencode(params)
            return auth_url, state
        
        # Fall back to standard OAuth flow
        return await super().get_authorization_url(user_id, state, **kwargs)
    
    async def _store_oauth_state(
        self,
        state: str,
        user_id: str,
        code_verifier: str
    ) -> None:
        """Store OAuth state for later validation"""
        state_data = {
            "user_id": user_id,
            "code_verifier": code_verifier,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "provider_id": self.config.provider_id
        }
        
        # Store in Redis with TTL
        state_key = f"oauth:state:{state}"
        await self.redis_storage.redis_client.setex(
            state_key,
            600,  # 10 minute TTL
            json.dumps(state_data)
        )
    
    async def establish_sse_connection(self, user_id: str) -> None:
        """
        Establish SSE connection for real-time updates (legacy transport).
        
        This is for MCP servers that still use SSE transport.
        """
        token = await self.get_user_token(user_id)
        if not token:
            raise ValueError("No token for SSE connection")
        
        try:
            # Note: This is a simplified example. Real SSE implementation
            # would require aiohttp-sse-client or similar
            logger.info(
                "Establishing SSE connection",
                user_id=user_id,
                server_url=self.mcp_config.mcp_server_url
            )
            
            # Store connection reference
            self._sse_connections[user_id] = {
                "connected_at": datetime.now(timezone.utc),
                "token": token.access_token
            }
            
        except Exception as e:
            logger.error(
                "Failed to establish SSE connection",
                user_id=user_id,
                error=str(e)
            )
            raise
    
    async def close_sse_connection(self, user_id: str) -> None:
        """Close SSE connection for user"""
        if user_id in self._sse_connections:
            del self._sse_connections[user_id]
            logger.info("Closed SSE connection", user_id=user_id)
    
    async def create_langchain_tools(
        self,
        user_id: str,
        tool_ids: List[str]
    ) -> List[BaseTool]:
        """
        Create LangChain tools that execute via MCP.
        
        These are thin wrappers that delegate to the MCP server.
        """
        from .mcp_tools import create_mcp_langchain_tools
        
        token = await self.get_user_token(user_id, auto_refresh=True)
        if not token:
            logger.warning("No token found for user", user_id=user_id)
            return []
        
        # Test MCP connection first
        if not await self.test_mcp_connection(user_id):
            logger.error(
                "MCP server not accessible",
                user_id=user_id,
                server_url=self.mcp_config.mcp_server_url
            )
            return []
        
        return create_mcp_langchain_tools(
            mcp_connector=self,
            user_id=user_id,
            tool_ids=tool_ids
        )