from datetime import datetime, timedelta, timezone
import os
from agents.components.compound.assistant import get_assistant
from agents.components.compound.financial_analysis_subgraph import (
    create_financial_analysis_subgraph,
)
from agents.components.compound.simple_subgraph_example import (
    create_simple_analyzer_subgraph,
    create_simple_greeter_subgraph,
)
from autogen_core import DefaultTopicId
from fastapi import WebSocket, WebSocketDisconnect
import json
import asyncio
from typing import Optional, Dict
import redis
from starlette.websockets import WebSocketState

from agents.api.data_types import (
    APIKeys,
    EndUserMessage,
    AgentEnum,
    AgentStructuredResponse,
    ErrorResponse,
)
from agents.api.utils import (
    load_documents,
    DocumentContextLengthError,
)

from agents.components.compound.agent import agent
from agents.api.websocket_interface import WebSocketInterface
from agents.storage.redis_service import SecureRedisService
from agents.storage.redis_storage import RedisStorage

from agents.utils.logging import logger


class WebSocketConnectionManager(WebSocketInterface):
    """
    Manages WebSocket connections for user sessions.
    """

    def __init__(
        self, redis_client: SecureRedisService, context_length_summariser: int
    ):
        # Use user_id:conversation_id as the key
        self.connections: Dict[str, WebSocket] = {}
        self.redis_client = redis_client
        self.message_storage = RedisStorage(redis_client)
        self.context_length_summariser = context_length_summariser
        # Add state storage for active connections
        self.active_sessions: Dict[str, dict] = {}
        # Track last activity time for each session
        self.session_last_active: Dict[str, datetime] = {}
        # Session timeout (5 minutes)
        self.SESSION_TIMEOUT = timedelta(minutes=10)
        # Store pubsub instances
        self.pubsub_instances: Dict[str, redis.client.PubSub] = {}
        # Add cleanup task
        self.cleanup_task: Optional[asyncio.Task] = None

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

    async def cleanup_inactive_sessions(self):
        """Cleanup sessions that have been inactive for longer than SESSION_TIMEOUT"""
        current_time = datetime.now()
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
                        f"Session {session_key} marked for cleanup: last_active={last_active}, is_active={session.get('is_active', False)}"
                    )

        for session_key in sessions_to_cleanup:
            await self._cleanup_session(session_key)
            logger.info(f"Cleaned up inactive session: {session_key}")

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
                    session["pubsub"].close()
                except:
                    pass
                # Also remove from pubsub_instances
                self.pubsub_instances.pop(session_key, None)

            if "agent_runtime" in session and session["agent_runtime"] is not None:
                cleanup_tasks.append(
                    asyncio.create_task(session["agent_runtime"].close())
                )

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

        from agents.components.compound.agent import agent
        from langchain_core.messages import HumanMessage

        agent_runtime = None
        background_task = None
        session_key = f"{user_id}:{conversation_id}"
        channel = f"agent_thoughts:{user_id}:{conversation_id}"

        try:
            # Initialize or update session state
            if session_key not in self.active_sessions:
                # Create new pubsub instance for new session
                pubsub = self.redis_client.pubsub(ignore_subscribe_messages=True)
                await asyncio.to_thread(pubsub.subscribe, channel)
                self.pubsub_instances[session_key] = pubsub

                self.active_sessions[session_key] = {
                    "agent_runtime": None,
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
                    await asyncio.to_thread(pubsub.subscribe, channel)
                    self.active_sessions[session_key]["pubsub"] = pubsub
                    self.pubsub_instances[session_key] = pubsub

                self.active_sessions[session_key]["websocket"] = websocket
                self.active_sessions[session_key]["is_active"] = True

            # Update session activity time
            self.session_last_active[session_key] = datetime.now(timezone.utc)

            # Check if we have an existing session state to restore
            session = self.active_sessions[session_key]
            agent_runtime = session.get("agent_runtime")
            background_task = session.get("background_task")
            pubsub = session["pubsub"]  # We know this exists now

            # Pre-compute keys that will be used throughout the session
            meta_key = f"chat_metadata:{user_id}:{conversation_id}"
            message_key = f"messages:{user_id}:{conversation_id}"
            api_keys_key = f"api_keys:{user_id}"

            # Initial setup tasks that can run concurrently
            setup_tasks = [
                asyncio.to_thread(self.redis_client.exists, meta_key),
                asyncio.to_thread(self.redis_client.hgetall, api_keys_key, user_id),
            ]

            # Wait for all setup tasks to complete
            exists, redis_api_keys = await asyncio.gather(*setup_tasks)

            if not exists:
                await websocket.close(code=4004, reason="Conversation not found")
                return

            if not redis_api_keys:
                await websocket.close(code=4006, reason="No API keys found")
                return

            # Accept connection
            self.add_connection(websocket, user_id, conversation_id)

            if os.getenv("ENABLE_USER_KEYS") == "true":
                api_keys = APIKeys(
                    sambanova_key=redis_api_keys.get("sambanova_key", ""),
                    fireworks_key=redis_api_keys.get("fireworks_key", ""),
                    serper_key=redis_api_keys.get("serper_key", ""),
                    exa_key=redis_api_keys.get("exa_key", ""),
                )
            else:
                # Initialize API keys object
                api_keys = APIKeys(
                    sambanova_key=redis_api_keys.get("sambanova_key", ""),
                    fireworks_key=os.getenv("FIREWORKS_KEY", ""),
                    serper_key=os.getenv("SERPER_KEY", ""),
                    exa_key=os.getenv("EXA_KEY", ""),
                )

            # Start background task for Redis messages if not restored
            if not background_task or background_task.done():
                background_task = asyncio.create_task(
                    self.handle_redis_messages(
                        websocket, pubsub, user_id, conversation_id
                    )
                )

            # Store session state
            self.active_sessions[session_key] = {
                "agent_runtime": agent_runtime,
                "background_task": background_task,
                "websocket": websocket,  # Store websocket reference
                "is_active": True,  # Track connection state
                "pubsub": pubsub,
            }

            # Send connection established message
            asyncio.create_task(
                websocket.send_json(
                    {
                        "event": "connection_established",
                        "data": "WebSocket connection established",
                        "user_id": user_id,
                        "conversation_id": conversation_id,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    }
                )
            )

            # Handle incoming WebSocket messages
            while True:
                # Check if connection is still active
                if not self.active_sessions.get(session_key, {}).get(
                    "is_active", False
                ):
                    break

                user_message_text = await websocket.receive_text()
                # Update session activity time on each message
                self.session_last_active[session_key] = datetime.now(timezone.utc)

                try:
                    user_message_input = json.loads(user_message_text)
                except json.JSONDecodeError:
                    asyncio.create_task(
                        websocket.send_json(
                            {
                                "event": "error",
                                "data": "Invalid JSON message format",
                                "user_id": user_id,
                                "conversation_id": conversation_id,
                                "timestamp": datetime.now(timezone.utc).isoformat(),
                            }
                        )
                    )
                    continue

                # Check provider and validate corresponding API key
                provider = user_message_input["provider"]
                if provider == "sambanova":
                    if api_keys.sambanova_key == "":
                        await websocket.close(
                            code=4007, reason="SambaNova API key required but not found"
                        )
                        return
                elif provider == "fireworks":
                    if api_keys.fireworks_key == "":
                        await websocket.close(
                            code=4008, reason="Fireworks API key required but not found"
                        )
                        return
                else:
                    await websocket.close(
                        code=4009, reason="Invalid or missing provider"
                    )
                    return

                # Prepare tasks for parallel execution
                tasks = [
                    self._update_metadata(
                        meta_key, user_message_input["data"], user_id
                    ),
                ]

                # Add document loading to parallel tasks if present
                document_content = None
                if (
                    "document_ids" in user_message_input
                    and user_message_input["document_ids"]
                ):
                    tasks.append(
                        asyncio.to_thread(
                            load_documents,
                            user_id,
                            user_message_input["document_ids"],
                            self.redis_client,
                            self.context_length_summariser,
                        )
                    )

                try:
                    # Execute all tasks in parallel
                    results = await asyncio.gather(*tasks)
                except DocumentContextLengthError as e:
                    logger.info(f"Document context length error: {str(e)}")
                    response = AgentStructuredResponse(
                        agent_type=AgentEnum.Error,
                        data=ErrorResponse(
                            error="The documents you are trying to add exceed the allowable size."
                        ),
                        message=f"Error processing deep research request: {str(e)}",
                        message_id=user_message_input["message_id"],
                        sender="error_handler",
                    )
                    await agent_runtime.publish_message(
                        response,
                        DefaultTopicId(
                            type="user_proxy", source=f"{user_id}:{conversation_id}"
                        ),
                    )
                    continue

                if (
                    "document_ids" in user_message_input
                    and user_message_input["document_ids"]
                ):
                    document_content = results[2]

                logger.info(
                    f"Received message from user: {user_id} in conversation: {conversation_id}"
                )

                config = await _run_input_and_config(
                    user_id=user_id,
                    thread_id=conversation_id,
                    api_keys=api_keys,
                    provider=user_message_input["provider"],
                    message_id=user_message_input["message_id"],
                )

                input_ = HumanMessage(
                    content=user_message_input["data"],
                    additional_kwargs={"timestamp": user_message_input["timestamp"]},
                )

                config["configurable"]["type==default/subgraphs"] = {
                    "financial_analysis": create_financial_analysis_subgraph(
                        self.redis_client
                    ),
                }

                # Stream the response directly via WebSocket
                await agent.astream_websocket(
                    input=input_,
                    config=config,
                    websocket_manager=self,
                    user_id=user_id,
                    conversation_id=conversation_id,
                    message_id=user_message_input["message_id"],
                )

        except WebSocketDisconnect:
            logger.info(
                f"WebSocket connection closed for conversation: {conversation_id}"
            )
            if session_key in self.active_sessions:
                # Only mark the connection as inactive, don't terminate the session
                self.active_sessions[session_key]["is_active"] = False
            self.remove_connection(user_id, conversation_id)
        except Exception as e:
            logger.error(
                f"Exception in WebSocket connection for conversation {conversation_id}: {str(e)}"
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
                logger.error(f"Error closing websocket: {str(e)}")

            # Update last active time on disconnect
            if session_key in self.session_last_active:
                self.session_last_active[session_key] = datetime.now(timezone.utc)

    async def _update_metadata(self, meta_key: str, message_data: str, user_id: str):
        """Helper method to update metadata asynchronously"""
        try:
            meta_data = await asyncio.to_thread(
                self.redis_client.get, meta_key, user_id
            )
            if meta_data:
                metadata = json.loads(meta_data)
                if "name" not in metadata:
                    metadata["name"] = message_data
                    await asyncio.to_thread(
                        self.redis_client.set, meta_key, json.dumps(metadata), user_id
                    )
        except Exception as e:
            logger.error(f"Error updating metadata: {str(e)}")

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
                        message = pubsub.get_message(timeout=0.05)
                        if message and message["type"] == "message":
                            messages.append(message)
                        if not message:
                            break
                    except Exception as e:
                        logger.error(f"Error getting Redis message: {str(e)}")
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
                            await asyncio.to_thread(
                                self.redis_client.rpush,
                                message_key,
                                json.dumps(message_data),
                                user_id,
                            )

                            # Then try to send via WebSocket if still active
                            if self.active_sessions.get(session_key, {}).get(
                                "is_active", False
                            ):
                                await self._safe_send(websocket, message_data)

                        except Exception as e:
                            logger.error(f"Error processing Redis message: {str(e)}")
                            continue

                await asyncio.sleep(0.2)

        except Exception as e:
            logger.error(f"Error in Redis message handler: {str(e)}")
        finally:
            # Update session activity time before exiting
            self.session_last_active[session_key] = datetime.now(timezone.utc)

    async def _safe_send(self, websocket: WebSocket, data: dict) -> bool:
        """
        Safely send a message through the WebSocket with state checking.
        """
        try:
            # Get session key from websocket
            for key, session in self.active_sessions.items():
                if session.get("websocket") == websocket:
                    if not session.get("is_active", False):
                        return False
                    break

            if (
                websocket.client_state != WebSocketState.DISCONNECTED
                and websocket.application_state != WebSocketState.DISCONNECTED
            ):
                await websocket.send_json(data)
                return True
            return False
        except Exception as e:
            logger.error(f"Error sending WebSocket message: {str(e)}")
            return False

    async def send_message(
        self, user_id: str, conversation_id: str, data: dict
    ) -> bool:
        """Send a message through the WebSocket for a specific conversation."""
        try:
            session_key = f"{user_id}:{conversation_id}"
            websocket = self.connections.get(session_key)

            if "event" in data and data["event"] == "agent_completion":
                was_saved = await self.message_storage.save_message_if_new(
                    user_id, conversation_id, data
                )

                if not was_saved:
                    return True  # Still successful, just skipped duplicate

            if not websocket:
                logger.info(f"No WebSocket connection found for {session_key}")
                return False

            if (
                websocket.client_state != WebSocketState.DISCONNECTED
                and websocket.application_state != WebSocketState.DISCONNECTED
            ):
                await websocket.send_text(json.dumps(data))
                return True
            return False
        except Exception as e:
            logger.error(f"Error sending WebSocket message: {str(e)}")
            return False


from langchain_core.runnables import RunnableConfig


# TODO: move this
async def _run_input_and_config(
    user_id: str,
    thread_id: str,
    api_keys: APIKeys,
    provider: str,
    message_id: str,
):
    # thread = await get_thread(user_id, payload.thread_id)
    # if not thread:
    #     raise HTTPException(status_code=404, detail="Thread not found")

    # assistant = await get_assistant(user_id, str(thread.assistant_id))
    # if not assistant:
    #     raise HTTPException(status_code=404, detail="Assistant not found")

    assistant = get_assistant(
        user_id=user_id,
        llm_type="DeepSeek V3",
    )

    if provider == "sambanova":
        api_key = api_keys.sambanova_key
    else:
        raise ValueError("Unsupported provider")

    config: RunnableConfig = {
        **assistant.config,
        "configurable": {
            **assistant.config["configurable"],
            "thread_id": thread_id,
            "user_id": user_id,
            "api_key": api_key,
            "message_id": message_id,
        },
    }

    return config
