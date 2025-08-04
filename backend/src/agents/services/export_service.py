import asyncio
import base64
import json
import time
import zipfile
from datetime import datetime
from io import BytesIO
from typing import Any, Dict, List, Optional, Tuple

import requests
import structlog
from agents.auth.auth0_config import get_auth0_config
from agents.storage.redis_storage import RedisStorage

logger = structlog.get_logger(__name__)


class ExportService:
    """Service for handling user data export functionality"""

    def __init__(self, redis_storage: RedisStorage):
        self.redis_storage = redis_storage

    async def get_user_info_from_token(self, token: str) -> Optional[Dict[str, Any]]:
        """Get user information including email from Auth0 using access token"""
        try:
            config = get_auth0_config()
            userinfo_url = f"https://{config.domain}/userinfo"
            headers = {"Authorization": f"Bearer {token}"}

            response = requests.get(userinfo_url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                return response.json()
            else:
                logger.error("Failed to get user info from Auth0", status_code=response.status_code)
                return None
                
        except Exception as e:
            logger.error("Error getting user info from Auth0", error=str(e))
            return None

    async def gather_user_conversations(self, user_id: str) -> List[Dict[str, Any]]:
        """Gather all conversations for a user"""
        try:
            # Get user's conversation list from Redis
            user_chats_key = f"user_chats:{user_id}"
            conversation_ids = await self.redis_storage.redis_client.zrevrange(user_chats_key, 0, -1)
            
            conversations = []
            
            for conv_id in conversation_ids:
                if isinstance(conv_id, bytes):
                    conv_id = conv_id.decode('utf-8')
                
                # Get conversation metadata
                meta_key = f"chat_metadata:{user_id}:{conv_id}"
                metadata_raw = await self.redis_storage.redis_client.get(meta_key, user_id)
                
                if metadata_raw:
                    try:
                        metadata = json.loads(metadata_raw)
                        
                        # Get all messages for this conversation
                        messages = await self.redis_storage.get_messages(user_id, conv_id)
                        
                        conversation_export = {
                            "conversation_id": conv_id,
                            "metadata": metadata,
                            "messages": messages,
                            "message_count": len(messages)
                        }
                        
                        conversations.append(conversation_export)
                        
                    except json.JSONDecodeError as e:
                        logger.error("Failed to parse conversation metadata", conv_id=conv_id, error=str(e))
                        continue
                        
            logger.info(f"Gathered {len(conversations)} conversations for user {user_id}")
            return conversations
            
        except Exception as e:
            logger.error("Error gathering user conversations", user_id=user_id, error=str(e))
            raise

    async def gather_user_files(self, user_id: str) -> List[Dict[str, Any]]:
        """Gather all files and artifacts for a user"""
        try:
            files = await self.redis_storage.list_user_files(user_id)
            
            files_export = []
            
            for file_metadata in files:
                file_id = file_metadata.get("file_id")
                if not file_id:
                    continue
                
                # Get file data
                file_data_result = await self.redis_storage.get_file(user_id, file_id)
                
                if file_data_result:
                    file_data, _ = file_data_result
                    
                    # Encode binary data as base64 for JSON serialization
                    file_export = {
                        "file_id": file_id,
                        "metadata": file_metadata,
                        "data": base64.b64encode(file_data).decode('utf-8') if file_data else None,
                        "data_type": "base64"
                    }
                    
                    files_export.append(file_export)
                    
            logger.info(f"Gathered {len(files_export)} files for user {user_id}")
            return files_export
            
        except Exception as e:
            logger.error("Error gathering user files", user_id=user_id, error=str(e))
            raise

    def create_export_zip(self, user_id: str, conversations: List[Dict[str, Any]], 
                         files: List[Dict[str, Any]], user_info: Optional[Dict[str, Any]] = None) -> bytes:
        """Create a ZIP archive containing all user data"""
        try:
            zip_buffer = BytesIO()
            
            with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
                
                # Add export metadata
                export_metadata = {
                    "export_date": datetime.utcnow().isoformat(),
                    "user_id": user_id,
                    "user_info": user_info,
                    "total_conversations": len(conversations),
                    "total_files": len(files),
                    "export_version": "1.0"
                }
                
                zip_file.writestr("export_metadata.json", json.dumps(export_metadata, indent=2))
                
                # Add conversations
                if conversations:
                    conversations_folder = "conversations/"
                    
                    # Create a summary file
                    conversations_summary = []
                    for conv in conversations:
                        summary = {
                            "conversation_id": conv["conversation_id"],
                            "name": conv["metadata"].get("name", "Untitled"),
                            "created_at": conv["metadata"].get("created_at"),
                            "updated_at": conv["metadata"].get("updated_at"),
                            "message_count": conv["message_count"]
                        }
                        conversations_summary.append(summary)
                    
                    zip_file.writestr(
                        f"{conversations_folder}conversations_summary.json",
                        json.dumps(conversations_summary, indent=2)
                    )
                    
                    # Add individual conversation files
                    for conv in conversations:
                        conv_id = conv["conversation_id"]
                        conv_name = conv["metadata"].get("name", "Untitled").replace("/", "_")
                        created_date = datetime.fromtimestamp(conv["metadata"].get("created_at", time.time())).strftime("%Y-%m-%d")
                        
                        # Create readable filename
                        filename = f"{conversations_folder}{created_date}_{conv_name}_{conv_id}.json"
                        
                        # Format conversation for export
                        conversation_export = {
                            "conversation_info": conv["metadata"],
                            "messages": conv["messages"]
                        }
                        
                        zip_file.writestr(filename, json.dumps(conversation_export, indent=2))
                
                # Add files and artifacts
                if files:
                    files_folder = "files/"
                    
                    # Create files summary
                    files_summary = []
                    for file_data in files:
                        metadata = file_data["metadata"]
                        summary = {
                            "file_id": file_data["file_id"],
                            "filename": metadata.get("filename", "unknown"),
                            "format": metadata.get("format", "unknown"),
                            "size_bytes": metadata.get("file_size", 0),
                            "created_at": metadata.get("upload_timestamp"),
                            "source": metadata.get("source", "unknown"),
                            "indexed": metadata.get("indexed", False)
                        }
                        files_summary.append(summary)
                    
                    zip_file.writestr(
                        f"{files_folder}files_summary.json",
                        json.dumps(files_summary, indent=2)
                    )
                    
                    # Add individual files
                    for file_data in files:
                        file_id = file_data["file_id"]
                        metadata = file_data["metadata"]
                        filename = metadata.get("filename", f"file_{file_id}")
                        
                        # Create safe filename
                        safe_filename = filename.replace("/", "_").replace("\\", "_")
                        
                        # Decode base64 data back to bytes
                        if file_data.get("data") and file_data.get("data_type") == "base64":
                            try:
                                file_bytes = base64.b64decode(file_data["data"])
                                zip_file.writestr(f"{files_folder}{safe_filename}", file_bytes)
                                
                                # Also add metadata as separate JSON file
                                metadata_filename = f"{files_folder}{safe_filename}.metadata.json"
                                zip_file.writestr(metadata_filename, json.dumps(metadata, indent=2))
                                
                            except Exception as e:
                                logger.error(f"Error adding file {file_id} to zip", error=str(e))
                                continue
                
                # Add README with instructions
                readme_content = self._create_readme_content(export_metadata)
                zip_file.writestr("README.txt", readme_content)
            
            zip_data = zip_buffer.getvalue()
            zip_buffer.close()
            
            logger.info(f"Created export zip for user {user_id}, size: {len(zip_data)} bytes")
            return zip_data
            
        except Exception as e:
            logger.error("Error creating export zip", user_id=user_id, error=str(e))
            raise

    def _create_readme_content(self, metadata: Dict[str, Any]) -> str:
        """Create README content for the export"""
        return f"""
Samba Co-Pilot Chat Export
==========================

Export Date: {metadata['export_date']}
User ID: {metadata['user_id']}
Export Version: {metadata['export_version']}

Contents:
---------
- conversations/: Contains all your chat conversations
  - conversations_summary.json: Overview of all conversations
  - Individual conversation files with date, name, and ID

- files/: Contains all uploaded files and generated artifacts
  - files_summary.json: Overview of all files
  - Individual files with their original names
  - .metadata.json files with additional file information

- export_metadata.json: Technical details about this export

Statistics:
-----------
Total Conversations: {metadata['total_conversations']}
Total Files: {metadata['total_files']}

File Format Information:
------------------------
- Conversations are stored as JSON files with message history
- Files are stored in their original format
- All timestamps are in UTC
- File metadata includes information about indexing and processing

This export contains all your personal data from Samba Co-Pilot.
Please keep this archive secure as it contains your private conversations and files.
"""

    async def export_user_data(self, user_id: str, token: str) -> Tuple[bytes, str, Optional[str]]:
        """
        Main export function that gathers all user data and creates a zip file
        
        Returns:
            Tuple of (zip_data, filename, user_email)
        """
        try:
            logger.info(f"Starting export for user {user_id}")
            
            # Get user info including email
            user_info = await self.get_user_info_from_token(token)
            user_email = user_info.get("email") if user_info else None
            
            # Gather all user data concurrently
            conversations_task = self.gather_user_conversations(user_id)
            files_task = self.gather_user_files(user_id)
            
            conversations, files = await asyncio.gather(conversations_task, files_task)
            
            # Create zip file
            zip_data = self.create_export_zip(user_id, conversations, files, user_info)
            
            # Create filename with timestamp
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            filename = f"samba_copilot_export_{timestamp}.zip"
            
            logger.info(f"Export completed for user {user_id}, file size: {len(zip_data)} bytes")
            
            return zip_data, filename, user_email
            
        except Exception as e:
            logger.error("Error during user data export", user_id=user_id, error=str(e))
            raise