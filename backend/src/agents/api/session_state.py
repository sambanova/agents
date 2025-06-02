from collections import deque
from typing import Optional
import json
from autogen_core.models import UserMessage, AssistantMessage
import redis

from agents.api.data_types import EndUserMessage


class SessionStateManager:
    def __init__(self, history_length: int = 10):
        self.session_states = {}
        self.session_histories = {}
        self.history_length = history_length
        
    def init_conversation(self, redis_client: redis.Redis, user_id: str, conversation_id: str) -> None:
        """
        Initialize a conversation by loading its history from Redis.
        Should be called when a new conversation websocket connection is established.
        """
        # Load existing messages from Redis
        messages_key = f"messages:{user_id}:{conversation_id}"
        messages_data = redis_client.lrange(messages_key, 0, -1, user_id)
        
        # Initialize history deque
        history = deque(maxlen=self.history_length)
        
        # Process messages if they exist
        if messages_data:
            # Convert messages to objects with timestamps for sorting
            messages = []
            for message_json in messages_data:
                message_data = json.loads(message_json)
                timestamp = message_data.get("timestamp", "")
                if message_data["event"] == "user_message":
                    message = (timestamp, UserMessage(content=message_data["data"], source="User"))
                    messages.append(message)
                elif message_data["event"] == "completion":
                    message = (timestamp, AssistantMessage(content=message_data["data"], source=message_data.get("source", "Assistant")))
                    messages.append(message)
            
            # Sort by timestamp and add to history
            messages.sort(key=lambda x: x[0])  # Sort by timestamp
            for _, message in messages:
                history.append(message)
        
        # Store in memory
        self.session_histories[conversation_id] = history

    def set_active_agent(self, conversation_id: str, agent_type: str) -> None:
        self.session_states[conversation_id] = agent_type

    def get_active_agent(self, conversation_id: str) -> Optional[str]:
        return self.session_states.get(conversation_id)

    def clear_session(self, conversation_id: str) -> None:
        if conversation_id in self.session_states:
            del self.session_states[conversation_id]
        if conversation_id in self.session_histories:
            del self.session_histories[conversation_id]

    def add_to_history(self, conversation_id: str, message: UserMessage | AssistantMessage) -> None:
        if conversation_id not in self.session_histories:
            self.session_histories[conversation_id] = deque(maxlen=self.history_length)
        self.session_histories[conversation_id].append(message)

    def get_history(self, conversation_id: str) -> deque:
        return self.session_histories.get(conversation_id, deque())
