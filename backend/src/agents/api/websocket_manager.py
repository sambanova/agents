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
                api_keys = APIKeys(
                    sambanova_key=redis_api_keys.sambanova_key,
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

                await self.message_storage.update_metadata(
                    user_message_input["data"], user_id, conversation_id
                )

                input_, model, multimodal_input = await self.create_user_message_input(
                    user_id, user_message_input
                )

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
            session_key = f"{user_id}:{conversation_id}"
            websocket = self.connections.get(session_key)

            if "event" in data and data["event"] in [
                "agent_completion",
                "stream_complete",
                "stream_start",
            ]:

                if "id" in data:
                    if data["id"] is None:
                        pass
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

            # Just try to send - most reliable way to detect if connection is still active
            return await self._safe_send(websocket, data)
        except Exception as e:
            logger.error("Error sending WebSocket message", error=str(e))
            return False

    async def _load_file_context_for_analysis(self, user_id: str, doc_ids: list) -> str:
        """Load file contents to provide as context for multi-file analysis."""
        file_context = "## UPLOADED FILES CONTEXT:\n\n"
        
        for doc_id in doc_ids:
            try:
                file_data, metadata = await self.message_storage.get_file(user_id, doc_id["id"])
                if file_data and metadata:
                    filename = metadata.get("filename", f"file_{doc_id['id']}")
                    file_format = metadata.get("format", "unknown")
                    
                    file_context += f"### File: {filename} (Format: {file_format})\n"
                    
                    # Handle different file types
                    if file_format == "text/csv":
                        # For CSV files, provide complete content for comprehensive analysis
                        try:
                            content = file_data.decode('utf-8')
                            # Provide complete CSV content - essential for accurate analysis
                            file_context += f"```csv\n{content}\n```\n\n"
                        except UnicodeDecodeError:
                            file_context += "Binary CSV file content (use pandas to read in analysis)\n\n"
                    
                    elif file_format == "application/pdf":
                        # For PDFs, extract and provide the actual text content
                        try:
                            pdf_text = await self._extract_pdf_text(file_data)
                            if pdf_text.strip():
                                # Provide complete PDF content for comprehensive analysis
                                file_context += f"```\n{pdf_text}\n```\n\n"
                            else:
                                file_context += "PDF document - Could not extract readable text content.\n\n"
                        except Exception as e:
                            logger.warning(f"Could not extract PDF text for {filename}: {str(e)}")
                            file_size = len(file_data)
                            file_context += f"PDF document ({file_size} bytes) - Could not extract text, but file is available for analysis.\n\n"
                    
                    elif file_format in ["text/plain", "text/markdown"]:
                        # For text files, show complete content
                        try:
                            content = file_data.decode('utf-8')
                            file_context += f"```\n{content}\n```\n\n"
                        except UnicodeDecodeError:
                            file_context += "Binary text file content\n\n"
                    
                    elif file_format in ["application/vnd.openxmlformats-officedocument.wordprocessingml.document", "application/msword"]:
                        # For Word documents, provide basic info and note they're available
                        file_size = len(file_data)
                        file_context += f"Word document ({file_size} bytes) - Available for text extraction and analysis.\n"
                        file_context += "Use document processing tools to extract content if needed.\n\n"
                    
                    elif file_format in ["application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "application/vnd.ms-excel"]:
                        # For Excel files, provide basic info
                        file_size = len(file_data)
                        file_context += f"Excel spreadsheet ({file_size} bytes) - Available for data analysis.\n"
                        file_context += "Use pandas or similar tools to read and analyze the data.\n\n"
                    
                    else:
                        # For other file types, provide basic info
                        file_size = len(file_data)
                        file_context += f"File format: {file_format}, Size: {file_size} bytes\n"
                        file_context += "File is available for processing in the analysis environment.\n\n"
                        
            except Exception as e:
                logger.warning(f"Could not load context for file {doc_id['id']}: {str(e)}")
                file_context += f"### File: {doc_id.get('filename', 'unknown')} - Could not load content\n\n"
        
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
        
        for doc_id in doc_ids:
            all_file_ids.append(doc_id["id"])
            if doc_id["indexed"]:
                indexed_doc_ids.append(doc_id["id"])
            if doc_id["format"] == "text/csv":
                data_analysis_doc_ids.append(doc_id["id"])
                directory_content.append(doc_id["filename"])

        enable_data_science = False
        if data_analysis_doc_ids:
            enable_data_science = True
            
        # Detect multi-file uploads that should bypass retrieval and go directly to sandbox
        # This handles cases like CSV + PDF combinations for comprehensive analysis
        multi_file_analysis = len(doc_ids) > 1 and any(
            doc_id["format"] in ["text/csv", "application/pdf", "text/plain", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"]
            for doc_id in doc_ids
        )

        retrieval_prompt = ""
        if indexed_doc_ids:
            retrieval_prompt = (
                f"{len(doc_ids)} documents are available for retrieval.\n\n"
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

        config = {
            "configurable": {
                "type==default/user_id": user_id,
                "type==default/llm_type": llm_type,
                "thread_id": thread_id,
                "user_id": user_id,
                "api_key": api_keys.sambanova_key,
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
                "description": "This subgraph is used to analyze financial data and return the a comprehensive report.",
                "next_node": END,
                "graph": create_financial_analysis_graph(self.redis_client),
                "state_input_mapper": lambda x: [HumanMessage(content=x)],
                "state_output_mapper": lambda x: x[-1],
            },
            "deep_research": {
                "description": "This subgraph generates comprehensive research reports with multiple perspectives, sources, and analysis. Use when the user requests: detailed research, in-depth analysis, comprehensive reports, market research, academic research, or thorough investigation of any topic. IMPORTANT: Pass the user's specific research question or topic as a clear, focused query. Extract the core research intent from the user's message and formulate it as a specific research question or topic statement. Examples: 'AI impact on healthcare industry', 'sustainable energy solutions for developing countries', 'cryptocurrency market trends 2024'.",
                "next_node": END,
                "graph": create_deep_research_graph(
                    api_key=api_keys.sambanova_key,
                    provider="sambanova",
                    request_timeout=120,
                    redis_storage=self.message_storage,
                    user_id=user_id,
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
                    sambanova_api_key=api_keys.sambanova_key,
                    redis_storage=self.message_storage,
                    daytona_manager=daytona_manager,
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
                        "api_key": api_keys.sambanova_key,
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
                    sambanova_api_key=api_keys.sambanova_key,
                    redis_storage=self.message_storage,
                    daytona_manager=daytona_manager,
                    directory_content=directory_content,
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

        all_tools = await load_static_tools(tools_config)
        config["configurable"]["type==default/tools"] = all_tools
        config["configurable"]["agent_type"] = "default"

        return config
