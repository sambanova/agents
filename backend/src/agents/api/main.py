import json
import os
import time
import uuid
from contextlib import asynccontextmanager
from typing import Optional

import jwt
import mlflow
import structlog
from agents.api.data_types import APIKeys
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

            # Enable MLflow LangChain autologging for LangGraph tracing
        try:
            # Enable MLflow LangChain autologging which supports LangGraph
            mlflow.langchain.autolog(disable=False, log_traces=True, silent=False)
            logger.info("MLflow LangChain autologging enabled for LangGraph tracing.")
        except Exception as e:
            logger.error(
                f"Failed to initialize MLflow LangChain autologging: {e}",
                exc_info=True,
            )

    app.state.context_length_summariser = 100_000

    # Create SecureRedisService with Redis client
    app.state.redis_client = get_secure_redis_client()
    app.state.redis_storage_service = RedisStorage(redis_client=app.state.redis_client)

    # Set global Redis storage service for tools
    set_global_redis_storage_service(app.state.redis_storage_service)

    logger.info("Using Redis with shared connection pool")

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
