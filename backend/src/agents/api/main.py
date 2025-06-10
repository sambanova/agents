from fastapi import (
    Depends,
    FastAPI,
    File,
    Query,
    Request,
    Response,
    UploadFile,
    WebSocket,
)
from fastapi_clerk_auth import (
    ClerkConfig,
    ClerkHTTPBearer,
    HTTPAuthorizationCredentials,
)
import jwt
from pydantic import BaseModel
import json
import uvicorn
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import time
import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import Optional, Dict, Any, List
from contextlib import asynccontextmanager
from fastapi.websockets import WebSocketState, WebSocketDisconnect

from agents.components.routing.user_proxy import UserProxyAgent
from agents.api.websocket_manager import WebSocketConnectionManager

from agents.api.data_types import APIKeys
from agents.utils.logging import logger
import os
import sys

import redis
import uuid

from agents.components.routing.route import SemanticRouterAgent

from agents.storage.redis_service import SecureRedisService
from agents.storage.redis_storage import RedisStorage

from agents.components.compound.xml_agent import (
    create_checkpointer,
    set_global_checkpointer,
)
from agents.tools.langgraph_tools import set_global_redis_storage_service

from agents.services.user_prompt_extractor_service import UserPromptExtractor
from agents.components.lead_generation_crew import ResearchCrew

# For financial analysis
from agents.services.financial_user_prompt_extractor_service import (
    FinancialPromptExtractor,
)
from agents.components.financial_analysis.financial_analysis_crew import (
    FinancialAnalysisCrew,
)

# For document processing
from agents.services.document_processing_service import DocumentProcessingService
from agents.storage.redis_service import SecureRedisService
from langgraph.checkpoint.redis import AsyncRedisSaver

CLERK_JWT_ISSUER = os.environ.get("CLERK_JWT_ISSUER")
clerk_config = ClerkConfig(jwks_url=CLERK_JWT_ISSUER)
clerk_auth_guard = ClerkHTTPBearer(config=clerk_config)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Handles the startup and shutdown lifespan events for the FastAPI application.

    Initializes the agent runtime and registers the UserProxyAgent.
    """

    redis_host = os.getenv("REDIS_HOST", "localhost")
    redis_port = int(os.getenv("REDIS_PORT", "6379"))
    app.state.context_length_summariser = 100_000

    # Create an async Redis connection pool
    pool = redis.asyncio.ConnectionPool(
        host=redis_host,
        port=redis_port,
        db=0,
        decode_responses=True,
        max_connections=100,
        socket_timeout=30,
        socket_connect_timeout=10,
        health_check_interval=30,
        retry_on_timeout=True,
    )

    # Create SecureRedisService with Redis client
    app.state.redis_client = SecureRedisService(
        connection_pool=pool, decode_responses=True
    )
    app.state.redis_storage_service = RedisStorage(redis_client=app.state.redis_client)

    # Set global Redis storage service for tools
    set_global_redis_storage_service(app.state.redis_storage_service)

    print(
        f"[LeadGenerationAPI] Using Redis at {redis_host}:{redis_port} with connection pool"
    )

    app.state.manager = WebSocketConnectionManager(
        redis_client=app.state.redis_client,
        context_length_summariser=app.state.context_length_summariser,
    )
    UserProxyAgent.connection_manager = app.state.manager
    SemanticRouterAgent.connection_manager = app.state.manager

    # Create checkpointer using the existing Redis client
    app.state.checkpointer = create_checkpointer(app.state.redis_client)

    # Set the global checkpointer for use in agents
    set_global_checkpointer(app.state.checkpointer)

    await AsyncRedisSaver(redis_client=app.state.redis_client).asetup()

    yield  # This separates the startup and shutdown logic

    # Close Redis connection pool
    await app.state.redis_client.aclose()
    await pool.aclose()


def get_user_id_from_token(token: HTTPAuthorizationCredentials) -> str:
    try:
        decoded_token = jwt.decode(
            token.credentials, options={"verify_signature": False}
        )
        return decoded_token.get("sub", "anonymous")
    except Exception as e:
        logger.error(f"Error decoding token: {str(e)}")
        return "anonymous"


class LeadGenerationAPI:
    def __init__(self):
        self.app = FastAPI(lifespan=lifespan, root_path="/api")
        self.setup_cors()
        self.setup_routes()
        self.executor = ThreadPoolExecutor(max_workers=15)

    def setup_cors(self):
        allowed_origins = os.getenv("ALLOWED_ORIGINS", "*").split(",")
        if not allowed_origins or (
            len(allowed_origins) == 1 and allowed_origins[0] == "*"
        ):
            allowed_origins = ["*"]
        else:
            allowed_origins.extend(
                [
                    "http://localhost:5173",
                    "http://localhost:5174",
                    "http://localhost:8000",
                ]
            )

        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=allowed_origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=[
                "*",
                "x-sambanova-key",
                "x-exa-key",
                "x-serper-key",
                "x-user-id",
                "x-run-id",
            ],
            expose_headers=["content-type", "content-length"],
        )

    def setup_routes(self):

        @self.app.get("/health")
        async def health_check():
            """Health check endpoint for Kubernetes liveness and readiness probes."""
            try:
                # Check Redis connection
                await self.app.state.redis_client.ping()
                return JSONResponse(
                    status_code=200,
                    content={"status": "healthy", "message": "Service is running"},
                )
            except Exception as e:
                return JSONResponse(
                    status_code=503, content={"status": "unhealthy", "message": str(e)}
                )

        # WebSocket endpoint to handle user messages
        @self.app.websocket("/chat")
        async def websocket_endpoint(
            websocket: WebSocket,
            conversation_id: str = Query(..., description="Conversation ID"),
        ):
            """
            WebSocket endpoint for handling user chat messages.

            Args:
                websocket (WebSocket): The WebSocket connection.
                conversation_id (str): The ID of the conversation.
            """
            try:
                # Accept the connection first
                await websocket.accept()

                # Wait for authentication message
                auth_message = await websocket.receive_text()
                try:
                    auth_data = json.loads(auth_message)
                    if auth_data.get("type") != "auth":
                        try:
                            await websocket.close(
                                code=4001, reason="Authentication message expected"
                            )
                        except Exception as close_error:
                            logger.error(f"Error closing WebSocket: {str(close_error)}")
                        return

                    token = auth_data.get("token", "")
                    if not token.startswith("Bearer "):
                        try:
                            await websocket.close(
                                code=4001, reason="Invalid authentication token format"
                            )
                        except Exception as close_error:
                            logger.error(f"Error closing WebSocket: {str(close_error)}")
                        return

                    token_data = HTTPAuthorizationCredentials(
                        scheme="Bearer", credentials=token.split(" ")[1]
                    )
                    user_id = get_user_id_from_token(token_data)

                    if not user_id:
                        try:
                            await websocket.close(
                                code=4001, reason="Invalid authentication token"
                            )
                        except Exception as close_error:
                            logger.error(f"Error closing WebSocket: {str(close_error)}")
                        return

                    # Verify conversation exists and belongs to user
                    if not await self.app.state.redis_storage_service.verify_conversation_exists(
                        user_id, conversation_id
                    ):
                        try:
                            await websocket.close(
                                code=4004, reason="Conversation not found"
                            )
                        except Exception as close_error:
                            logger.error(f"Error closing WebSocket: {str(close_error)}")
                        return

                    await self.app.state.manager.handle_websocket(
                        websocket, user_id, conversation_id
                    )
                except json.JSONDecodeError:
                    try:
                        await websocket.close(
                            code=4001, reason="Invalid authentication message format"
                        )
                    except Exception as close_error:
                        logger.error(f"Error closing WebSocket: {str(close_error)}")
                    return
            except WebSocketDisconnect as wsd:
                # Log normal disconnects at INFO level
                logger.info(
                    f"[/chat/websocket] WebSocket disconnected: code={wsd.code}, reason='{wsd.reason}' - conversation_id: {conversation_id}"
                )
                # No need to attempt closing again, it's already disconnected.
            except Exception as e:
                # Log detailed information about the WebSocket state and error
                logger.error(
                    f"[/chat/websocket] Error in WebSocket connection: {str(e)}"
                )
                logger.error(
                    f"[/chat/websocket] WebSocket state - client: {websocket.client_state}, application: {websocket.application_state}"
                )
                logger.error(
                    f"[/chat/websocket] Connection details - conversation_id: {conversation_id}"
                )

                # Only attempt to close if the connection is still open
                try:
                    if (
                        websocket.client_state != WebSocketState.DISCONNECTED
                        and websocket.application_state != WebSocketState.DISCONNECTED
                    ):
                        await websocket.close(code=4000, reason="Internal server error")
                except Exception as close_error:
                    logger.error(f"Error closing WebSocket: {str(close_error)}")
                    # Just log the error, don't re-raise

        @self.app.post("/chat/init")
        async def init_chat(
            chat_name: Optional[str] = None,
            token_data: HTTPAuthorizationCredentials = Depends(clerk_auth_guard),
        ):
            """
            Initializes a new chat session and stores the provided API keys.
            Returns a chat ID for subsequent interactions.

            Args:
                chat_name (Optional[str]): Optional name for the chat. If not provided, a default will be used.
                token_data (HTTPAuthorizationCredentials): The authentication token data
            """
            # Get and verify authenticated user
            user_id = get_user_id_from_token(token_data)
            if not user_id:
                return JSONResponse(
                    status_code=401, content={"error": "Invalid authentication token"}
                )

            try:
                # Generate a unique chat ID
                conversation_id = str(uuid.uuid4())

                # Use provided chat name or default
                timestamp = time.time()

                # Store chat metadata
                metadata = {
                    "conversation_id": conversation_id,
                    **({"name": chat_name} if chat_name else {}),
                    "created_at": timestamp,
                    "updated_at": timestamp,
                    "user_id": user_id,
                }
                chat_meta_key = f"chat_metadata:{user_id}:{conversation_id}"
                await self.app.state.redis_client.set(
                    chat_meta_key, json.dumps(metadata), user_id
                )

                # Add to user's conversation list
                user_chats_key = f"user_chats:{user_id}"
                await self.app.state.redis_client.zadd(
                    user_chats_key, {conversation_id: timestamp}
                )

                return JSONResponse(
                    status_code=200,
                    content={
                        "conversation_id": conversation_id,
                        "name": chat_name,
                        "created_at": timestamp,
                        "assistant_message": "Hello! How can I help you today?",
                    },
                )

            except Exception as e:
                print(f"[/chat/init] Error initializing chat: {str(e)}")
                return JSONResponse(
                    status_code=500,
                    content={"error": f"Failed to initialize chat: {str(e)}"},
                )

        @self.app.get("/chat/history/{conversation_id}")
        async def get_conversation_messages(
            conversation_id: str,
            token_data: HTTPAuthorizationCredentials = Depends(clerk_auth_guard),
        ):
            """
            Retrieve all messages for a specific conversation.

            Args:
                user_id (str): The ID of the user
                conversation_id (str): The ID of the conversation
                token_data (HTTPAuthorizationCredentials): The authentication token data
            """
            user_id = get_user_id_from_token(token_data)
            if not user_id:
                return JSONResponse(
                    status_code=401, content={"error": "Invalid authentication token"}
                )

            try:
                # Verify chat exists and belongs to user
                if not await self.app.state.redis_storage_service.verify_conversation_exists(
                    user_id, conversation_id
                ):
                    return JSONResponse(
                        status_code=404,
                        content={"error": "Chat not found or access denied"},
                    )

                messages = await self.app.state.redis_storage_service.get_messages(
                    user_id, conversation_id
                )

                if not messages:
                    return JSONResponse(status_code=200, content={"messages": []})

                # Sort messages by timestamp
                messages.sort(key=lambda x: x.get("timestamp", ""))

                return JSONResponse(status_code=200, content={"messages": messages})

            except Exception as e:
                print(
                    f"[/chat/history/{conversation_id}] Error retrieving messages: {str(e)}"
                )
                return JSONResponse(
                    status_code=500,
                    content={"error": f"Failed to retrieve messages: {str(e)}"},
                )

        @self.app.get("/chat/list")
        async def list_chats(
            token_data: HTTPAuthorizationCredentials = Depends(clerk_auth_guard),
        ):
            """
            Get list of all chats for a user, sorted by most recent first.

            Args:
                user_id (str): The ID of the user
                token_data (HTTPAuthorizationCredentials): The authentication token data
            """
            try:
                user_id = get_user_id_from_token(token_data)
                if not user_id:
                    return JSONResponse(
                        status_code=401,
                        content={"error": "Invalid authentication token"},
                    )

                # Get all conversation IDs for the user, sorted by most recent
                user_chats_key = f"user_chats:{user_id}"
                conversation_ids = await self.app.state.redis_client.zrevrange(
                    user_chats_key, 0, -1
                )

                if not conversation_ids:
                    return JSONResponse(status_code=200, content={"chats": []})

                # Get metadata for each conversation
                chats = []
                for conv_id in conversation_ids:
                    meta_key = f"chat_metadata:{user_id}:{conv_id}"
                    meta_data = await self.app.state.redis_client.get(meta_key, user_id)
                    if meta_data:
                        data = json.loads(meta_data)
                        if "name" not in data:
                            data["name"] = ""
                        chats.append(data)

                return JSONResponse(status_code=200, content={"chats": chats})

            except Exception as e:
                print(f"[/chat/list] Error retrieving chats: {str(e)}")
                return JSONResponse(
                    status_code=500,
                    content={"error": f"Failed to retrieve chats: {str(e)}"},
                )

        @self.app.delete("/chat/{conversation_id}")
        async def delete_chat(
            conversation_id: str,
            token_data: HTTPAuthorizationCredentials = Depends(clerk_auth_guard),
        ):
            """
            Delete a chat conversation and all its associated data.

            Args:
                user_id (str): The ID of the user
                conversation_id (str): The ID of the conversation to delete
                token_data (HTTPAuthorizationCredentials): The authentication token data
            """
            try:
                user_id = get_user_id_from_token(token_data)
                if not user_id:
                    return JSONResponse(
                        status_code=401,
                        content={"error": "Invalid authentication token"},
                    )

                # Verify chat exists and belongs to user
                if not await self.app.state.redis_storage_service.verify_conversation_exists(
                    user_id, conversation_id
                ):
                    return JSONResponse(
                        status_code=404,
                        content={"error": "Chat not found or access denied"},
                    )

                # Close any active WebSocket connections for this chat
                connection = self.app.state.manager.get_connection(
                    user_id, conversation_id
                )
                if connection:
                    await connection.close(code=4000, reason="Chat deleted")
                    self.app.state.manager.remove_connection(user_id, conversation_id)

                # Delete chat metadata
                await self.app.state.redis_storage_service.delete_all_user_data(
                    user_id, conversation_id
                )

                return JSONResponse(
                    status_code=200, content={"message": "Chat deleted successfully"}
                )

            except Exception as e:
                print(f"[/chat/delete] Error deleting chat: {str(e)}")
                return JSONResponse(
                    status_code=500,
                    content={"error": f"Failed to delete chat: {str(e)}"},
                )

        @self.app.post("/upload")
        async def upload_document(
            file: UploadFile = File(...),
            token_data: HTTPAuthorizationCredentials = Depends(clerk_auth_guard),
        ):
            """Upload and process a document or image file."""
            try:
                # Get and verify authenticated user
                user_id = get_user_id_from_token(token_data)
                if not user_id:
                    return JSONResponse(
                        status_code=401,
                        content={"error": "Invalid authentication token"},
                    )

                # Generate unique file ID
                file_id = str(uuid.uuid4())

                # Read file content
                content = await file.read()

                # Check if file is an image
                image_extensions = {
                    ".png",
                    ".jpg",
                    ".jpeg",
                    ".gif",
                    ".svg",
                    ".bmp",
                    ".tiff",
                    ".webp",
                }
                file_extension = (
                    os.path.splitext(file.filename.lower())[1] if file.filename else ""
                )

                is_image = file_extension in image_extensions or (
                    file.content_type and file.content_type.startswith("image/")
                )

                if is_image:
                    # Handle as image file using general file storage
                    format_ext = file_extension.lstrip(".") if file_extension else "png"
                    upload_time = time.time()

                    await self.app.state.redis_storage_service.put_file(
                        user_id,
                        file_id,
                        data=content,
                        title=file.filename or f"image.{format_ext}",
                        format=format_ext,
                        upload_timestamp=upload_time,
                    )

                    return JSONResponse(
                        status_code=200,
                        content={
                            "message": "Image uploaded successfully",
                            "file": {
                                "id": file_id,
                                "filename": file.filename,
                                "type": "image",
                                "upload_timestamp": upload_time,
                                "user_id": user_id,
                            },
                        },
                    )
                else:
                    # Handle as document with processing and chunking
                    doc_processor = DocumentProcessingService()
                    chunks = doc_processor.process_document(content, file.filename)

                    # Store document metadata
                    document_metadata = {
                        "id": file_id,
                        "filename": file.filename,
                        "upload_timestamp": time.time(),
                        "num_chunks": len(chunks),
                        "user_id": user_id,
                    }

                    # Store document metadata
                    await self.app.state.redis_storage_service.store_document_metadata(
                        user_id, file_id, document_metadata
                    )

                    # Add to user's document list
                    await self.app.state.redis_storage_service.add_document_to_user_list(
                        user_id, file_id
                    )

                    # Store document chunks
                    chunks_data = [
                        {
                            "text": chunk.page_content,
                            "metadata": {**chunk.metadata, "document_id": file_id},
                        }
                        for chunk in chunks
                    ]
                    await self.app.state.redis_storage_service.store_document_chunks(
                        user_id, file_id, chunks_data
                    )

                    return JSONResponse(
                        status_code=200,
                        content={
                            "message": "Document processed successfully",
                            "document": document_metadata,
                        },
                    )

            except Exception as e:
                print(f"[/upload] Error processing file: {str(e)}")
                return JSONResponse(status_code=500, content={"error": str(e)})

        @self.app.get("/files")
        async def get_user_files(
            token_data: HTTPAuthorizationCredentials = Depends(clerk_auth_guard),
        ):
            """Retrieve all documents and uploaded files for a user."""
            try:
                user_id = get_user_id_from_token(token_data)
                if not user_id:
                    return JSONResponse(
                        status_code=401,
                        content={"error": "Invalid authentication token"},
                    )

                # Get all documents for the user
                documents = (
                    await self.app.state.redis_storage_service.get_user_documents(
                        user_id
                    )
                )

                # Get all uploaded files (images, etc.) for the user
                files = await self.app.state.redis_storage_service.list_user_files(
                    user_id
                )

                # Combine both lists and add type information
                all_items = []

                # Add documents with type "document"
                for doc in documents:
                    doc["type"] = "document"
                    all_items.append(doc)

                # Add files with type "file" and convert file metadata format
                for file_item in files:
                    file_metadata = {
                        "id": file_item["file_id"],
                        "filename": file_item["title"],
                        "upload_timestamp": file_item.get("created_at", 0),
                        "user_id": user_id,
                        "type": "file",
                        "format": file_item.get("format", ""),
                        "file_size": file_item.get("file_size", 0),
                    }
                    all_items.append(file_metadata)

                # Sort by upload timestamp (most recent first)
                all_items.sort(key=lambda x: x.get("upload_timestamp", 0), reverse=True)

                return JSONResponse(status_code=200, content={"documents": all_items})

            except Exception as e:
                print(f"[/documents] Error retrieving documents: {str(e)}")
                return JSONResponse(status_code=500, content={"error": str(e)})

        @self.app.get("/files/{file_id}")
        async def get_file(
            file_id: str,
            token_data: HTTPAuthorizationCredentials = Depends(clerk_auth_guard),
        ):
            """Serve a file by its ID for authenticated users."""
            try:
                user_id = get_user_id_from_token(token_data)
                if not user_id:
                    return JSONResponse(
                        status_code=401,
                        content={"error": "Invalid authentication token"},
                    )

                # Get file metadata and data
                file_metadata = (
                    await self.app.state.redis_storage_service.get_file_metadata(
                        user_id, file_id
                    )
                )

                if not file_metadata:
                    return JSONResponse(
                        status_code=404,
                        content={"error": "File not found"},
                    )

                file_data = await self.app.state.redis_storage_service.get_file(
                    user_id, file_id
                )

                if not file_data:
                    return JSONResponse(
                        status_code=404,
                        content={"error": "File data not found"},
                    )

                # Determine content type based on format
                format_ext = file_metadata.get("format", "png")
                content_type = (
                    f"image/{format_ext}"
                    if format_ext in ["png", "jpg", "jpeg", "gif", "svg", "bmp", "webp"]
                    else "application/octet-stream"
                )

                return Response(
                    content=file_data,
                    media_type=content_type,
                    headers={
                        "Content-Disposition": f"inline; filename={file_metadata.get('title', f'file.{format_ext}')}"
                    },
                )

            except Exception as e:
                print(f"[/files/get] Error serving file: {str(e)}")
                return JSONResponse(status_code=500, content={"error": str(e)})

        @self.app.delete("/files/{file_id}")
        async def delete_file(
            file_id: str,
            token_data: HTTPAuthorizationCredentials = Depends(clerk_auth_guard),
        ):
            """Delete a file (document or uploaded file) and its associated data."""
            try:
                user_id = get_user_id_from_token(token_data)
                if not user_id:
                    return JSONResponse(
                        status_code=401,
                        content={"error": "Invalid authentication token"},
                    )

                # Check if it's a document first
                is_document = await self.app.state.redis_storage_service.verify_document_belongs_to_user(
                    user_id, file_id
                )

                # Check if it's a regular file
                file_metadata = (
                    await self.app.state.redis_storage_service.get_file_metadata(
                        user_id, file_id
                    )
                )
                is_file = file_metadata is not None

                if not is_document and not is_file:
                    return JSONResponse(
                        status_code=404,
                        content={"error": "File not found or access denied"},
                    )

                # Delete based on type
                if is_document:
                    await self.app.state.redis_storage_service.delete_document(
                        user_id, file_id
                    )
                    message = "Document deleted successfully"
                else:
                    await self.app.state.redis_storage_service.delete_file(
                        user_id, file_id
                    )
                    message = "File deleted successfully"

                return JSONResponse(
                    status_code=200,
                    content={"message": message},
                )

            except Exception as e:
                print(f"[/files/delete] Error deleting file: {str(e)}")
                return JSONResponse(status_code=500, content={"error": str(e)})

        @self.app.post("/set_api_keys")
        async def set_api_keys(
            keys: APIKeys,
            token_data: HTTPAuthorizationCredentials = Depends(clerk_auth_guard),
        ):
            """
            Store API keys for a user in Redis.

            Args:
                user_id (str): The ID of the user
                keys (APIKeys): The API keys to store
                token_data (HTTPAuthorizationCredentials): The authentication token data
            """
            try:
                user_id = get_user_id_from_token(token_data)
                if not user_id:
                    return JSONResponse(
                        status_code=401,
                        content={"error": "Invalid authentication token"},
                    )

                # Store keys in Redis with user-specific prefix
                key_prefix = f"api_keys:{user_id}"
                await self.app.state.redis_client.hset(
                    key_prefix,
                    mapping={
                        "sambanova_key": keys.sambanova_key,
                        "serper_key": keys.serper_key,
                        "exa_key": keys.exa_key,
                        "fireworks_key": keys.fireworks_key,
                    },
                    user_id=user_id,
                )

                return JSONResponse(
                    status_code=200, content={"message": "API keys stored successfully"}
                )

            except Exception as e:
                print(f"[/set_api_keys] Error storing API keys: {str(e)}")
                return JSONResponse(
                    status_code=500,
                    content={"error": f"Failed to store API keys: {str(e)}"},
                )

        @self.app.get("/get_api_keys")
        async def get_api_keys(
            token_data: HTTPAuthorizationCredentials = Depends(clerk_auth_guard),
        ):
            """
            Retrieve stored API keys for a user.

            Args:
                user_id (str): The ID of the user
                token_data (HTTPAuthorizationCredentials): The authentication token data
            """
            try:
                user_id = get_user_id_from_token(token_data)
                if not user_id:
                    return JSONResponse(
                        status_code=401,
                        content={"error": "Invalid authentication token"},
                    )

                key_prefix = f"api_keys:{user_id}"
                stored_keys = await self.app.state.redis_client.hgetall(
                    key_prefix, user_id
                )

                if not stored_keys:
                    return JSONResponse(
                        status_code=404,
                        content={"error": "No API keys found for this user"},
                    )

                return JSONResponse(
                    status_code=200,
                    content={
                        "sambanova_key": stored_keys.get("sambanova_key", ""),
                        "serper_key": stored_keys.get("serper_key", ""),
                        "exa_key": stored_keys.get("exa_key", ""),
                        "fireworks_key": stored_keys.get("fireworks_key", ""),
                    },
                )

            except Exception as e:
                print(f"[/get_api_keys] Error retrieving API keys: {str(e)}")
                return JSONResponse(
                    status_code=500,
                    content={"error": f"Failed to retrieve API keys: {str(e)}"},
                )

        @self.app.delete("/user/data")
        async def delete_user_data(
            token_data: HTTPAuthorizationCredentials = Depends(clerk_auth_guard),
        ):
            """
            Delete all data associated with the authenticated user.
            This includes all conversations, documents, and API keys.

            Args:
                token_data (HTTPAuthorizationCredentials): The authentication token data
            """
            try:
                user_id = get_user_id_from_token(token_data)
                if not user_id:
                    return JSONResponse(
                        status_code=401,
                        content={"error": "Invalid authentication token"},
                    )

                # 1. Delete all conversations
                user_chats_key = f"user_chats:{user_id}"
                conversation_ids = await self.app.state.redis_client.zrange(
                    user_chats_key, 0, -1
                )

                for conversation_id in conversation_ids:
                    # Close any active WebSocket connections
                    connection = self.app.state.manager.get_connection(
                        user_id, conversation_id
                    )
                    if connection:
                        await connection.close(code=4000, reason="User data deleted")
                        self.app.state.manager.remove_connection(
                            user_id, conversation_id
                        )

                    # Delete chat metadata and messages
                    meta_key = f"chat_metadata:{user_id}:{conversation_id}"
                    message_key = f"messages:{user_id}:{conversation_id}"
                    await self.app.state.redis_client.delete(meta_key)
                    await self.app.state.redis_client.delete(message_key)

                # Delete the user's chat list
                await self.app.state.redis_client.delete(user_chats_key)

                # 2. Delete all documents
                user_docs_key = f"user_documents:{user_id}"
                doc_ids = await self.app.state.redis_client.smembers(user_docs_key)

                for doc_id in doc_ids:
                    # Delete document metadata and chunks
                    doc_key = f"document:{doc_id}"
                    chunks_key = f"document_chunks:{doc_id}"
                    await self.app.state.redis_client.delete(doc_key)
                    await self.app.state.redis_client.delete(chunks_key)

                # Delete the user's document list
                await self.app.state.redis_client.delete(user_docs_key)

                # 3. Delete API keys
                key_prefix = f"api_keys:{user_id}"
                await self.app.state.redis_client.delete(key_prefix)

                return JSONResponse(
                    status_code=200,
                    content={"message": "All user data deleted successfully"},
                )

            except Exception as e:
                print(f"[/user/data] Error deleting user data: {str(e)}")
                return JSONResponse(
                    status_code=500,
                    content={"error": f"Failed to delete user data: {str(e)}"},
                )

    async def execute_research(self, crew: ResearchCrew, parameters: Dict[str, Any]):
        extractor = UserPromptExtractor(crew.llm.api_key)
        combined_text = " ".join(
            [
                parameters.get("industry", ""),
                parameters.get("company_stage", ""),
                parameters.get("geography", ""),
                parameters.get("funding_stage", ""),
                parameters.get("product", ""),
            ]
        ).strip()
        extracted_info = extractor.extract_lead_info(combined_text)

        raw_result, _ = await asyncio.to_thread(crew.execute_research, extracted_info)
        return raw_result

    async def execute_financial(
        self, crew: FinancialAnalysisCrew, parameters: Dict[str, Any], provider: str
    ):
        fextractor = FinancialPromptExtractor(crew.llm.api_key, provider)
        query_text = parameters.get("query_text", "")
        extracted_ticker, extracted_company = fextractor.extract_info(query_text)

        if not extracted_ticker:
            extracted_ticker = parameters.get("ticker", "")
        if not extracted_company:
            extracted_company = parameters.get("company_name", "")

        if not extracted_ticker:
            extracted_ticker = "AAPL"
        if not extracted_company:
            extracted_company = "Apple Inc"

        inputs = {"ticker": extracted_ticker, "company_name": extracted_company}

        if "docs" in parameters:
            inputs["docs"] = parameters["docs"]

        raw_result, _ = await asyncio.to_thread(crew.execute_financial_analysis, inputs)
        return raw_result


def create_app():
    api = LeadGenerationAPI()
    return api.app


if __name__ == "__main__":
    # Configure logging for uvicorn
    from agents.utils.logging import configure_uvicorn_logging

    configure_uvicorn_logging()

    # Create and run the application
    app = create_app()
    uvicorn.run(
        app,
        host="127.0.0.1",
        port=8000,
        log_config=None,  # Disable uvicorn's default logging config
    )
