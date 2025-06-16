import asyncio
import json
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import redis
import structlog
from agents.api.data_types import AgentStructuredResponse, EndUserMessage
from agents.api.session_state import SessionStateManager
from agents.api.websocket_interface import WebSocketInterface
from autogen_core import DefaultTopicId, MessageContext, RoutedAgent, message_handler
from autogen_core.models import AssistantMessage

logger = structlog.get_logger(__name__)


# User Proxy Agent
class UserProxyAgent(RoutedAgent):
    """
    Acts as a proxy between the user and the routing agent.
    """

    def __init__(
        self,
        session_manager: SessionStateManager,
        websocket_manager: WebSocketInterface,
        redis_client: redis.Redis,
    ) -> None:
        super().__init__("UserProxyAgent")
        logger.info(
            logger.format_message(
                None,
                f"Initializing UserProxyAgent with ID: {self.id} and WebSocket connection",
            )
        )
        self.session_manager = session_manager
        self.websocket_manager = websocket_manager
        self.redis_client = redis_client
        self.message_timings = {}  # Store message processing times

    def _calculate_token_savings(self, data: dict) -> float:
        """
        Calculate token savings based on metadata information.

        Args:
            data (dict): The parsed message data containing metadata with token information

        Returns:
            dict: Token savings calculations or None if required metadata is missing
        """
        if not (
            "metadata" in data
            and "prompt_tokens" in data["metadata"]
            and "completion_tokens" in data["metadata"]
        ):
            return None

        metadata = data["metadata"]
        input_token_saving = (2.5 - 0.6) * metadata["prompt_tokens"] / 1e6
        output_token_saving = (10 - 1.2) * metadata["completion_tokens"] / 1e6
        total_saving_per_run = input_token_saving + output_token_saving
        X = (
            1e6 / (365 * total_saving_per_run)
            if total_saving_per_run > 0
            else float("inf")
        )

        return X

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
                logger.error(
                    f"No start time found for message {ctx.topic_id.source}. Processing time calculation skipped."
                )
                processing_time = None
            else:
                processing_time = time.time() - start_time

            message_data = message.model_dump()
            # Initialize metadata if None or add duration to existing metadata
            if message_data.get("metadata") is None:
                message_data["metadata"] = {}
            message_data["metadata"]["duration"] = processing_time

            # Calculate token savings
            token_savings = self._calculate_token_savings(message_data)
            if token_savings:
                message_data["metadata"]["token_savings"] = token_savings
            if "cached_prompt_tokens" in message_data["metadata"]:
                del message_data["metadata"]["cached_prompt_tokens"]

            # Prepare message data
            message_data = {
                "event": "completion",
                "data": json.dumps(message_data),
                "user_id": user_id,
                "conversation_id": conversation_id,
                "message_id": message.message_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

            # Create tasks for Redis operation and WebSocket send
            message_key = f"messages:{user_id}:{conversation_id}"
            tasks = [
                asyncio.create_task(
                    asyncio.to_thread(
                        self.redis_client.rpush,
                        message_key,
                        json.dumps(message_data),
                        user_id,
                    )
                ),
                asyncio.create_task(
                    self.websocket_manager.send_message(
                        user_id, conversation_id, message_data
                    )
                ),
            ]

            # Wait for all tasks to complete
            await asyncio.gather(*tasks)

            log_message = "Stored message in Redis and sent via WebSocket"
            if processing_time is not None:
                log_message += f". Processing time: {processing_time:.2f} seconds"

            logger.info(logger.format_message(ctx.topic_id.source, log_message))

            # Update conversation history
            self.session_manager.add_to_history(
                conversation_id,
                AssistantMessage(
                    content=message.data.model_dump_json(),
                    source=ctx.sender.type if ctx.sender else "assistant",
                ),
            )

            # Clear timing data after completion
            if ctx.topic_id.source in self.message_timings:
                del self.message_timings[ctx.topic_id.source]

        except Exception as e:
            logger.error(
                logger.format_message(
                    ctx.topic_id.source, f"Failed to send message: {str(e)}"
                ),
                exc_info=True,
            )

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

        logger.info(
            logger.format_message(
                ctx.topic_id.source,
                f"Forwarding user message to router: '{message.content[:100]}...'",
            )
        )

        # Forward the message to the router
        await self.publish_message(
            message,
            DefaultTopicId(type="router", source=ctx.topic_id.source),
        )
