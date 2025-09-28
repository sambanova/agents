"""
Google OAuth Connector

Provides OAuth integration for Google services (Gmail, Drive, Calendar, etc.)
with user-level management and tool selection.
"""

from typing import Any, Dict, List, Optional, Tuple

import httpx
import structlog
from agents.connectors.core.base_connector import (
    BaseOAuthConnector,
    ConnectorMetadata,
    ConnectorTool,
    OAuthConfig,
    OAuthVersion,
)
from langchain.tools import BaseTool

logger = structlog.get_logger(__name__)


class GoogleConnector(BaseOAuthConnector):
    """
    Google OAuth 2.0 Connector
    
    Supports Gmail, Google Drive, Calendar, and other Google Workspace APIs
    """
    
    def _get_metadata(self) -> ConnectorMetadata:
        """Get Google connector metadata"""
        return ConnectorMetadata(
            provider_id="google",
            name="Google Workspace",
            description="Connect to Gmail, Google Drive, Calendar, and other Google services",
            icon_url="https://www.google.com/favicon.ico",
            oauth_version=OAuthVersion.OAUTH2_0,
            available_tools=[
                # Gmail Tools
                ConnectorTool(
                    id="gmail_search",
                    name="Search Gmail",
                    description="Search emails in Gmail",
                    parameters_schema={
                        "type": "object",
                        "properties": {
                            "query": {"type": "string", "description": "Gmail search query"},
                            "max_results": {"type": "integer", "default": 10}
                        },
                        "required": ["query"]
                    }
                ),
                ConnectorTool(
                    id="gmail_send",
                    name="Send Email",
                    description="Send an email via Gmail",
                    parameters_schema={
                        "type": "object",
                        "properties": {
                            "to": {"type": "string", "description": "Recipient email"},
                            "subject": {"type": "string", "description": "Email subject"},
                            "body": {"type": "string", "description": "Email body"},
                            "cc": {"type": "string", "description": "CC recipients (optional)"}
                        },
                        "required": ["to", "subject", "body"]
                    }
                ),
                ConnectorTool(
                    id="gmail_draft",
                    name="Create Draft",
                    description="Create a draft email in Gmail",
                    parameters_schema={
                        "type": "object",
                        "properties": {
                            "to": {"type": "string", "description": "Recipient email"},
                            "subject": {"type": "string", "description": "Email subject"},
                            "body": {"type": "string", "description": "Email body"}
                        },
                        "required": ["to", "subject", "body"]
                    }
                ),
                
                # Google Drive Tools
                ConnectorTool(
                    id="drive_search",
                    name="Search Drive",
                    description="Search files in Google Drive",
                    parameters_schema={
                        "type": "object",
                        "properties": {
                            "query": {"type": "string", "description": "Search query"},
                            "mime_type": {"type": "string", "description": "MIME type filter (optional)"},
                            "max_results": {"type": "integer", "default": 10}
                        },
                        "required": ["query"]
                    }
                ),
                ConnectorTool(
                    id="drive_read",
                    name="Read Drive File",
                    description="Read content from a Google Drive file",
                    parameters_schema={
                        "type": "object",
                        "properties": {
                            "file_id": {"type": "string", "description": "Google Drive file ID"}
                        },
                        "required": ["file_id"]
                    }
                ),
                ConnectorTool(
                    id="drive_create",
                    name="Create Drive File",
                    description="Create a new file in Google Drive",
                    parameters_schema={
                        "type": "object",
                        "properties": {
                            "name": {"type": "string", "description": "File name"},
                            "content": {"type": "string", "description": "File content"},
                            "mime_type": {"type": "string", "description": "MIME type", "default": "text/plain"},
                            "folder_id": {"type": "string", "description": "Parent folder ID (optional)"}
                        },
                        "required": ["name", "content"]
                    }
                ),
                
                # Google Calendar Tools
                ConnectorTool(
                    id="calendar_list",
                    name="List Calendar Events",
                    description="List upcoming calendar events",
                    parameters_schema={
                        "type": "object",
                        "properties": {
                            "max_results": {"type": "integer", "default": 10},
                            "calendar_id": {"type": "string", "default": "primary"}
                        }
                    }
                ),
                ConnectorTool(
                    id="calendar_create",
                    name="Create Calendar Event",
                    description="Create a new calendar event",
                    parameters_schema={
                        "type": "object",
                        "properties": {
                            "summary": {"type": "string", "description": "Event title"},
                            "start_time": {"type": "string", "description": "Start time (ISO format)"},
                            "end_time": {"type": "string", "description": "End time (ISO format)"},
                            "description": {"type": "string", "description": "Event description (optional)"},
                            "location": {"type": "string", "description": "Event location (optional)"}
                        },
                        "required": ["summary", "start_time", "end_time"]
                    }
                ),
            ],
            required_scopes=[
                "https://www.googleapis.com/auth/gmail.modify",
                "https://www.googleapis.com/auth/drive",
                "https://www.googleapis.com/auth/calendar"
            ],
            optional_scopes=[
                "https://www.googleapis.com/auth/gmail.send",
                "https://www.googleapis.com/auth/drive.file",
                "https://www.googleapis.com/auth/calendar.events"
            ]
        )
    
    async def get_user_info(self, user_id: str) -> Dict[str, Any]:
        """Get Google user information"""
        token = await self.get_user_token(user_id)
        if not token:
            raise ValueError("No token found for user")
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    "https://www.googleapis.com/oauth2/v1/userinfo",
                    headers={"Authorization": f"Bearer {token.access_token}"}
                )
                response.raise_for_status()
                return response.json()
        except Exception as e:
            logger.error(
                "Failed to get user info",
                user_id=user_id,
                error=str(e)
            )
            raise
    
    async def get_authorization_url(self, user_id: str, state: Optional[str] = None, **kwargs) -> Tuple[str, str]:
        """
        Generate Google OAuth authorization URL with refresh token support
        
        Google requires access_type=offline and prompt=consent to get refresh tokens
        """
        # Add Google-specific parameters for refresh token
        google_params = {
            'access_type': 'offline',  # Required for refresh token
            'prompt': 'consent',        # Force consent screen to get refresh token
            'include_granted_scopes': 'true',  # Incremental auth
            **kwargs
        }
        
        # Call parent method with Google-specific parameters
        return await super().get_authorization_url(user_id, state, **google_params)
    
    async def create_langchain_tools(self, user_id: str, tool_ids: List[str]) -> List[BaseTool]:
        """
        Create LangChain tools for enabled Google services
        
        This method is called by the connector manager to create actual tools
        """
        from .google_tools import create_google_langchain_tools
        
        # Get token with auto-refresh enabled
        token = await self.get_user_token(user_id, auto_refresh=True)
        
        if not token:
            logger.warning("No token found for user", user_id=user_id)
            return []
        
        # Double-check: if token is still expired after auto-refresh attempt, we have a problem
        if token.is_expired:
            logger.error(
                "Token is still expired after auto-refresh attempt",
                user_id=user_id,
                has_refresh_token=bool(token.refresh_token)
            )
            # If we have a refresh token, try one more explicit refresh
            if token.refresh_token:
                try:
                    logger.info("Attempting explicit token refresh", user_id=user_id)
                    token = await self.refresh_user_token(user_id)
                    logger.info("Explicit refresh successful", user_id=user_id)
                except Exception as e:
                    logger.error(
                        "Explicit refresh also failed",
                        user_id=user_id,
                        error=str(e)
                    )
                    return []
            else:
                logger.error("No refresh token available, cannot refresh", user_id=user_id)
                return []
        
        # Log token details for debugging
        logger.info(
            "Creating Google tools with token",
            user_id=user_id,
            has_access_token=bool(token.access_token),
            has_refresh_token=bool(token.refresh_token),
            token_expired=token.is_expired,
            needs_refresh=token.needs_refresh,
            expires_at=token.expires_at.isoformat() if token.expires_at else None
        )
        
        # Map our tool IDs to the standardized ones in google_tools.py
        tool_id_mapping = {
            "gmail_search": "gmail_search",
            "gmail_send": "gmail_send",
            "gmail_draft": "gmail_draft",  # Now using proper draft tool
            "drive_search": "google_drive_search",
            "drive_read": "google_drive_read",  # Now properly mapped to read tool
            "drive_create": "google_drive_upload",
            "calendar_list": "google_calendar_list",
            "calendar_create": "google_calendar_create",
        }
        
        # Map the requested tool IDs to the standardized ones
        mapped_tool_ids = []
        for tool_id in tool_ids:
            if tool_id in tool_id_mapping:
                mapped_id = tool_id_mapping[tool_id]
                if mapped_id not in mapped_tool_ids:  # Avoid duplicates
                    mapped_tool_ids.append(mapped_id)
        
        # Create and return the tools with all OAuth credentials for auto-refresh
        return create_google_langchain_tools(
            access_token=token.access_token,
            refresh_token=token.refresh_token,
            client_id=self.config.client_id,
            client_secret=self.config.client_secret,
            token_uri=self.config.token_url,
            user_id=user_id,
            tool_ids=mapped_tool_ids
        )
