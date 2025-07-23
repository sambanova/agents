import asyncio
import json
import os
import time
import uuid
from contextlib import asynccontextmanager
from typing import List, Optional

import mlflow
import structlog
from agents.api.data_types import APIKeys
from agents.api.middleware import LoggingMiddleware
from agents.api.routers.chat import router as chat_router
from agents.api.websocket_manager import WebSocketConnectionManager
from agents.auth.auth0_config import (
    extract_user_id,
    get_current_user_id,
    token_verifier,
)
from agents.components.compound.xml_agent import (
    create_checkpointer,
    set_global_checkpointer,
)
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
from fastapi.security import HTTPAuthorizationCredentials
from fastapi.websockets import WebSocketDisconnect, WebSocketState
from langgraph.checkpoint.redis import AsyncRedisSaver

logger = structlog.get_logger(__name__)


# Auth0 configuration is handled in auth0_config.py

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

    logger.info("Using Redis with shared connection pool")

    app.state.manager = WebSocketConnectionManager(
        redis_client=app.state.redis_client,
        sync_redis_client=app.state.sync_redis_client,
    )

    # Create checkpointer using the existing Redis client
    app.state.checkpointer = create_checkpointer(app.state.redis_client)

    # Set the global checkpointer for use in agents
    set_global_checkpointer(app.state.checkpointer)

    await AsyncRedisSaver(redis_client=app.state.redis_client).asetup()

    yield


# get_user_id_from_token is now imported from auth0_config.py


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

app.include_router(chat_router)


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


@app.post("/upload")
async def upload_document(
    file: UploadFile = File(...),
    user_id: str = Depends(get_current_user_id),
):
    """Upload and process a document or image file."""
    try:
        # Get and verify authenticated user
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
    user_id: str = Depends(get_current_user_id),
):
    """Retrieve all documents and uploaded files for a user."""
    try:
        start_time = time.time()
        if not user_id:
            return JSONResponse(
                status_code=401,
                content={"error": "Invalid authentication token"},
            )

        files = await app.state.redis_storage_service.list_user_files(user_id)

        files.sort(key=lambda x: x.get("created_at", 0), reverse=True)

        duration = time.time() - start_time
        logger.info(
            f"Retrieved {len(files)} files for user {user_id} in {duration:.3f}s",
            user_id=user_id,
            file_count=len(files),
            duration_ms=round(duration * 1000, 2),
        )

        return JSONResponse(status_code=200, content={"documents": files})

    except Exception as e:
        logger.error(f"Error retrieving files: {str(e)}")
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.get("/files/{file_id}")
async def get_file(
    file_id: str,
    user_id: str = Depends(get_current_user_id),
):
    """Serve a file by its ID for authenticated users."""
    try:
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
    user_id: str = Depends(get_current_user_id),
):
    """Delete a file (document or uploaded file) and its associated data."""
    try:
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
    user_id: str = Depends(get_current_user_id),
):
    """
    Store API keys for a user in Redis.

    Args:
        user_id (str): The ID of the user
        keys (APIKeys): The API keys to store
        token_data (HTTPAuthorizationCredentials): The authentication token data
    """
    try:
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
    user_id: str = Depends(get_current_user_id),
):
    """
    Retrieve stored API keys for a user.

    Args:
        user_id (str): The ID of the user
        token_data (HTTPAuthorizationCredentials): The authentication token data
    """
    try:
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


@app.post("/chat/{conversation_id}/share")
async def create_conversation_share(
    conversation_id: str,
    user_id: str = Depends(get_current_user_id),
):
    """Create a new share link for a conversation (like ChatGPT)"""
    try:
        share_token = await app.state.redis_storage_service.create_share(
            user_id, conversation_id
        )

        return JSONResponse(
            status_code=201,
            content={
                "share_url": f"/share/{share_token}",
                "share_token": share_token,
                "message": "Share created successfully",
            },
        )

    except ValueError as e:
        return JSONResponse(status_code=404, content={"error": str(e)})
    except Exception as e:
        logger.error(f"Error creating share: {str(e)}")
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.get("/share/{share_token}")
async def get_shared_conversation(share_token: str):
    """Get shared conversation (public access, no authentication required)"""
    try:
        shared_conversation = (
            await app.state.redis_storage_service.get_shared_conversation(share_token)
        )

        if not shared_conversation:
            return JSONResponse(
                status_code=404, content={"error": "Shared conversation not found"}
            )

        return JSONResponse(status_code=200, content=shared_conversation)

    except Exception as e:
        logger.error(f"Error accessing shared conversation: {str(e)}")
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.get("/share/{share_token}/files/{file_id}")
async def get_shared_file(share_token: str, file_id: str):
    """Get file from shared conversation (public access, no authentication required)"""
    try:
        # First verify the share token is valid and get the original user/conversation
        shared_conversation = (
            await app.state.redis_storage_service.get_shared_conversation(share_token)
        )

        if not shared_conversation:
            return JSONResponse(
                status_code=404, content={"error": "Shared conversation not found"}
            )

        # Get the original user_id and conversation_id from the shared conversation
        original_user_id = shared_conversation.get("user_id")
        conversation_id = shared_conversation.get("conversation_id")

        if not original_user_id or not conversation_id:
            return JSONResponse(
                status_code=404, content={"error": "Invalid shared conversation data"}
            )

        # Get the conversation messages to verify the file is actually part of this conversation
        conversation_messages = await app.state.redis_storage_service.get_messages(
            original_user_id, conversation_id
        )

        # Check if the file_id is referenced in any message in this conversation
        file_referenced_in_conversation = False
        for message in conversation_messages:
            # Parse file references from the message content
            files = message.get("additional_kwargs", {}).get("files", [])
            if file_id in files:
                file_referenced_in_conversation = True
                break

        if not file_referenced_in_conversation:
            return JSONResponse(
                status_code=403,
                content={"error": "File not part of this shared conversation"},
            )

        # Get the file data using the original user's context
        file_data, file_metadata = await app.state.redis_storage_service.get_file(
            original_user_id, file_id
        )

        if not file_data:
            return JSONResponse(
                status_code=404,
                content={"error": "File not found in shared conversation"},
            )

        return Response(
            content=file_data,
            media_type=file_metadata["format"],
            headers={
                "Content-Disposition": f"inline; filename={file_metadata['filename']}"
            },
        )

    except Exception as e:
        logger.error(
            f"Error serving shared file: {str(e)}",
            share_token=share_token,
            file_id=file_id,
        )
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.get("/chat/{conversation_id}/shares")
async def list_conversation_shares(
    conversation_id: str,
    user_id: str = Depends(get_current_user_id),
):
    """List all shares for a conversation"""
    try:
        # Verify user owns the conversation
        if not await app.state.redis_storage_service.verify_conversation_exists(
            user_id, conversation_id
        ):
            return JSONResponse(
                status_code=404, content={"error": "Conversation not found"}
            )

        # Get all user's shares and filter for this conversation
        all_shares = await app.state.redis_storage_service.get_user_shares(user_id)
        conversation_shares = [
            share for share in all_shares if share["conversation_id"] == conversation_id
        ]

        return JSONResponse(status_code=200, content={"shares": conversation_shares})

    except Exception as e:
        logger.error(f"Error listing shares: {str(e)}")
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.delete("/share/{share_token}")
async def delete_share(
    share_token: str,
    user_id: str = Depends(get_current_user_id),
):
    """Delete a share (owner only)"""
    try:
        success = await app.state.redis_storage_service.delete_share(
            user_id, share_token
        )

        if not success:
            return JSONResponse(
                status_code=404, content={"error": "Share not found or access denied"}
            )

        return JSONResponse(
            status_code=200, content={"message": "Share deleted successfully"}
        )

    except Exception as e:
        logger.error(f"Error deleting share: {str(e)}")
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.delete("/user/data")
async def delete_user_data(
    user_id: str = Depends(get_current_user_id),
):
    """
    Delete all data associated with the authenticated user.
    This includes all conversations, documents, and API keys.

    Args:
        token_data (HTTPAuthorizationCredentials): The authentication token data
    """
    try:
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
