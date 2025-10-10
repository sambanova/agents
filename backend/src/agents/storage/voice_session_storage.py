"""
Voice session storage for managing voice chat sessions and state.
"""
import json
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional

import structlog
from agents.storage.redis_service import SecureRedisService

logger = structlog.get_logger(__name__)


class VoiceSessionStorage:
    """Storage manager for voice chat sessions."""

    def __init__(self, redis_client: SecureRedisService):
        """
        Initialize voice session storage.

        Args:
            redis_client: SecureRedisService instance
        """
        self.redis_client = redis_client
        self.session_timeout = timedelta(minutes=30)

    async def create_session(
        self,
        user_id: str,
        conversation_id: str,
        chat_group_id: Optional[str] = None,
    ) -> str:
        """
        Create a new voice session.

        Args:
            user_id: User ID
            conversation_id: Conversation ID
            chat_group_id: Optional Hume chat group ID for resuming

        Returns:
            Session ID
        """
        try:
            session_id = f"{user_id}:{conversation_id}:voice"

            session_data = {
                "session_id": session_id,
                "user_id": user_id,
                "conversation_id": conversation_id,
                "chat_group_id": chat_group_id,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "last_active": datetime.now(timezone.utc).isoformat(),
                "status": "active",
                "notification_count": 0,
                "last_notification_time": None,
            }

            session_key = f"voice_session:{session_id}"
            await self.redis_client.set(
                session_key,
                json.dumps(session_data),
                user_id,
            )

            # Set expiration
            await self.redis_client.expire(
                session_key,
                int(self.session_timeout.total_seconds()),
            )

            logger.info(
                "Created voice session",
                user_id=user_id[:8],
                conversation_id=conversation_id,
            )

            return session_id

        except Exception as e:
            logger.error(f"Error creating voice session: {str(e)}")
            raise

    async def get_session(self, session_id: str, user_id: str) -> Optional[Dict]:
        """
        Get voice session data.

        Args:
            session_id: Session ID
            user_id: User ID

        Returns:
            Session data dict, or None if not found
        """
        try:
            session_key = f"voice_session:{session_id}"
            session_data = await self.redis_client.get(session_key, user_id)

            if session_data:
                return json.loads(session_data)

            return None

        except Exception as e:
            logger.error(f"Error retrieving voice session: {str(e)}")
            return None

    async def update_session(
        self,
        session_id: str,
        user_id: str,
        updates: Dict,
    ) -> bool:
        """
        Update voice session data.

        Args:
            session_id: Session ID
            user_id: User ID
            updates: Dict of fields to update

        Returns:
            True if updated successfully
        """
        try:
            session_data = await self.get_session(session_id, user_id)

            if not session_data:
                logger.warning(
                    f"Cannot update non-existent session: {session_id}"
                )
                return False

            # Update fields
            session_data.update(updates)
            session_data["last_active"] = datetime.now(timezone.utc).isoformat()

            # Save back to Redis
            session_key = f"voice_session:{session_id}"
            await self.redis_client.set(
                session_key,
                json.dumps(session_data),
                user_id,
            )

            # Refresh expiration
            await self.redis_client.expire(
                session_key,
                int(self.session_timeout.total_seconds()),
            )

            return True

        except Exception as e:
            logger.error(f"Error updating voice session: {str(e)}")
            return False

    async def end_session(self, session_id: str, user_id: str) -> bool:
        """
        End a voice session.

        Args:
            session_id: Session ID
            user_id: User ID

        Returns:
            True if ended successfully
        """
        try:
            # Update status to ended
            await self.update_session(
                session_id,
                user_id,
                {"status": "ended", "ended_at": datetime.now(timezone.utc).isoformat()},
            )

            logger.info(
                "Ended voice session",
                user_id=user_id[:8],
                session_id=session_id,
            )

            return True

        except Exception as e:
            logger.error(f"Error ending voice session: {str(e)}")
            return False

    async def record_notification(
        self,
        session_id: str,
        user_id: str,
        notification_text: str,
    ) -> bool:
        """
        Record that a voice notification was sent.

        Args:
            session_id: Session ID
            user_id: User ID
            notification_text: The notification that was sent

        Returns:
            True if recorded successfully
        """
        try:
            import time

            session_data = await self.get_session(session_id, user_id)

            if not session_data:
                return False

            # Update notification tracking
            updates = {
                "notification_count": session_data.get("notification_count", 0) + 1,
                "last_notification_time": time.time(),
                "last_notification_text": notification_text,
            }

            return await self.update_session(session_id, user_id, updates)

        except Exception as e:
            logger.error(f"Error recording notification: {str(e)}")
            return False

    async def get_active_sessions(self, user_id: str) -> list:
        """
        Get all active voice sessions for a user.

        Args:
            user_id: User ID

        Returns:
            List of active session dicts
        """
        try:
            # Search for all voice sessions for this user
            pattern = f"voice_session:{user_id}:*:voice"
            keys = await self.redis_client.scan_keys(pattern)

            sessions = []
            for key in keys:
                session_data = await self.redis_client.get(key, user_id)
                if session_data:
                    data = json.loads(session_data)
                    if data.get("status") == "active":
                        sessions.append(data)

            return sessions

        except Exception as e:
            logger.error(f"Error retrieving active sessions: {str(e)}")
            return []
