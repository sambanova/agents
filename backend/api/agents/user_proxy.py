from datetime import datetime
import json
import time
from typing import Dict, List, Any, Optional
import asyncio

from autogen_core import MessageContext
from autogen_core import (
    DefaultTopicId,
    RoutedAgent,
    message_handler,
    type_subscription,
)
from autogen_core.models import AssistantMessage
from fastapi import WebSocket
import redis

from api.session_state import SessionStateManager

from ..data_types import (
    AgentStructuredResponse,
    EndUserMessage,
    AgentRequest,
)
from utils.logging import logger


# User Proxy Agent
class UserProxyAgent(RoutedAgent):
    """
    Acts as a proxy between the user and the routing agent.
    """

    def __init__(self, session_manager: SessionStateManager, websocket: WebSocket, redis_client: redis.Redis) -> None:
        super().__init__("UserProxyAgent")
        logger.info(logger.format_message(None, f"Initializing UserProxyAgent with ID: {self.id} and WebSocket connection"))
        self.session_manager = session_manager
        self.websocket = websocket
        self.redis_client = redis_client
        self.message_timings = {}  # Store message processing times

    @message_handler
    async def handle_agent_response(
        self,
        message: AgentStructuredResponse,
        ctx: MessageContext,
    ) -> None:
        """
        Handle responses from other agents.
        """
        try:
            # Extract conversation info from context
            source_parts = ctx.topic_id.source.split(":")
            if len(source_parts) != 2:
                logger.error(f"Invalid topic source format: {ctx.topic_id.source}")
                return
            user_id, conversation_id = source_parts

            # Calculate processing time
            start_time = self.message_timings.get(ctx.topic_id.source)
            if start_time is None:
                logger.error(f"No start time found for message {ctx.topic_id.source}. Processing time calculation skipped.")
                processing_time = None
            else:
                processing_time = time.time() - start_time

            message_data = message.model_dump()
            # Initialize metadata if None or add duration to existing metadata
            if message_data.get("metadata") is None:
                message_data["metadata"] = {}
            message_data["metadata"]["duration"] = processing_time

            # Prepare message data
            message_data = {
                "event": "completion",
                "data": json.dumps(message_data),
                "user_id": user_id,
                "conversation_id": conversation_id,
                "timestamp": datetime.now().isoformat()
            }

            if self.websocket:
                # Create tasks for Redis operation and WebSocket send
                message_key = f"messages:{user_id}:{conversation_id}"
                tasks = [
                    asyncio.create_task(asyncio.to_thread(
                        self.redis_client.rpush,
                        message_key,
                        json.dumps(message_data)
                    )),
                    asyncio.create_task(self.websocket.send_text(json.dumps(message_data)))
                ]

                # Wait for all tasks to complete
                await asyncio.gather(*tasks)

                log_message = "Stored message in Redis and sent via WebSocket"
                if processing_time is not None:
                    log_message += f". Processing time: {processing_time:.2f} seconds"
                
                logger.info(logger.format_message(
                    ctx.topic_id.source,
                    log_message
                ))

                # Update conversation history
                self.session_manager.add_to_history(
                    conversation_id,
                    AssistantMessage(
                        content=message.data.model_dump_json(), 
                        source=ctx.sender.type
                    ),
                )

                # Clear timing data after completion
                if ctx.topic_id.source in self.message_timings:
                    del self.message_timings[ctx.topic_id.source]

        except Exception as e:
            logger.error(logger.format_message(
                ctx.topic_id.source,
                f"Failed to send message: {str(e)}"
            ), exc_info=True)

    @message_handler
    async def handle_user_message(
        self, message: EndUserMessage, ctx: MessageContext
    ) -> None:
        """
        Forwards the user's message to the router for further processing.

        Args:
            message (EndUserMessage): The user's message.
            ctx (MessageContext): The message context.
        """
        
        # Start timing for this conversation
        self.message_timings[ctx.topic_id.source] = time.time()

        logger.info(logger.format_message(
            ctx.topic_id.source,
            f"Forwarding user message to router: '{message.content[:100]}...'"
        ))

        # Forward the message to the router
        await self.publish_message(
            message,
            DefaultTopicId(type="router", source=ctx.topic_id.source),
        )
