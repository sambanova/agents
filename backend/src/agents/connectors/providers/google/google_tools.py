"""
Google connector LangChain tools implementation.

Provides actual executable tools for Gmail, Google Drive, and Google Calendar.
"""

import base64
import json
from typing import Any, Dict, List, Optional, Type

import structlog
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from langchain.callbacks.manager import CallbackManagerForToolRun
from langchain.tools import BaseTool
from pydantic import BaseModel, Field

logger = structlog.get_logger(__name__)


class GmailSearchInput(BaseModel):
    """Input for Gmail search."""
    query: str = Field(description="Search query for Gmail (e.g., 'from:sender@example.com', 'subject:meeting', 'has:attachment')")
    max_results: int = Field(default=10, description="Maximum number of results to return")


class GmailSearchTool(BaseTool):
    """Tool for searching Gmail messages."""
    
    name: str = "gmail_search"
    description: str = "Search Gmail messages using query parameters. Use queries like 'from:email', 'subject:text', 'after:2024/1/1', 'has:attachment'"
    args_schema: Type[BaseModel] = GmailSearchInput
    
    access_token: str
    refresh_token: Optional[str] = None
    client_id: Optional[str] = None
    client_secret: Optional[str] = None
    token_uri: Optional[str] = None
    user_id: str
    
    def _run(
        self,
        query: str,
        max_results: int = 10,
        run_manager: Optional[CallbackManagerForToolRun] = None,
    ) -> str:
        """Execute Gmail search."""
        try:
            # Build Gmail service with OAuth token
            from google.auth.transport.requests import Request
            from google.oauth2.credentials import Credentials
            
            # Create credentials with all required fields for auto-refresh
            creds = Credentials(
                token=self.access_token,
                refresh_token=self.refresh_token,
                token_uri=self.token_uri or "https://oauth2.googleapis.com/token",
                client_id=self.client_id,
                client_secret=self.client_secret
            )
            
            # Refresh if needed
            if creds.expired and creds.refresh_token:
                creds.refresh(Request())
                # Update our stored token for next time
                self.access_token = creds.token
            
            service = build('gmail', 'v1', credentials=creds)
            
            # Search for messages
            results = service.users().messages().list(
                userId='me',
                q=query,
                maxResults=max_results
            ).execute()
            
            messages = results.get('messages', [])
            
            if not messages:
                return f"No messages found for query: {query}"
            
            # Get details for each message
            detailed_messages = []
            for msg in messages[:max_results]:
                try:
                    message = service.users().messages().get(
                        userId='me',
                        id=msg['id'],
                        format='metadata',
                        metadataHeaders=['From', 'To', 'Subject', 'Date']
                    ).execute()
                    
                    headers = {h['name']: h['value'] for h in message['payload'].get('headers', [])}
                    
                    detailed_messages.append({
                        'id': message['id'],
                        'threadId': message['threadId'],
                        'from': headers.get('From', 'Unknown'),
                        'to': headers.get('To', 'Unknown'),
                        'subject': headers.get('Subject', 'No Subject'),
                        'date': headers.get('Date', 'Unknown'),
                        'snippet': message.get('snippet', '')[:200]
                    })
                except Exception as e:
                    logger.error(f"Error fetching message {msg['id']}: {e}")
                    continue
            
            # Format results
            result_text = f"Found {len(detailed_messages)} messages:\n\n"
            for i, msg in enumerate(detailed_messages, 1):
                result_text += f"{i}. Subject: {msg['subject']}\n"
                result_text += f"   From: {msg['from']}\n"
                result_text += f"   Date: {msg['date']}\n"
                result_text += f"   Preview: {msg['snippet']}\n\n"
            
            return result_text
            
        except HttpError as e:
            error_msg = f"Gmail API error: {e}"
            logger.error(error_msg)
            return error_msg
        except Exception as e:
            error_msg = f"Error searching Gmail: {str(e)}"
            logger.error(error_msg)
            return error_msg


class GmailDraftInput(BaseModel):
    """Input for creating Gmail draft."""
    to: str = Field(description="Recipient email address")
    subject: str = Field(description="Email subject")
    body: str = Field(description="Email body (plain text)")
    cc: Optional[str] = Field(None, description="CC recipients (comma-separated)")
    bcc: Optional[str] = Field(None, description="BCC recipients (comma-separated)")


class GmailDraftTool(BaseTool):
    """Tool for creating Gmail draft messages."""

    name: str = "gmail_draft"
    description: str = "Create a draft email in Gmail (does not send)"
    args_schema: Type[BaseModel] = GmailDraftInput

    access_token: str
    refresh_token: Optional[str] = None
    client_id: Optional[str] = None
    client_secret: Optional[str] = None
    token_uri: Optional[str] = None
    user_id: str

    def _run(
        self,
        to: str,
        subject: str,
        body: str,
        cc: Optional[str] = None,
        bcc: Optional[str] = None,
        run_manager: Optional[CallbackManagerForToolRun] = None,
    ) -> str:
        """Create Gmail draft."""
        try:
            from email.mime.text import MIMEText
            from google.auth.transport.requests import Request
            from google.oauth2.credentials import Credentials

            # Create credentials with all required fields for auto-refresh
            creds = Credentials(
                token=self.access_token,
                refresh_token=self.refresh_token,
                token_uri=self.token_uri or "https://oauth2.googleapis.com/token",
                client_id=self.client_id,
                client_secret=self.client_secret
            )

            # Refresh if needed
            if creds.expired and creds.refresh_token:
                creds.refresh(Request())
                self.access_token = creds.token

            service = build('gmail', 'v1', credentials=creds)

            # Create message
            message = MIMEText(body)
            message['to'] = to
            message['subject'] = subject

            if cc:
                message['cc'] = cc
            if bcc:
                message['bcc'] = bcc

            # Encode the message
            raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode('utf-8')

            # Create draft
            draft = service.users().drafts().create(
                userId='me',
                body={
                    'message': {
                        'raw': raw_message
                    }
                }
            ).execute()

            draft_id = draft.get('id', 'Unknown')
            message_id = draft.get('message', {}).get('id', 'Unknown')

            return f"Draft created successfully!\nDraft ID: {draft_id}\nMessage ID: {message_id}\nTo: {to}\nSubject: {subject}"

        except HttpError as e:
            error_msg = f"Gmail API error: {e}"
            logger.error(error_msg)
            return error_msg
        except Exception as e:
            error_msg = f"Error creating Gmail draft: {str(e)}"
            logger.error(error_msg)
            return error_msg


class GmailSendInput(BaseModel):
    """Input for sending Gmail."""
    to: str = Field(description="Recipient email address")
    subject: str = Field(description="Email subject")
    body: str = Field(description="Email body (plain text)")
    cc: Optional[str] = Field(None, description="CC recipients (comma-separated)")
    bcc: Optional[str] = Field(None, description="BCC recipients (comma-separated)")


class GmailSendTool(BaseTool):
    """Tool for sending Gmail messages."""
    
    name: str = "gmail_send"
    description: str = "Send an email via Gmail"
    args_schema: Type[BaseModel] = GmailSendInput
    
    access_token: str
    refresh_token: Optional[str] = None
    client_id: Optional[str] = None
    client_secret: Optional[str] = None
    token_uri: Optional[str] = None
    user_id: str
    
    def _run(
        self,
        to: str,
        subject: str,
        body: str,
        cc: Optional[str] = None,
        bcc: Optional[str] = None,
        run_manager: Optional[CallbackManagerForToolRun] = None,
    ) -> str:
        """Send Gmail message."""
        try:
            from google.auth.transport.requests import Request
            from google.oauth2.credentials import Credentials
            from email.mime.text import MIMEText
            
            # Create credentials with all required fields for auto-refresh
            creds = Credentials(
                token=self.access_token,
                refresh_token=self.refresh_token,
                token_uri=self.token_uri or "https://oauth2.googleapis.com/token",
                client_id=self.client_id,
                client_secret=self.client_secret
            )
            
            # Refresh if needed
            if creds.expired and creds.refresh_token:
                creds.refresh(Request())
                self.access_token = creds.token
            
            # Create message
            message = MIMEText(body)
            message['to'] = to
            message['subject'] = subject
            if cc:
                message['cc'] = cc
            if bcc:
                message['bcc'] = bcc
            
            # Encode message
            raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode('utf-8')
            
            # Build Gmail service
            service = build('gmail', 'v1', credentials=creds)
            
            # Send message
            result = service.users().messages().send(
                userId='me',
                body={'raw': raw_message}
            ).execute()
            
            return f"Email sent successfully! Message ID: {result['id']}"
            
        except Exception as e:
            error_msg = f"Error sending email: {str(e)}"
            logger.error(error_msg)
            return error_msg


class GoogleDriveSearchInput(BaseModel):
    """Input for Google Drive search."""
    query: str = Field(description="Search query for Google Drive files")
    max_results: int = Field(default=10, description="Maximum number of results")


class GoogleDriveSearchTool(BaseTool):
    """Tool for searching Google Drive."""
    
    name: str = "google_drive_search"
    description: str = "Search for files in Google Drive"
    args_schema: Type[BaseModel] = GoogleDriveSearchInput
    
    access_token: str
    refresh_token: Optional[str] = None
    client_id: Optional[str] = None
    client_secret: Optional[str] = None
    token_uri: Optional[str] = None
    user_id: str
    
    def _run(
        self,
        query: str,
        max_results: int = 10,
        run_manager: Optional[CallbackManagerForToolRun] = None,
    ) -> str:
        """Search Google Drive."""
        try:
            from google.auth.transport.requests import Request
            from google.oauth2.credentials import Credentials
            
            # Log credential details for debugging
            logger.info(
                f"GoogleDriveSearchTool credentials - "
                f"has_access_token: {bool(self.access_token)}, "
                f"has_refresh_token: {bool(self.refresh_token)}, "
                f"has_client_id: {bool(self.client_id)}, "
                f"has_client_secret: {bool(self.client_secret)}, "
                f"token_uri: {self.token_uri or 'default'}"
            )
            
            # Validate we have all required fields for refresh
            if not all([self.refresh_token, self.client_id, self.client_secret]):
                error_msg = (
                    f"Missing OAuth credentials for auto-refresh. "
                    f"refresh_token: {'present' if self.refresh_token else 'MISSING'}, "
                    f"client_id: {'present' if self.client_id else 'MISSING'}, "
                    f"client_secret: {'present' if self.client_secret else 'MISSING'}"
                )
                logger.error(error_msg)
                return f"Error: {error_msg}. Please reconnect your Google account."
            
            # Create credentials with all required fields for auto-refresh
            creds = Credentials(
                token=self.access_token,
                refresh_token=self.refresh_token,
                token_uri=self.token_uri or "https://oauth2.googleapis.com/token",
                client_id=self.client_id,
                client_secret=self.client_secret
            )
            
            # Refresh if needed (the library should handle this automatically on 401)
            if creds.expired and creds.refresh_token:
                logger.info("Token appears expired, will refresh on first API call")
                creds.refresh(Request())
                self.access_token = creds.token
                logger.info("Token refreshed successfully")
            
            service = build('drive', 'v3', credentials=creds)
            
            # Build search query
            drive_query = f"name contains '{query}' and trashed = false"
            
            # Search for files
            results = service.files().list(
                q=drive_query,
                pageSize=max_results,
                fields="files(id, name, mimeType, modifiedTime, size, webViewLink)"
            ).execute()
            
            files = results.get('files', [])
            
            if not files:
                return f"No files found matching: {query}"
            
            # Format results
            result_text = f"Found {len(files)} files:\n\n"
            for i, file in enumerate(files, 1):
                result_text += f"{i}. {file['name']}\n"
                result_text += f"   Type: {file.get('mimeType', 'Unknown')}\n"
                result_text += f"   Modified: {file.get('modifiedTime', 'Unknown')}\n"
                if 'size' in file:
                    size_mb = int(file['size']) / (1024 * 1024)
                    result_text += f"   Size: {size_mb:.2f} MB\n"
                if 'webViewLink' in file:
                    result_text += f"   Link: {file['webViewLink']}\n"
                result_text += "\n"
            
            return result_text
            
        except Exception as e:
            error_msg = f"Error searching Google Drive: {str(e)}"
            logger.error(error_msg)
            return error_msg


class GoogleDriveReadInput(BaseModel):
    """Input for Google Drive file reading."""
    file_id: str = Field(description="The Google Drive file ID to read")


class GoogleDriveReadTool(BaseTool):
    """Tool for reading file contents from Google Drive."""
    
    name: str = "google_drive_read"
    description: str = "Read the contents of a file from Google Drive. Supports text files, Google Docs, Sheets, and Slides."
    args_schema: Type[BaseModel] = GoogleDriveReadInput
    
    access_token: str
    refresh_token: Optional[str] = None
    client_id: Optional[str] = None
    client_secret: Optional[str] = None
    token_uri: Optional[str] = None
    user_id: str
    
    def _run(
        self,
        file_id: str,
        run_manager: Optional[CallbackManagerForToolRun] = None,
    ) -> str:
        """Read Google Drive file contents."""
        try:
            from google.auth.transport.requests import Request
            from google.oauth2.credentials import Credentials
            import io
            
            # Log credential details for debugging
            logger.info(
                f"GoogleDriveReadTool credentials - "
                f"has_access_token: {bool(self.access_token)}, "
                f"has_refresh_token: {bool(self.refresh_token)}, "
                f"file_id: {file_id}"
            )
            
            # Validate we have all required fields for refresh
            if not all([self.refresh_token, self.client_id, self.client_secret]):
                error_msg = (
                    f"Missing OAuth credentials for auto-refresh. "
                    f"refresh_token: {'present' if self.refresh_token else 'MISSING'}, "
                    f"client_id: {'present' if self.client_id else 'MISSING'}, "
                    f"client_secret: {'present' if self.client_secret else 'MISSING'}"
                )
                logger.error(error_msg)
                return f"Error: {error_msg}. Please reconnect your Google account."
            
            # Create credentials with all required fields for auto-refresh
            creds = Credentials(
                token=self.access_token,
                refresh_token=self.refresh_token,
                token_uri=self.token_uri or "https://oauth2.googleapis.com/token",
                client_id=self.client_id,
                client_secret=self.client_secret
            )
            
            # Refresh if needed
            if creds.expired and creds.refresh_token:
                logger.info("Token appears expired, refreshing")
                creds.refresh(Request())
                self.access_token = creds.token
                logger.info("Token refreshed successfully")
            
            service = build('drive', 'v3', credentials=creds)
            
            # First, get file metadata to determine the type
            file_metadata = service.files().get(
                fileId=file_id,
                fields='id, name, mimeType, size, modifiedTime'
            ).execute()
            
            file_name = file_metadata.get('name', 'Unknown')
            mime_type = file_metadata.get('mimeType', '')
            
            logger.info(f"Reading file: {file_name} (type: {mime_type})")
            
            # Determine export format based on Google Workspace file types
            if mime_type == 'application/vnd.google-apps.document':
                # Google Docs - export as plain text
                export_mime_type = 'text/plain'
                content = service.files().export(
                    fileId=file_id,
                    mimeType=export_mime_type
                ).execute()
                return f"Content of Google Doc '{file_name}':\n\n{content.decode('utf-8')}"
                
            elif mime_type == 'application/vnd.google-apps.spreadsheet':
                # Google Sheets - export as CSV
                export_mime_type = 'text/csv'
                content = service.files().export(
                    fileId=file_id,
                    mimeType=export_mime_type
                ).execute()
                return f"Content of Google Sheet '{file_name}' (CSV format):\n\n{content.decode('utf-8')}"
                
            elif mime_type == 'application/vnd.google-apps.presentation':
                # Google Slides - export as plain text
                export_mime_type = 'text/plain'
                content = service.files().export(
                    fileId=file_id,
                    mimeType=export_mime_type
                ).execute()
                return f"Content of Google Slides '{file_name}':\n\n{content.decode('utf-8')}"
                
            elif mime_type.startswith('text/') or mime_type in ['application/json', 'application/xml']:
                # Regular text files - download directly
                content = service.files().get_media(fileId=file_id).execute()
                return f"Content of file '{file_name}':\n\n{content.decode('utf-8')}"
                
            else:
                # For binary files or unsupported types
                file_size = file_metadata.get('size', 'Unknown')
                return (
                    f"File '{file_name}' is a binary file (type: {mime_type}, size: {file_size} bytes). "
                    f"Cannot display content as text. "
                    f"Use the file ID '{file_id}' to download it if needed."
                )
                
        except HttpError as e:
            error_msg = f"Google Drive API error: {e}"
            logger.error(error_msg)
            return error_msg
        except UnicodeDecodeError:
            return f"File '{file_name}' contains binary data that cannot be displayed as text."
        except Exception as e:
            error_msg = f"Error reading file from Google Drive: {str(e)}"
            logger.error(error_msg)
            return error_msg


class GoogleDriveUploadInput(BaseModel):
    """Input for Google Drive upload."""
    file_name: str = Field(description="Name for the file in Google Drive")
    content: str = Field(description="File content to upload")
    mime_type: str = Field(default="text/plain", description="MIME type of the file")
    folder_id: Optional[str] = Field(None, description="Parent folder ID (optional)")


class GoogleDriveUploadTool(BaseTool):
    """Tool for uploading files to Google Drive."""
    
    name: str = "google_drive_upload"
    description: str = "Upload a file to Google Drive"
    args_schema: Type[BaseModel] = GoogleDriveUploadInput
    
    access_token: str
    refresh_token: Optional[str] = None
    client_id: Optional[str] = None
    client_secret: Optional[str] = None
    token_uri: Optional[str] = None
    user_id: str
    
    def _run(
        self,
        file_name: str,
        content: str,
        mime_type: str = "text/plain",
        folder_id: Optional[str] = None,
        run_manager: Optional[CallbackManagerForToolRun] = None,
    ) -> str:
        """Upload file to Google Drive."""
        try:
            from google.auth.transport.requests import Request
            from google.oauth2.credentials import Credentials
            from googleapiclient.http import MediaInMemoryUpload
            
            # Create credentials with all required fields for auto-refresh
            creds = Credentials(
                token=self.access_token,
                refresh_token=self.refresh_token,
                token_uri=self.token_uri or "https://oauth2.googleapis.com/token",
                client_id=self.client_id,
                client_secret=self.client_secret
            )
            
            # Refresh if needed
            if creds.expired and creds.refresh_token:
                creds.refresh(Request())
                self.access_token = creds.token
            
            service = build('drive', 'v3', credentials=creds)
            
            # Create file metadata
            file_metadata = {'name': file_name}
            if folder_id:
                file_metadata['parents'] = [folder_id]
            
            # Upload file
            media = MediaInMemoryUpload(content.encode('utf-8'), mimetype=mime_type)
            file = service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id, name, webViewLink'
            ).execute()
            
            return f"File '{file_name}' uploaded successfully!\nFile ID: {file['id']}\nLink: {file.get('webViewLink', 'N/A')}"
            
        except Exception as e:
            error_msg = f"Error uploading to Google Drive: {str(e)}"
            logger.error(error_msg)
            return error_msg


class GoogleCalendarListInput(BaseModel):
    """Input for listing calendar events."""
    max_results: int = Field(default=10, description="Maximum number of events to return")
    time_min: Optional[str] = Field(None, description="Start time in ISO format (e.g., 2024-01-01T00:00:00Z)")
    time_max: Optional[str] = Field(None, description="End time in ISO format")


class GoogleCalendarListTool(BaseTool):
    """Tool for listing Google Calendar events."""
    
    name: str = "google_calendar_list"
    description: str = "List upcoming events from Google Calendar"
    args_schema: Type[BaseModel] = GoogleCalendarListInput
    
    access_token: str
    refresh_token: Optional[str] = None
    client_id: Optional[str] = None
    client_secret: Optional[str] = None
    token_uri: Optional[str] = None
    user_id: str
    
    def _run(
        self,
        max_results: int = 10,
        time_min: Optional[str] = None,
        time_max: Optional[str] = None,
        run_manager: Optional[CallbackManagerForToolRun] = None,
    ) -> str:
        """List calendar events."""
        try:
            from google.auth.transport.requests import Request
            from google.oauth2.credentials import Credentials
            from datetime import datetime, timezone
            
            # Create credentials with all required fields for auto-refresh
            creds = Credentials(
                token=self.access_token,
                refresh_token=self.refresh_token,
                token_uri=self.token_uri or "https://oauth2.googleapis.com/token",
                client_id=self.client_id,
                client_secret=self.client_secret
            )
            
            # Refresh if needed
            if creds.expired and creds.refresh_token:
                creds.refresh(Request())
                self.access_token = creds.token
            
            service = build('calendar', 'v3', credentials=creds)
            
            # Default to current time if not specified
            if not time_min:
                time_min = datetime.now(timezone.utc).isoformat()
            
            # List events
            events_result = service.events().list(
                calendarId='primary',
                timeMin=time_min,
                timeMax=time_max,
                maxResults=max_results,
                singleEvents=True,
                orderBy='startTime'
            ).execute()
            
            events = events_result.get('items', [])
            
            if not events:
                return "No upcoming events found."
            
            # Format results
            result_text = f"Found {len(events)} events:\n\n"
            for i, event in enumerate(events, 1):
                start = event['start'].get('dateTime', event['start'].get('date'))
                result_text += f"{i}. {event.get('summary', 'No Title')}\n"
                result_text += f"   When: {start}\n"
                if 'location' in event:
                    result_text += f"   Where: {event['location']}\n"
                if 'description' in event:
                    desc_preview = event['description'][:100] + '...' if len(event['description']) > 100 else event['description']
                    result_text += f"   Description: {desc_preview}\n"
                result_text += "\n"
            
            return result_text
            
        except Exception as e:
            error_msg = f"Error listing calendar events: {str(e)}"
            logger.error(error_msg)
            return error_msg


class GoogleCalendarCreateInput(BaseModel):
    """Input for creating calendar event."""
    summary: str = Field(description="Event title")
    start_time: str = Field(description="Start time in ISO format (e.g., 2024-01-01T10:00:00-07:00)")
    end_time: str = Field(description="End time in ISO format")
    description: Optional[str] = Field(None, description="Event description")
    location: Optional[str] = Field(None, description="Event location")
    attendees: Optional[List[str]] = Field(None, description="List of attendee email addresses")


class GoogleCalendarCreateTool(BaseTool):
    """Tool for creating Google Calendar events."""
    
    name: str = "google_calendar_create"
    description: str = "Create a new event in Google Calendar"
    args_schema: Type[BaseModel] = GoogleCalendarCreateInput
    
    access_token: str
    refresh_token: Optional[str] = None
    client_id: Optional[str] = None
    client_secret: Optional[str] = None
    token_uri: Optional[str] = None
    user_id: str
    
    def _run(
        self,
        summary: str,
        start_time: str,
        end_time: str,
        description: Optional[str] = None,
        location: Optional[str] = None,
        attendees: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForToolRun] = None,
    ) -> str:
        """Create calendar event."""
        try:
            from google.auth.transport.requests import Request
            from google.oauth2.credentials import Credentials
            
            # Create credentials with all required fields for auto-refresh
            creds = Credentials(
                token=self.access_token,
                refresh_token=self.refresh_token,
                token_uri=self.token_uri or "https://oauth2.googleapis.com/token",
                client_id=self.client_id,
                client_secret=self.client_secret
            )
            
            # Refresh if needed
            if creds.expired and creds.refresh_token:
                creds.refresh(Request())
                self.access_token = creds.token
            
            service = build('calendar', 'v3', credentials=creds)
            
            # Build event
            event = {
                'summary': summary,
                'start': {'dateTime': start_time, 'timeZone': 'America/Los_Angeles'},
                'end': {'dateTime': end_time, 'timeZone': 'America/Los_Angeles'},
            }
            
            if description:
                event['description'] = description
            if location:
                event['location'] = location
            if attendees:
                event['attendees'] = [{'email': email} for email in attendees]
            
            # Create event
            created_event = service.events().insert(
                calendarId='primary',
                body=event
            ).execute()
            
            return f"Event created successfully!\nEvent ID: {created_event['id']}\nLink: {created_event.get('htmlLink', 'N/A')}"
            
        except Exception as e:
            error_msg = f"Error creating calendar event: {str(e)}"
            logger.error(error_msg)
            return error_msg


def create_google_langchain_tools(
    access_token: str, 
    user_id: str, 
    tool_ids: List[str],
    refresh_token: Optional[str] = None,
    client_id: Optional[str] = None,
    client_secret: Optional[str] = None,
    token_uri: Optional[str] = None
) -> List[BaseTool]:
    """
    Create LangChain tools for Google services.
    
    Args:
        access_token: OAuth access token for Google APIs
        user_id: User ID for tracking
        tool_ids: List of tool IDs to create
        refresh_token: OAuth refresh token for automatic token refresh
        client_id: OAuth client ID
        client_secret: OAuth client secret
        token_uri: OAuth token endpoint URI
        
    Returns:
        List of LangChain tools
    """
    tools = []
    
    tool_mapping = {
        'gmail_search': GmailSearchTool,
        'gmail_send': GmailSendTool,
        'gmail_draft': GmailDraftTool,
        'google_drive_search': GoogleDriveSearchTool,
        'google_drive_read': GoogleDriveReadTool,
        'google_drive_upload': GoogleDriveUploadTool,
        'google_calendar_list': GoogleCalendarListTool,
        'google_calendar_create': GoogleCalendarCreateTool,
    }
    
    for tool_id in tool_ids:
        if tool_id in tool_mapping:
            tool_class = tool_mapping[tool_id]
            
            # Log what we're passing to the tool
            logger.info(
                f"Creating {tool_id} with credentials - "
                f"has_refresh_token: {bool(refresh_token)}, "
                f"has_client_id: {bool(client_id)}, "
                f"has_client_secret: {bool(client_secret)}, "
                f"token_uri: {token_uri}"
            )
            
            tool = tool_class(
                access_token=access_token,
                refresh_token=refresh_token,
                client_id=client_id,
                client_secret=client_secret,
                token_uri=token_uri,
                user_id=user_id
            )
            tools.append(tool)
            logger.info(f"Created Google tool: {tool_id} for user: {user_id}")
        else:
            logger.warning(f"Unknown Google tool ID: {tool_id}")
    
    return tools