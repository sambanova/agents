import asyncio
import json
import os
import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from io import BytesIO
from typing import Optional

import jwt
import markdown
import mlflow
import structlog
from agents.api.data_types import (
    APIKeys,
    MCPServerConfig,
    MCPServerCreateRequest,
    MCPServerUpdateRequest,
    MCPServerListResponse,
    MCPServerHealthResponse,
    MCPServerStatus,
    MCPToolInfo,
)
from agents.api.middleware import LoggingMiddleware
from agents.api.websocket_manager import WebSocketConnectionManager
from agents.components.compound.xml_agent import (
    create_checkpointer,
    set_global_checkpointer,
)
from agents.components.routing.route import SemanticRouterAgent
from agents.components.routing.user_proxy import UserProxyAgent
from agents.rag.upload import convert_ingestion_input_to_blob, ingest_runnable
from agents.storage.global_services import (
    get_secure_redis_client,
    get_sync_redis_client,
    set_global_redis_storage_service,
)
from agents.storage.redis_storage import RedisStorage
from agents.utils.logging_config import configure_logging
from fastapi import Depends, FastAPI, File, Query, Response, UploadFile, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.websockets import WebSocketDisconnect, WebSocketState
from fastapi_clerk_auth import (
    ClerkConfig,
    ClerkHTTPBearer,
    HTTPAuthorizationCredentials,
)
from langgraph.checkpoint.redis import AsyncRedisSaver
from weasyprint import CSS, HTML
from uuid import uuid4

logger = structlog.get_logger(__name__)


CLERK_JWT_ISSUER = os.environ.get("CLERK_JWT_ISSUER")
clerk_config = ClerkConfig(jwks_url=CLERK_JWT_ISSUER)
clerk_auth_guard = ClerkHTTPBearer(config=clerk_config)

configure_logging(os.getenv("ENVIRONMENT", "dev"))


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Handles the startup and shutdown lifespan events for the FastAPI application.

    Initializes the agent runtime and registers the UserProxyAgent.
    """

    if os.getenv("MLFLOW_TRACKING_ENABLED", "false") == "true":
        # Set MLflow Tracking URI from environment variable
        mlflow_tracking_uri = os.getenv("MLFLOW_TRACKING_URI")
        if mlflow_tracking_uri:
            mlflow.set_tracking_uri(mlflow_tracking_uri)
            mlflow.set_experiment("aiskagents")
            logger.info(f"MLflow tracking URI set to: {mlflow_tracking_uri}")
        else:
            logger.warning(
                "MLFLOW_TRACKING_URI environment variable not set. MLflow will default to local ./mlruns."
            )
        try:
            # At the moment, this is not working, it does not work with FastAPI: https://github.com/mlflow/mlflow/issues/14836
            # Also the documentation mentions that MLflow CrewAI integration currently only supports synchronous task execution.
            mlflow.crewai.autolog()
            mlflow.langchain.autolog()
            logger.info("MLflow CrewAI autologging enabled.")
        except Exception as e:
            logger.error(
                f"Failed to initialize MLflow CrewAI autologging: {e}",
                exc_info=True,
            )

    # Create SecureRedisService with Redis client
    app.state.redis_client = get_secure_redis_client()
    app.state.redis_storage_service = RedisStorage(redis_client=app.state.redis_client)
    app.state.sync_redis_client = get_sync_redis_client()

    # Set global Redis storage service for tools
    set_global_redis_storage_service(app.state.redis_storage_service)

    # Initialize MCP services
        # Initialize MCP services with lazy loading to avoid circular imports
    try:
        from agents.storage.global_services import initialize_mcp_services
        initialize_mcp_services(app.state.redis_storage_service)
    except Exception as e:
        logger.warning(f"MCP services initialization failed: {e}")
        # Continue without MCP services - they'll be initialized on first use

    logger.info("Using Redis with shared connection pool")

    app.state.manager = WebSocketConnectionManager(
        redis_client=app.state.redis_client,
        sync_redis_client=app.state.sync_redis_client,
    )
    UserProxyAgent.connection_manager = app.state.manager
    SemanticRouterAgent.connection_manager = app.state.manager

    # Create checkpointer using the existing Redis client
    app.state.checkpointer = create_checkpointer(app.state.redis_client)

    # Set the global checkpointer for use in agents
    set_global_checkpointer(app.state.checkpointer)

    await AsyncRedisSaver(redis_client=app.state.redis_client).asetup()

    yield


def get_user_id_from_token(token: HTTPAuthorizationCredentials) -> str:
    try:
        decoded_token = jwt.decode(
            token.credentials, options={"verify_signature": False}
        )
        return decoded_token.get("sub", "anonymous")
    except Exception as e:
        logger.error(f"Error decoding token: {str(e)}")
        return "anonymous"


app = FastAPI(
    title="Sambanova Agents Service",
    description="Service for Sambanova agents",
    version="0.0.1",
    lifespan=lifespan,
    root_path="/api",
)

# Add logging middleware first (so it wraps all other middleware)
app.add_middleware(LoggingMiddleware)


def get_allowed_origins():
    allowed_origins = os.getenv("ALLOWED_ORIGINS", "*").split(",")
    if not allowed_origins or (len(allowed_origins) == 1 and allowed_origins[0] == "*"):
        allowed_origins = ["*"]
    else:
        allowed_origins.extend(
            [
                "http://localhost:5173",
                "http://localhost:5174",
                "http://localhost:8000",
            ]
        )
    return allowed_origins


app.add_middleware(
    CORSMiddleware,
    allow_origins=get_allowed_origins(),
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


@app.get("/health")
async def health_check():
    """Health check endpoint for Kubernetes liveness and readiness probes."""
    try:
        # Check Redis connection
        await app.state.redis_client.ping()
        return JSONResponse(
            status_code=200,
            content={"status": "healthy", "message": "Service is running"},
        )
    except Exception as e:
        return JSONResponse(
            status_code=503, content={"status": "unhealthy", "message": str(e)}
        )


# WebSocket endpoint to handle user messages
@app.websocket("/chat")
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
            if not await app.state.redis_storage_service.verify_conversation_exists(
                user_id, conversation_id
            ):
                try:
                    await websocket.close(code=4004, reason="Conversation not found")
                except Exception as close_error:
                    logger.error(f"Error closing WebSocket: {str(close_error)}")
                return

            await app.state.manager.handle_websocket(
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
        logger.error(f"[/chat/websocket] Error in WebSocket connection: {str(e)}")
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


@app.post("/chat/init")
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
        await app.state.redis_client.set(chat_meta_key, json.dumps(metadata), user_id)

        # Add to user's conversation list
        user_chats_key = f"user_chats:{user_id}"
        await app.state.redis_client.zadd(user_chats_key, {conversation_id: timestamp})

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
        logger.error(f"Error initializing chat: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"error": f"Failed to initialize chat: {str(e)}"},
        )


@app.get("/chat/history/{conversation_id}")
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
        if not await app.state.redis_storage_service.verify_conversation_exists(
            user_id, conversation_id
        ):
            return JSONResponse(
                status_code=404,
                content={"error": "Chat not found or access denied"},
            )

        messages = await app.state.redis_storage_service.get_messages(
            user_id, conversation_id
        )

        if not messages:
            return JSONResponse(status_code=200, content={"messages": []})

        # Sort messages by timestamp
        messages.sort(key=lambda x: x.get("timestamp", ""))

        return JSONResponse(status_code=200, content={"messages": messages})

    except Exception as e:
        logger.error(
            f"Error retrieving messages: {str(e)}", conversation_id=conversation_id
        )
        return JSONResponse(
            status_code=500,
            content={"error": f"Failed to retrieve messages: {str(e)}"},
        )


@app.get("/chat/list")
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
        conversation_ids = await app.state.redis_client.zrevrange(user_chats_key, 0, -1)

        if not conversation_ids:
            return JSONResponse(status_code=200, content={"chats": []})

        # Get metadata for each conversation
        chats = []
        for conv_id in conversation_ids:
            meta_key = f"chat_metadata:{user_id}:{conv_id}"
            meta_data = await app.state.redis_client.get(meta_key, user_id)
            if meta_data:
                data = json.loads(meta_data)
                if "name" not in data:
                    data["name"] = ""
                chats.append(data)

        return JSONResponse(status_code=200, content={"chats": chats})

    except Exception as e:
        logger.error(f"Error retrieving chats: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"error": f"Failed to retrieve chats: {str(e)}"},
        )


@app.delete("/chat/{conversation_id}")
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
        if not await app.state.redis_storage_service.verify_conversation_exists(
            user_id, conversation_id
        ):
            return JSONResponse(
                status_code=404,
                content={"error": "Chat not found or access denied"},
            )

        # Close any active WebSocket connections for this chat
        connection = app.state.manager.get_connection(user_id, conversation_id)
        if connection:
            await connection.close(code=4000, reason="Chat deleted")
            app.state.manager.remove_connection(user_id, conversation_id)

        # Delete chat metadata
        await app.state.redis_storage_service.delete_all_user_data(
            user_id, conversation_id
        )

        return JSONResponse(
            status_code=200, content={"message": "Chat deleted successfully"}
        )

    except Exception as e:
        logger.error(f"Error deleting chat: {str(e)}", conversation_id=conversation_id)
        return JSONResponse(
            status_code=500,
            content={"error": f"Failed to delete chat: {str(e)}"},
        )


@app.post("/upload")
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
        indexed = False
        vector_ids = []

        upload_time = time.time()
        if file.content_type == "application/pdf":
            file_blobs = await convert_ingestion_input_to_blob(content, file.filename)
            api_keys = await app.state.redis_storage_service.get_user_api_key(user_id)
            vector_ids = await ingest_runnable.ainvoke(
                file_blobs,
                {
                    "user_id": user_id,
                    "document_id": file_id,
                    "api_key": api_keys.sambanova_key,
                    "redis_client": app.state.sync_redis_client,
                },
            )
            logger.info("Indexed file successfully", file_id=file_id)
            indexed = True

        await app.state.redis_storage_service.put_file(
            user_id,
            file_id,
            data=content,
            filename=file.filename,
            format=file.content_type,
            upload_timestamp=upload_time,
            indexed=indexed,
            source="upload",
            vector_ids=vector_ids,
        )

        duration = time.time() - upload_time
        logger.info(
            "File uploaded successfully",
            file_id=file_id,
            duration_ms=round(duration * 1000, 2),
        )

        return JSONResponse(
            status_code=200,
            content={
                "message": "File uploaded successfully",
                "file": {
                    "file_id": file_id,
                    "filename": file.filename,
                    "type": file.content_type,
                    "created_at": upload_time,
                    "user_id": user_id,
                },
            },
        )

    except Exception as e:
        logger.error(f"Error processing file: {str(e)}")
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.get("/files")
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

        files = await app.state.redis_storage_service.list_user_files(user_id)

        files.sort(key=lambda x: x.get("created_at", 0), reverse=True)

        return JSONResponse(status_code=200, content={"documents": files})

    except Exception as e:
        logger.error(f"Error retrieving files: {str(e)}")
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.get("/files/{file_id}")
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

        file_data, file_metadata = await app.state.redis_storage_service.get_file(
            user_id, file_id
        )

        if not file_data:
            return JSONResponse(
                status_code=404,
                content={"error": "File data not found"},
            )

        return Response(
            content=file_data,
            media_type=file_metadata["format"],
            headers={
                "Content-Disposition": f"inline; filename={file_metadata['filename']}"
            },
        )

    except Exception as e:
        logger.error(f"Error serving file: {str(e)}", file_id=file_id)
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.delete("/files/{file_id}")
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

        # If the file is indexed, delete its vectors from the vector store
        metadata = await app.state.redis_storage_service.get_file_metadata(
            user_id, file_id
        )

        if not metadata:
            logger.error("File metadata not found", file_id=file_id)
            return JSONResponse(
                status_code=404,
                content={"error": "File not found"},
            )

        if metadata and metadata.get("indexed"):
            vector_ids = metadata.get("vector_ids")
            if vector_ids:
                api_keys = await app.state.redis_storage_service.get_user_api_key(
                    user_id
                )
                if api_keys and api_keys.sambanova_key:
                    await app.state.redis_storage_service.delete_vectors(vector_ids)

        result = await app.state.redis_storage_service.delete_file(user_id, file_id)

        if not result:
            return JSONResponse(
                status_code=404,
                content={"error": "File not found or access denied"},
            )

        return JSONResponse(
            status_code=200,
            content={"message": "File deleted successfully"},
        )

    except Exception as e:
        logger.error(f"Error deleting file: {str(e)}", file_id=file_id)
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.post("/set_api_keys")
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

        await app.state.redis_storage_service.set_user_api_key(user_id, keys)

        # Create default MCP servers if this is a new user
        await create_default_mcp_servers(user_id)

        return JSONResponse(
            status_code=200, content={"message": "API keys stored successfully"}
        )

    except Exception as e:
        logger.error(f"Error storing API keys: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"error": f"Failed to store API keys: {str(e)}"},
        )


@app.get("/get_api_keys")
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
        stored_keys = await app.state.redis_client.hgetall(key_prefix, user_id)

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
        logger.error(f"Error retrieving API keys: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"error": f"Failed to retrieve API keys: {str(e)}"},
        )


@app.delete("/user/data")
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
        conversation_ids = await app.state.redis_client.zrange(user_chats_key, 0, -1)

        for conversation_id in conversation_ids:
            # Close any active WebSocket connections
            connection = app.state.manager.get_connection(user_id, conversation_id)
            if connection:
                await connection.close(code=4000, reason="User data deleted")
                app.state.manager.remove_connection(user_id, conversation_id)

            # Delete chat metadata and messages
            meta_key = f"chat_metadata:{user_id}:{conversation_id}"
            message_key = f"messages:{user_id}:{conversation_id}"
            await app.state.redis_client.delete(meta_key)
            await app.state.redis_client.delete(message_key)

        # Delete the user's chat list
        await app.state.redis_client.delete(user_chats_key)

        # 2. Delete all documents
        user_docs_key = f"user_documents:{user_id}"
        doc_ids = await app.state.redis_client.smembers(user_docs_key)

        for doc_id in doc_ids:
            # Delete document metadata and chunks
            doc_key = f"document:{doc_id}"
            chunks_key = f"document_chunks:{doc_id}"
            await app.state.redis_client.delete(doc_key)
            await app.state.redis_client.delete(chunks_key)

        # Delete the user's document list
        await app.state.redis_client.delete(user_docs_key)

        # 3. Delete API keys
        key_prefix = f"api_keys:{user_id}"
        await app.state.redis_client.delete(key_prefix)

        return JSONResponse(
            status_code=200,
            content={"message": "All user data deleted successfully"},
        )

    except Exception as e:
        logger.error(f"Error deleting user data: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"error": f"Failed to delete user data: {str(e)}"},
        )


# MCP Server Management Endpoints

@app.get("/mcp/servers", response_model=MCPServerListResponse)
async def list_mcp_servers(
    token_data: HTTPAuthorizationCredentials = Depends(clerk_auth_guard),
):
    """
    List all MCP servers for the authenticated user.
    
    Returns:
        MCPServerListResponse: List of user's MCP servers
    """
    try:
        user_id = get_user_id_from_token(token_data)
        if not user_id:
            return JSONResponse(
                status_code=401,
                content={"error": "Invalid authentication token"},
            )

        servers = await app.state.redis_storage_service.list_user_mcp_servers(user_id)
        
        return MCPServerListResponse(
            servers=servers,
            total=len(servers)
        )

    except Exception as e:
        logger.error(f"Error listing MCP servers: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"error": f"Failed to list MCP servers: {str(e)}"},
        )


@app.post("/mcp/servers")
async def create_mcp_server(
    server_request: MCPServerCreateRequest,
    token_data: HTTPAuthorizationCredentials = Depends(clerk_auth_guard),
):
    """
    Create a new MCP server for the authenticated user.
    
    Args:
        server_request: MCP server configuration
        
    Returns:
        Created server configuration
    """
    try:
        user_id = get_user_id_from_token(token_data)
        if not user_id:
            return JSONResponse(
                status_code=401,
                content={"error": "Invalid authentication token"},
            )

        # Generate unique server ID
        server_id = str(uuid.uuid4())
        
        # Create server configuration
        server_config = MCPServerConfig(
            server_id=server_id,
            name=server_request.name,
            description=server_request.description,
            command=server_request.command,
            args=server_request.args,
            url=server_request.url,
            transport=server_request.transport,
            env_vars=server_request.env_vars,
            enabled=server_request.enabled,
        )
        
        # Store server configuration
        await app.state.redis_storage_service.store_mcp_server_config(user_id, server_config)
        
        # If enabled, try to start the server and discover tools
        if server_config.enabled:
            from agents.storage.global_services import get_global_mcp_server_manager
            mcp_manager = get_global_mcp_server_manager()
            if mcp_manager:
                # Start server in background
                asyncio.create_task(mcp_manager.start_server(user_id, server_id))
        
        return JSONResponse(
            status_code=201,
            content=server_config.model_dump(mode='json'),
        )

    except Exception as e:
        logger.error(f"Error creating MCP server: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"error": f"Failed to create MCP server: {str(e)}"},
        )


@app.get("/mcp/servers/{server_id}")
async def get_mcp_server(
    server_id: str,
    token_data: HTTPAuthorizationCredentials = Depends(clerk_auth_guard),
):
    """
    Get a specific MCP server configuration.
    
    Args:
        server_id: ID of the MCP server
        
    Returns:
        MCP server configuration
    """
    try:
        user_id = get_user_id_from_token(token_data)
        if not user_id:
            return JSONResponse(
                status_code=401,
                content={"error": "Invalid authentication token"},
            )

        server_config = await app.state.redis_storage_service.get_mcp_server_config(
            user_id, server_id
        )
        
        if not server_config:
            return JSONResponse(
                status_code=404,
                content={"error": "MCP server not found"},
            )
        
        return JSONResponse(
            status_code=200,
            content=server_config.model_dump(mode='json'),
        )

    except Exception as e:
        logger.error(f"Error getting MCP server: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"error": f"Failed to get MCP server: {str(e)}"},
        )


@app.put("/mcp/servers/{server_id}")
async def update_mcp_server(
    server_id: str,
    server_request: MCPServerUpdateRequest,
    token_data: HTTPAuthorizationCredentials = Depends(clerk_auth_guard),
):
    """
    Update an existing MCP server configuration.
    
    Args:
        server_id: ID of the MCP server
        server_request: Updated server configuration
        
    Returns:
        Updated server configuration
    """
    try:
        user_id = get_user_id_from_token(token_data)
        if not user_id:
            return JSONResponse(
                status_code=401,
                content={"error": "Invalid authentication token"},
            )

        # Prepare updates (only include non-None values)
        updates = {}
        for field, value in server_request.model_dump(exclude_none=True).items():
            updates[field] = value
        
        if not updates:
            return JSONResponse(
                status_code=400,
                content={"error": "No updates provided"},
            )
        
        # Update server configuration
        success = await app.state.redis_storage_service.update_mcp_server_config(
            user_id, server_id, updates
        )
        
        if not success:
            return JSONResponse(
                status_code=404,
                content={"error": "MCP server not found"},
            )
        
        # Get updated configuration
        updated_config = await app.state.redis_storage_service.get_mcp_server_config(
            user_id, server_id
        )
        
        # Invalidate tool cache after update
        from agents.storage.global_services import get_global_dynamic_tool_loader
        dyn_loader = get_global_dynamic_tool_loader()
        if dyn_loader:
            dyn_loader.invalidate_user_cache(user_id)

        # Handle server restart if needed
        if "enabled" in updates or "command" in updates or "args" in updates or "url" in updates:
            from agents.storage.global_services import get_global_mcp_server_manager
            mcp_manager = get_global_mcp_server_manager()
            if mcp_manager:
                # Restart server in background
                asyncio.create_task(mcp_manager.restart_server(user_id, server_id))
        
        return JSONResponse(
            status_code=200,
            content=updated_config.model_dump(mode='json') if updated_config else {},
        )

    except Exception as e:
        logger.error(f"Error updating MCP server: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"error": f"Failed to update MCP server: {str(e)}"},
        )


@app.delete("/mcp/servers/{server_id}")
async def delete_mcp_server(
    server_id: str,
    token_data: HTTPAuthorizationCredentials = Depends(clerk_auth_guard),
):
    """
    Delete an MCP server configuration.
    
    Args:
        server_id: ID of the MCP server
        
    Returns:
        Success message
    """
    try:
        user_id = get_user_id_from_token(token_data)
        if not user_id:
            return JSONResponse(
                status_code=401,
                content={"error": "Invalid authentication token"},
            )

        # Stop server if running
        from agents.storage.global_services import get_global_mcp_server_manager
        mcp_manager = get_global_mcp_server_manager()
        if mcp_manager:
            await mcp_manager.stop_server(user_id, server_id)
        
        # Delete server configuration
        success = await app.state.redis_storage_service.delete_mcp_server_config(
            user_id, server_id
        )
        
        if not success:
            return JSONResponse(
                status_code=404,
                content={"error": "MCP server not found"},
            )
        
        return JSONResponse(
            status_code=200,
            content={"message": "MCP server deleted successfully"},
        )

    except Exception as e:
        logger.error(f"Error deleting MCP server: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"error": f"Failed to delete MCP server: {str(e)}"},
        )


@app.post("/mcp/servers/{server_id}/toggle")
async def toggle_mcp_server(
    server_id: str,
    token_data: HTTPAuthorizationCredentials = Depends(clerk_auth_guard),
):
    """
    Toggle an MCP server's enabled status.
    
    Args:
        server_id: ID of the MCP server
        
    Returns:
        Updated server configuration
    """
    try:
        user_id = get_user_id_from_token(token_data)
        if not user_id:
            return JSONResponse(
                status_code=401,
                content={"error": "Invalid authentication token"},
            )

        # Get current configuration
        server_config = await app.state.redis_storage_service.get_mcp_server_config(
            user_id, server_id
        )
        
        if not server_config:
            return JSONResponse(
                status_code=404,
                content={"error": "MCP server not found"},
            )
        
        # Toggle enabled status
        new_enabled = not server_config.enabled
        success = await app.state.redis_storage_service.update_mcp_server_config(
            user_id, server_id, {"enabled": new_enabled}
        )
        
        if not success:
            return JSONResponse(
                status_code=500,
                content={"error": "Failed to update server status"},
            )
        
        # Invalidate tool cache
        from agents.storage.global_services import get_global_dynamic_tool_loader
        dyn_loader = get_global_dynamic_tool_loader()
        if dyn_loader:
            dyn_loader.invalidate_user_cache(user_id)

        # Start or stop server based on new status
        from agents.storage.global_services import get_global_mcp_server_manager
        mcp_manager = get_global_mcp_server_manager()
        if mcp_manager:
            if new_enabled:
                asyncio.create_task(mcp_manager.start_server(user_id, server_id))
            else:
                asyncio.create_task(mcp_manager.stop_server(user_id, server_id))
        
        # Get updated configuration
        updated_config = await app.state.redis_storage_service.get_mcp_server_config(
            user_id, server_id
        )
        
        return JSONResponse(
            status_code=200,
            content=updated_config.model_dump(mode='json') if updated_config else {},
        )

    except Exception as e:
        logger.error(f"Error toggling MCP server: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"error": f"Failed to toggle MCP server: {str(e)}"},
        )


@app.get("/mcp/servers/{server_id}/health", response_model=MCPServerHealthResponse)
async def get_mcp_server_health(
    server_id: str,
    token_data: HTTPAuthorizationCredentials = Depends(clerk_auth_guard),
):
    """
    Get health status of an MCP server.
    
    Args:
        server_id: ID of the MCP server
        
    Returns:
        Server health information
    """
    try:
        user_id = get_user_id_from_token(token_data)
        if not user_id:
            return JSONResponse(
                status_code=401,
                content={"error": "Invalid authentication token"},
            )

        # Get server configuration first
        server_config = await app.state.redis_storage_service.get_mcp_server_config(
            user_id, server_id
        )
        
        if not server_config:
            return JSONResponse(
                status_code=404,
                content={"error": "MCP server not found"},
            )
        
        # Get health status from MCP manager
        from agents.storage.global_services import get_global_mcp_server_manager
        mcp_manager = get_global_mcp_server_manager()
        
        if mcp_manager:
            status, message = await mcp_manager.health_check(user_id, server_id)
            tools = await mcp_manager.discover_tools(user_id, server_id)
        else:
            status = MCPServerStatus.UNKNOWN
            message = "MCP manager not available"
            tools = []
        
        return MCPServerHealthResponse(
            server_id=server_id,
            status=status,
            message=message,
            last_check=datetime.now(),
            available_tools=tools,
        )

    except Exception as e:
        logger.error(f"Error getting MCP server health: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"error": f"Failed to get MCP server health: {str(e)}"},
        )


@app.post("/mcp/servers/{server_id}/discover-tools")
async def discover_mcp_tools(
    server_id: str,
    force_refresh: bool = Query(False, description="Force refresh tool cache"),
    token_data: HTTPAuthorizationCredentials = Depends(clerk_auth_guard),
):
    """
    Discover tools from an MCP server.
    
    Args:
        server_id: ID of the MCP server
        force_refresh: Whether to force refresh the tool cache
        
    Returns:
        List of discovered tools
    """
    try:
        user_id = get_user_id_from_token(token_data)
        if not user_id:
            return JSONResponse(
                status_code=401,
                content={"error": "Invalid authentication token"},
            )

        # Check if server exists
        server_config = await app.state.redis_storage_service.get_mcp_server_config(
            user_id, server_id
        )
        
        if not server_config:
            return JSONResponse(
                status_code=404,
                content={"error": "MCP server not found"},
            )
        
        # Discover tools
        from agents.storage.global_services import get_global_mcp_server_manager
        mcp_manager = get_global_mcp_server_manager()
        
        if mcp_manager:
            tools = await mcp_manager.discover_tools(user_id, server_id, force_refresh)
        else:
            tools = []
        
        return JSONResponse(
            status_code=200,
            content={
                "server_id": server_id,
                "tools": [tool.model_dump(mode='json') for tool in tools],
                "total": len(tools),
            },
        )

    except Exception as e:
        logger.error(f"Error discovering MCP tools: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"error": f"Failed to discover MCP tools: {str(e)}"},
        )


@app.get("/mcp/tools")
async def get_user_mcp_tools(
    token_data: HTTPAuthorizationCredentials = Depends(clerk_auth_guard),
):
    """
    Get all available MCP tools for the authenticated user.
    
    Returns:
        Information about user's MCP tools and servers
    """
    try:
        user_id = get_user_id_from_token(token_data)
        if not user_id:
            return JSONResponse(
                status_code=401,
                content={"error": "Invalid authentication token"},
            )

        # Get tool information
        from agents.storage.global_services import get_global_dynamic_tool_loader
        tool_loader = get_global_dynamic_tool_loader()
        
        if tool_loader:
            tool_info = await tool_loader.get_user_tool_info(user_id)
        else:
            tool_info = {
                "total_mcp_servers": 0,
                "enabled_mcp_servers": 0,
                "available_mcp_tools": 0,
                "cached_tools": 0,
                "cache_valid": False,
                "servers": [],
            }
        
        return JSONResponse(
            status_code=200,
            content=tool_info,
        )

    except Exception as e:
        logger.error(f"Error getting user MCP tools: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"error": f"Failed to get user MCP tools: {str(e)}"},
        )


@app.post("/mcp/tools/reload")
async def reload_user_mcp_tools(
    token_data: HTTPAuthorizationCredentials = Depends(clerk_auth_guard),
):
    """
    Reload MCP tools for the authenticated user.
    
    This will invalidate the tool cache and restart MCP servers if needed.
    
    Returns:
        Success message
    """
    try:
        user_id = get_user_id_from_token(token_data)
        if not user_id:
            return JSONResponse(
                status_code=401,
                content={"error": "Invalid authentication token"},
            )

        # Reload tools
        from agents.storage.global_services import get_global_dynamic_tool_loader
        tool_loader = get_global_dynamic_tool_loader()
        
        if tool_loader:
            await tool_loader.reload_user_mcp_tools(user_id)
        
        return JSONResponse(
            status_code=200,
            content={"message": "MCP tools reloaded successfully"},
        )

    except Exception as e:
        logger.error(f"Error reloading user MCP tools: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"error": f"Failed to reload MCP tools: {str(e)}"},
        )


async def create_default_mcp_servers(user_id: str):
    """Create default MCP server configurations for new users."""
    try:
        # Check if user already has servers
        existing_servers = await app.state.redis_storage_service.list_user_mcp_servers(user_id)
        if existing_servers:
            return  # User already has servers, don't create defaults
        
        # Create default MCP servers (all disabled by default)
        default_servers = [
            # Jira MCP server
            MCPServerConfig(
                server_id=str(uuid4()),
                name="Jira",
                description="Connect to your Atlassian Jira and Confluence instances for project management and knowledge base access",
                transport="stdio",
                url=None,
                command="uvx",
                args=[
                    "mcp-atlassian",
                    "--jira-url", "https://your-company.atlassian.net",
                    "--jira-username", "your.email@company.com", 
                    "--jira-token", "your_api_token"
                ],
                env_vars={},
                enabled=False,  # Disabled by default
                created_at=datetime.now(timezone.utc),
                last_updated=datetime.now(timezone.utc)
            ),
            # GitHub MCP server
            MCPServerConfig(
                server_id=str(uuid4()),
                name="GitHub",
                description="The GitHub MCP Server is a Model Context Protocol (MCP) server that provides seamless integration with GitHub APIs, enabling advanced automation and repository management capabilities for large language models",
                transport="stdio",
                url=None,
                command="npx",
                args=[
                    "-y",
                    "@modelcontextprotocol/server-github"
                ],
                env_vars={
                    "GITHUB_PERSONAL_ACCESS_TOKEN": "ghp_YOUR_PERSONAL_ACCESS_TOKEN_HERE"
                },
                enabled=False,  # Disabled by default
                created_at=datetime.now(timezone.utc),
                last_updated=datetime.now(timezone.utc)
            ),
            # Fetch MCP server
            MCPServerConfig(
                server_id=str(uuid4()),
                name="Fetch",
                description="Web content fetching and scraping",
                transport="stdio",
                url=None,
                command="uvx",
                args=[
                    "mcp-server-fetch"
                ],
                env_vars={},
                enabled=False,  # Disabled by default
                created_at=datetime.now(timezone.utc),
                last_updated=datetime.now(timezone.utc)
            )
        ]
        
        # Store all default servers
        for server in default_servers:
            await app.state.redis_storage_service.store_mcp_server_config(user_id, server)
        logger.info(f"Created default MCP servers for user {user_id}")
        
    except Exception as e:
        logger.error(f"Error creating default MCP servers for user {user_id}: {e}")
