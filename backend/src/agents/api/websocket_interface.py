from typing import Protocol
from fastapi import WebSocket

class WebSocketInterface(Protocol):
    """Interface for WebSocket operations"""
    async def send_message(self, user_id: str, conversation_id: str, data: dict) -> bool:
        """Send a message through the WebSocket for a specific conversation."""
        ... 