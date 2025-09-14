"""
Atlassian MCP Connector

Provides OAuth integration for Atlassian products (Jira and Confluence)
using the official Atlassian Remote MCP Server.
"""

import json
from typing import Any, Dict, List, Optional, Tuple

import structlog
from agents.connectors.core.base_connector import ConnectorMetadata, ConnectorTool, OAuthVersion, UserOAuthToken
from agents.connectors.core.mcp_connector import MCPConfig, MCPConnector
from agents.connectors.core.mcp_tools import create_predefined_mcp_tools
from langchain.tools import BaseTool

logger = structlog.get_logger(__name__)


class AtlassianConnector(MCPConnector):
    """
    Atlassian connector using MCP protocol.
    
    Leverages Atlassian's official Remote MCP Server for Jira and Confluence.
    This is essentially a pre-configured GenericMCPConnector with Atlassian-specific settings.
    """
    
    def _get_metadata(self) -> ConnectorMetadata:
        """Get Atlassian connector metadata"""
        return ConnectorMetadata(
            provider_id="atlassian",
            name="Atlassian (Jira & Confluence)",
            description="Connect to Jira and Confluence via Atlassian's official MCP server",
            icon_url="https://wac-cdn.atlassian.com/assets/img/favicons/atlassian/favicon.png",
            oauth_version=OAuthVersion.OAUTH2_0,
            available_tools=[
                # Jira Tools
                ConnectorTool(
                    id="jira_create_issue",
                    name="Create Jira Issue",
                    description="Create a new issue in Jira",
                    parameters_schema={
                        "type": "object",
                        "properties": {
                            "project": {
                                "type": "string",
                                "description": "Project key (e.g., 'PROJ')"
                            },
                            "summary": {
                                "type": "string",
                                "description": "Issue summary/title"
                            },
                            "description": {
                                "type": "string",
                                "description": "Issue description"
                            },
                            "issue_type": {
                                "type": "string",
                                "enum": ["Bug", "Task", "Story", "Epic"],
                                "description": "Type of issue"
                            },
                            "priority": {
                                "type": "string",
                                "enum": ["Highest", "High", "Medium", "Low", "Lowest"],
                                "description": "Issue priority"
                            },
                            "assignee": {
                                "type": "string",
                                "description": "Assignee username (optional)"
                            },
                            "labels": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Issue labels (optional)"
                            }
                        },
                        "required": ["project", "summary", "issue_type"]
                    }
                ),
                ConnectorTool(
                    id="jira_search_issues",
                    name="Search Jira Issues",
                    description="Search for issues using JQL (Jira Query Language)",
                    parameters_schema={
                        "type": "object",
                        "properties": {
                            "jql": {
                                "type": "string",
                                "description": "JQL query (e.g., 'project = PROJ AND status = Open')"
                            },
                            "max_results": {
                                "type": "integer",
                                "default": 10,
                                "description": "Maximum number of results"
                            },
                            "fields": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Fields to include in response"
                            }
                        },
                        "required": ["jql"]
                    }
                ),
                ConnectorTool(
                    id="jira_get_issue",
                    name="Get Jira Issue",
                    description="Get details of a specific Jira issue",
                    parameters_schema={
                        "type": "object",
                        "properties": {
                            "issue_key": {
                                "type": "string",
                                "description": "Issue key (e.g., 'PROJ-123')"
                            },
                            "expand": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Additional data to expand (comments, changelog, etc.)"
                            }
                        },
                        "required": ["issue_key"]
                    }
                ),
                ConnectorTool(
                    id="jira_update_issue",
                    name="Update Jira Issue",
                    description="Update an existing Jira issue",
                    parameters_schema={
                        "type": "object",
                        "properties": {
                            "issue_key": {
                                "type": "string",
                                "description": "Issue key (e.g., 'PROJ-123')"
                            },
                            "fields": {
                                "type": "object",
                                "description": "Fields to update"
                            },
                            "transition": {
                                "type": "string",
                                "description": "Transition to perform (optional)"
                            }
                        },
                        "required": ["issue_key", "fields"]
                    }
                ),
                ConnectorTool(
                    id="jira_add_comment",
                    name="Add Jira Comment",
                    description="Add a comment to a Jira issue",
                    parameters_schema={
                        "type": "object",
                        "properties": {
                            "issue_key": {
                                "type": "string",
                                "description": "Issue key (e.g., 'PROJ-123')"
                            },
                            "comment": {
                                "type": "string",
                                "description": "Comment text"
                            }
                        },
                        "required": ["issue_key", "comment"]
                    }
                ),
                # Confluence Tools
                ConnectorTool(
                    id="confluence_create_page",
                    name="Create Confluence Page",
                    description="Create a new page in Confluence",
                    parameters_schema={
                        "type": "object",
                        "properties": {
                            "space": {
                                "type": "string",
                                "description": "Space key"
                            },
                            "title": {
                                "type": "string",
                                "description": "Page title"
                            },
                            "content": {
                                "type": "string",
                                "description": "Page content (HTML or Markdown)"
                            },
                            "parent_id": {
                                "type": "string",
                                "description": "Parent page ID (optional)"
                            }
                        },
                        "required": ["space", "title", "content"]
                    }
                ),
                ConnectorTool(
                    id="confluence_search",
                    name="Search Confluence",
                    description="Search for pages and content in Confluence",
                    parameters_schema={
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "Search query"
                            },
                            "space": {
                                "type": "string",
                                "description": "Limit to specific space (optional)"
                            },
                            "type": {
                                "type": "string",
                                "enum": ["page", "blogpost", "comment", "attachment"],
                                "description": "Content type filter"
                            },
                            "max_results": {
                                "type": "integer",
                                "default": 10,
                                "description": "Maximum results"
                            }
                        },
                        "required": ["query"]
                    }
                ),
                ConnectorTool(
                    id="confluence_get_page",
                    name="Get Confluence Page",
                    description="Retrieve content of a specific Confluence page",
                    parameters_schema={
                        "type": "object",
                        "properties": {
                            "page_id": {
                                "type": "string",
                                "description": "Page ID"
                            },
                            "expand": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Additional data to expand (body, version, etc.)"
                            }
                        },
                        "required": ["page_id"]
                    }
                ),
                ConnectorTool(
                    id="confluence_update_page",
                    name="Update Confluence Page",
                    description="Update an existing Confluence page",
                    parameters_schema={
                        "type": "object",
                        "properties": {
                            "page_id": {
                                "type": "string",
                                "description": "Page ID"
                            },
                            "title": {
                                "type": "string",
                                "description": "New title (optional)"
                            },
                            "content": {
                                "type": "string",
                                "description": "New content"
                            },
                            "version_comment": {
                                "type": "string",
                                "description": "Version comment"
                            }
                        },
                        "required": ["page_id", "content"]
                    }
                )
            ]
        )
    
    def _get_mcp_server_info(self) -> Dict[str, Any]:
        """Get Atlassian MCP server information"""
        return {
            "server_url": self.mcp_config.mcp_server_url,
            "server_type": "atlassian-official",
            "supported_products": ["jira", "confluence", "compass"],
            "transport": self.mcp_config.transport_type,
            "oauth_enabled": True
        }
    
    async def get_authorization_url(
        self,
        user_id: str,
        state: Optional[str] = None,
        **kwargs
    ) -> Tuple[str, str]:
        """
        Generate Atlassian OAuth authorization URL.
        
        Atlassian uses OAuth 2.0 (3LO) with specific requirements.
        Since Atlassian's MCP server doesn't fully implement discovery,
        we use their standard OAuth endpoints directly.
        """
        # Check if we have OAuth credentials configured
        if not self.mcp_config.client_id:
            raise ValueError(
                "Atlassian OAuth app credentials not configured. "
                "Please register an app at https://developer.atlassian.com/console/myapps/ "
                "and set ATLASSIAN_CLIENT_ID and ATLASSIAN_CLIENT_SECRET environment variables."
            )
        
        # Use Atlassian's standard OAuth endpoints if not already set
        if not self.mcp_config.authorize_url:
            self.mcp_config.authorize_url = "https://auth.atlassian.com/authorize"
        if not self.mcp_config.token_url:
            self.mcp_config.token_url = "https://auth.atlassian.com/oauth/token"
        
        # Atlassian-specific OAuth parameters
        # Atlassian requires specific scopes for API access
        # CRITICAL: offline_access is required for refresh tokens to work
        scopes = [
            "read:jira-work",
            "write:jira-work",
            "read:jira-user",
            "read:confluence-content.all",
            "write:confluence-content",
            "read:confluence-space.summary",
            "search:confluence",  # REQUIRED for Confluence search API
            "offline_access"  # REQUIRED for refresh token support
        ]
        
        atlassian_params = {
            "audience": "api.atlassian.com",  # Required for Atlassian
            "prompt": "consent",  # Ensure we get refresh token
            "scope": " ".join(scopes),  # Override default scopes
            **kwargs
        }
        
        # Call parent method with Atlassian-specific params
        return await super().get_authorization_url(user_id, state, **atlassian_params)
    
    async def exchange_code_for_token(self, code: str, state: str, user_id: str) -> UserOAuthToken:
        """
        Exchange authorization code for access token with Atlassian-specific handling.
        
        Atlassian requires specific parameters in the token exchange.
        """
        # First get the state data
        state_key = f"oauth:state:{state}"
        from redis.asyncio import Redis
        plain_redis = Redis(
            connection_pool=self.redis_storage.redis_client.connection_pool,
            decode_responses=True
        )
        state_json = await plain_redis.get(state_key)
        
        if not state_json:
            await plain_redis.close()
            raise ValueError("Invalid or expired state parameter")
        
        state_data = json.loads(state_json)
        code_verifier = state_data.get("code_verifier")
        
        # Delete state from Redis
        await plain_redis.delete(state_key)
        await plain_redis.close()
        
        # Exchange code for token with Atlassian-specific parameters
        import httpx
        
        token_params = {
            "grant_type": "authorization_code",
            "client_id": self.mcp_config.client_id,
            "client_secret": self.mcp_config.client_secret,
            "code": code,
            "redirect_uri": self.mcp_config.redirect_uri,
            "code_verifier": code_verifier
        }
        
        logger.info(
            "Exchanging code for Atlassian token",
            user_id=user_id,
            has_code_verifier=bool(code_verifier),
            redirect_uri=self.mcp_config.redirect_uri
        )
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.mcp_config.token_url,
                data=token_params,
                headers={
                    "Content-Type": "application/x-www-form-urlencoded",
                    "Accept": "application/json"
                }
            )
            
            if response.status_code != 200:
                logger.error(
                    "Atlassian token exchange failed",
                    status_code=response.status_code,
                    response=response.text
                )
                raise ValueError(f"Token exchange failed: {response.text}")
            
            token_data = response.json()
            
        # Parse the token response
        from datetime import datetime, timedelta
        expires_in = token_data.get("expires_in", 3600)
        expires_at = datetime.utcnow() + timedelta(seconds=int(expires_in))
        
        # Check if we got a refresh token
        refresh_token = token_data.get("refresh_token")
        if not refresh_token:
            logger.warning(
                "No refresh token received from Atlassian - offline_access scope may be missing",
                user_id=user_id,
                scope=token_data.get("scope")
            )
        
        token = UserOAuthToken(
            user_id=user_id,
            provider_id=self.mcp_config.provider_id,
            access_token=token_data["access_token"],
            token_type=token_data.get("token_type", "Bearer"),
            refresh_token=refresh_token,
            expires_at=expires_at,
            scope=token_data.get("scope"),
            additional_data={
                "cloud_id": None,  # Will be fetched when needed
                "token_issued_at": datetime.utcnow().isoformat(),
                "rotating_refresh": True,  # Atlassian uses rotating refresh tokens
                "refresh_invalid": False  # Initially valid
            },
            last_refreshed=datetime.utcnow()
        )
        
        # Store token
        await self.store_user_token(token)
        
        # Update connector status
        from agents.connectors.core.base_connector import ConnectorStatus
        await self._update_user_connector_status(user_id, ConnectorStatus.CONNECTED)
        
        logger.info(
            "Successfully exchanged code for Atlassian token",
            user_id=user_id,
            has_refresh_token=bool(token.refresh_token),
            scope=token.scope
        )
        
        return token
    
    async def refresh_user_token(self, user_id: str) -> UserOAuthToken:
        """
        Refresh Atlassian token with specific handling.
        """
        # Get existing token WITHOUT auto-refresh to avoid recursion
        token = await self.get_user_token(user_id, auto_refresh=False)
        if not token or not token.refresh_token:
            raise ValueError("No refresh token available")
        
        import httpx
        from datetime import datetime, timedelta
        
        # Refresh the token with Atlassian-specific parameters
        token_params = {
            "grant_type": "refresh_token",
            "refresh_token": token.refresh_token,
            "client_id": self.mcp_config.client_id,
            "client_secret": self.mcp_config.client_secret
        }
        
        logger.info(
            "Refreshing Atlassian token",
            user_id=user_id,
            has_refresh_token=bool(token.refresh_token)
        )
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.mcp_config.token_url,
                data=token_params,
                headers={
                    "Content-Type": "application/x-www-form-urlencoded",
                    "Accept": "application/json"
                }
            )
            
            if response.status_code != 200:
                logger.error(
                    "Atlassian token refresh failed",
                    status_code=response.status_code,
                    response=response.text
                )
                raise ValueError(f"Token refresh failed: {response.text}")
            
            token_data = response.json()
            
        # Parse the new token
        expires_in = token_data.get("expires_in", 3600)
        expires_at = datetime.utcnow() + timedelta(seconds=int(expires_in))
        
        # CRITICAL: Atlassian uses rotating refresh tokens
        # We MUST use the new refresh token and discard the old one
        new_refresh_token = token_data.get("refresh_token")
        if not new_refresh_token:
            logger.error(
                "No new refresh token in response - Atlassian requires rotating refresh tokens",
                user_id=user_id
            )
            # If no new refresh token, the old one is likely invalid
            # User will need to re-authenticate
            raise ValueError("No new refresh token received - re-authentication required")
        
        new_token = UserOAuthToken(
            user_id=user_id,
            provider_id=self.mcp_config.provider_id,
            access_token=token_data["access_token"],
            token_type=token_data.get("token_type", "Bearer"),
            refresh_token=new_refresh_token,  # ALWAYS use the new refresh token
            expires_at=expires_at,
            scope=token_data.get("scope"),
            additional_data={
                "cloud_id": token.additional_data.get("cloud_id") if token.additional_data else None,
                "refreshed_at": datetime.utcnow().isoformat(),
                "rotating_refresh": True  # Flag to indicate rotating refresh token
            },
            last_refreshed=datetime.utcnow()
        )
        
        # Store the refreshed token
        await self.store_user_token(new_token)
        
        logger.info(
            "Successfully refreshed Atlassian token",
            user_id=user_id,
            new_token_preview=new_token.access_token[:20] if new_token.access_token else None,
            has_new_refresh_token=bool(new_token.refresh_token)
        )
        
        return new_token
    
    async def create_langchain_tools(
        self,
        user_id: str,
        tool_ids: List[str]
    ) -> List[BaseTool]:
        """
        Create LangChain tools for Atlassian services.
        
        Uses predefined tool wrappers for better type safety.
        """
        token = await self.get_user_token(user_id, auto_refresh=True)
        if not token:
            logger.warning("No token found for user", user_id=user_id)
            return []
        
        # Check if token is expired
        if token.is_expired and not token.refresh_token:
            logger.error(
                "Token expired and no refresh token available",
                user_id=user_id
            )
            return []
        
        # Since Atlassian's MCP server is in beta and has authentication issues,
        # use direct REST API implementation instead
        logger.info(
            "Using direct REST API for Atlassian tools (MCP server in beta)",
            user_id=user_id,
            has_token=bool(token.access_token),
            token_expired=token.is_expired if token else None,
            has_refresh_token=bool(token.refresh_token) if token else None
        )
        
        # Check if we should try to refresh the token
        # Don't auto-refresh if we know the refresh token is invalid
        should_refresh = (
            token.refresh_token and 
            not (token.additional_data and token.additional_data.get("refresh_invalid"))
        )
        
        # Also check if we've already tried to refresh in this session
        if should_refresh and token.additional_data:
            # Check if we've marked this as needing re-auth
            if token.additional_data.get("needs_reauth"):
                logger.warning(
                    "Token needs re-authentication, skipping refresh",
                    user_id=user_id
                )
                should_refresh = False
        
        if should_refresh:
            logger.info("Attempting to refresh Atlassian token", user_id=user_id)
            try:
                token = await self.refresh_user_token(user_id)
                logger.info("Successfully refreshed Atlassian token", user_id=user_id)
            except Exception as e:
                error_str = str(e)
                logger.error(
                    "Failed to refresh Atlassian token",
                    user_id=user_id,
                    error=error_str
                )
                
                # If refresh token is invalid, mark it so we don't keep trying
                if "refresh_token is invalid" in error_str or "unauthorized_client" in error_str:
                    logger.warning(
                        "Refresh token is invalid - user needs to re-authenticate",
                        user_id=user_id
                    )
                    # Mark the token as having an invalid refresh token
                    if token.additional_data is None:
                        token.additional_data = {}
                    token.additional_data["refresh_invalid"] = True
                    await self.store_user_token(token)
                    
                # Continue with existing token if refresh fails
                pass
        
        # Import the direct API implementation
        from .atlassian_direct_connector import create_atlassian_direct_tools
        
        # Create tools using direct REST API
        tools = await create_atlassian_direct_tools(
            access_token=token.access_token,
            tool_ids=tool_ids
        )
        
        logger.info(
            "Created Atlassian tools",
            user_id=user_id,
            num_tools=len(tools),
            tool_ids=tool_ids
        )
        
        return tools
    
    async def get_user_info(self, user_id: str) -> Dict[str, Any]:
        """
        Get user information from Atlassian.
        
        For MCP connectors, this is handled by the MCP server.
        """
        try:
            # For MCP connectors, user info is typically obtained through the MCP server
            # The MCP server handles the actual API calls to Atlassian
            token = await self.get_user_token(user_id)
            if not token:
                raise ValueError("No token found for user")
            
            # Basic user info - MCP server handles the details
            return {
                "provider": "atlassian",
                "authenticated": True,
                "mcp_server": self.mcp_config.mcp_server_url
            }
            
        except Exception as e:
            logger.error(
                "Failed to get user info",
                user_id=user_id,
                error=str(e)
            )
            raise
    
    async def get_cloud_id(self, user_id: str) -> Optional[str]:
        """
        Get Atlassian Cloud ID for the user's instance.
        
        This is required for API calls.
        """
        try:
            token = await self.get_user_token(user_id)
            if not token:
                return None
            
            # Call Atlassian's accessible resources endpoint
            import httpx
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    "https://api.atlassian.com/oauth/token/accessible-resources",
                    headers={"Authorization": f"Bearer {token.access_token}"}
                )
                response.raise_for_status()
                resources = response.json()
                
                if resources and len(resources) > 0:
                    # Return the first cloud ID (user might have access to multiple)
                    return resources[0].get("id")
                
                return None
                
        except Exception as e:
            logger.error(
                "Failed to get Atlassian Cloud ID",
                user_id=user_id,
                error=str(e)
            )
            return None