from datetime import datetime, timedelta
from autogen_core import DefaultTopicId
from fastapi import WebSocket, WebSocketDisconnect
import json
import asyncio
from typing import Optional, Dict
import redis
from starlette.websockets import WebSocketState

from api.data_types import APIKeys, EndUserMessage, AgentEnum, AgentStructuredResponse, ErrorResponse
from api.utils import initialize_agent_runtime, load_documents, DocumentContextLengthError
from api.websocket_interface import WebSocketInterface

from .otlp_tracing import logger


class WebSocketConnectionManager(WebSocketInterface):
    """
    Manages WebSocket connections for user sessions.
    """

    def __init__(self, redis_client: redis.Redis, context_length_summariser: int):
        # Use user_id:conversation_id as the key
        self.connections: Dict[str, WebSocket] = {}
        self.redis_client = redis_client
        self.context_length_summariser = context_length_summariser
        # Add state storage for active connections
        self.active_sessions: Dict[str, dict] = {}
        # Track last activity time for each session
        self.session_last_active: Dict[str, datetime] = {}
        # Session timeout (30 minutes)
        self.SESSION_TIMEOUT = timedelta(minutes=30)

    def add_connection(self, websocket: WebSocket, user_id: str, conversation_id: str) -> None:
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
            if current_time - last_active > self.SESSION_TIMEOUT:
                sessions_to_cleanup.append(session_key)

        for session_key in sessions_to_cleanup:
            await self._cleanup_session(session_key)

    async def _cleanup_session(self, session_key: str):
        """Clean up a specific session and its resources"""
        if session_key in self.active_sessions:
            session = self.active_sessions[session_key]
            cleanup_tasks = []

            if 'background_task' in session and session['background_task'] is not None:
                session['background_task'].cancel()
                cleanup_tasks.append(session['background_task'])

            if 'pubsub' in session and session['pubsub'] is not None:
                cleanup_tasks.extend([
                    asyncio.create_task(asyncio.to_thread(session['pubsub'].unsubscribe)),
                    asyncio.create_task(asyncio.to_thread(session['pubsub'].close))
                ])

            if 'agent_runtime' in session and session['agent_runtime'] is not None:
                cleanup_tasks.append(asyncio.create_task(session['agent_runtime'].close()))

            if cleanup_tasks:
                await asyncio.gather(*cleanup_tasks, return_exceptions=True)

            del self.active_sessions[session_key]
            self.session_last_active.pop(session_key, None)
            logger.info(f"Cleaned up inactive session: {session_key}")

    async def handle_websocket(self, websocket: WebSocket, user_id: str, conversation_id: str):
        """
        Handles incoming WebSocket messages and manages connection lifecycle.
        """
        agent_runtime = None
        pubsub = None
        background_task = None
        session_key = f"{user_id}:{conversation_id}"

        try:
            # Update session activity time
            self.session_last_active[session_key] = datetime.now()

            # Check if we have an existing session
            if session_key in self.active_sessions:
                # Restore previous session state
                session = self.active_sessions[session_key]
                agent_runtime = session.get('agent_runtime')
                pubsub = session.get('pubsub')
                background_task = session.get('background_task')

                # Update the websocket reference without recreating the agent runtime
                session['websocket'] = websocket
                session['is_active'] = True

            # Pre-compute keys that will be used throughout the session
            meta_key = f"chat_metadata:{user_id}:{conversation_id}"
            message_key = f"messages:{user_id}:{conversation_id}"
            api_keys_key = f"api_keys:{user_id}"
            source = f"{user_id}:{conversation_id}"
            channel = f"agent_thoughts:{source}"

            # Initial setup tasks that can run concurrently
            setup_tasks = [
                asyncio.to_thread(self.redis_client.exists, meta_key),
                asyncio.to_thread(self.redis_client.hgetall, api_keys_key),
            ]

            # Only create new pubsub if not restored from session
            if not pubsub:
                setup_tasks.append(asyncio.to_thread(
                    lambda: self.redis_client.pubsub(ignore_subscribe_messages=True)
                ))

            # Wait for all setup tasks to complete
            results = await asyncio.gather(*setup_tasks)
            exists, redis_api_keys = results[:2]
            if not pubsub and len(results) > 2:
                pubsub = results[2]

            if not exists:
                await websocket.close(code=4004, reason="Conversation not found")
                return

            if not redis_api_keys:
                await websocket.close(code=4006, reason="No API keys found")
                return

            # Accept connection and subscribe to channel
            self.add_connection(websocket, user_id, conversation_id)

            # Subscribe to channel if not already subscribed
            if not pubsub.patterns:
                await asyncio.to_thread(pubsub.subscribe, channel)

            # Initialize API keys object
            api_keys = APIKeys(
                sambanova_key=redis_api_keys.get("sambanova_key", ""),
                fireworks_key=redis_api_keys.get("fireworks_key", ""),
                serper_key=redis_api_keys.get("serper_key", ""),
                exa_key=redis_api_keys.get("exa_key", "")
            )

            api_keys = APIKeys(
                sambanova_key="9327289d-a701-4782-93dc-91c33cff59e8",
                fireworks_key=redis_api_keys.get("fireworks_key", ""),
                serper_key=redis_api_keys.get("serper_key", ""),
                exa_key=redis_api_keys.get("exa_key", ""),
                extra_headers={
                    "SNUserId": "tamas.jambor@sambanovasystems.com",
                    # "SNUserId": "kwasi.ankomah@sambanovasystems.com",
                    # "SNUserId": "chandan.rajah@sambanovasystems.com",
                }
            )

            # Initialize agent runtime if not restored from session
            if not agent_runtime:
                try:
                    agent_runtime = await initialize_agent_runtime(
                        redis_client=self.redis_client,
                        api_keys=api_keys,
                        user_id=user_id,
                        conversation_id=conversation_id,
                        websocket_manager=self
                    )
                except Exception as e:
                    logger.error(f"Failed to initialize agent runtime: {str(e)}")
                    await websocket.close(code=4005, reason="Failed to initialize agent runtime")
                    return

            # Start background task for Redis messages if not restored
            if not background_task or background_task.done():
                background_task = asyncio.create_task(
                    self.handle_redis_messages(websocket, pubsub, user_id, conversation_id)
                )

            # Store session state
            self.active_sessions[session_key] = {
                'agent_runtime': agent_runtime,
                'pubsub': pubsub,
                'background_task': background_task,
                'websocket': websocket,  # Store websocket reference
                'is_active': True  # Track connection state
            }

            # Send connection established message
            asyncio.create_task(websocket.send_json({
                "event": "connection_established",
                "data": "WebSocket connection established",
                "user_id": user_id,
                "conversation_id": conversation_id,
                "timestamp": datetime.now().isoformat()
            }))

            # Handle incoming WebSocket messages
            while True:
                # Check if connection is still active
                if not self.active_sessions.get(session_key, {}).get('is_active', False):
                    break

                user_message_text = await websocket.receive_text()
                # Update session activity time on each message
                self.session_last_active[session_key] = datetime.now()

                try:
                    user_message_input = json.loads(user_message_text)
                except json.JSONDecodeError:
                    asyncio.create_task(websocket.send_json({
                        "event": "error",
                        "data": "Invalid JSON message format",
                        "user_id": user_id,
                        "conversation_id": conversation_id,
                        "timestamp": datetime.now().isoformat()
                    }))
                    continue

                # Check provider and validate corresponding API key
                provider = user_message_input["provider"]
                if provider == "sambanova":
                    if api_keys.sambanova_key == "":
                        await websocket.close(code=4007, reason="SambaNova API key required but not found")
                        return
                elif provider == "fireworks":
                    if api_keys.fireworks_key == "":
                        await websocket.close(code=4008, reason="Fireworks API key required but not found") 
                        return
                else:
                    await websocket.close(code=4009, reason="Invalid or missing provider")
                    return

                # Create message data once
                message_data = {
                    "event": "user_message", 
                    "data": user_message_input["data"],
                    "user_id": user_id,
                    "conversation_id": conversation_id,
                    "message_id": user_message_input["message_id"],
                    "timestamp": user_message_input["timestamp"]
                }

                # Prepare tasks for parallel execution
                tasks = [
                    self._update_metadata(meta_key, user_message_input["data"]),
                    asyncio.to_thread(
                        self.redis_client.rpush,
                        message_key,
                        json.dumps(message_data)
                    )
                ]

                # Add document loading to parallel tasks if present
                document_content = None
                if "document_ids" in user_message_input and user_message_input["document_ids"]:
                    tasks.append(asyncio.to_thread(
                        load_documents,
                        user_id,
                        user_message_input["document_ids"],
                        self.redis_client,
                        self.context_length_summariser,
                    ))

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
                        sender="error_handler"
                    )
                    await agent_runtime.publish_message(
                        response,
                        DefaultTopicId(type="user_proxy", source=source),
                    )
                    continue

                if "document_ids" in user_message_input and user_message_input["document_ids"]:
                    document_content = results[2]

                logger.info(f"Received message from user: {user_id} in conversation: {conversation_id}")

                # Create and publish user message
                user_message = EndUserMessage(
                    message_id=user_message_input["message_id"],
                    source="User",
                    content=user_message_input["data"], 
                    use_planner=False,
                    provider=user_message_input["provider"],
                    docs=document_content if "document_ids" in user_message_input and user_message_input["document_ids"] else None,
                    planner_model=user_message_input["planner_model"]
                )

                # This must be awaited as it affects the conversation flow
                await agent_runtime.publish_message(
                    user_message,
                    DefaultTopicId(type="user_proxy", source=source),
                )

        except WebSocketDisconnect:
            logger.info(f"WebSocket connection closed for conversation: {conversation_id}")
            if session_key in self.active_sessions:
                # Only mark the connection as inactive, don't terminate the session
                self.active_sessions[session_key]['is_active'] = False
            self.remove_connection(user_id, conversation_id)
        except Exception as e:
            logger.error(f"Exception in WebSocket connection for conversation {conversation_id}: {str(e)}")
            if session_key in self.active_sessions:
                self.active_sessions[session_key]['is_active'] = False
        finally:
            self.remove_connection(user_id, conversation_id)

            # Only close websocket if it hasn't been closed already
            try:
                if (websocket.client_state != WebSocketState.DISCONNECTED and 
                    websocket.application_state != WebSocketState.DISCONNECTED):
                    await websocket.close()
            except Exception as e:
                logger.error(f"Error closing websocket: {str(e)}")

            # Don't cleanup immediately on disconnect
            # Only check for truly inactive sessions based on timeout
            if session_key in self.session_last_active:
                current_time = datetime.now()
                last_active = self.session_last_active[session_key]
                if current_time - last_active > self.SESSION_TIMEOUT:
                    await self.cleanup_inactive_sessions()

    async def _update_metadata(self, meta_key: str, message_data: str):
        """Helper method to update metadata asynchronously"""
        try:
            meta_data = await asyncio.to_thread(self.redis_client.get, meta_key)
            if meta_data:
                metadata = json.loads(meta_data)
                if "name" not in metadata:
                    metadata["name"] = message_data
                    await asyncio.to_thread(
                        self.redis_client.set,
                        meta_key,
                        json.dumps(metadata)
                    )
        except Exception as e:
            logger.error(f"Error updating metadata: {str(e)}")

    async def handle_redis_messages(self, websocket: WebSocket, pubsub, user_id: str, conversation_id: str):
        """
        Background task to handle Redis pub/sub messages.
        """
        message_key = f"messages:{user_id}:{conversation_id}"
        session_key = f"{user_id}:{conversation_id}"
        BATCH_SIZE = 25

        try:
            while self.active_sessions.get(session_key, {}).get('is_active', False):
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
                            if not self.active_sessions.get(session_key, {}).get('is_active', False):
                                break

                            data_str = message["data"]
                            data_parsed = json.loads(data_str)
                            message_data = {
                                "event": "think",
                                "data": data_str,
                                "user_id": user_id,
                                "conversation_id": conversation_id,
                                "timestamp": datetime.now().isoformat(),
                                "message_id": data_parsed["message_id"]
                            }

                            # Store in Redis first
                            await asyncio.to_thread(
                                self.redis_client.rpush,
                                message_key,
                                json.dumps(message_data)
                            )

                            # Then try to send via WebSocket if still active
                            if self.active_sessions.get(session_key, {}).get('is_active', False):
                                await self._safe_send(websocket, message_data)

                        except Exception as e:
                            logger.error(f"Error processing Redis message: {str(e)}")
                            continue

                await asyncio.sleep(0.2)

        except Exception as e:
            logger.error(f"Error in Redis message handler: {str(e)}")
        finally:
            # Update session activity time before exiting
            self.session_last_active[session_key] = datetime.now()

    async def _safe_send(self, websocket: WebSocket, data: dict) -> bool:
        """
        Safely send a message through the WebSocket with state checking.
        """
        try:
            # Get session key from websocket
            for key, session in self.active_sessions.items():
                if session.get('websocket') == websocket:
                    if not session.get('is_active', False):
                        return False
                    break

            if (websocket.client_state != WebSocketState.DISCONNECTED and 
                websocket.application_state != WebSocketState.DISCONNECTED):
                await websocket.send_json(data)
                return True
            return False
        except Exception as e:
            logger.error(f"Error sending WebSocket message: {str(e)}")
            return False

    async def send_message(self, user_id: str, conversation_id: str, data: dict) -> bool:
        """Send a message through the WebSocket for a specific conversation."""
        try:
            session_key = f"{user_id}:{conversation_id}"
            websocket = self.connections.get(session_key)

            if not websocket:
                logger.error(f"No WebSocket connection found for {session_key}")
                return False

            if (websocket.client_state != WebSocketState.DISCONNECTED and 
                websocket.application_state != WebSocketState.DISCONNECTED):
                await websocket.send_text(json.dumps(data))
                return True
            return False
        except Exception as e:
            logger.error(f"Error sending WebSocket message: {str(e)}")
            return False
