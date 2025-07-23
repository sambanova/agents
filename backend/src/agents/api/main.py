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
from agents.api.routers.files import router as files_router
from agents.api.routers.share import router as share_router
from agents.api.routers.upload import router as upload_router
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
app.include_router(upload_router)
app.include_router(files_router)
app.include_router(share_router)


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
    user_id: str = Depends(get_current_user_id),
):
    """
    Delete all data associated with the authenticated user.
    This includes all conversations, documents, and API keys.

    Args:
        token_data (HTTPAuthorizationCredentials): The authentication token data
    """
    try:
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
