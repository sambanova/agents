import json
import asyncio
from typing import List, Dict, Any, Optional

from agents.storage.redis_service import SecureRedisService
from agents.utils.logging import logger


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
            is_new = await asyncio.to_thread(
                self.redis_client.hsetnx, dedup_key, message_data["id"], "1", user_id
            )

            if not is_new:
                return False

        # Save the message
        await asyncio.to_thread(
            self.redis_client.rpush,
            message_key,
            json.dumps(message_data),
            user_id,
        )
        return True

    async def get_messages(
        self, user_id: str, conversation_id: str, start: int = 0, end: int = -1
    ) -> List[Dict[str, Any]]:
        """
        Get messages for a conversation.
        start and end work like Redis LRANGE (0-based, -1 means last element)
        """
        message_key = self._get_message_key(user_id, conversation_id)

        messages_raw = await asyncio.to_thread(
            self.redis_client.lrange, message_key, start, end, user_id
        )

        if not messages_raw:
            return []

        # Parse JSON messages
        messages = []
        for msg_json in messages_raw:
            try:
                messages.append(json.loads(msg_json))
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse message JSON: {e}")
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
        return (
            await asyncio.to_thread(
                self.redis_client.hget, dedup_key, message_id, user_id
            )
            is not None
        )

    async def delete_conversation_messages(
        self, user_id: str, conversation_id: str
    ) -> bool:
        """Delete all messages for a conversation"""
        message_key = self._get_message_key(user_id, conversation_id)
        dedup_key = self._get_dedup_key(user_id, conversation_id)

        # Delete both the message list and deduplication hash
        deleted_messages = await asyncio.to_thread(
            self.redis_client.delete, message_key
        )
        deleted_dedup = await asyncio.to_thread(self.redis_client.delete, dedup_key)

        return deleted_messages > 0 or deleted_dedup > 0

    async def get_message_count(self, user_id: str, conversation_id: str) -> int:
        """Get the total number of messages in a conversation"""
        message_key = self._get_message_key(user_id, conversation_id)
        return await asyncio.to_thread(self.redis_client.llen, message_key)

    async def verify_conversation_exists(
        self, user_id: str, conversation_id: str
    ) -> bool:
        """
        Verify if a conversation's metadata exists for the given user.
        """
        meta_key = self._get_chat_metadata_key(user_id, conversation_id)
        return bool(await asyncio.to_thread(self.redis_client.exists, meta_key))

    async def delete_all_user_data(self, user_id: str, conversation_id: str) -> int:
        """
        Delete the metadata for a given conversation.
        """
        meta_key = self._get_chat_metadata_key(user_id, conversation_id)
        message_key = f"messages:{user_id}:{conversation_id}"
        user_chats_key = f"user_chats:{user_id}"

        # Execute all deletions in one thread
        return await asyncio.to_thread(
            lambda: (
                self.redis_client.delete(meta_key),
                self.redis_client.delete(message_key),
                self.redis_client.zrem(user_chats_key, conversation_id),
            )
        )
