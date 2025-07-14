import base64
import json
import time
from typing import Any, Dict, List, Optional, Tuple

import structlog
from agents.storage.redis_service import SecureRedisService

logger = structlog.get_logger(__name__)


class RedisStorage:
    """Service for handling all message storage operations"""

    def __init__(self, redis_client: SecureRedisService):
        self.redis_client = redis_client

    def _get_message_key(self, user_id: str, conversation_id: str) -> str:
        """Get the Redis key for storing messages"""
        return f"messages:{user_id}:{conversation_id}"

    def _get_dedup_key(self, user_id: str, conversation_id: str) -> str:
        """Get the Redis key for message deduplication"""
        return f"message_ids:{user_id}:{conversation_id}"

    def _get_chat_metadata_key(self, user_id: str, conversation_id: str) -> str:
        """Get the Redis key for chat metadata"""
        return f"chat_metadata:{user_id}:{conversation_id}"

    def _get_file_metadata_key(self, user_id: str, file_id: str) -> str:
        """Get the Redis key for file metadata"""
        return f"file_metadata:{user_id}:{file_id}"

    def _get_user_files_key(self, user_id: str) -> str:
        """Get the Redis key for user files"""
        return f"user_files:{user_id}"

    def _get_file_data_key(self, user_id: str, file_id: str) -> str:
        """Get the Redis key for file data"""
        return f"file_data:{user_id}:{file_id}"

    def _get_api_key_key(self, user_id: str) -> str:
        """Get the Redis key for user API keys"""
        return f"api_keys:{user_id}"

    def _get_cumulative_usage_key(self, user_id: str, conversation_id: str) -> str:
        """Get the Redis key for cumulative usage data"""
        return f"cumulative_usage:{user_id}:{conversation_id}"

    async def is_message_new(
        self, user_id: str, conversation_id: str, message_id: str
    ) -> bool:
        """Check if a message is new"""

        dedup_key = self._get_dedup_key(user_id, conversation_id)
        is_new = await self.redis_client.hsetnx(dedup_key, message_id, "1", user_id)

        if not is_new:
            return False

        return True

    async def save_message_if_new(
        self, user_id: str, conversation_id: str, message_data: Dict[str, Any]
    ) -> bool:
        """
        Save a message if it doesn't already exist (based on message ID).
        Returns True if message was saved, False if it was a duplicate.
        """
        message_key = self._get_message_key(user_id, conversation_id)

        # Check for duplicates if message has an ID
        if "id" in message_data:
            dedup_key = self._get_dedup_key(user_id, conversation_id)

            # Atomic check-and-set: returns True if newly set, False if already existed
            is_new = await self.redis_client.hsetnx(
                dedup_key, message_data["id"], "1", user_id
            )

            if not is_new:
                return False

        # Save the message
        await self.redis_client.rpush(
            message_key,
            json.dumps(message_data),
            user_id,
        )
        return True

    async def save_message(
        self, user_id: str, conversation_id: str, message_data: Dict[str, Any]
    ) -> None:
        """
        Save a message.
        """
        message_key = self._get_message_key(user_id, conversation_id)

        # Save the message
        await self.redis_client.rpush(
            message_key,
            json.dumps(message_data),
            user_id,
        )

    async def get_messages(
        self, user_id: str, conversation_id: str, start: int = 0, end: int = -1
    ) -> List[Dict[str, Any]]:
        """
        Get messages for a conversation.
        start and end work like Redis LRANGE (0-based, -1 means last element)
        """
        message_key = self._get_message_key(user_id, conversation_id)

        messages_raw = await self.redis_client.lrange(message_key, start, end, user_id)

        if not messages_raw:
            return []

        # Parse JSON messages
        messages = []
        for msg_json in messages_raw:
            try:
                messages.append(json.loads(msg_json))
            except json.JSONDecodeError as e:
                logger.error("Failed to parse message JSON", error=str(e))
                continue

        return messages

    async def get_last_message(
        self, user_id: str, conversation_id: str
    ) -> Optional[Dict[str, Any]]:
        """Get the last message in a conversation"""
        messages = await self.get_messages(user_id, conversation_id, -1, -1)
        return messages[0] if messages else None

    async def message_exists(
        self, user_id: str, conversation_id: str, message_id: str
    ) -> bool:
        """Check if a message ID already exists"""
        dedup_key = self._get_dedup_key(user_id, conversation_id)
        return await self.redis_client.hget(dedup_key, message_id, user_id) is not None

    async def delete_conversation_messages(
        self, user_id: str, conversation_id: str
    ) -> bool:
        """Delete all messages for a conversation"""
        message_key = self._get_message_key(user_id, conversation_id)
        dedup_key = self._get_dedup_key(user_id, conversation_id)

        # Delete both the message list and deduplication hash
        deleted_messages = await self.redis_client.delete(message_key)
        deleted_dedup = await self.redis_client.delete(dedup_key)

        return deleted_messages > 0 or deleted_dedup > 0

    async def get_message_count(self, user_id: str, conversation_id: str) -> int:
        """Get the total number of messages in a conversation"""
        message_key = self._get_message_key(user_id, conversation_id)
        return await self.redis_client.llen(message_key)

    async def verify_conversation_exists(
        self, user_id: str, conversation_id: str
    ) -> bool:
        """
        Verify if a conversation's metadata exists for the given user.
        """
        meta_key = self._get_chat_metadata_key(user_id, conversation_id)
        return bool(await self.redis_client.exists(meta_key))

    async def delete_all_user_data(self, user_id: str, conversation_id: str) -> int:
        """
        Delete the metadata for a given conversation.
        """
        meta_key = self._get_chat_metadata_key(user_id, conversation_id)
        message_key = f"messages:{user_id}:{conversation_id}"
        user_chats_key = f"user_chats:{user_id}"

        # Execute all deletions
        await self.redis_client.delete(meta_key)
        await self.redis_client.delete(message_key)
        return await self.redis_client.zrem(user_chats_key, conversation_id)

    async def put_file(
        self,
        user_id: str,
        file_id: str,
        *,
        data: bytes,
        filename: str,
        format: str,
        upload_timestamp: float,
        indexed: bool,
        source: str,
        vector_ids: Optional[List[str]] = None,
    ):
        """Put a file in Redis storage."""
        try:
            # Ensure data is bytes
            if isinstance(data, str):
                data = data.encode("utf-8")

            # Store file data with user-namespaced key
            file_data_key = f"file_data:{user_id}:{file_id}"
            await self.redis_client.set(file_data_key, data, user_id)

            await self.store_file_metadata(
                user_id,
                file_id,
                filename=filename,
                format=format,
                upload_timestamp=upload_timestamp,
                file_size=len(data),
                indexed=indexed,
                source=source,
                vector_ids=vector_ids,
            )

            await self.add_file_to_user_list(user_id, file_id)

            logger.info(
                "File stored in Redis",
                file_id=file_id,
                size_bytes=len(data),
                user_id=user_id,
            )

        except Exception as e:
            logger.error(
                "Error storing file in Redis",
                file_id=file_id,
                error=str(e),
                exc_info=True,
            )
            raise

    async def get_file(
        self, user_id: str, file_id: str
    ) -> Optional[Tuple[bytes, dict]]:
        """Get a file from Redis storage."""
        try:

            if not await self.verify_file_belongs_to_user(user_id, file_id):
                return None, None

            file_metadata = await self.get_file_metadata(user_id, file_id)

            if not file_metadata:
                return None, None

            # Get file data
            file_data_key = self._get_file_data_key(user_id, file_id)
            file_data = await self.redis_client.get(file_data_key, user_id)

            if isinstance(file_data, str):
                file_data = file_data.encode("utf-8")

            return file_data, file_metadata

        except Exception as e:
            logger.error(
                "Error retrieving file from Redis",
                file_id=file_id,
                error=str(e),
                exc_info=True,
            )
            return None, None

    async def get_file_metadata(self, user_id: str, file_id: str) -> Optional[dict]:
        """Get file metadata from Redis storage."""
        try:

            if not await self.verify_file_belongs_to_user(user_id, file_id):
                return None

            file_metadata_key = self._get_file_metadata_key(user_id, file_id)
            metadata_str = await self.redis_client.get(file_metadata_key, user_id)

            if not metadata_str:
                return None

            return json.loads(metadata_str)

        except Exception as e:
            logger.error(
                "Error retrieving file metadata from Redis",
                file_id=file_id,
                error=str(e),
                exc_info=True,
            )
            return None

    async def get_file_as_base64(self, user_id: str, file_id: str) -> Optional[str]:
        """Get a file as base64 string."""
        data, _ = await self.get_file(user_id, file_id)
        if data:
            return base64.b64encode(data).decode("utf-8")
        return None

    async def get_file_data_url(self, user_id: str, file_id: str) -> Optional[str]:
        """Get file as data URL for direct embedding."""
        try:
            # Get metadata to determine MIME type
            metadata = await self.get_file_metadata(user_id, file_id)
            if not metadata:
                return None

            # Get file data
            data = await self.get_file(user_id, file_id)
            if not data:
                return None

            base64_data = base64.b64encode(data).decode("utf-8")

            # Determine MIME type
            format_lower = metadata["format"].lower()
            mime_types = {
                "png": "image/png",
                "jpg": "image/jpeg",
                "jpeg": "image/jpeg",
                "gif": "image/gif",
                "svg": "image/svg+xml",
            }
            mime_type = mime_types.get(format_lower, "application/octet-stream")

            return f"data:{mime_type};base64,{base64_data}"

        except Exception as e:
            logger.error(
                "Error creating data URL", file_id=file_id, error=str(e), exc_info=True
            )
            return None

    async def delete_file(self, user_id: str, file_id: str) -> bool:
        """Delete a file from Redis storage."""
        try:

            if not await self.verify_file_belongs_to_user(user_id, file_id):
                return False

            # Delete file data and metadata
            file_data_key = self._get_file_data_key(user_id, file_id)
            file_metadata_key = self._get_file_metadata_key(user_id, file_id)
            user_files_key = self._get_user_files_key(user_id)

            # Remove from all locations
            await self.redis_client.delete(file_data_key)
            await self.redis_client.delete(file_metadata_key)
            await self.redis_client.srem(user_files_key, file_id)

            logger.info("File deleted from Redis", file_id=file_id, user_id=user_id)
            return True

        except Exception as e:
            logger.error(
                "Error deleting file from Redis",
                file_id=file_id,
                error=str(e),
                exc_info=True,
            )
            return False

    async def list_user_files(self, user_id: str) -> list:
        """List all files for a user."""
        try:

            user_files_key = self._get_user_files_key(user_id)
            file_ids = await self.redis_client.smembers(user_files_key)

            if not file_ids:
                return []

            # Get metadata for each file
            files = []
            for file_id in file_ids:
                if isinstance(file_id, bytes):
                    file_id = file_id.decode("utf-8")
                metadata = await self.get_file_metadata(user_id, file_id)
                if metadata:
                    metadata["file_id"] = file_id
                    files.append(metadata)

            return files

        except Exception as e:
            logger.error(
                "Error listing files for user",
                user_id=user_id,
                error=str(e),
                exc_info=True,
            )
            return []

    # Document storage methods
    async def store_file_metadata(
        self,
        user_id: str,
        file_id: str,
        *,
        filename: str,
        format: str,
        upload_timestamp: float,
        file_size: int,
        indexed: bool,
        source: str,
        vector_ids: Optional[List[str]] = None,
    ) -> None:
        """Store document metadata in Redis."""
        metadata = {
            "user_id": user_id,
            "filename": filename,
            "format": format,
            "created_at": upload_timestamp or time.time(),
            "file_size": file_size,
            "indexed": indexed,
            "source": source,
        }
        if vector_ids:
            metadata["vector_ids"] = vector_ids
        file_metadata_key = self._get_file_metadata_key(user_id, file_id)
        await self.redis_client.set(file_metadata_key, json.dumps(metadata), user_id)

    async def add_file_to_user_list(self, user_id: str, file_id: str) -> None:
        """Add file to user's file list."""
        user_files_key = self._get_user_files_key(user_id)
        await self.redis_client.sadd(user_files_key, file_id)

    async def verify_file_belongs_to_user(self, user_id: str, file_id: str) -> bool:
        """Verify if a document belongs to a user."""
        user_files_key = self._get_user_files_key(user_id)
        return await self.redis_client.sismember(user_files_key, file_id)

    async def get_user_api_key(self, user_id: str) -> "APIKeys":
        """Get a user's API key."""
        from agents.api.data_types import APIKeys

        user_api_key_key = self._get_api_key_key(user_id)
        api_keys = await self.redis_client.hgetall(user_api_key_key, user_id)
        return APIKeys(
            sambanova_key=api_keys.get("sambanova_key", ""),
            serper_key=api_keys.get("serper_key", ""),
            exa_key=api_keys.get("exa_key", ""),
            fireworks_key=api_keys.get("fireworks_key", ""),
        )

    async def set_user_api_key(self, user_id: str, keys: "APIKeys") -> None:
        """Set a user's API key."""

        # Store keys in Redis with user-specific prefix
        key_prefix = self._get_api_key_key(user_id)
        await self.redis_client.hset(
            key_prefix,
            mapping={
                "sambanova_key": keys.sambanova_key,
                "serper_key": keys.serper_key,
                "exa_key": keys.exa_key,
                "fireworks_key": keys.fireworks_key,
            },
            user_id=user_id,
        )

    async def update_metadata(
        self, message_data: str, user_id: str, conversation_id: str
    ):
        """Helper method to update metadata asynchronously"""
        try:
            meta_key = self._get_chat_metadata_key(user_id, conversation_id)
            meta_data = await self.redis_client.get(meta_key, user_id)
            if meta_data:
                metadata = json.loads(meta_data)
                if "name" not in metadata:
                    metadata["name"] = message_data
                    await self.redis_client.set(meta_key, json.dumps(metadata), user_id)
        except Exception as e:
            logger.error("Error updating metadata", error=str(e), exc_info=True)

    async def delete_vectors(self, vector_ids: List[str]) -> None:
        """Delete vectors from the vector store."""
        if not vector_ids:
            return
        try:
            await self.redis_client.delete(*vector_ids)
            logger.info("Successfully deleted vectors", num_deleted=len(vector_ids))
        except Exception as e:
            logger.error(
                "Error deleting vectors",
                error=str(e),
                exc_info=True,
            )

    async def update_and_get_cumulative_usage(
        self,
        user_id: str,
        conversation_id: str,
        current_usage: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Updates and retrieves the cumulative usage for a session.
        """
        cumulative_usage_key = self._get_cumulative_usage_key(user_id, conversation_id)
        # Fetch existing cumulative usage
        existing_cumulative_usage_str = await self.redis_client.get(
            cumulative_usage_key, user_id
        )

        if existing_cumulative_usage_str:
            try:
                cumulative_usage = json.loads(existing_cumulative_usage_str)
            except json.JSONDecodeError:
                cumulative_usage = {}
        else:
            cumulative_usage = {}

        if current_usage:
            for key, value in current_usage.items():
                if isinstance(value, (int, float)):
                    cumulative_usage[key] = cumulative_usage.get(key, 0) + value

            # Store the updated cumulative usage back to Redis
            await self.redis_client.set(
                cumulative_usage_key, json.dumps(cumulative_usage), user_id
            )

        return cumulative_usage
