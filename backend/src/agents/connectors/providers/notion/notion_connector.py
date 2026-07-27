"""
Notion OAuth Connector with Direct API Integration

This connector provides access to Notion's workspace management, database operations,
page creation, and content editing through their REST API.

Uses OAuth 2.0 Authorization Code flow to support multiple users, where each
user can connect and authorize access to their own Notion workspace.
"""

import base64
import json
from typing import Any, Dict, List, Optional
from datetime import datetime, timedelta

import aiohttp
import structlog
from langchain.tools import BaseTool

from agents.connectors.core.base_connector import (
    BaseOAuthConnector,
    ConnectorMetadata,
    ConnectorTool,
    OAuthConfig,
    OAuthVersion,
    UserOAuthToken
)

logger = structlog.get_logger(__name__)

NOTION_API_VERSION = "2022-06-28"  # Latest stable API version


class NotionConnector(BaseOAuthConnector):
    """
    Notion connector using OAuth 2.0 and direct REST API.
    
    This connector provides access to Notion's workspace, database, page, 
    and block management capabilities.
    """
    
    def __init__(self, oauth_config: OAuthConfig, redis_storage):
        """
        Initialize Notion connector with OAuth configuration.
        
        Args:
            oauth_config: OAuth 2.0 configuration for Notion
            redis_storage: Redis storage for token management
        """
        super().__init__(oauth_config, redis_storage)
        self.api_base_url = "https://api.notion.com/v1"
        
    def _get_metadata(self) -> ConnectorMetadata:
        """Get connector metadata."""
        return ConnectorMetadata(
            provider_id="notion",
            name="Notion",
            description="Access Notion workspaces, databases, pages, and blocks",
            icon_url="https://www.notion.so/images/favicon.ico",
            oauth_version=OAuthVersion.OAUTH2_0,
            available_tools=self._get_tool_definitions()
        )
    
    def _get_tool_definitions(self) -> List[ConnectorTool]:
        """Get Notion tool definitions."""
        return [
            ConnectorTool(
                id="notion_search",
                name="Search Notion",
                description="Search across all pages and databases in your workspace",
                parameters_schema={
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Search query"
                        },
                        "filter": {
                            "type": "string",
                            "enum": ["page", "database"],
                            "description": "Filter by object type"
                        }
                    },
                    "required": ["query"]
                }
            ),
            ConnectorTool(
                id="notion_list_databases",
                name="List Databases",
                description="List all databases in your workspace",
                parameters_schema={
                    "type": "object",
                    "properties": {}
                }
            ),
            ConnectorTool(
                id="notion_query_database",
                name="Query Database",
                description="Query a database with filters and sorts",
                parameters_schema={
                    "type": "object",
                    "properties": {
                        "database_id": {
                            "type": "string",
                            "description": "Database ID to query"
                        },
                        "filter": {
                            "type": "object",
                            "description": "Filter conditions (Notion filter format)"
                        },
                        "sorts": {
                            "type": "array",
                            "description": "Sort conditions"
                        },
                        "page_size": {
                            "type": "integer",
                            "description": "Number of results to return (max 100)",
                            "default": 10
                        }
                    },
                    "required": ["database_id"]
                }
            ),
            ConnectorTool(
                id="notion_get_database_schema",
                name="Get Database Schema",
                description="Get the schema of a database including all property names and types. Use this BEFORE creating pages to understand the database structure.",
                parameters_schema={
                    "type": "object",
                    "properties": {
                        "database_id": {
                            "type": "string",
                            "description": "Database ID"
                        }
                    },
                    "required": ["database_id"]
                }
            ),
            ConnectorTool(
                id="notion_create_page",
                name="Create Page",
                description="Create a new page in a database or as a child of another page",
                parameters_schema={
                    "type": "object",
                    "properties": {
                        "parent_type": {
                            "type": "string",
                            "enum": ["database_id", "page_id"],
                            "description": "Type of parent"
                        },
                        "parent_id": {
                            "type": "string",
                            "description": "ID of the parent database or page"
                        },
                        "title": {
                            "type": "string",
                            "description": "Page title"
                        },
                        "properties": {
                            "type": "object",
                            "description": "Database properties (if parent is database)"
                        },
                        "content": {
                            "type": "array",
                            "description": "Initial page content blocks"
                        }
                    },
                    "required": ["parent_type", "parent_id", "title"]
                }
            ),
            ConnectorTool(
                id="notion_get_page",
                name="Get Page",
                description="Get a page's properties and metadata",
                parameters_schema={
                    "type": "object",
                    "properties": {
                        "page_id": {
                            "type": "string",
                            "description": "Page ID"
                        }
                    },
                    "required": ["page_id"]
                }
            ),
            ConnectorTool(
                id="notion_update_page",
                name="Update Page",
                description="Update a page's properties",
                parameters_schema={
                    "type": "object",
                    "properties": {
                        "page_id": {
                            "type": "string",
                            "description": "Page ID to update"
                        },
                        "properties": {
                            "type": "object",
                            "description": "Properties to update"
                        },
                        "archived": {
                            "type": "boolean",
                            "description": "Whether to archive the page"
                        }
                    },
                    "required": ["page_id"]
                }
            ),
            ConnectorTool(
                id="notion_get_blocks",
                name="Get Page Blocks",
                description="Get all blocks (content) from a page",
                parameters_schema={
                    "type": "object",
                    "properties": {
                        "page_id": {
                            "type": "string",
                            "description": "Page ID"
                        }
                    },
                    "required": ["page_id"]
                }
            ),
            ConnectorTool(
                id="notion_append_blocks",
                name="Append Blocks",
                description="Add new blocks to a page",
                parameters_schema={
                    "type": "object",
                    "properties": {
                        "page_id": {
                            "type": "string",
                            "description": "Page ID to append to"
                        },
                        "children": {
                            "type": "array",
                            "description": "Array of block objects to append"
                        }
                    },
                    "required": ["page_id", "children"]
                }
            ),
            ConnectorTool(
                id="notion_create_database",
                name="Create Database",
                description="Create a new database as a child of a page (workspace-level databases not supported via API)",
                parameters_schema={
                    "type": "object",
                    "properties": {
                        "parent_type": {
                            "type": "string",
                            "enum": ["page_id"],
                            "description": "Type of parent (must be page_id)"
                        },
                        "parent_id": {
                            "type": "string",
                            "description": "Parent page ID"
                        },
                        "title": {
                            "type": "string",
                            "description": "Database title"
                        },
                        "properties": {
                            "type": "object",
                            "description": "Database schema properties"
                        }
                    },
                    "required": ["parent_type", "parent_id", "title", "properties"]
                }
            )
        ]
    
    async def exchange_code_for_token(self, code: str, state: str, user_id: str) -> UserOAuthToken:
        """
        Exchange authorization code for access token.
        
        Notion uses HTTP Basic Auth for the token exchange with
        client_id:client_secret base64 encoded.
        
        Args:
            code: Authorization code from OAuth callback
            state: OAuth state parameter (for CSRF protection)
            user_id: User ID
        """
        try:
            # Prepare Basic Auth header
            credentials = f"{self.config.client_id}:{self.config.client_secret}"
            encoded_credentials = base64.b64encode(credentials.encode()).decode()
            
            headers = {
                "Authorization": f"Basic {encoded_credentials}",
                "Content-Type": "application/json"
            }
            
            data = {
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": self.config.redirect_uri
            }
            
            logger.info(
                "Exchanging code for Notion token",
                user_id=user_id,
                redirect_uri=self.config.redirect_uri
            )
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.config.token_url,
                    headers=headers,
                    json=data
                ) as response:
                    response_text = await response.text()
                    
                    if response.status != 200:
                        logger.error(
                            "Failed to exchange code for token",
                            status=response.status,
                            response=response_text
                        )
                        raise Exception(f"Token exchange failed: {response_text}")
                    
                    token_data = json.loads(response_text)
                    
                    # Notion returns additional useful data
                    workspace_id = token_data.get("workspace_id")
                    workspace_name = token_data.get("workspace_name")
                    workspace_icon = token_data.get("workspace_icon")
                    bot_id = token_data.get("bot_id")
                    owner_info = token_data.get("owner", {})
                    
                    # Create token object
                    token = UserOAuthToken(
                        provider_id="notion",
                        user_id=user_id,
                        access_token=token_data["access_token"],
                        refresh_token=None,  # Notion doesn't provide refresh tokens
                        expires_at=None,  # Notion tokens don't expire
                        scope=None,  # Notion doesn't use scopes in the traditional way
                        token_type=token_data.get("token_type", "bearer"),
                        additional_data={
                            "workspace_id": workspace_id,
                            "workspace_name": workspace_name,
                            "workspace_icon": workspace_icon,
                            "bot_id": bot_id,
                            "owner": owner_info
                        }
                    )
                    
                    # Store token
                    await self.store_user_token(token)
                    
                    logger.info(
                        "Successfully obtained Notion token",
                        user_id=user_id,
                        workspace_id=workspace_id,
                        workspace_name=workspace_name
                    )
                    
                    return token
                    
        except Exception as e:
            logger.error(
                "Failed to exchange code for token",
                user_id=user_id,
                error=str(e),
                exc_info=True
            )
            raise
    
    async def refresh_token(self, user_id: str) -> UserOAuthToken:
        """
        Refresh access token.
        
        Note: Notion doesn't support refresh tokens. Their access tokens
        don't expire unless explicitly revoked.
        """
        # Notion tokens don't expire, so just return the existing token
        token = await self.get_user_token(user_id)
        if not token:
            raise Exception("No token found for user")
        return token
    
    async def revoke_token(self, user_id: str) -> bool:
        """
        Revoke user's access token.
        
        Note: Notion doesn't provide a programmatic revoke endpoint.
        Users must revoke access through their Notion settings.
        """
        try:
            # Remove token from storage
            await self.delete_user_token(user_id)
            
            logger.info(
                "Removed Notion token from storage",
                user_id=user_id,
                note="User must manually revoke in Notion settings"
            )
            
            return True
            
        except Exception as e:
            logger.error(
                "Failed to revoke token",
                user_id=user_id,
                error=str(e)
            )
            return False
    
    async def get_user_info(self, user_id: str) -> Optional[Dict[str, Any]]:
        """
        Get user information from Notion.
        
        Returns user details including name, email, and workspace info.
        """
        try:
            token = await self.get_user_token(user_id, auto_refresh=False)
            if not token:
                return None
            
            headers = {
                "Authorization": f"Bearer {token.access_token}",
                "Notion-Version": NOTION_API_VERSION
            }
            
            async with aiohttp.ClientSession() as session:
                # Get current user info
                async with session.get(
                    f"{self.api_base_url}/users/me",
                    headers=headers
                ) as response:
                    if response.status == 200:
                        user_data = await response.json()
                        
                        return {
                            "id": user_data.get("id"),
                            "name": user_data.get("name"),
                            "email": user_data.get("person", {}).get("email"),
                            "type": user_data.get("type"),
                            "workspace": token.additional_data
                        }
                    else:
                        logger.error(
                            "Failed to get user info",
                            user_id=user_id,
                            status=response.status
                        )
                        return None
                        
        except Exception as e:
            logger.error(
                "Failed to get user info",
                user_id=user_id,
                error=str(e),
                exc_info=True
            )
            return None
    
    async def test_connection(self, user_id: str) -> Dict[str, Any]:
        """
        Test connection by fetching current user information.
        """
        try:
            token = await self.get_user_token(user_id, auto_refresh=False)
            if not token:
                return {
                    "connected": False,
                    "error": "No token found"
                }
            
            headers = {
                "Authorization": f"Bearer {token.access_token}",
                "Notion-Version": NOTION_API_VERSION
            }
            
            async with aiohttp.ClientSession() as session:
                # Get current user info
                async with session.get(
                    f"{self.api_base_url}/users/me",
                    headers=headers
                ) as response:
                    if response.status == 200:
                        user_data = await response.json()
                        
                        return {
                            "connected": True,
                            "user": {
                                "id": user_data.get("id"),
                                "name": user_data.get("name"),
                                "email": user_data.get("person", {}).get("email"),
                                "type": user_data.get("type")
                            },
                            "workspace": token.additional_data
                        }
                    else:
                        error_text = await response.text()
                        return {
                            "connected": False,
                            "error": f"Connection test failed: {error_text}"
                        }
                        
        except Exception as e:
            logger.error(
                "Connection test failed",
                user_id=user_id,
                error=str(e),
                exc_info=True
            )
            return {
                "connected": False,
                "error": str(e)
            }
    
    async def get_available_tools(self) -> List[ConnectorTool]:
        """
        Get list of available Notion tools.
        """
        return self._get_tool_definitions()
    
    async def create_langchain_tools(self, user_id: str, tool_ids: Optional[List[str]] = None) -> List[BaseTool]:
        """
        Create LangChain tools for direct API access.
        
        This delegates to the direct API implementation.
        """
        from agents.connectors.providers.notion.notion_direct_connector import NotionDirectConnector
        
        direct_connector = NotionDirectConnector(self.redis_storage)
        direct_connector.config = self.config
        direct_connector.parent_connector = self
        
        return await direct_connector.create_langchain_tools(user_id, tool_ids)