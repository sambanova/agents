import asyncio
import json
import os
import tempfile
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

import pdfplumber  # Unified PDF parsing with inline tables
import redis
import structlog
from agents.api.data_types import APIKeys
from agents.api.utils import to_agent_thinking
from agents.api.websocket_interface import WebSocketInterface
from agents.components.compound.code_execution_subgraph import (
    create_code_execution_graph,
)
from agents.components.compound.data_science_subgraph import (
    create_data_science_subgraph,
)
from agents.components.compound.data_types import LiberalFunctionMessage
from agents.components.compound.financial_analysis_subgraph import (
    create_financial_analysis_graph,
)
from agents.components.datagen.tools.persistent_daytona import PersistentDaytonaManager
from agents.components.open_deep_research.graph import create_deep_research_graph
from agents.storage.redis_service import SecureRedisService
from agents.storage.redis_storage import RedisStorage
from agents.tools.langgraph_tools import RETRIEVAL_DESCRIPTION, load_static_tools
from fastapi import WebSocket, WebSocketDisconnect
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.graph import END
from starlette.websockets import WebSocketState

logger = structlog.get_logger(__name__)


class WebSocketConnectionManager(WebSocketInterface):
    """
    Manages WebSocket connections for user sessions.
    """

    def __init__(
        self, redis_client: SecureRedisService, sync_redis_client: redis.Redis
    ):
        # Use user_id:conversation_id as the key
        self.connections: Dict[str, WebSocket] = {}
        self.voice_connections: Dict[str, WebSocket] = {}  # Track voice WebSockets separately
        self.redis_client = redis_client
        self.sync_redis_client = sync_redis_client
        self.message_storage = RedisStorage(redis_client)
        # Add state storage for active connections
        self.active_sessions: Dict[str, dict] = {}
        self.daytona_managers: Dict[str, PersistentDaytonaManager] = {}
        # Track last activity time for each session
        self.session_last_active: Dict[str, datetime] = {}
        # Session timeout (5 minutes)
        self.SESSION_TIMEOUT = timedelta(minutes=10)
        # Store pubsub instances
        self.pubsub_instances: Dict[str, redis.client.PubSub] = {}
        # Add cleanup task
        self.cleanup_task: Optional[asyncio.Task] = None
        # Voice message deduplication tracker: {conversation_id: {message_hash: timestamp}}
        self.voice_message_tracker: Dict[str, Dict[str, datetime]] = {}
        # Deduplication window (5 seconds)
        self.DEDUP_WINDOW = timedelta(seconds=5)

        # Auto-approval deduplication: {conversation_id: timestamp}
        # Ensures we only auto-approve once per conversation interrupt
        self.auto_approval_tracker: Dict[str, datetime] = {}

    def add_connection(
        self, websocket: WebSocket, user_id: str, conversation_id: str
    ) -> None:
        """
        Adds a new WebSocket connection to the manager.

        Args:
            websocket (WebSocket): The WebSocket connection.
            user_id (str): The ID of the user.
            conversation_id (str): The ID of the conversation.
        """
        key = f"{user_id}:{conversation_id}"
        self.connections[key] = websocket

    def get_connection(self, user_id: str, conversation_id: str) -> Optional[WebSocket]:
        """
        Gets WebSocket connection for a user's conversation.

        Args:
            user_id (str): The ID of the user.
            conversation_id (str): The ID of the conversation.

        Returns:
            Optional[WebSocket]: The WebSocket connection if found, None otherwise.
        """
        key = f"{user_id}:{conversation_id}"
        return self.connections.get(key)

    def remove_connection(self, user_id: str, conversation_id: str) -> None:
        """
        Removes a WebSocket connection from the manager.

        Args:
            user_id (str): The ID of the user.
            conversation_id (str): The ID of the conversation.
        """
        key = f"{user_id}:{conversation_id}"
        if key in self.connections:
            del self.connections[key]

    async def add_voice_connection(
        self, websocket: WebSocket, user_id: str, conversation_id: str
    ) -> None:
        """
        Adds a voice WebSocket connection to the manager.
        Closes any existing voice connection for the same user/conversation first.

        Args:
            websocket (WebSocket): The voice WebSocket connection.
            user_id (str): The ID of the user.
            conversation_id (str): The ID of the conversation.
        """
        key = f"{user_id}:{conversation_id}"

        # Close existing voice connection if any (prevents duplicate voice sockets)
        existing = self.voice_connections.get(key)
        if existing:
            logger.warning(f"Closing existing voice connection for {key} before adding new one")
            try:
                if existing.client_state != WebSocketState.DISCONNECTED:
                    await existing.close()
            except Exception as e:
                logger.error(f"Error closing existing voice connection: {str(e)}")

        self.voice_connections[key] = websocket
        logger.info(f"Added voice connection for {key}")

    def get_voice_connection(
        self, user_id: str, conversation_id: str
    ) -> Optional[WebSocket]:
        """
        Gets voice WebSocket connection for a user's conversation.

        Args:
            user_id (str): The ID of the user.
            conversation_id (str): The ID of the conversation.

        Returns:
            Optional[WebSocket]: The voice WebSocket connection if found, None otherwise.
        """
        key = f"{user_id}:{conversation_id}"
        return self.voice_connections.get(key)

    def remove_voice_connection(self, user_id: str, conversation_id: str) -> None:
        """
        Removes a voice WebSocket connection from the manager.

        Args:
            user_id (str): The ID of the user.
            conversation_id (str): The ID of the conversation.
        """
        key = f"{user_id}:{conversation_id}"
        if key in self.voice_connections:
            del self.voice_connections[key]
            logger.info(f"Removed voice connection for {key}")

    async def cleanup_inactive_sessions(self):
        """Cleanup sessions that have been inactive for longer than SESSION_TIMEOUT"""
        current_time = datetime.now(timezone.utc)
        sessions_to_cleanup = []

        for session_key, last_active in self.session_last_active.items():
            # Only clean up if:
            # 1. Session has exceeded timeout AND
            # 2. Session exists in active_sessions AND is marked as inactive
            if current_time - last_active > self.SESSION_TIMEOUT:
                session = self.active_sessions.get(session_key)
                if session is not None and not session.get("is_active", False):
                    sessions_to_cleanup.append(session_key)
                    logger.info(
                        "Session marked for cleanup",
                        session_key=session_key,
                        last_active=last_active,
                        is_active=session.get("is_active", False),
                    )

        for session_key in sessions_to_cleanup:
            await self._cleanup_session(session_key)
            logger.info("Cleaned up inactive session", session_key=session_key)

    async def _cleanup_session(self, session_key: str):
        """Clean up a specific session and its resources"""
        if session_key in self.active_sessions:
            session = self.active_sessions[session_key]
            cleanup_tasks = []

            if "background_task" in session and session["background_task"] is not None:
                session["background_task"].cancel()
                cleanup_tasks.append(session["background_task"])

            # Clean up pubsub from session
            if "pubsub" in session:
                try:
                    await session["pubsub"].close()
                except:
                    pass
                # Also remove from pubsub_instances
                self.pubsub_instances.pop(session_key, None)

            if cleanup_tasks:
                await asyncio.gather(*cleanup_tasks, return_exceptions=True)

            del self.active_sessions[session_key]
            self.session_last_active.pop(session_key, None)

    async def start_cleanup_task(self):
        """Start the background task for cleaning up inactive sessions"""
        if self.cleanup_task is None or self.cleanup_task.done():
            self.cleanup_task = asyncio.create_task(self.periodic_cleanup())

    async def periodic_cleanup(self):
        """Periodically check and cleanup inactive sessions"""
        while True:
            await self.cleanup_inactive_sessions()
            await asyncio.sleep(30)  # Check every 30 seconds

    async def handle_websocket(
        self, websocket: WebSocket, user_id: str, conversation_id: str
    ):
        """
        Handles incoming WebSocket messages and manages connection lifecycle.
        """
        # Start the cleanup task when the first connection is established
        await self.start_cleanup_task()

        from agents.components.compound.agent import enhanced_agent

        background_task = None
        session_key = f"{user_id}:{conversation_id}"
        channel = f"agent_thoughts:{user_id}:{conversation_id}"

        try:
            # Initialize or update session state
            if session_key not in self.active_sessions:
                # Create new pubsub instance for new session
                pubsub = self.redis_client.pubsub(ignore_subscribe_messages=True)
                await pubsub.subscribe(channel)
                self.pubsub_instances[session_key] = pubsub

                self.active_sessions[session_key] = {
                    "background_task": None,
                    "websocket": websocket,
                    "is_active": True,
                    "pubsub": pubsub,
                }
            else:
                # Reuse existing pubsub if session exists
                pubsub = self.active_sessions[session_key].get("pubsub")
                if not pubsub:
                    # Create new pubsub if somehow missing
                    pubsub = self.redis_client.pubsub(ignore_subscribe_messages=True)
                    await pubsub.subscribe(channel)
                    self.active_sessions[session_key]["pubsub"] = pubsub
                    self.pubsub_instances[session_key] = pubsub

                self.active_sessions[session_key]["websocket"] = websocket
                self.active_sessions[session_key]["is_active"] = True

            # Update session activity time
            self.session_last_active[session_key] = datetime.now(timezone.utc)

            # Check if we have an existing session state to restore
            session = self.active_sessions[session_key]
            background_task = session.get("background_task")
            pubsub = session["pubsub"]  # We know this exists now

            redis_api_keys = await self.message_storage.get_user_api_key(user_id)

            if redis_api_keys.sambanova_key == "":
                await websocket.close(code=4006, reason="No API keys found")
                return

            # Accept connection
            self.add_connection(websocket, user_id, conversation_id)

            if os.getenv("ENABLE_USER_KEYS") == "true":
                api_keys = redis_api_keys
            else:
                # Initialize API keys object
                # When admin panel is enabled, use user's stored Fireworks key
                admin_enabled = os.getenv("SHOW_ADMIN_PANEL", "false").lower() == "true"

                # Log what we have in redis_api_keys
                if admin_enabled:
                    logger.info(f"Redis API keys: sambanova={bool(redis_api_keys.sambanova_key)}, "
                              f"fireworks={bool(redis_api_keys.fireworks_key)}, "
                              f"together={bool(redis_api_keys.together_key)}")

                api_keys = APIKeys(
                    sambanova_key=redis_api_keys.sambanova_key,
                    fireworks_key=redis_api_keys.fireworks_key if admin_enabled else os.getenv("FIREWORKS_KEY", ""),
                    together_key=redis_api_keys.together_key if admin_enabled else "",
                    serper_key=redis_api_keys.serper_key or os.getenv("SERPER_KEY", ""),
                    exa_key=redis_api_keys.exa_key or os.getenv("EXA_KEY", ""),
                )

                # Log the final api_keys object
                logger.info(f"Final API keys after initialization: sambanova={bool(api_keys.sambanova_key)}, "
                          f"fireworks={bool(api_keys.fireworks_key)}, "
                          f"together={bool(api_keys.together_key)}")

            # Start background task for Redis messages if not restored
            if not background_task or background_task.done():
                background_task = asyncio.create_task(
                    self.handle_redis_messages(
                        websocket, pubsub, user_id, conversation_id
                    )
                )

            # Store session state
            self.active_sessions[session_key] = {
                "background_task": background_task,
                "websocket": websocket,  # Store websocket reference
                "is_active": True,  # Track connection state
                "pubsub": pubsub,
            }

            # Send connection established message
            await websocket.send_json(
                {
                    "event": "connection_established",
                    "data": "WebSocket connection established",
                    "user_id": user_id,
                    "conversation_id": conversation_id,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
            )

            # Handle incoming WebSocket messages
            while True:
                # Check if connection is still active
                if not self.active_sessions.get(session_key, {}).get(
                    "is_active", False
                ):
                    break

                user_message_text = await websocket.receive_text()

                # Handle ping messages
                if user_message_text == '{"type":"ping"}':
                    await websocket.send_json({"type": "pong"})
                    continue

                logger.info(
                    "Received message from user",
                    user_id=user_id,
                    conversation_id=conversation_id,
                )

                # Update session activity time on each message
                self.session_last_active[session_key] = datetime.now(timezone.utc)

                try:
                    user_message_input = json.loads(user_message_text)
                except json.JSONDecodeError:
                    await websocket.send_json(
                        {
                            "event": "error",
                            "data": "Invalid JSON message format",
                            "user_id": user_id,
                            "conversation_id": conversation_id,
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                        }
                    )
                    continue

                # Check provider and validate corresponding API key
                provider = user_message_input["provider"]
                logger.info(f"Provider requested: {provider}, API keys available: "
                          f"sambanova={bool(api_keys.sambanova_key)}, "
                          f"fireworks={bool(api_keys.fireworks_key)}, "
                          f"together={bool(api_keys.together_key)}")

                if provider == "sambanova":
                    if api_keys.sambanova_key == "":
                        await websocket.close(
                            code=4007, reason="SambaNova API key required but not found"
                        )
                        return
                elif provider == "fireworks":
                    if api_keys.fireworks_key == "":
                        logger.error(f"Fireworks key is empty! Closing websocket.")
                        await websocket.close(
                            code=4008, reason="Fireworks API key required but not found"
                        )
                        return
                elif provider == "together":
                    if not hasattr(api_keys, 'together_key') or api_keys.together_key == "":
                        await websocket.close(
                            code=4010, reason="Together API key required but not found"
                        )
                        return
                else:
                    await websocket.close(
                        code=4009, reason="Invalid or missing provider"
                    )
                    return

                await self.message_storage.update_metadata(
                    user_message_input["data"], user_id, conversation_id
                )

                input_, model, multimodal_input = await self.create_user_message_input(
                    user_id, user_message_input
                )

                # Check if user has config in Redis and load it into config manager
                # This ensures the config manager has the latest user overrides
                admin_enabled = os.getenv("SHOW_ADMIN_PANEL", "false").lower() == "true"
                if admin_enabled:
                    try:
                        from agents.config.llm_config_manager import get_config_manager
                        config_manager = get_config_manager()

                        # Check if config exists in Redis
                        config_key = f"llm_config:{user_id}"
                        stored_config = await self.message_storage.redis_client.get(config_key, user_id=user_id)

                        if stored_config:
                            # Load config from Redis into config manager
                            overrides = json.loads(stored_config)
                            logger.info(f"[CONFIG_LOAD] Loading user config from Redis for user {user_id[:8]}...")
                            logger.info(f"[CONFIG_LOAD] Config has task_models: {'task_models' in overrides}, custom_providers: {'custom_providers' in overrides}")
                            if 'task_models' in overrides:
                                logger.info(f"[CONFIG_LOAD] Number of task_models: {len(overrides['task_models'])}")
                                # Log financial analysis tasks specifically
                                for task_name in ['financial_analysis_main', 'financial_competitor_finder', 'financial_aggregator']:
                                    if task_name in overrides['task_models']:
                                        logger.info(f"[CONFIG_LOAD] {task_name}: {overrides['task_models'][task_name]}")

                            config_manager.set_user_override(user_id, overrides)
                            logger.info(f"[CONFIG_LOAD] Successfully loaded config for user {user_id[:8]}...")
                        elif config_manager.has_user_override(user_id):
                            # Redis doesn't have config but singleton does - clear it
                            logger.info(f"Clearing stale config override for user {user_id[:8]}...")
                            config_manager.clear_user_override(user_id)
                    except Exception as e:
                        logger.error(f"Error checking config freshness: {e}")

                config = await self.create_config(
                    user_id=user_id,
                    thread_id=conversation_id,
                    api_keys=api_keys,
                    provider=provider,
                    message_id=user_message_input["message_id"],
                    llm_type=model,
                    doc_ids=tuple(user_message_input["document_ids"]),
                    multimodal_input=multimodal_input,
                )

                await enhanced_agent.astream_websocket(
                    input=input_,
                    config=config,
                    websocket_manager=self,
                    user_id=user_id,
                    conversation_id=conversation_id,
                    message_id=user_message_input["message_id"],
                )

        except WebSocketDisconnect:
            logger.info("WebSocket connection closed", conversation_id=conversation_id)
            if session_key in self.active_sessions:
                # Only mark the connection as inactive, don't terminate the session
                self.active_sessions[session_key]["is_active"] = False
            self.remove_connection(user_id, conversation_id)
        except Exception as e:
            logger.info(
                "WebSocket connection closed with error",
                conversation_id=conversation_id,
                error=str(e),
            )
            if session_key in self.active_sessions:
                self.active_sessions[session_key]["is_active"] = False
        finally:
            self.remove_connection(user_id, conversation_id)

            # Only close websocket if it hasn't been closed already
            try:
                if (
                    websocket.client_state != WebSocketState.DISCONNECTED
                    and websocket.application_state != WebSocketState.DISCONNECTED
                ):
                    await websocket.close()
            except Exception as e:
                logger.error("Error closing websocket", error=str(e))

            # Update last active time on disconnect
            if session_key in self.session_last_active:
                self.session_last_active[session_key] = datetime.now(timezone.utc)

    async def create_user_message_input(self, user_id: str, user_message_input: dict):
        image_content = []
        multimodal_input = False
        for doc in user_message_input["document_ids"]:
            format = doc["format"].split("/")[0]
            if format == "image":
                retrived_content = await self.message_storage.get_file_as_base64(
                    user_id, doc["id"]
                )
                if retrived_content:
                    image_content.append(
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": "data:image/png;base64," + retrived_content,
                            },
                        }
                    )
                multimodal_input = True

        model = user_message_input["planner_model"]
        if len(image_content) > 0:
            input_ = HumanMessage(
                content=[
                    {"type": "text", "text": user_message_input["data"]},
                    *image_content,
                ],
                additional_kwargs={
                    "timestamp": user_message_input["timestamp"],
                    "agent_type": "human",
                    "resume": user_message_input["resume"],
                },
            )
            model = "Llama 4 Maverick"
        else:
            input_ = HumanMessage(
                content=user_message_input["data"],
                additional_kwargs={
                    "timestamp": user_message_input["timestamp"],
                    "agent_type": "human",
                    "resume": user_message_input["resume"],
                },
            )

        return input_, model, multimodal_input

    async def handle_redis_messages(
        self, websocket: WebSocket, pubsub, user_id: str, conversation_id: str
    ):
        """
        Background task to handle Redis pub/sub messages.
        """
        message_key = f"messages:{user_id}:{conversation_id}"
        session_key = f"{user_id}:{conversation_id}"
        BATCH_SIZE = 25

        try:
            while self.active_sessions.get(session_key, {}).get("is_active", False):
                # Process messages only if session is active
                messages = []
                for _ in range(BATCH_SIZE):
                    try:
                        message = await pubsub.get_message(timeout=0.05)
                        if message and message["type"] == "message":
                            messages.append(message)
                        if not message:
                            break
                    except Exception as e:
                        logger.error("Error getting Redis message", error=str(e))
                        break

                if messages:
                    for message in messages:
                        try:
                            if not self.active_sessions.get(session_key, {}).get(
                                "is_active", False
                            ):
                                break

                            data_str = message["data"]
                            data_parsed = json.loads(data_str)
                            message_data = {
                                "event": "think",
                                "data": data_str,
                                "user_id": user_id,
                                "conversation_id": conversation_id,
                                "timestamp": datetime.now(timezone.utc).isoformat(),
                                "message_id": data_parsed["message_id"],
                            }

                            # Store in Redis first
                            await self.redis_client.rpush(
                                message_key,
                                json.dumps(message_data),
                                user_id,
                            )

                            # Then try to send via WebSocket if still active
                            if self.active_sessions.get(session_key, {}).get(
                                "is_active", False
                            ):
                                await self._safe_send(websocket, message_data)

                                # ALSO send to voice WebSocket if active (for EVI progress updates)
                                voice_websocket = self.get_voice_connection(user_id, conversation_id)
                                if voice_websocket:
                                    try:
                                        # Extract step/task info for EVI context
                                        step_text = data_parsed.get("text", "")
                                        task = data_parsed.get("metadata", {}).get("task", "")
                                        agent_name = data_parsed.get("agent_name", "")

                                        # Create brief summary for EVI
                                        if "search" in step_text.lower() or "search" in task.lower():
                                            context = "Searching for information"
                                        elif "analy" in step_text.lower() or "analy" in task.lower():
                                            context = f"Analyzing data"
                                        elif "compet" in step_text.lower() or "compet" in task.lower():
                                            context = "Analyzing competitors"
                                        elif "technical" in step_text.lower() or "technical" in task.lower():
                                            context = "Running technical analysis"
                                        elif "risk" in step_text.lower() or "risk" in task.lower():
                                            context = "Assessing risk metrics"
                                        elif "fundamental" in step_text.lower() or "fundamental" in task.lower():
                                            context = "Analyzing fundamentals"
                                        elif "news" in step_text.lower() or "news" in task.lower():
                                            context = "Fetching recent news"
                                        elif agent_name:
                                            context = f"Running {agent_name}"
                                        else:
                                            context = step_text[:100] if step_text else "Processing"

                                        await voice_websocket.send_json({
                                            "type": "agent_context",
                                            "context": context,
                                            "timestamp": message_data.get("timestamp"),
                                            "message_id": data_parsed.get("message_id") or f"voice_ctx_{int(time.time() * 1000)}",
                                            "agent_name": agent_name,
                                            "task": task,
                                        })

                                        logger.debug(
                                            "Sent agent thought to voice WebSocket",
                                            user_id=user_id[:8],
                                            context=context,
                                        )
                                    except Exception as voice_err:
                                        logger.debug(
                                            f"Failed to send thought to voice WebSocket: {str(voice_err)}",
                                            user_id=user_id[:8],
                                        )

                                # ALSO send an agent_completion event with model metadata
                                # so trackRunMetrics can count the model usage in real-time
                                if "metadata" in data_parsed and "llm_name" in data_parsed["metadata"]:
                                    model_tracking_event = {
                                        "event": "agent_completion",
                                        "user_id": user_id,
                                        "conversation_id": conversation_id,
                                        "timestamp": datetime.now(timezone.utc).isoformat(),
                                        "message_id": data_parsed["message_id"],
                                        "id": str(uuid.uuid4()),  # Unique ID for deduplication
                                        "type": "AIMessage",
                                        "content": "",  # Empty content since this is just for tracking
                                        "response_metadata": {
                                            "model_name": data_parsed["metadata"]["llm_name"],
                                        },
                                        "additional_kwargs": {
                                            "agent_type": "crewai_llm_call",
                                        },
                                    }

                                    # Save to Redis for persistence using message_storage
                                    await self.message_storage.save_message(
                                        user_id,
                                        conversation_id,
                                        model_tracking_event
                                    )

                                    logger.info(
                                        "Saved CrewAI model tracking event to Redis",
                                        model_name=data_parsed["metadata"]["llm_name"],
                                        message_id=data_parsed["message_id"],
                                    )

                                    # Send via WebSocket
                                    await self._safe_send(websocket, model_tracking_event)

                        except Exception as e:
                            logger.error("Error processing Redis message", error=str(e))
                            continue

                await asyncio.sleep(0.2)

        except Exception as e:
            logger.error("Error in Redis message handler", error=str(e))
        finally:
            # Update session activity time before exiting
            self.session_last_active[session_key] = datetime.now(timezone.utc)

    async def _safe_send(self, websocket: WebSocket, data: dict) -> bool:
        """
        Safely send a message through the WebSocket.
        """
        try:
            # Check if session is still active
            for key, session in self.active_sessions.items():
                if session.get("websocket") == websocket:
                    if not session.get("is_active", False):
                        return False
                    break

            # Just try to send - most reliable way to detect if connection is still active
            await websocket.send_json(data)
            return True
        except Exception as e:
            # Mark the session as inactive when send fails
            for key, session in self.active_sessions.items():
                if session.get("websocket") == websocket:
                    self.active_sessions[key]["is_active"] = False
                    logger.info(
                        "Marked session as inactive due to send failure",
                        session_key=key,
                    )
                    break

            return False

    async def send_message(
        self, user_id: str, conversation_id: str, data: dict
    ) -> bool:
        """Send a message through the WebSocket for a specific conversation."""
        try:
            import uuid

            # Ensure message always has a valid ID to prevent Vue prop warnings
            if not data.get("id") and not data.get("message_id"):
                # Generate a fallback ID based on event type and timestamp
                timestamp = int(time.time() * 1000)
                event_type = data.get("event", "unknown")
                fallback_id = f"{event_type}_{timestamp}_{str(uuid.uuid4())[:8]}"
                data["id"] = fallback_id
                logger.debug(
                    "Generated fallback message ID",
                    fallback_id=fallback_id,
                    event=event_type,
                )

            session_key = f"{user_id}:{conversation_id}"
            websocket = self.connections.get(session_key)

            if "event" in data and data["event"] in [
                "agent_completion",
                "stream_complete",
                "stream_start",
            ]:

                if "id" in data:
                    if data["id"] is None:
                        pass  # Skip deduplication if no id
                    else:
                        is_new = await self.message_storage.is_message_new(
                            user_id, conversation_id, data["id"]
                        )

                        if not is_new:
                            return True  # Still successful, just skipped duplicate

                current_usage = data.get("usage_metadata")
                cumulative_usage = (
                    await self.message_storage.update_and_get_cumulative_usage(
                        user_id, conversation_id, current_usage
                    )
                )

                if cumulative_usage:
                    data["cumulative_usage_metadata"] = cumulative_usage

                content = to_agent_thinking(data)
                if content:
                    # Map to old format persist it and send it
                    await self.message_storage.save_message(
                        user_id,
                        conversation_id,
                        content,
                    )
                    await self._safe_send(websocket, content)

                await self.message_storage.save_message(user_id, conversation_id, data)

            if not websocket:
                logger.info(
                    "No WebSocket connection found for session", session_key=session_key
                )
                return False

            # Send to main WebSocket
            result = await self._safe_send(websocket, data)

            # Send events to voice WebSocket for EVI narration
            voice_websocket = self.get_voice_connection(user_id, conversation_id)
            if voice_websocket:
                try:
                    # Filter out LangChain internal message types and messages without proper event types
                    message_type = data.get("type")
                    event_type = data.get("event")

                    # List of internal message types to filter out
                    internal_types = [
                        "AIMessage",
                        "HumanMessage",
                        "LiberalFunctionMessage",
                        "FunctionMessage",
                        "SystemMessage",
                        None
                    ]

                    # Only send specific event types to voice, skip everything else
                    if event_type not in ["agent_completion", "think"]:
                        logger.debug(
                            "Skipping non-voice event for voice WebSocket",
                            message_type=message_type,
                            event_type=event_type,
                        )
                        pass
                    # Agent completion - final response for EVI to speak
                    elif event_type == "agent_completion":
                        # Skip model tracking events (CrewAI LLM calls) - these have empty content
                        agent_type = data.get("additional_kwargs", {}).get("agent_type")

                        # VOICE MODE AUTO-APPROVAL: Detect deep research interrupt and auto-approve
                        if agent_type == "deep_research_interrupt":
                            # Check if we've already triggered auto-approval for this conversation recently
                            current_time = datetime.now(timezone.utc)
                            last_approval = self.auto_approval_tracker.get(conversation_id)

                            # Only trigger if we haven't auto-approved in the last 5 seconds
                            # Reduced from 10s to be more responsive in voice mode
                            if not last_approval or (current_time - last_approval).total_seconds() > 5:
                                logger.info(
                                    "Voice mode: Detected deep research interrupt - will auto-approve",
                                    user_id=user_id[:8],
                                    conversation_id=conversation_id,
                                )
                                # Mark that we're auto-approving for this conversation
                                self.auto_approval_tracker[conversation_id] = current_time

                                # Schedule auto-approval after a brief delay to let the interrupt persist
                                asyncio.create_task(
                                    self._auto_approve_interrupt(user_id, conversation_id)
                                )
                            else:
                                logger.debug(
                                    "Voice mode: Skipping duplicate auto-approval",
                                    user_id=user_id[:8],
                                    time_since_last=int((current_time - last_approval).total_seconds()),
                                )

                        if agent_type == "crewai_llm_call":
                            logger.debug(
                                "Skipping CrewAI LLM tracking event for voice",
                                user_id=user_id[:8],
                            )
                            pass
                        else:
                            # Extract response text from agent completion
                            response_text = (
                                data.get("content") or
                                data.get("data") or
                                data.get("text") or
                                ""
                            )

                            # Only send if we have actual content
                            if response_text:
                                # EVI has character limits - if response is too long, create a summary
                                MAX_EVI_LENGTH = 2000  # Conservative limit for EVI consumption
                                original_length = len(response_text)

                                if len(response_text) > MAX_EVI_LENGTH:
                                    logger.info(
                                        "Response too long for EVI - creating summary",
                                        user_id=user_id[:8],
                                        original_length=original_length,
                                        max_length=MAX_EVI_LENGTH,
                                    )

                                    # Try to extract key findings/summary from the report
                                    # Look for common summary sections
                                    summary_text = response_text

                                    # Check for executive summary, key findings, or conclusion sections
                                    for marker in ["## Executive Summary", "## Key Findings", "## Summary", "## Conclusion"]:
                                        if marker in response_text:
                                            # Extract section after marker up to next ## or end
                                            start_idx = response_text.find(marker) + len(marker)
                                            next_section = response_text.find("##", start_idx)
                                            if next_section > 0:
                                                summary_text = response_text[start_idx:next_section].strip()
                                            else:
                                                summary_text = response_text[start_idx:].strip()
                                            break

                                    # If still too long, take first MAX_EVI_LENGTH chars with ellipsis
                                    if len(summary_text) > MAX_EVI_LENGTH:
                                        summary_text = summary_text[:MAX_EVI_LENGTH - 50] + "\n\n[Full report available in chat interface]"

                                    response_text = summary_text
                                    logger.info(
                                        "Summary created for EVI",
                                        user_id=user_id[:8],
                                        summary_length=len(response_text),
                                    )

                                # Send simplified response for EVI
                                await voice_websocket.send_json({
                                    "type": "agent_response",
                                    "text": response_text,
                                    "timestamp": data.get("timestamp"),
                                    "message_id": data.get("id") or data.get("message_id") or f"voice_resp_{int(time.time() * 1000)}",
                                })

                                # ALSO send full agent_completion message for chat UI to detect Daytona/tool calls
                                # This ensures sidebar detection works in real-time
                                await voice_websocket.send_json({
                                    "type": "agent_completion_full",
                                    "event": "agent_completion",
                                    "data": data,  # Full message data
                                    "message_id": data.get("id") or data.get("message_id"),
                                    "timestamp": data.get("timestamp"),
                                })

                                logger.info(
                                    "Sent agent response to voice",
                                    user_id=user_id[:8],
                                    text_preview=response_text[:50],
                                    agent_type=agent_type,
                                    response_length=len(response_text),
                                )
                            else:
                                logger.warning(
                                    "Agent completion has no content for voice",
                                    user_id=user_id[:8],
                                    data_keys=list(data.keys()),
                                    agent_type=agent_type,
                                )

                    # LLM stream chunk - send to voice for potential tool call detection
                    elif event_type == "llm_stream_chunk":
                        # Send full chunk to voice WebSocket for chat UI to detect tool calls
                        await voice_websocket.send_json({
                            "type": "llm_stream_chunk_full",
                            "event": "llm_stream_chunk",
                            "data": data,
                            "message_id": data.get("id") or data.get("message_id"),
                            "timestamp": data.get("timestamp"),
                        })

                    # Agent thinking - send brief context for EVI to narrate naturally
                    elif event_type == "think":
                        think_data = json.loads(data.get("data", "{}")) if isinstance(data.get("data"), str) else data.get("data", {})

                        # Extract brief progress update (< 200 chars for EVI)
                        agent_type = think_data.get("metadata", {}).get("agent_type", "")
                        step = think_data.get("step", "")

                        # Create brief summary for EVI context
                        if "search" in step.lower():
                            context = "Searching for information"
                        elif "analy" in step.lower():
                            context = f"Analyzing {agent_type or 'data'}"
                        elif "research" in step.lower():
                            context = "Conducting research"
                        elif "generat" in step.lower() or "writ" in step.lower():
                            context = "Generating report"
                        else:
                            context = step[:150] if step else f"Working on {agent_type}"

                        await voice_websocket.send_json({
                            "type": "agent_context",
                            "context": context,
                            "timestamp": data.get("timestamp"),
                        })

                except Exception as voice_err:
                    logger.error(
                        f"Failed to send to voice WebSocket: {str(voice_err)}",
                        user_id=user_id[:8],
                    )

            return result
        except Exception as e:
            logger.error(
                "Error sending WebSocket message",
                error=str(e),
                data_keys=list(data.keys()) if isinstance(data, dict) else type(data),
                event_type=data.get("event") if isinstance(data, dict) else None,  # Renamed to avoid conflict with structlog
                agent_type=data.get("additional_kwargs", {}).get("agent_type") if isinstance(data, dict) else None,
                message_id=data.get("id") if isinstance(data, dict) else None,
            )
            # Try to find which field has None
            if isinstance(data, dict):
                none_fields = []
                for key, value in data.items():
                    if value is None:
                        none_fields.append(key)
                    elif isinstance(value, dict):
                        for sub_key, sub_value in value.items():
                            if sub_value is None:
                                none_fields.append(f"{key}.{sub_key}")
                if none_fields:
                    logger.error("Found None values in fields", none_fields=none_fields)
            return False

    async def _load_file_context_for_analysis(self, user_id: str, doc_ids: list) -> str:
        """Load file contents to provide as context for multi-file analysis with smart context management."""
        file_context = "## UPLOADED FILES CONTEXT:\n\n"
        
        # Context limits (approximate token estimation: ~4 chars per token for 32K context)
        MAX_CONTEXT_LENGTH = 120000  # Leave room for system prompt and user message
        current_context_length = len(file_context)
        
        for doc_id in doc_ids:
            try:
                file_data, metadata = await self.message_storage.get_file(user_id, doc_id["id"])
                if file_data and metadata:
                    filename = metadata.get("filename", f"file_{doc_id['id']}")
                    file_format = metadata.get("format", "unknown")
                    
                    file_context += f"### File: {filename} (Format: {file_format})\n"
                    
                    # Handle different file types with smart context management
                    if file_format == "text/csv":
                        # For CSV files, check size first
                        try:
                            content = file_data.decode('utf-8')
                            if current_context_length + len(content) < MAX_CONTEXT_LENGTH:
                                # Provide complete CSV content for comprehensive analysis
                                file_context += f"```csv\n{content}\n```\n\n"
                                current_context_length += len(content)
                            else:
                                # CSV too large - provide sample and note file availability
                                lines = content.split('\n')
                                header = lines[0] if lines else ""
                                sample_lines = lines[:5] if len(lines) > 5 else lines
                                sample_content = '\n'.join(sample_lines)
                                file_context += f"**Large CSV file - Sample content:**\n```csv\n{sample_content}\n```\n"
                                file_context += f"**Full file available in sandbox as '{filename}' with {len(lines)} total rows.**\n\n"
                                current_context_length += len(sample_content) + 200
                        except UnicodeDecodeError:
                            file_context += "Binary CSV file content (use pandas to read in analysis)\n\n"
                    
                    elif file_format == "application/pdf":
                        # For PDFs, extract and provide the actual text content
                        try:
                            pdf_text = await self._extract_pdf_text(file_data)
                            if pdf_text.strip():
                                if current_context_length + len(pdf_text) < MAX_CONTEXT_LENGTH:
                                    # Provide complete PDF content for comprehensive analysis
                                    file_context += f"```\n{pdf_text}\n```\n\n"
                                    current_context_length += len(pdf_text)
                                else:
                                    # PDF too large - provide summary
                                    pdf_sample = pdf_text[:2000] + "..."
                                    file_context += f"**Large PDF document - Content preview:**\n```\n{pdf_sample}\n```\n"
                                    file_context += f"**Full document available in sandbox as '{filename}'.**\n\n"
                                    current_context_length += 2500
                            else:
                                file_context += "PDF document - Could not extract readable text content.\n\n"
                        except Exception as e:
                            logger.warning(f"Could not extract PDF text for {filename}: {str(e)}")
                            file_size = len(file_data)
                            file_context += f"PDF document ({file_size} bytes) - Could not extract text, but file is available for analysis.\n\n"
                    
                    elif file_format in ["text/plain", "text/markdown"]:
                        # For text files, show content with size check
                        try:
                            content = file_data.decode('utf-8')
                            if current_context_length + len(content) < MAX_CONTEXT_LENGTH:
                                file_context += f"```\n{content}\n```\n\n"
                                current_context_length += len(content)
                            else:
                                content_sample = content[:2000] + "..."
                                file_context += f"**Large text file - Content preview:**\n```\n{content_sample}\n```\n"
                                file_context += f"**Full file available in sandbox as '{filename}'.**\n\n"
                                current_context_length += 2500
                        except UnicodeDecodeError:
                            file_context += "Binary text file content\n\n"
                    
                    elif file_format in ["application/vnd.openxmlformats-officedocument.wordprocessingml.document", "application/msword"]:
                        # For Word documents, provide basic info and note they're available
                        file_size = len(file_data)
                        file_context += f"Word document ({file_size} bytes) - Available for text extraction and analysis.\n"
                        file_context += "Use document processing tools to extract content if needed.\n\n"
                    
                    elif file_format in ["application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "application/vnd.ms-excel"]:
                        # For XLSX files, use intelligent approach based on size
                        try:
                            # First try to get full content
                            xlsx_content = await self._extract_xlsx_content(file_data)
                            if xlsx_content.strip():
                                # Check if full content fits in context
                                if current_context_length + len(xlsx_content) < MAX_CONTEXT_LENGTH:
                                    # Small enough - provide complete XLSX content
                                    file_context += f"```xlsx\n{xlsx_content}\n```\n\n"
                                    current_context_length += len(xlsx_content)
                                else:
                                    # Too large - provide intelligent summary instead
                                    logger.info(f"XLSX file {filename} too large ({len(xlsx_content)} chars), creating summary")
                                    xlsx_summary = await self._create_xlsx_summary(file_data, filename)
                                    file_context += f"**XLSX File Analysis Summary (Large File):**\n```\n{xlsx_summary}\n```\n"
                                    file_context += f"**Complete spreadsheet data available in sandbox as '{filename}' for detailed analysis.**\n\n"
                                    current_context_length += len(xlsx_summary) + 200
                            else:
                                file_size = len(file_data)
                                file_context += f"Excel spreadsheet ({file_size} bytes) - Available for data analysis.\n"
                                file_context += "Use pandas or similar tools to read and analyze the data.\n\n"
                        except Exception as e:
                            logger.warning(f"Could not extract XLSX content for {filename}: {str(e)}")
                            file_size = len(file_data)
                            file_context += f"Excel spreadsheet ({file_size} bytes) - Could not extract content, but file is available for analysis.\n\n"
                    
                    else:
                        # For other file types, provide basic info
                        file_size = len(file_data)
                        file_context += f"File format: {file_format}, Size: {file_size} bytes\n"
                        file_context += "File is available for processing in the analysis environment.\n\n"
                        
            except Exception as e:
                logger.warning(f"Could not load context for file {doc_id['id']}: {str(e)}")
                file_context += f"### File: {doc_id.get('filename', 'unknown')} - Could not load content\n\n"
        
        logger.info(f"Generated context with {current_context_length} characters for {len(doc_ids)} files")
        return file_context

    async def _extract_pdf_text(self, file_data: bytes) -> str:
        """Extract text content from PDF file data using PyMuPDF."""
        try:
            # Create a temporary file to write the PDF data
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_file:
                temp_file.write(file_data)
                temp_path = temp_file.name

            try:
                # Extract text using PyMuPDF in a separate thread to avoid blocking
                text = await asyncio.to_thread(self._extract_pdf_text_sync, temp_path)
                return text
            finally:
                # Clean up the temporary file
                if os.path.exists(temp_path):
                    os.unlink(temp_path)
                    
        except Exception as e:
            logger.error(f"Error extracting PDF text: {str(e)}")
            raise

    def _extract_pdf_text_sync(self, file_path: str) -> str:
        """Unified PDF extraction using pdfplumber with inline table formatting."""
        text = ""
        
        try:
            with pdfplumber.open(file_path) as pdf:
                for page_num, page in enumerate(pdf.pages):
                    text += f"--- Page {page_num + 1} ---\n"
                    
                    # Extract tables from this page
                    tables = page.extract_tables()
                    
                    if tables:
                        # Extract regular text first
                        page_text = page.extract_text()
                        if page_text:
                            text += page_text + "\n\n"
                        
                        # Add clean HTML tables inline for better LLM parsing
                        for table_idx, table in enumerate(tables):
                            if table and len(table) > 1:  # Valid table with data
                                # Convert table to DataFrame for clean HTML output
                                import pandas as pd
                                
                                # Use first row as headers if it looks like headers
                                headers = table[0] if table[0] else [f"Column_{i}" for i in range(len(table[0]) if table[0] else 0)]
                                data_rows = table[1:] if len(table) > 1 else []
                                
                                if data_rows:
                                    # Clean headers and data
                                    clean_headers = []
                                    for i, h in enumerate(headers):
                                        if h and str(h).strip():
                                            clean_headers.append(str(h).strip())
                                        else:
                                            clean_headers.append(f"Column_{i}")
                                    
                                    # Create DataFrame with proper data cleaning
                                    clean_data = []
                                    for row in data_rows:
                                        clean_row = []
                                        for cell in row:
                                            if cell:
                                                cell_text = str(cell).strip().replace('\n', ' ').replace('\r', ' ')
                                                cell_text = cell_text.replace('  ', ' ').strip()
                                                clean_row.append(cell_text)
                                            else:
                                                clean_row.append("")
                                        clean_data.append(clean_row)
                                    
                                    # Ensure data rows match header length
                                    max_cols = len(clean_headers)
                                    for row in clean_data:
                                        while len(row) < max_cols:
                                            row.append("")
                                        if len(row) > max_cols:
                                            row = row[:max_cols]
                                    
                                    df = pd.DataFrame(clean_data, columns=clean_headers)
                                    
                                    # Remove completely empty rows and columns
                                    df = df.dropna(how='all').dropna(axis=1, how='all')
                                    
                                    if not df.empty:
                                        # Convert to clean HTML
                                        html_table = df.to_html(
                                            index=False,
                                            na_rep='',
                                            classes="extracted-table",
                                            escape=False,
                                            border=1
                                        )
                                        
                                        text += f"\n[TABLE {table_idx+1} - Page {page_num+1}]\n"
                                        text += html_table + "\n"
                                        text += f"[END TABLE {table_idx+1}]\n\n"
                    
                    else:
                        # No tables, just extract text
                        page_text = page.extract_text()
                        if page_text:
                            text += page_text + "\n\n"
                            
        except Exception as e:
            logger.error(f"Error in pdfplumber extraction: {str(e)}")
            # Fallback to basic text extraction
            try:
                with pdfplumber.open(file_path) as pdf:
                    for page_num, page in enumerate(pdf.pages):
                        page_text = page.extract_text()
                        if page_text:
                            text += f"--- Page {page_num + 1} ---\n{page_text}\n\n"
            except Exception as fallback_error:
                logger.error(f"Fallback extraction failed: {str(fallback_error)}")
                raise
                
        return text.strip()

    async def _extract_xlsx_content(self, file_data: bytes) -> str:
        """Extract content from XLSX file data directly from bytes using pandas and openpyxl."""
        try:
            # Extract content using pandas in a separate thread to avoid blocking
            content = await asyncio.to_thread(self._extract_xlsx_content_sync, file_data)
            return content
        except Exception as e:
            logger.error(f"Error extracting XLSX content: {str(e)}")
            raise

    def _extract_xlsx_content_sync(self, file_data: bytes) -> str:
        """Synchronous XLSX extraction using pandas directly from bytes."""
        import pandas as pd
        from io import BytesIO
        
        content = ""
        
        try:
            # Create BytesIO object from file data - no temp file needed
            bytes_io = BytesIO(file_data)
            
            # Read all sheets from the XLSX file
            xlsx_file = pd.ExcelFile(bytes_io)
            
            for sheet_num, sheet_name in enumerate(xlsx_file.sheet_names):
                content += f"--- Sheet: {sheet_name} ---\n"
                
                try:
                    # Read the sheet data directly from BytesIO
                    df = pd.read_excel(bytes_io, sheet_name=sheet_name)
                    
                    # Convert dataframe to string representation for context
                    if not df.empty:
                        # Provide complete sheet content for comprehensive analysis
                        sheet_content = df.to_string(index=False, max_rows=None, max_cols=None)
                        content += f"{sheet_content}\n\n"
                    else:
                        content += "Empty sheet\n\n"
                        
                except Exception as sheet_error:
                    logger.warning(f"Could not read sheet '{sheet_name}': {str(sheet_error)}")
                    content += f"Could not read sheet '{sheet_name}'\n\n"
                    
        except Exception as e:
            logger.error(f"Error in XLSX extraction: {str(e)}")
            raise
            
        return content.strip()

    async def _create_xlsx_summary(self, file_data: bytes, filename: str) -> str:
        """Create an intelligent summary of XLSX file content for large files."""
        try:
            content = await asyncio.to_thread(self._create_xlsx_summary_sync, file_data, filename)
            return content
        except Exception as e:
            logger.error(f"Error creating XLSX summary: {str(e)}")
            raise

    def _create_xlsx_summary_sync(self, file_data: bytes, filename: str) -> str:
        """Synchronous XLSX summarization for large files."""
        import pandas as pd
        from io import BytesIO
        
        summary = f"XLSX File Summary: {filename}\n\n"
        
        try:
            # Create BytesIO object from file data
            bytes_io = BytesIO(file_data)
            
            # Read all sheets from the XLSX file
            xlsx_file = pd.ExcelFile(bytes_io)
            
            summary += f"Number of sheets: {len(xlsx_file.sheet_names)}\n"
            summary += f"Sheet names: {', '.join(xlsx_file.sheet_names)}\n\n"
            
            for sheet_num, sheet_name in enumerate(xlsx_file.sheet_names):
                summary += f"### Sheet: {sheet_name}\n"
                
                try:
                    # Read the sheet data directly from BytesIO
                    df = pd.read_excel(bytes_io, sheet_name=sheet_name)
                    
                    if not df.empty:
                        # Basic statistics
                        summary += f"- Dimensions: {df.shape[0]} rows × {df.shape[1]} columns\n"
                        
                        # Column information
                        summary += f"- Columns: {', '.join(df.columns.tolist())}\n"
                        
                        # Data types
                        dtype_summary = df.dtypes.value_counts().to_dict()
                        summary += f"- Data types: {dtype_summary}\n"
                        
                        # Sample of first few rows for context
                        if len(df) > 0:
                            summary += f"- First 3 rows sample:\n"
                            sample_df = df.head(3)
                            summary += sample_df.to_string(index=False) + "\n"
                        
                        # Numeric column statistics
                        numeric_cols = df.select_dtypes(include=['number']).columns
                        if len(numeric_cols) > 0:
                            summary += f"- Numeric columns ({len(numeric_cols)}): {', '.join(numeric_cols)}\n"
                            desc = df[numeric_cols].describe()
                            summary += f"- Key statistics:\n{desc.to_string()}\n"
                        
                        # Categorical columns info
                        categorical_cols = df.select_dtypes(include=['object', 'category']).columns
                        if len(categorical_cols) > 0:
                            summary += f"- Text/Categorical columns ({len(categorical_cols)}): {', '.join(categorical_cols)}\n"
                            for col in categorical_cols[:3]:  # Show unique values for first 3 categorical columns
                                unique_vals = df[col].unique()[:10]  # First 10 unique values
                                summary += f"  - {col}: {len(df[col].unique())} unique values, sample: {list(unique_vals)}\n"
                        
                        # Missing data info
                        missing_data = df.isnull().sum()
                        missing_cols = missing_data[missing_data > 0]
                        if len(missing_cols) > 0:
                            summary += f"- Missing data: {missing_cols.to_dict()}\n"
                    else:
                        summary += "- Empty sheet\n"
                        
                    summary += "\n"
                        
                except Exception as sheet_error:
                    logger.warning(f"Could not analyze sheet '{sheet_name}': {str(sheet_error)}")
                    summary += f"- Could not analyze sheet '{sheet_name}'\n\n"
                    
        except Exception as e:
            logger.error(f"Error in XLSX summarization: {str(e)}")
            raise
            
        return summary.strip()

    async def _auto_approve_interrupt(
        self,
        user_id: str,
        conversation_id: str,
    ) -> None:
        """
        Auto-approve a pending interrupt in voice mode.

        This follows the same pattern as the API router - when deep research
        or other workflows create an interrupt, voice mode automatically approves
        it to avoid requiring verbal confirmation.

        Args:
            user_id: User ID
            conversation_id: Conversation ID
        """
        try:
            # Delay to ensure interrupt is fully persisted to checkpoint
            # Increased to 1.0s to give checkpoint time to save
            await asyncio.sleep(1.0)

            logger.info(
                "Voice mode: Auto-approving interrupt",
                user_id=user_id[:8],
                conversation_id=conversation_id,
            )

            # Inject approval message as if user said "approved"
            # This triggers the resume flow in stream.py
            await self.inject_voice_message(
                user_id=user_id,
                conversation_id=conversation_id,
                message_text="approved",
                message_id=None,  # Generate new ID
            )

            logger.info(
                "Voice mode: Auto-approval message injected",
                user_id=user_id[:8],
            )

            # Clear the approval tracker for this conversation after successful approval
            # This allows future interrupts to be auto-approved
            if conversation_id in self.auto_approval_tracker:
                del self.auto_approval_tracker[conversation_id]
                logger.debug(
                    "Cleared auto-approval tracker for conversation",
                    conversation_id=conversation_id,
                )

        except Exception as e:
            logger.error(
                f"Voice mode: Failed to auto-approve interrupt: {str(e)}",
                user_id=user_id[:8],
                exc_info=True,
            )

    async def inject_voice_message(
        self,
        user_id: str,
        conversation_id: str,
        message_text: str,
        message_id: Optional[str] = None,
    ) -> tuple[bool, Optional[str]]:
        """
        Inject a voice-transcribed message into the chat workflow.

        This method allows voice transcriptions to trigger the same agent
        processing as regular text messages.

        Args:
            user_id: User ID
            conversation_id: Conversation ID
            message_text: Transcribed text from voice input
            message_id: Optional message ID for tracking

        Returns:
            Tuple of (success: bool, message_id: str) - the actual message ID used
        """
        try:
            from agents.components.compound.agent import enhanced_agent
            import uuid
            import hashlib

            # Generate message ID if not provided
            if not message_id:
                message_id = str(uuid.uuid4())

            # Deduplication: Check if this message was recently processed
            message_hash = hashlib.md5(message_text.encode()).hexdigest()
            current_time = datetime.now(timezone.utc)

            # Initialize tracker for this conversation if needed
            if conversation_id not in self.voice_message_tracker:
                self.voice_message_tracker[conversation_id] = {}

            # Clean up old entries (older than dedup window)
            conversation_tracker = self.voice_message_tracker[conversation_id]
            expired_hashes = [
                h for h, t in conversation_tracker.items()
                if current_time - t > self.DEDUP_WINDOW
            ]
            for h in expired_hashes:
                del conversation_tracker[h]

            # Check if this is a duplicate
            if message_hash in conversation_tracker:
                time_since_last = current_time - conversation_tracker[message_hash]
                logger.info(
                    "Skipping duplicate voice message",
                    user_id=user_id[:8],
                    message_preview=message_text[:50],
                    time_since_last_ms=int(time_since_last.total_seconds() * 1000),
                )
                return (True, message_id)  # Return success but don't process

            # Track this message
            conversation_tracker[message_hash] = current_time

            # Get the WebSocket connection - try main connection first, fallback to voice connection
            websocket = self.get_connection(user_id, conversation_id)

            if not websocket:
                # No main connection, try voice connection as fallback
                websocket = self.get_voice_connection(user_id, conversation_id)

            if not websocket:
                logger.error(
                    "Cannot inject voice message: no active WebSocket connection",
                    user_id=user_id[:8],
                    conversation_id=conversation_id,
                )
                return (False, None)

            # Determine which connection we're using
            is_using_main_connection = self.get_connection(user_id, conversation_id) is not None

            logger.info(
                "Using WebSocket for voice message injection",
                user_id=user_id[:8],
                connection_type="main" if is_using_main_connection else "voice",
            )

            # If using voice connection as main, register it temporarily
            # This ensures UI updates work even if ChatView isn't open
            if not is_using_main_connection:
                self.add_connection(websocket, user_id, conversation_id)
                logger.info(
                    "Temporarily registered voice WebSocket as main connection",
                    user_id=user_id[:8],
                )

            # Set up session if not exists (for voice-only mode)
            session_key = f"{user_id}:{conversation_id}"
            channel = f"agent_thoughts:{user_id}:{conversation_id}"

            # Initialize session if it doesn't exist
            if session_key not in self.active_sessions:
                # Create pubsub instance for voice session
                pubsub = self.redis_client.pubsub(ignore_subscribe_messages=True)
                await pubsub.subscribe(channel)
                self.pubsub_instances[session_key] = pubsub

                self.active_sessions[session_key] = {
                    "background_task": None,
                    "websocket": websocket,
                    "is_active": True,
                    "pubsub": pubsub,
                }

                logger.info(
                    "Created voice session",
                    user_id=user_id[:8],
                    conversation_id=conversation_id,
                )

            # Update session activity time
            self.session_last_active[session_key] = datetime.now(timezone.utc)

            # Start background task for Redis messages if not running
            session = self.active_sessions[session_key]
            if not session.get("background_task") or session["background_task"].done():
                session["background_task"] = asyncio.create_task(
                    self.handle_redis_messages(
                        websocket, session["pubsub"], user_id, conversation_id
                    )
                )
                logger.info(
                    "Started background task for voice session",
                    user_id=user_id[:8],
                )

            # Load user's API keys and provider settings
            redis_api_keys = await self.message_storage.get_user_api_key(user_id)

            if redis_api_keys.sambanova_key == "":
                logger.error("No API keys found for voice message injection")
                return (False, None)

            # Determine provider (default to sambanova for voice)
            provider = "sambanova"

            # Use admin keys if admin panel is disabled
            admin_enabled = os.getenv("SHOW_ADMIN_PANEL", "false").lower() == "true"

            if admin_enabled:
                from agents.api.data_types import APIKeys
                api_keys = APIKeys(
                    sambanova_key=redis_api_keys.sambanova_key,
                    fireworks_key=redis_api_keys.fireworks_key,
                    together_key=redis_api_keys.together_key,
                    serper_key=redis_api_keys.serper_key or os.getenv("SERPER_KEY", ""),
                    exa_key=redis_api_keys.exa_key or os.getenv("EXA_KEY", ""),
                )
            else:
                from agents.api.data_types import APIKeys
                api_keys = APIKeys(
                    sambanova_key=redis_api_keys.sambanova_key,
                    fireworks_key=os.getenv("FIREWORKS_KEY", ""),
                    together_key="",
                    serper_key=redis_api_keys.serper_key or os.getenv("SERPER_KEY", ""),
                    exa_key=redis_api_keys.exa_key or os.getenv("EXA_KEY", ""),
                )

            # Check if this is an approval message (for resuming interrupts)
            # Note: We can't reliably detect interrupts because subgraphs are recreated
            # with new checkpointers on each message. Instead, we detect approval keywords.
            # IMPORTANT: Only enable auto-approval for EXISTING conversations (not new ones)
            should_resume = False

            # Load existing messages to check if this is a new conversation
            existing_messages = await self.message_storage.get_messages(
                user_id, conversation_id
            )
            num_messages = len(existing_messages)

            logger.info(
                "Voice message injection context",
                user_id=user_id[:8],
                num_messages=num_messages,
            )

            # Only apply auto-approval detection if there are existing messages
            # (meaning there's an interrupted workflow that could be resumed)
            if num_messages > 0:
                content_lower = message_text.lower().strip()
                approval_keywords = [
                    "approve", "approved", "yes", "continue", "proceed", "true",
                    "ok", "okay", "sure", "go ahead", "yep", "yeah", "affirmative",
                    "confirm", "confirmed", "accepted"
                ]

                if any(keyword in content_lower for keyword in approval_keywords):
                    # This looks like an approval - set resume=True to continue interrupted workflow
                    should_resume = True
                    logger.info(
                        "Detected approval keyword in existing conversation - setting resume=True to continue interrupted workflow",
                        user_id=user_id[:8],
                        message_text=message_text[:50],
                        num_messages=num_messages,
                    )
            else:
                logger.info(
                    "New conversation (num_messages=0) - skipping auto-approval detection, letting agent route normally",
                    user_id=user_id[:8],
                    message_text=message_text[:50],
                )

            # Create HumanMessage from voice transcription
            input_message = HumanMessage(
                content=message_text,
                additional_kwargs={
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "agent_type": "human",
                    "resume": should_resume,  # Set based on interrupt state
                    "source": "voice",  # Mark as voice input
                },
            )

            # Store the user message
            await self.message_storage.save_message(
                user_id,
                conversation_id,
                {
                    "event": "user_message",
                    "data": message_text,
                    "message_id": message_id,
                    "conversation_id": conversation_id,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "source": "voice",
                },
            )

            # Update conversation metadata with title from first message
            await self.message_storage.update_metadata(
                message_text, user_id, conversation_id
            )

            # Create config for agent processing
            config = await self.create_config(
                user_id=user_id,
                thread_id=conversation_id,
                api_keys=api_keys,
                provider=provider,
                message_id=message_id,
                llm_type="DeepSeek V3",  # Default model for voice
                doc_ids=tuple(),  # No documents for voice messages (for now)
                multimodal_input=False,
            )

            # Trigger agent workflow (same as regular messages)
            await enhanced_agent.astream_websocket(
                input=input_message,
                config=config,
                websocket_manager=self,
                user_id=user_id,
                conversation_id=conversation_id,
                message_id=message_id,
            )

            # Note: Auto-approval for interrupts is now handled in send_message
            # when the deep_research_interrupt message is detected

            logger.info(
                "Successfully injected voice message into chat workflow",
                user_id=user_id[:8],
                conversation_id=conversation_id,
                message_preview=message_text[:50],
            )

            return (True, message_id)

        except Exception as e:
            logger.error(
                f"Error injecting voice message: {str(e)}",
                user_id=user_id[:8] if user_id else "unknown",
                conversation_id=conversation_id,
            )
            return (False, None)

    async def create_config(
        self,
        user_id: str,
        thread_id: str,
        api_keys: APIKeys,
        provider: str,
        message_id: str,
        llm_type: str,
        doc_ids: Dict[str, Any],
        multimodal_input: bool,
    ):
        # Add cleanup task
        self.cleanup_task: Optional[asyncio.Task] = None

        indexed_doc_ids = []
        data_analysis_doc_ids = []
        all_file_ids = []
        directory_content = []

        logger.info(f"[DOCUMENT_TRACE] Received doc_ids: {doc_ids}")

        for doc_id in doc_ids:
            all_file_ids.append(doc_id["id"])
            logger.info(f"[DOCUMENT_TRACE] Processing doc_id: {doc_id['id']}, indexed: {doc_id.get('indexed', False)}, format: {doc_id.get('format', 'unknown')}")
            if doc_id["indexed"]:
                indexed_doc_ids.append(doc_id["id"])
                logger.info(f"[DOCUMENT_TRACE] Added {doc_id['id']} to indexed_doc_ids")
            else:
                logger.warning(f"[DOCUMENT_TRACE] Skipping {doc_id['id']} - NOT INDEXED!")
            if doc_id["format"] in ["text/csv", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "application/vnd.ms-excel"]:
                data_analysis_doc_ids.append(doc_id["id"])
                directory_content.append(doc_id["filename"])

        logger.info(f"[DOCUMENT_TRACE] Final indexed_doc_ids: {indexed_doc_ids}")
        logger.info(f"[DOCUMENT_TRACE] Final all_file_ids: {all_file_ids}")

        enable_data_science = False
        if data_analysis_doc_ids:
            enable_data_science = True
            
        # Detect multi-file uploads OR single data files (XLSX/CSV) that should bypass retrieval and go directly to sandbox
        # This handles cases like CSV + PDF combinations for comprehensive analysis, OR single XLSX/CSV files that need context
        multi_file_analysis = (len(doc_ids) > 1 and any(
            doc_id["format"] in ["text/csv", "application/pdf", "text/plain", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"]
            for doc_id in doc_ids
        )) or (len(doc_ids) == 1 and any(
            doc_id["format"] in ["text/csv", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "application/vnd.ms-excel"]
            for doc_id in doc_ids
        ))

        retrieval_prompt = ""
        if indexed_doc_ids:
            retrieval_prompt = (
                f"{len(doc_ids)} documents are available for retrieval.\n\n"
                "IMPORTANT: To search these documents, use the Retriever tool and pass the user's question or a relevant search query as the 'query' parameter. "
                "Extract the key information the user is asking about and use that as your search query. "
                "For example, if the user asks 'summarize this pdf' or 'what does this document say about X', pass a specific query like 'summary' or 'X' to the Retriever tool.\n\n"
            )

        data_analysis_prompt = ""
        if enable_data_science:
            data_analysis_prompt = (
                f"The following datasets are available to analyze:\n\n"
            )
            data_analysis_prompt += "\n".join(directory_content)
            data_analysis_prompt += (
                "\n\nGUIDELINES FOR DATA ANALYSIS ROUTING:\n\n"
                "Use the **data_science subgraph** for complex analysis requiring:\n"
                "- Exploratory Data Analysis (EDA) and comprehensive data exploration\n"
                "- Machine learning model development or training\n"
                "- Predictive analytics and forecasting\n"
                "- Statistical modeling and hypothesis testing\n"
                "- Multi-step data science pipelines\n"
                "- Advanced statistical analysis (regression, clustering, etc.)\n"
                "- Feature engineering and model evaluation\n"
                "- Complex data visualization\n"
                "- Statistical visualization (correlation matrices, distribution analysis, etc.)\n"
                "- Comprehensive analysis workflows with multiple visualization types\n\n"
                "Use the **DaytonaCodeSandbox subgraph** for:\n"
                "- Multi-file data analysis and processing\n"
                "- Calculations and data manipulation\n"
                "- Report and spreadsheet generation\n"
                "- Any task requiring code execution\n\n"
                "CHOOSE the appropriate subgraph based on the complexity and requirements of the user's request.\n\n"
            )

        # For multi-file analysis, pass all files to the daytona manager, not just CSVs
        daytona_file_ids = all_file_ids if multi_file_analysis else data_analysis_doc_ids
        
        # Load file context for multi-file analysis
        file_context = ""
        if multi_file_analysis:
            file_context = await self._load_file_context_for_analysis(user_id, doc_ids)
        
        daytona_manager = self.daytona_managers.get(f"{user_id}:{thread_id}")
        if not daytona_manager:
            daytona_manager = PersistentDaytonaManager(
                user_id=user_id,
                redis_storage=self.message_storage,
                snapshot="data-analysis:0.0.10",
                file_ids=daytona_file_ids,
            )
            self.daytona_managers[f"{user_id}:{thread_id}"] = daytona_manager

        tools_config = [
            {
                "type": "arxiv",
                "config": {},
            },
            {
                "type": "search_tavily",
                "config": {},
            },
            {
                "type": "search_tavily_answer",
                "config": {},
            },
            {
                "type": "wikipedia",
                "config": {},
            },
        ]

        # Determine the correct API key based on provider
        admin_enabled = os.getenv("SHOW_ADMIN_PANEL", "false").lower() == "true"

        # Set the correct API key based on the provider
        if provider == "fireworks":
            api_key_to_use = api_keys.fireworks_key
        elif provider == "together":
            api_key_to_use = getattr(api_keys, 'together_key', "")
        else:
            api_key_to_use = api_keys.sambanova_key  # Default to sambanova

        if admin_enabled:
            # Debug log API keys before creating config
            logger.info(f"Creating config with API keys - sambanova: {bool(api_keys.sambanova_key)}, "
                       f"fireworks: {bool(api_keys.fireworks_key)}, "
                       f"together: {bool(getattr(api_keys, 'together_key', ''))}")
            logger.info(f"Using API key for provider {provider}: {bool(api_key_to_use)}")

            # When admin panel is enabled, pass all API keys
            config = {
                "configurable": {
                    "type==default/user_id": user_id,
                    "type==default/llm_type": llm_type,
                    "thread_id": thread_id,
                    "user_id": user_id,
                    "api_key": api_key_to_use,  # Keep for backward compatibility
                    "api_keys": {
                        "sambanova": api_keys.sambanova_key,
                        "fireworks": api_keys.fireworks_key,
                        "together": getattr(api_keys, 'together_key', ""),
                    },
                    "message_id": message_id,
                },
                "recursion_limit": 50,
            }
        else:
            # Original behavior when admin panel is disabled
            if provider == "fireworks":
                api_key_to_use = api_keys.fireworks_key
            elif provider == "together":
                api_key_to_use = getattr(api_keys, 'together_key', "")
            else:
                api_key_to_use = api_keys.sambanova_key

            config = {
                "configurable": {
                    "type==default/user_id": user_id,
                    "type==default/llm_type": llm_type,
                    "thread_id": thread_id,
                    "user_id": user_id,
                    "api_key": api_key_to_use,
                    "message_id": message_id,
                },
                "recursion_limit": 50,
            }

        # Construct system message with file context and routing guidance
        multi_file_guidance = ""
        if multi_file_analysis:
            multi_file_guidance = f"""
## MULTI-FILE ANALYSIS MODE ACTIVE

You have been provided with {len(doc_ids)} files for comprehensive analysis. For queries that require analyzing, comparing, or combining data from multiple files, you should DIRECTLY use the DaytonaCodeSandbox subgraph rather than the Retrieval tool.

{file_context}

**ROUTING PRIORITY FOR MULTI-FILE ANALYSIS:**
1. For comprehensive analysis involving multiple files → Use DaytonaCodeSandbox subgraph
2. For creating reports/spreadsheets combining multiple data sources → Use DaytonaCodeSandbox subgraph  
3. For general questions about specific document content → Use Retrieval tool
4. For complex data science workflows → Use data_science subgraph (if available)

**COMPLETE DATA PROVIDED FOR ANALYSIS:**

When performing multi-file analysis:
- Complete file contents are provided below (no truncation)
- All data from every file is available for comprehensive analysis
- DO NOT attempt to import, read, or load files - all data is already provided in context
- Use the provided data directly in your code and analysis
- Extract and use all relevant information to fully answer the user's question
- Cross-reference data between files as needed
- Always verify that your analysis is complete and thorough. For example, some calculations will be dependent on your previous calculations. Be sure to check your work and verify that you have not missed any data and or subsequent calculations.
    - Here's an example of a calculation that is dependent on your previous calculations:
    - Metric B = Metric A * 0.2 (You must have calculated Metric A first and then use that value to calculate Metric B)
    - Metric C = Metric B * 0.3 (You must have calculated Metric B first and then use that value to calculate Metric C)
- Note if you return back for some analysis that you have not completed, you will be penalized, especially if the data to complete the analysis is provided in the context.
- For example as I said before if you say, metric x is 5% of total, and you know the total amount, you MUST calculate the value of metric x ie 5% of 1000 is 50.
- Put yourself in the shoes of the user and think like an analyst with 20 years of experience.
- VERY IMPORTANT: Before you return back your analysis, you MUST verify that you have completed the analysis and that you have not missed any data.
- Create a checklist of all the data you need to complete the analysis and verify that you have not missed any data.


**COMPREHENSIVE MULTI-FILE ANALYSIS METHODOLOGY:**

- MANY calculations will be dependent on your previous calculations. YOU MUST PROVIDE THESE CALCULATIONS IN YOUR SCRIPT AND ANALYSIS. This is MULTI-STEP ANALYSIS. For example, if you say, metric x is 5% of total, and you know the total amount, you MUST calculate the value of metric x ie 5% of 1000 is 50.


**Data Extraction & Validation:**
- Parse HTML tables systematically - they contain the most structured data
- Extract ALL numerical data, currency amounts, percentages, and calculation formulas
- Cross-reference data between files to identify relationships and dependencies
- Validate data completeness by checking for missing values, gaps, or inconsistencies
- Verify calculations using provided formulas, rates, and conversion factors

**Analysis Depth Requirements:**
- Perform percentage calculations and ratio analysis between data sources
- Calculate totals, subtotals, and derived metrics from multiple file sources
- Identify cost drivers, assumptions, and variable factors affecting outcomes
- Apply all relevant fees, taxes, surcharges, and adjustment factors
- Consider time-based changes (annual increases, contract terms, escalations)

**Completeness Verification:**
- Cross-check that all cost components from each file are included in final analysis
- Verify that percentages add up correctly and relationships are maintained
- Ensure no line items, fees, or cost elements are missed or double-counted
- Validate that exchange rates, minimums, and calculation methods are properly applied
- Perform sanity checks on final totals and breakdowns

**Professional Analysis Standards:**
- Categorize costs appropriately (one-time, recurring, variable, conditional)
- Document all assumptions, exclusions, and calculation methodologies
- Provide detailed line-item breakdowns with source references
- Include sensitivity analysis for key variables and assumptions
- Present comprehensive cost scenarios and total cost of ownership perspectives

"""

        config["configurable"][
            "type==default/system_message"
        ] = f"""
You are a helpful assistant. Today's date is {datetime.now().strftime('%Y-%m-%d')}. {retrieval_prompt} {data_analysis_prompt} {multi_file_guidance}

CRITICAL: Use DaytonaCodeSandbox subgraph when analysis requires code execution, data processing, multi-file synthesis, calculations, or file generation. For simple explanations or discussions, respond directly.

IMPORTANT: When file data is provided in context, work directly with that data. Do not attempt to import, read, or load external files - use the provided context data in your analysis.

ANALYSIS THOROUGHNESS: When performing multi-file analysis, conduct comprehensive calculations, cross-validation, and completeness checks. Apply all relevant percentages, fees, and formulas. Verify that no data is missed and all relationships between files are properly analyzed.

DATA OUTPUT FORMATTING: When creating reports or analysis outputs, structure data in clean, professional HTML tables for better readability and machine processing. Use proper table headers, clear categorization, and precise numerical formatting.
"""

        if multimodal_input:
            config["configurable"][
                "type==default/system_message"
            ] += " The user has provided an image. Use your multimodal capabilities to answer questions related to the image, do not use a tool to process the image."

        config["configurable"]["type==default/subgraphs"] = {
            "financial_analysis": {
                "description": "This subgraph is used to analyze financial data and return the a comprehensive report. KEY TRIGGER TERMS: Use this when the user says 'get financials' or 'analyze financials' for a single company.",
                "next_node": END,
                "graph": create_financial_analysis_graph(
                    redis_client=self.redis_client,
                    user_id=user_id,
                    api_keys=config["configurable"].get("api_keys") if admin_enabled else None
                ),
                "state_input_mapper": lambda x: [HumanMessage(content=x)],
                "state_output_mapper": lambda x: x[-1],
            },
            "deep_research": {
                "description": "This subgraph generates comprehensive research reports with multiple perspectives, sources, and analysis. KEY TRIGGER TERM: Use this when the user says 'deep research'. Also use when the user requests: detailed research, in-depth analysis, comprehensive reports, market research, academic research, or thorough investigation of any topic. IMPORTANT: Pass the user's specific research question or topic as a clear, focused query. Extract the core research intent from the user's message and formulate it as a specific research question or topic statement. Examples: 'AI impact on healthcare industry', 'sustainable energy solutions for developing countries', 'cryptocurrency market trends 2024'.",
                "next_node": END,
                "graph": create_deep_research_graph(
                    api_key=api_key_to_use,
                    provider=provider,
                    request_timeout=120,
                    redis_storage=self.message_storage,
                    user_id=user_id,
                    api_keys=config["configurable"].get("api_keys") if admin_enabled else None,
                ),
                "state_input_mapper": lambda x: {"topic": x},
                "state_output_mapper": lambda x: AIMessage(
                    content=x["final_report"],
                    name="DeepResearch",
                    additional_kwargs={
                        "agent_type": "deep_research_end",
                        "pdf_report": x["pdf_report"],
                    },
                ),
            },
            "DaytonaCodeSandbox": {
                "description": "This subgraph executes Python code in a secure sandbox environment. Use for: data exploration, basic analysis, code debugging, file operations, simple calculations, data visualization, multi-file analysis, report generation, and any general programming tasks. Perfect for examining datasets, creating plots, running straightforward code snippets, and combining data from multiple uploaded files. PRIORITY CHOICE for multi-file analysis tasks.",
                "next_node": "agent",
                "graph": create_code_execution_graph(
                    user_id=user_id,
                    sambanova_api_key=api_key_to_use,
                    redis_storage=self.message_storage,
                    daytona_manager=daytona_manager,
                    api_keys=config["configurable"].get("api_keys") if admin_enabled else None,
                ),
                "state_input_mapper": lambda x: {
                    "code": x,
                    "current_retry": 0,
                    "max_retries": 5,
                    "steps_taken": [],
                    "error_detected": False,
                    "final_result": "",
                    "corrections_proposed": [],
                    "files": [],
                },
                "state_output_mapper": lambda x: LiberalFunctionMessage(
                    name="DaytonaCodeSandbox",
                    content="\n".join(x["steps_taken"]),
                    additional_kwargs={
                        "agent_type": "tool_response",
                        "timestamp": datetime.now().isoformat(),
                        "files": x["files"],
                    },
                    # TODO: Mesure latency for code execution
                    result={"useage": {"total_latency": 0.0}},
                ),
            },
        }

        # Add retrieval tool, but with modified description for multi-file scenarios
        if indexed_doc_ids:
            retrieval_description = RETRIEVAL_DESCRIPTION
            if multi_file_analysis:
                retrieval_description = """Can be used to look up specific information from individual documents. 
For comprehensive analysis combining multiple files, prefer using the DaytonaCodeSandbox subgraph instead."""
            
            tools_config.append(
                {
                    "type": "retrieval",
                    "config": {
                        "user_id": user_id,
                        "doc_ids": indexed_doc_ids,
                        "description": retrieval_description,
                        "api_key": api_key_to_use,
                        "redis_client": self.sync_redis_client,
                    },
                }
            )

        if enable_data_science:
            config["configurable"]["type==default/subgraphs"]["data_science"] = {
                "description": "This subgraph performs comprehensive end-to-end data science workflows with multiple specialized agents. Use ONLY for complex projects requiring: machine learning model development, predictive analytics, statistical modeling, hypothesis testing, or multi-step data science pipelines. IMPORTANT: Pass the user's natural language request (e.g., 'build a machine learning model to predict customer churn', 'perform statistical analysis on sales trends'), NOT code. Do NOT use for simple data exploration - use DaytonaCodeSandbox instead.",
                "next_node": END,
                "graph": create_data_science_subgraph(
                    user_id=user_id,
                    sambanova_api_key=api_key_to_use,
                    redis_storage=self.message_storage,
                    daytona_manager=daytona_manager,
                    directory_content=directory_content,
                    api_keys=config["configurable"].get("api_keys") if admin_enabled else None,
                ),
                "state_input_mapper": lambda x: {
                    "internal_messages": [
                        HumanMessage(content=x, id=str(uuid.uuid4()))
                    ],
                    "hypothesis": "",
                    "process": "",
                    "process_decision": None,
                    "visualization_state": "",
                    "searcher_state": "",
                    "code_state": "",
                    "report_section": "",
                    "quality_review": "",
                    "needs_revision": False,
                    "sender": "",
                },
                "state_output_mapper": lambda x: x["internal_messages"][-1].model_copy(
                    update={
                        "additional_kwargs": {
                            **(x["internal_messages"][-1].additional_kwargs or {}),
                            "agent_type": "data_science_end",
                        }
                    }
                ),
            }

        # Load static tools
        all_tools = await load_static_tools(tools_config)
        
        # Load connector tools for the user
        try:
            from agents.connectors.core.connector_manager import get_connector_manager
            connector_manager = get_connector_manager()
            if connector_manager:
                connector_tools = await connector_manager.get_user_tools(user_id)
                all_tools.extend(connector_tools)
                logger.info(
                    "Loaded connector tools for user",
                    user_id=user_id,
                    num_connector_tools=len(connector_tools),
                    total_tools=len(all_tools)
                )
        except Exception as e:
            logger.error(
                "Failed to load connector tools",
                user_id=user_id,
                error=str(e)
            )
        
        config["configurable"]["type==default/tools"] = all_tools
        config["configurable"]["agent_type"] = "default"

        return config
