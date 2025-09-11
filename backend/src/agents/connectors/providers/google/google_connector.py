"""
Google OAuth Connector

Provides OAuth integration for Google services (Gmail, Drive, Calendar, etc.)
with user-level management and tool selection.
"""

import base64
from typing import Any, Dict, List, Optional

import httpx
import structlog
from agents.connectors.core.base_connector import (
    BaseOAuthConnector,
    ConnectorMetadata,
    ConnectorTool,
    OAuthConfig,
    OAuthVersion,
)
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from langchain.tools import BaseTool, StructuredTool
from pydantic import BaseModel, Field

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
    
    async def create_langchain_tools(self, user_id: str, tool_ids: List[str]) -> List[BaseTool]:
        """
        Create LangChain tools for enabled Google services
        
        This method is called by the connector manager to create actual tools
        """
        tools = []
        token = await self.get_user_token(user_id)
        
        if not token:
            logger.warning("No token found for user", user_id=user_id)
            return tools
        
        # Create credentials object
        creds = Credentials(
            token=token.access_token,
            refresh_token=token.refresh_token,
            token_uri=self.config.token_url,
            client_id=self.config.client_id,
            client_secret=self.config.client_secret,
            scopes=token.scope.split() if token.scope else []
        )
        
        # Gmail tools
        if "gmail_search" in tool_ids:
            tools.append(self._create_gmail_search_tool(user_id, creds))
        if "gmail_send" in tool_ids:
            tools.append(self._create_gmail_send_tool(user_id, creds))
        if "gmail_draft" in tool_ids:
            tools.append(self._create_gmail_draft_tool(user_id, creds))
        
        # Drive tools
        if "drive_search" in tool_ids:
            tools.append(self._create_drive_search_tool(user_id, creds))
        if "drive_read" in tool_ids:
            tools.append(self._create_drive_read_tool(user_id, creds))
        if "drive_create" in tool_ids:
            tools.append(self._create_drive_create_tool(user_id, creds))
        
        # Calendar tools
        if "calendar_list" in tool_ids:
            tools.append(self._create_calendar_list_tool(user_id, creds))
        if "calendar_create" in tool_ids:
            tools.append(self._create_calendar_create_tool(user_id, creds))
        
        return tools
    
    def _create_gmail_search_tool(self, user_id: str, creds: Credentials) -> BaseTool:
        """Create Gmail search tool"""
        
        class GmailSearchInput(BaseModel):
            query: str = Field(description="Gmail search query")
            max_results: int = Field(default=10, description="Maximum results to return")
        
        def search_gmail(query: str, max_results: int = 10) -> str:
            """Search Gmail emails"""
            try:
                service = build('gmail', 'v1', credentials=creds)
                results = service.users().messages().list(
                    userId='me',
                    q=query,
                    maxResults=max_results
                ).execute()
                
                messages = results.get('messages', [])
                if not messages:
                    return "No messages found."
                
                output = []
                for msg in messages[:max_results]:
                    msg_data = service.users().messages().get(
                        userId='me',
                        id=msg['id']
                    ).execute()
                    
                    headers = msg_data['payload'].get('headers', [])
                    subject = next((h['value'] for h in headers if h['name'] == 'Subject'), 'No Subject')
                    sender = next((h['value'] for h in headers if h['name'] == 'From'), 'Unknown')
                    date = next((h['value'] for h in headers if h['name'] == 'Date'), 'Unknown')
                    
                    output.append(f"- From: {sender}\n  Subject: {subject}\n  Date: {date}")
                
                return "\n\n".join(output)
                
            except Exception as e:
                return f"Error searching Gmail: {str(e)}"
        
        return StructuredTool(
            name="gmail_search",
            description="Search emails in Gmail",
            func=search_gmail,
            args_schema=GmailSearchInput
        )
    
    def _create_gmail_send_tool(self, user_id: str, creds: Credentials) -> BaseTool:
        """Create Gmail send tool"""
        
        class GmailSendInput(BaseModel):
            to: str = Field(description="Recipient email address")
            subject: str = Field(description="Email subject")
            body: str = Field(description="Email body")
            cc: Optional[str] = Field(default=None, description="CC recipients")
        
        def send_gmail(to: str, subject: str, body: str, cc: Optional[str] = None) -> str:
            """Send an email via Gmail"""
            try:
                service = build('gmail', 'v1', credentials=creds)
                
                message = f"To: {to}\n"
                if cc:
                    message += f"Cc: {cc}\n"
                message += f"Subject: {subject}\n\n{body}"
                
                encoded_message = base64.urlsafe_b64encode(message.encode()).decode()
                
                send_message = service.users().messages().send(
                    userId='me',
                    body={'raw': encoded_message}
                ).execute()
                
                return f"Email sent successfully. Message ID: {send_message['id']}"
                
            except Exception as e:
                return f"Error sending email: {str(e)}"
        
        return StructuredTool(
            name="gmail_send",
            description="Send an email via Gmail",
            func=send_gmail,
            args_schema=GmailSendInput
        )
    
    def _create_gmail_draft_tool(self, user_id: str, creds: Credentials) -> BaseTool:
        """Create Gmail draft tool"""
        
        class GmailDraftInput(BaseModel):
            to: str = Field(description="Recipient email address")
            subject: str = Field(description="Email subject")
            body: str = Field(description="Email body")
        
        def create_draft(to: str, subject: str, body: str) -> str:
            """Create a draft email in Gmail"""
            try:
                service = build('gmail', 'v1', credentials=creds)
                
                message = f"To: {to}\nSubject: {subject}\n\n{body}"
                encoded_message = base64.urlsafe_b64encode(message.encode()).decode()
                
                draft = service.users().drafts().create(
                    userId='me',
                    body={'message': {'raw': encoded_message}}
                ).execute()
                
                return f"Draft created successfully. Draft ID: {draft['id']}"
                
            except Exception as e:
                return f"Error creating draft: {str(e)}"
        
        return StructuredTool(
            name="gmail_create_draft",
            description="Create a draft email in Gmail",
            func=create_draft,
            args_schema=GmailDraftInput
        )
    
    def _create_drive_search_tool(self, user_id: str, creds: Credentials) -> BaseTool:
        """Create Google Drive search tool"""
        
        class DriveSearchInput(BaseModel):
            query: str = Field(description="Search query")
            mime_type: Optional[str] = Field(default=None, description="MIME type filter")
            max_results: int = Field(default=10, description="Maximum results")
        
        def search_drive(query: str, mime_type: Optional[str] = None, max_results: int = 10) -> str:
            """Search files in Google Drive"""
            try:
                service = build('drive', 'v3', credentials=creds)
                
                search_query = f"name contains '{query}'"
                if mime_type:
                    search_query += f" and mimeType='{mime_type}'"
                
                results = service.files().list(
                    q=search_query,
                    pageSize=max_results,
                    fields="files(id, name, mimeType, modifiedTime)"
                ).execute()
                
                files = results.get('files', [])
                if not files:
                    return "No files found."
                
                output = []
                for file in files:
                    output.append(
                        f"- {file['name']}\n"
                        f"  ID: {file['id']}\n"
                        f"  Type: {file['mimeType']}\n"
                        f"  Modified: {file['modifiedTime']}"
                    )
                
                return "\n\n".join(output)
                
            except Exception as e:
                return f"Error searching Drive: {str(e)}"
        
        return StructuredTool(
            name="drive_search",
            description="Search files in Google Drive",
            func=search_drive,
            args_schema=DriveSearchInput
        )
    
    def _create_drive_read_tool(self, user_id: str, creds: Credentials) -> BaseTool:
        """Create Google Drive read tool"""
        
        class DriveReadInput(BaseModel):
            file_id: str = Field(description="Google Drive file ID")
        
        def read_drive_file(file_id: str) -> str:
            """Read content from a Google Drive file"""
            try:
                service = build('drive', 'v3', credentials=creds)
                
                # Get file metadata
                file = service.files().get(fileId=file_id).execute()
                
                # Download file content
                request = service.files().get_media(fileId=file_id)
                content = request.execute()
                
                # Try to decode as text
                try:
                    text_content = content.decode('utf-8')
                    return f"File: {file['name']}\n\nContent:\n{text_content}"
                except:
                    return f"File: {file['name']}\n\nBinary file - cannot display content as text"
                
            except Exception as e:
                return f"Error reading file: {str(e)}"
        
        return StructuredTool(
            name="drive_read_file",
            description="Read content from a Google Drive file",
            func=read_drive_file,
            args_schema=DriveReadInput
        )
    
    def _create_drive_create_tool(self, user_id: str, creds: Credentials) -> BaseTool:
        """Create Google Drive file creation tool"""
        
        class DriveCreateInput(BaseModel):
            name: str = Field(description="File name")
            content: str = Field(description="File content")
            mime_type: str = Field(default="text/plain", description="MIME type")
            folder_id: Optional[str] = Field(default=None, description="Parent folder ID")
        
        def create_drive_file(
            name: str,
            content: str,
            mime_type: str = "text/plain",
            folder_id: Optional[str] = None
        ) -> str:
            """Create a new file in Google Drive"""
            try:
                service = build('drive', 'v3', credentials=creds)
                
                file_metadata = {'name': name}
                if folder_id:
                    file_metadata['parents'] = [folder_id]
                
                # Create file
                from googleapiclient.http import MediaInMemoryUpload
                media = MediaInMemoryUpload(
                    content.encode('utf-8'),
                    mimetype=mime_type
                )
                
                file = service.files().create(
                    body=file_metadata,
                    media_body=media,
                    fields='id,name'
                ).execute()
                
                return f"File created: {file['name']} (ID: {file['id']})"
                
            except Exception as e:
                return f"Error creating file: {str(e)}"
        
        return StructuredTool(
            name="drive_create_file",
            description="Create a new file in Google Drive",
            func=create_drive_file,
            args_schema=DriveCreateInput
        )
    
    def _create_calendar_list_tool(self, user_id: str, creds: Credentials) -> BaseTool:
        """Create Google Calendar list events tool"""
        
        class CalendarListInput(BaseModel):
            max_results: int = Field(default=10, description="Maximum events to return")
            calendar_id: str = Field(default="primary", description="Calendar ID")
        
        def list_calendar_events(max_results: int = 10, calendar_id: str = "primary") -> str:
            """List upcoming calendar events"""
            try:
                service = build('calendar', 'v3', credentials=creds)
                
                from datetime import datetime
                now = datetime.utcnow().isoformat() + 'Z'
                
                events_result = service.events().list(
                    calendarId=calendar_id,
                    timeMin=now,
                    maxResults=max_results,
                    singleEvents=True,
                    orderBy='startTime'
                ).execute()
                
                events = events_result.get('items', [])
                
                if not events:
                    return "No upcoming events found."
                
                output = []
                for event in events:
                    start = event['start'].get('dateTime', event['start'].get('date'))
                    output.append(
                        f"- {event.get('summary', 'No Title')}\n"
                        f"  Start: {start}\n"
                        f"  Location: {event.get('location', 'No location')}"
                    )
                
                return "\n\n".join(output)
                
            except Exception as e:
                return f"Error listing events: {str(e)}"
        
        return StructuredTool(
            name="calendar_list_events",
            description="List upcoming calendar events",
            func=list_calendar_events,
            args_schema=CalendarListInput
        )
    
    def _create_calendar_create_tool(self, user_id: str, creds: Credentials) -> BaseTool:
        """Create Google Calendar event creation tool"""
        
        class CalendarCreateInput(BaseModel):
            summary: str = Field(description="Event title")
            start_time: str = Field(description="Start time (ISO format)")
            end_time: str = Field(description="End time (ISO format)")
            description: Optional[str] = Field(default=None, description="Event description")
            location: Optional[str] = Field(default=None, description="Event location")
        
        def create_calendar_event(
            summary: str,
            start_time: str,
            end_time: str,
            description: Optional[str] = None,
            location: Optional[str] = None
        ) -> str:
            """Create a new calendar event"""
            try:
                service = build('calendar', 'v3', credentials=creds)
                
                event = {
                    'summary': summary,
                    'start': {'dateTime': start_time, 'timeZone': 'UTC'},
                    'end': {'dateTime': end_time, 'timeZone': 'UTC'},
                }
                
                if description:
                    event['description'] = description
                if location:
                    event['location'] = location
                
                event = service.events().insert(
                    calendarId='primary',
                    body=event
                ).execute()
                
                return f"Event created: {event.get('htmlLink')}"
                
            except Exception as e:
                return f"Error creating event: {str(e)}"
        
        return StructuredTool(
            name="calendar_create_event",
            description="Create a new calendar event",
            func=create_calendar_event,
            args_schema=CalendarCreateInput
        )