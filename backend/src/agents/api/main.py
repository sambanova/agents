import os
from contextlib import asynccontextmanager

import mlflow
import structlog
from agents.api.data_types import APIKeys
from agents.api.middleware import LoggingMiddleware
from agents.api.routers.admin import router as admin_router
from agents.api.routers.agent import router as agent_router
from agents.api.routers.chat import router as chat_router
from agents.api.routers.connectors import router as connectors_router
from agents.api.routers.dynamic_mcp import router as dynamic_mcp_router
from agents.api.routers.export import router as export_router
from agents.api.routers.files import router as files_router
from agents.api.routers.openai_responses import router as openai_router
from agents.api.routers.share import router as share_router
from agents.api.routers.upload import router as upload_router
from agents.api.routers.user import router as user_router
from agents.api.routers.voice import router as voice_router
from agents.api.websocket_manager import WebSocketConnectionManager
from agents.auth.auth0_config import get_current_user_id
from agents.components.compound.xml_agent import (
    create_checkpointer,
    set_global_checkpointer,
)
from agents.storage.global_services import (
    get_secure_redis_client,
    get_sync_redis_client,
    set_global_redis_storage_service,
)
from agents.storage.redis_storage import RedisStorage
from agents.utils.logging_config import configure_logging
from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
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
    
    # Initialize OAuth connectors
    try:
        from agents.connectors.runtime.integration import initialize_connectors
        from agents.tools.dynamic_tool_loader import set_dynamic_tool_loader, DynamicToolLoader
        
        app.state.connector_manager = await initialize_connectors(app.state.redis_storage_service)
        
        # Initialize the dynamic tool loader with connector manager
        dynamic_loader = DynamicToolLoader(app.state.redis_storage_service, app.state.connector_manager)
        set_dynamic_tool_loader(dynamic_loader)
        
        logger.info("OAuth connector system and dynamic tool loader initialized")
    except Exception as e:
        logger.error(f"Failed to initialize OAuth connectors: {e}", exc_info=True)

    logger.info("Using Redis with shared connection pool")

    app.state.manager = WebSocketConnectionManager(
        redis_client=app.state.redis_client,
        sync_redis_client=app.state.sync_redis_client,
    )

    # Create checkpointer using the existing Redis client
    app.state.checkpointer = create_checkpointer(app.state.redis_client)

    # Set the global checkpointer for use in agents
    set_global_checkpointer(app.state.checkpointer)

    # Setup the checkpointer (create Redis indexes)
    if app.state.checkpointer:
        await app.state.checkpointer.asetup()

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

app.include_router(admin_router)
app.include_router(chat_router)
app.include_router(upload_router)
app.include_router(files_router)
app.include_router(share_router)
app.include_router(user_router)
app.include_router(agent_router)
app.include_router(export_router)
app.include_router(connectors_router)
app.include_router(dynamic_mcp_router)
app.include_router(voice_router)
app.include_router(openai_router)


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

    When admin panel is enabled (SHOW_ADMIN_PANEL=true):
    - This endpoint should only be called by non-admin components (for Serper/Exa keys)
    - Preserves Fireworks/Together/SambaNova keys and PayPal email managed by admin panel
    - Admin panel uses /admin/config endpoint for LLM provider keys and PayPal email

    When admin panel is disabled:
    - This endpoint manages all API keys as before

    Args:
        user_id (str): The ID of the user
        keys (APIKeys): The API keys to store
        token_data (HTTPAuthorizationCredentials): The authentication token data
    """
    try:
        admin_enabled = os.getenv("SHOW_ADMIN_PANEL", "false").lower() == "true"

        if admin_enabled:
            # When admin panel is enabled, preserve LLM provider keys
            # This endpoint should only update non-LLM keys (Serper, Exa)
            existing_keys = await app.state.redis_storage_service.get_user_api_key(user_id)

            # Preserve all LLM provider keys and PayPal email from admin panel
            if existing_keys:
                # Keep existing provider keys if not explicitly provided
                if not keys.sambanova_key and existing_keys.sambanova_key:
                    keys.sambanova_key = existing_keys.sambanova_key
                if not keys.fireworks_key and existing_keys.fireworks_key:
                    keys.fireworks_key = existing_keys.fireworks_key
                if not getattr(keys, 'together_key', '') and getattr(existing_keys, 'together_key', ''):
                    keys.together_key = existing_keys.together_key
                # Preserve PayPal invoicing email
                if not getattr(keys, 'paypal_invoicing_email', '') and getattr(existing_keys, 'paypal_invoicing_email', ''):
                    keys.paypal_invoicing_email = existing_keys.paypal_invoicing_email

            logger.info(f"Preserving LLM keys and PayPal email while updating other keys for user {user_id[:8]}...")

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
        # Use the redis_storage_service which properly handles the data
        stored_keys = await app.state.redis_storage_service.get_user_api_key(user_id)

        if not stored_keys or not stored_keys.sambanova_key:
            return JSONResponse(
                status_code=404,
                content={"error": "No API keys found for this user"},
            )

        response_data = {
            "sambanova_key": stored_keys.sambanova_key,
            "serper_key": stored_keys.serper_key,
            "exa_key": stored_keys.exa_key,
            "fireworks_key": stored_keys.fireworks_key,
            "together_key": stored_keys.together_key,
        }

        # Also include custom provider API keys from LLM config
        config_key = f"llm_config:{user_id}"
        stored_config = await app.state.redis_storage_service.redis_client.get(
            config_key,
            user_id=user_id
        )

        if stored_config:
            import json
            overrides = json.loads(stored_config)

            # Add custom provider API keys if they exist
            if "custom_api_keys" in overrides:
                response_data.update(overrides["custom_api_keys"])

        return JSONResponse(
            status_code=200,
            content=response_data,
        )

    except Exception as e:
        logger.error(f"Error retrieving API keys: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"error": f"Failed to retrieve API keys: {str(e)}"},
        )
