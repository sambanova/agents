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
from agents.connectors.providers.google.google_connector import GoogleConnector
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
            manager.register_connector(google_connector)
            logger.info("Registered Google OAuth connector")
        else:
            logger.warning("Google OAuth credentials not configured")
        
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