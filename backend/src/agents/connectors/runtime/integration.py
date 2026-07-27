"""
Integration layer for OAuth connectors with the agent runtime

This module bridges the connector system with the existing dynamic tool loader,
allowing connector tools to be injected into agent conversations.
"""

import os
from typing import List, Optional

import structlog
from agents.connectors.core.connector_manager import (
    ConnectorManager,
    set_connector_manager,
)
from agents.connectors.core.base_connector import OAuthConfig, OAuthVersion
from agents.connectors.core.mcp_connector import MCPConfig
from agents.connectors.providers.google.google_connector import GoogleConnector
from agents.connectors.providers.atlassian.atlassian_connector import AtlassianConnector
from agents.connectors.providers.paypal.paypal_connector import PayPalConnector
from agents.connectors.providers.notion.notion_connector import NotionConnector
from agents.storage.redis_storage import RedisStorage
from agents.tools.dynamic_tool_loader import DynamicToolLoader
from langchain.tools import BaseTool

logger = structlog.get_logger(__name__)


async def initialize_connectors(redis_storage: RedisStorage) -> ConnectorManager:
    """
    Initialize the connector system with available OAuth providers
    
    This function should be called during app startup after Redis is initialized.
    """
    try:
        # Create connector manager
        manager = ConnectorManager(redis_storage)
        
        # Initialize Google connector if credentials are configured
        google_client_id = os.getenv("GOOGLE_OAUTH_CLIENT_ID")
        google_client_secret = os.getenv("GOOGLE_OAUTH_CLIENT_SECRET")
        
        logger.info(
            "Checking Google OAuth credentials",
            has_client_id=bool(google_client_id),
            has_client_secret=bool(google_client_secret),
            client_id_prefix=google_client_id[:10] if google_client_id else None
        )
        
        if google_client_id and google_client_secret:
            google_config = OAuthConfig(
                provider_id="google",
                client_id=google_client_id,
                client_secret=google_client_secret,
                authorize_url="https://accounts.google.com/o/oauth2/v2/auth",
                token_url="https://oauth2.googleapis.com/token",
                redirect_uri=os.getenv("GOOGLE_OAUTH_REDIRECT_URI", "http://localhost:8000/api/connectors/google/callback"),
                scopes=[
                    "https://www.googleapis.com/auth/gmail.modify",
                    "https://www.googleapis.com/auth/drive",
                    "https://www.googleapis.com/auth/calendar",
                    "openid",
                    "email",
                    "profile",
                ],
                oauth_version=OAuthVersion.OAUTH2_0,
                use_pkce=True,
                revoke_url="https://oauth2.googleapis.com/revoke",
                userinfo_url="https://www.googleapis.com/oauth2/v1/userinfo",
                additional_params={
                    "access_type": "offline",  # To get refresh token
                    "prompt": "consent",  # Force consent to get refresh token
                }
            )
            
            google_connector = GoogleConnector(google_config, redis_storage)
            manager.register_connector("google", google_connector)
            logger.info("Registered Google OAuth connector")
        else:
            logger.warning("Google OAuth credentials not configured")
        
        # Initialize Atlassian MCP connector
        atlassian_mcp_server = os.getenv("ATLASSIAN_MCP_SERVER_URL")
        atlassian_client_id = os.getenv("ATLASSIAN_CLIENT_ID")
        atlassian_client_secret = os.getenv("ATLASSIAN_CLIENT_SECRET")
        
        if atlassian_mcp_server:
            # Atlassian's MCP server doesn't fully implement OAuth discovery
            # So we need either OAuth app credentials OR use a community server
            
            if atlassian_client_id and atlassian_client_secret:
                # Option 1: Using official Atlassian MCP with OAuth app
                atlassian_config = MCPConfig(
                    provider_id="atlassian",
                    mcp_server_url=atlassian_mcp_server,
                    transport_type="sse",
                    use_discovery=False,  # Atlassian doesn't support discovery
                    redirect_uri=os.getenv("ATLASSIAN_OAUTH_REDIRECT_URI", "http://localhost:8000/connectors/atlassian/callback"),
                    oauth_version=OAuthVersion.OAUTH2_0,
                    use_pkce=True,
                    client_id=atlassian_client_id,
                    client_secret=atlassian_client_secret,
                    authorize_url="https://auth.atlassian.com/authorize",
                    token_url="https://auth.atlassian.com/oauth/token",
                    scopes=["read:jira-work", "write:jira-work", "read:confluence-content.all", "write:confluence-content"]
                )
            else:
                # Option 2: Community MCP server or other implementation
                logger.warning(
                    "Atlassian MCP server configured but no OAuth credentials provided.",
                    help="Either provide ATLASSIAN_CLIENT_ID/SECRET or use a community MCP server"
                )
                # Still create connector for community servers that might not need OAuth
                atlassian_config = MCPConfig(
                    provider_id="atlassian",
                    mcp_server_url=atlassian_mcp_server,
                    transport_type="sse",
                    use_discovery=True,  # Try discovery for community servers
                    redirect_uri=os.getenv("ATLASSIAN_OAUTH_REDIRECT_URI", "http://localhost:8000/connectors/atlassian/callback"),
                    oauth_version=OAuthVersion.OAUTH2_0,
                    use_pkce=True,
                    client_id="",
                    client_secret="",
                    authorize_url="",
                    token_url="",
                    scopes=[]
                )
            
            atlassian_connector = AtlassianConnector(atlassian_config, redis_storage)
            
            # Discover OAuth metadata from the MCP server
            try:
                import asyncio
                metadata = asyncio.run(atlassian_connector.discover_oauth_metadata())
                logger.info(
                    "Discovered Atlassian MCP OAuth metadata",
                    metadata=metadata
                )
            except Exception as e:
                logger.warning(
                    "Could not discover Atlassian MCP metadata (will retry on first use)",
                    error=str(e)
                )
            
            manager.register_connector("atlassian", atlassian_connector)
            logger.info("Registered Atlassian MCP connector", server_url=atlassian_mcp_server)
        else:
            logger.info("Atlassian MCP server URL not configured")
        
        # Initialize PayPal connector
        paypal_client_id = os.getenv("PAYPAL_CLIENT_ID")
        paypal_client_secret = os.getenv("PAYPAL_CLIENT_SECRET")
        
        logger.info(
            "Checking PayPal OAuth credentials",
            has_client_id=bool(paypal_client_id),
            has_client_secret=bool(paypal_client_secret)
        )
        
        if paypal_client_id and paypal_client_secret:
            # Initialize PayPal connector (uses sandbox by default)
            paypal_connector = PayPalConnector(redis_storage)
            
            # Initialize with OAuth credentials
            await paypal_connector.initialize(
                client_id=paypal_client_id,
                client_secret=paypal_client_secret,
                redirect_uri=os.getenv("PAYPAL_OAUTH_REDIRECT_URI", "http://localhost:8000/api/connectors/paypal/callback")
            )
            
            manager.register_connector("paypal", paypal_connector)
            logger.info(
                "Registered PayPal connector",
                is_sandbox=True,  # Always using sandbox for testing
                mcp_url="https://mcp.sandbox.paypal.com/mcp"
            )
        else:
            logger.info("PayPal OAuth credentials not configured")
        
        # Initialize Notion connector
        notion_client_id = os.getenv("NOTION_CLIENT_ID")
        notion_client_secret = os.getenv("NOTION_CLIENT_SECRET")
        
        logger.info(
            "Checking Notion OAuth credentials",
            has_client_id=bool(notion_client_id),
            has_client_secret=bool(notion_client_secret)
        )
        
        if notion_client_id and notion_client_secret:
            notion_config = OAuthConfig(
                provider_id="notion",
                client_id=notion_client_id,
                client_secret=notion_client_secret,
                authorize_url="https://api.notion.com/v1/oauth/authorize",
                token_url="https://api.notion.com/v1/oauth/token",
                redirect_uri=os.getenv("NOTION_OAUTH_REDIRECT_URI", "http://localhost:8000/api/connectors/notion/callback"),
                scopes=[],  # Notion doesn't use scopes in the traditional OAuth sense
                oauth_version=OAuthVersion.OAUTH2_0,
                use_pkce=False,  # Notion doesn't require PKCE
                additional_params={
                    "owner": "user"  # Request access to user's resources
                }
            )
            
            notion_connector = NotionConnector(notion_config, redis_storage)
            manager.register_connector("notion", notion_connector)
            logger.info("Registered Notion OAuth connector")
        else:
            logger.info("Notion OAuth credentials not configured")
        
        # Set global connector manager
        set_connector_manager(manager)
        
        logger.info(
            "Connector system initialized",
            num_connectors=len(manager.connectors)
        )
        
        return manager
        
    except Exception as e:
        logger.error(
            "Failed to initialize connector system",
            error=str(e),
            exc_info=True
        )
        raise


class ConnectorToolLoader:
    """
    Adapter to integrate connector tools with the existing DynamicToolLoader
    """
    
    def __init__(self, connector_manager: ConnectorManager):
        self.connector_manager = connector_manager
    
    async def load_user_connector_tools(self, user_id: str) -> List[BaseTool]:
        """
        Load all enabled connector tools for a user
        
        This method is called by the DynamicToolLoader to get connector tools.
        """
        try:
            # Get all connector tools for the user
            tools = await self.connector_manager.get_user_tools(user_id)
            
            logger.info(
                "Loaded connector tools for user",
                user_id=user_id,
                num_tools=len(tools)
            )
            
            return tools
            
        except Exception as e:
            logger.error(
                "Failed to load connector tools",
                user_id=user_id,
                error=str(e),
                exc_info=True
            )
            return []