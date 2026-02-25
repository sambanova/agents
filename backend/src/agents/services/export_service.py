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

    def _clean_messages(self, messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Clean and filter messages to remove redundant stream events and sensitive data"""
        cleaned_messages = []
        
        for message in messages:
            # Skip redundant stream events
            if message.get("event") in ["stream_start", "stream_complete"]:
                continue
            
            # Create cleaned message
            cleaned_message = message.copy()
            
            # Remove sensitive IDs but keep message_id for tracking
            cleaned_message.pop("user_id", None)
            cleaned_message.pop("conversation_id", None)
            
            # Keep essential fields for meaningful export
            cleaned_messages.append(cleaned_message)
        
        return cleaned_messages

    def _clean_conversation_metadata(self, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Clean conversation metadata to remove sensitive data"""
        cleaned_metadata = metadata.copy()
        
        # Remove sensitive IDs
        cleaned_metadata.pop("conversation_id", None)
        cleaned_metadata.pop("user_id", None)
        
        return cleaned_metadata

    def _clean_file_metadata(self, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Clean file metadata to remove sensitive data"""
        cleaned_metadata = metadata.copy()
        
        # Remove sensitive IDs
        cleaned_metadata.pop("file_id", None)
        cleaned_metadata.pop("user_id", None)
        
        return cleaned_metadata

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

    async def gather_user_conversations(self, user_id: str, files: List[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
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
                        raw_messages = await self.redis_storage.get_messages(user_id, conv_id)
                        
                        # Find associated files for this conversation (like in delete_chat endpoint)
                        conversation_file_ids = set()
                        for message in raw_messages:
                            files = message.get("additional_kwargs", {}).get("files", [])
                            conversation_file_ids.update(files)
                        
                        # Debug logging for file associations
                        if conversation_file_ids:
                            logger.info(f"Conversation {conv_id} has {len(conversation_file_ids)} associated files: {list(conversation_file_ids)}")
                        else:
                            logger.info(f"Conversation {conv_id} has no associated files in message additional_kwargs")
                            
                            # Alternative association: Try to match files by timing and content clues
                            conv_created = metadata.get("created_at", 0)
                            conv_updated = metadata.get("updated_at", 0)
                            conv_name = metadata.get("name", "").lower()
                            
                            # Look for files created during this conversation's timeframe
                            timing_matched_files = []
                            for file_data in files if files else []:
                                file_metadata = file_data.get("metadata", {})
                                file_created = file_metadata.get("created_at", 0)
                                file_source = file_metadata.get("source", "")
                                
                                # Check if file was created within conversation timeframe (with some buffer)
                                time_buffer = 3600  # 1 hour buffer
                                if (conv_created - time_buffer) <= file_created <= (conv_updated + time_buffer):
                                    # Additional heuristics based on conversation content and file source
                                    if (("research" in conv_name or "report" in conv_name) and file_source == "deep_research_pdf") or \
                                       (("data" in conv_name or "analysis" in conv_name) and file_source in ["data_science_agent", "upload"]) or \
                                       (("dashboard" in conv_name or "visualization" in conv_name) and file_source in ["generated", "data_science_agent"]):
                                        timing_matched_files.append(file_data.get("_temp_file_id"))
                            
                            if timing_matched_files:
                                conversation_file_ids.update(timing_matched_files)
                                logger.info(f"Added {len(timing_matched_files)} files to conversation {conv_id} based on timing/content matching: {timing_matched_files}")
                        
                        # Clean and filter messages
                        cleaned_messages = self._clean_messages(raw_messages)
                        cleaned_metadata = self._clean_conversation_metadata(metadata)
                        
                        conversation_export = {
                            "metadata": cleaned_metadata,
                            "messages": cleaned_messages,
                            "message_count": len(cleaned_messages),
                            "associated_file_ids": list(conversation_file_ids),  # Files associated with this conversation
                            "_temp_conversation_id": conv_id,  # Temporary for file naming
                            "_temp_original_metadata": metadata  # Temporary for file naming
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
                    
                    # Clean file metadata and encode binary data as base64 for JSON serialization
                    cleaned_metadata = self._clean_file_metadata(file_metadata)
                    file_export = {
                        "metadata": cleaned_metadata,
                        "data": base64.b64encode(file_data).decode('utf-8') if file_data else None,
                        "data_type": "base64",
                        "_temp_file_id": file_id  # Temporary for conversation association
                    }
                    
                    files_export.append(file_export)
                    
            logger.info(f"Gathered {len(files_export)} files for user {user_id}")
            return files_export
            
        except Exception as e:
            logger.error("Error gathering user files", user_id=user_id, error=str(e))
            raise

    def create_export_zip(self, user_id: str, conversations: List[Dict[str, Any]], 
                         files: List[Dict[str, Any]], user_info: Optional[Dict[str, Any]] = None) -> bytes:
        """Create a ZIP archive containing all user data organized by conversation"""
        try:
            zip_buffer = BytesIO()
            
            # Create a mapping of file_id to file_data for quick lookup
            files_by_id = {}
            if files:
                for file_data in files:
                    file_id = file_data.get("_temp_file_id")
                    if file_id:
                        files_by_id[file_id] = file_data
            
            with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
                
                # Add README
                readme_content = self._create_readme_content(conversations, files)
                zip_file.writestr("README.txt", readme_content)
                
                # Add export metadata (cleaned for privacy)
                cleaned_user_info = None
                if user_info:
                    # Only keep non-sensitive user info
                    cleaned_user_info = {
                        "name": user_info.get("name"),
                        "email": user_info.get("email"),
                        "locale": user_info.get("locale")
                    }
                
                export_metadata = {
                    "export_date": datetime.utcnow().isoformat(),
                    "user_info": cleaned_user_info,
                    "total_conversations": len(conversations),
                    "total_files": len(files),
                    "export_version": "3.0",  # Updated version for conversation-organized export
                    "privacy_notes": "Sensitive IDs have been removed for privacy protection. Files are organized by conversation."
                }
                
                zip_file.writestr("export_metadata.json", json.dumps(export_metadata, indent=2))
                
                # Add conversations summary
                if conversations:
                    conversations_summary = []
                    for i, conv in enumerate(conversations):
                        summary = {
                            "conversation_number": i + 1,  # Sequential number instead of ID
                            "name": conv["metadata"].get("name", "Untitled"),
                            "created_at": conv["metadata"].get("created_at"),
                            "updated_at": conv["metadata"].get("updated_at"),
                            "message_count": conv["message_count"],
                            "associated_files_count": len(conv.get("associated_file_ids", []))
                        }
                        conversations_summary.append(summary)
                    
                    zip_file.writestr(
                        "conversations_summary.json",
                        json.dumps(conversations_summary, indent=2)
                    )
                
                # Create individual conversation folders
                for i, conv in enumerate(conversations):
                    try:
                        # Use temporary data for folder naming
                        conv_id = conv["_temp_conversation_id"]
                        original_metadata = conv["_temp_original_metadata"]
                        conv_name = original_metadata.get("name", "Untitled").replace("/", "_")
                        
                        # Handle potential issues with timestamp
                        created_timestamp = original_metadata.get("created_at")
                        if created_timestamp:
                            try:
                                created_date = datetime.fromtimestamp(created_timestamp).strftime("%Y-%m-%d")
                            except (ValueError, OSError):
                                created_date = datetime.utcnow().strftime("%Y-%m-%d")
                        else:
                            created_date = datetime.utcnow().strftime("%Y-%m-%d")
                        
                        # Truncate very long conversation names
                        if len(conv_name) > 40:
                            conv_name = conv_name[:40] + "..."
                        
                        # Create conversation folder name
                        folder_name = f"conversation_{i+1}_{created_date}_{conv_name}/"
                        
                        # Add conversation JSON
                        conversation_export = {
                            "metadata": conv["metadata"],
                            "messages": conv["messages"],
                            "message_count": conv["message_count"]
                        }
                        
                        zip_file.writestr(f"{folder_name}conversation.json", json.dumps(conversation_export, indent=2))
                        logger.info(f"Added conversation {i+1} to folder: {folder_name}")
                        
                        # Add associated files to this conversation's folder
                        associated_file_ids = conv.get("associated_file_ids", [])
                        if associated_file_ids:
                            files_added = 0
                            for file_id in associated_file_ids:
                                file_data = files_by_id.get(file_id)
                                if file_data:
                                    try:
                                        metadata = file_data["metadata"]
                                        filename = metadata.get("filename", f"file_{file_id}")
                                        
                                        # Create safe filename
                                        safe_filename = filename.replace("/", "_").replace("\\", "_")
                                        
                                        # Decode base64 data back to bytes
                                        if file_data.get("data") and file_data.get("data_type") == "base64":
                                            file_bytes = base64.b64decode(file_data["data"])
                                            zip_file.writestr(f"{folder_name}{safe_filename}", file_bytes)
                                            
                                            # Also add metadata as separate JSON file
                                            metadata_filename = f"{folder_name}{safe_filename}.metadata.json"
                                            zip_file.writestr(metadata_filename, json.dumps(metadata, indent=2))
                                            
                                            files_added += 1
                                            logger.info(f"Added file to conversation {i+1}: {safe_filename}")
                                        else:
                                            logger.warning(f"No valid data found for file {filename} in conversation {i+1}")
                                    except Exception as e:
                                        logger.error(f"Error adding file {file_id} to conversation {i+1}", error=str(e))
                            
                            logger.info(f"Added {files_added} files to conversation {i+1}")
                        
                    except Exception as e:
                        logger.error(f"Error creating folder for conversation {i+1}", 
                                   conv_id=conv.get("_temp_conversation_id", "unknown"),
                                   error=str(e), exc_info=True)
                        
                        # Try to add with a fallback folder
                        try:
                            fallback_folder = f"conversation_{i+1}_error/"
                            fallback_export = {
                                "metadata": conv.get("metadata", {}),
                                "messages": conv.get("messages", []),
                                "export_error": f"Error processing: {str(e)}"
                            }
                            zip_file.writestr(f"{fallback_folder}conversation.json", json.dumps(fallback_export, indent=2))
                            logger.info(f"Added conversation {i+1} with fallback folder: {fallback_folder}")
                        except Exception as fallback_error:
                            logger.error(f"Failed to add conversation {i+1} even with fallback", 
                                       error=str(fallback_error), exc_info=True)
                
                # Organize unassociated files by source instead of orphaned folder
                unassociated_files = []
                if files:
                    all_associated_file_ids = set()
                    for conv in conversations:
                        all_associated_file_ids.update(conv.get("associated_file_ids", []))
                    
                    for file_data in files:
                        file_id = file_data.get("_temp_file_id")
                        if file_id and file_id not in all_associated_file_ids:
                            unassociated_files.append(file_data)
                
                if unassociated_files:
                    logger.info(f"Adding {len(unassociated_files)} unassociated files organized by source")
                    
                    # Group files by source
                    files_by_source = {}
                    for file_data in unassociated_files:
                        source = file_data["metadata"].get("source", "unknown")
                        if source not in files_by_source:
                            files_by_source[source] = []
                        files_by_source[source].append(file_data)
                    
                    # Create folders by source
                    for source, source_files in files_by_source.items():
                        # Create readable folder name based on source
                        source_folder_map = {
                            "upload": "uploaded_files/",
                            "deep_research_pdf": "research_reports/", 
                            "data_analysis": "data_analysis_outputs/",
                            "visualization": "visualizations/",
                            "generated": "generated_files/",
                            "unknown": "other_files/"
                        }
                        
                        folder_name = source_folder_map.get(source, f"{source}_files/")
                        logger.info(f"Creating folder '{folder_name}' for {len(source_files)} files from source '{source}'")
                        
                        for file_data in source_files:
                            try:
                                metadata = file_data["metadata"]
                                filename = metadata.get("filename", f"file_{file_data.get('_temp_file_id', 'unknown')}")
                                
                                # Create safe filename
                                safe_filename = filename.replace("/", "_").replace("\\", "_")
                                
                                # Decode base64 data back to bytes
                                if file_data.get("data") and file_data.get("data_type") == "base64":
                                    file_bytes = base64.b64decode(file_data["data"])
                                    zip_file.writestr(f"{folder_name}{safe_filename}", file_bytes)
                                    
                                    # Also add metadata as separate JSON file
                                    metadata_filename = f"{folder_name}{safe_filename}.metadata.json"
                                    zip_file.writestr(metadata_filename, json.dumps(metadata, indent=2))
                                    
                                    logger.info(f"Added {source} file: {safe_filename}")
                                else:
                                    logger.warning(f"No valid data found for {source} file {filename}")
                            except Exception as e:
                                logger.error(f"Error adding {source} file {filename}", error=str(e))
                

            
            zip_data = zip_buffer.getvalue()
            zip_buffer.close()
            
            logger.info(f"Created export zip for user {user_id}, size: {len(zip_data)} bytes")
            return zip_data
            
        except Exception as e:
            logger.error("Error creating export zip", user_id=user_id, error=str(e))
            raise

    def _create_readme_content(self, conversations: List[Dict[str, Any]], files: List[Dict[str, Any]]) -> str:
        """Create README content for the export"""
        export_date = datetime.utcnow().isoformat()
        
        return f"""
Samba Co-Pilot Chat Export
==========================

Export Date: {export_date}
Export Version: 3.0
Organization: Conversation-Based

Contents:
---------
- conversations_summary.json: Overview of all conversations with statistics

- conversation_X_YYYY-MM-DD_Name/: Individual conversation folders
  - conversation.json: Complete conversation data (messages, metadata)
  - Associated files and artifacts generated in this conversation
  - .metadata.json files with additional file information

- uploaded_files/: User-uploaded files not linked to specific conversations
- research_reports/: Generated research reports and PDFs  
- data_analysis_outputs/: Generated analysis files and results
- other_files/: Files from unknown or miscellaneous sources

- export_metadata.json: Technical details about this export

Statistics:
-----------
Total Conversations: {len(conversations)}
Total Files: {len(files)}

New Organization (v3.0):
------------------------
🎯 CONVERSATION-FOCUSED STRUCTURE:
Each conversation now has its own folder containing:
- The complete conversation history (conversation.json)
- All files, reports, and artifacts generated within that conversation
- This makes it easy to see what files belong to which discussion

📁 FOLDER NAMING:
conversation_1_2025-01-15_Project Planning/
conversation_2_2025-01-16_Data Analysis/
...

🔗 FILE ASSOCIATION:
Files are automatically placed in the conversation folder where they were created or referenced.
This provides clear context for each file and makes the export much more intuitive to navigate.

Privacy & Cleaning:
-------------------
- Sensitive IDs (user_id, conversation_id, file_id) have been removed for privacy
- Stream events (stream_start, stream_complete) filtered out for clarity
- Message IDs preserved for tracking conversation flow
- All timestamps are in UTC
- Content and files remain complete and unmodified

This export contains all your personal data from Samba Co-Pilot.
Please keep this archive secure as it contains your private conversations and files.
"""

    async def export_user_data(self, user_id: str, user_email: Optional[str] = None) -> Tuple[bytes, str]:
        """
        Main export function that gathers all user data and creates a zip file.

        Args:
            user_id: The user ID to export data for.
            user_email: Pre-resolved user email (avoids passing raw JWTs to background tasks).

        Returns:
            Tuple of (zip_data, filename)
        """
        try:
            logger.info(f"Starting export for user {user_id}")

            # Build minimal user_info for the zip metadata
            user_info = {"email": user_email} if user_email else None

            # Gather files first, then conversations with file context for better association
            files = await self.gather_user_files(user_id)
            conversations = await self.gather_user_conversations(user_id, files)

            # Create zip file
            zip_data = self.create_export_zip(user_id, conversations, files, user_info)

            # Create filename with timestamp
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            filename = f"samba_copilot_export_{timestamp}.zip"

            logger.info(f"Export completed for user {user_id}, file size: {len(zip_data)} bytes")

            return zip_data, filename

        except Exception as e:
            logger.error("Error during user data export", user_id=user_id, error=str(e))
            raise