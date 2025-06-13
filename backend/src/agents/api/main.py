"""
Main FastAPI application entry point.
"""

import mimetypes
import uuid
from agents.rag.upload import convert_ingestion_input_to_blob
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

from agents.components.routing.route import SemanticRouterAgent

from agents.storage.redis_service import SecureRedisService
from agents.storage.redis_storage import RedisStorage
from agents.storage.global_services import (
    get_secure_redis_client,
    set_global_redis_storage_service,
)

from agents.components.compound.xml_agent import (
    create_checkpointer,
    set_global_checkpointer,
)

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
from langgraph.checkpoint.redis import AsyncRedisSaver
from agents.rag.upload import ingest_runnable

CLERK_JWT_ISSUER = os.environ.get("CLERK_JWT_ISSUER")
clerk_config = ClerkConfig(jwks_url=CLERK_JWT_ISSUER)
clerk_auth_guard = ClerkHTTPBearer(config=clerk_config)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Handles the startup and shutdown lifespan events for the FastAPI application.

    Initializes the agent runtime and registers the UserProxyAgent.
    """
    app.state.context_length_summariser = 100_000

    # Create SecureRedisService with Redis client
    app.state.redis_client = get_secure_redis_client()
    app.state.redis_storage_service = RedisStorage(redis_client=app.state.redis_client)

    # Set global Redis storage service for tools
    set_global_redis_storage_service(app.state.redis_storage_service)

    print(f"[LeadGenerationAPI] Using Redis with shared connection pool")

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
                indexed = False

                upload_time = time.time()
                if file.content_type == "application/pdf":
                    file_blobs = await convert_ingestion_input_to_blob(
                        content, file.filename
                    )
                    api_keys = (
                        await self.app.state.redis_storage_service.get_user_api_key(
                            user_id
                        )
                    )
                    await ingest_runnable.ainvoke(
                        file_blobs,
                        {
                            "user_id": user_id,
                            "document_id": file_id,
                            "api_key": api_keys.sambanova_key,
                        },
                    )
                    logger.info(f"Indexed file successfully: {file_id}")
                    indexed = True

                await self.app.state.redis_storage_service.put_file(
                    user_id,
                    file_id,
                    data=content,
                    filename=file.filename,
                    format=file.content_type,
                    upload_timestamp=upload_time,
                    indexed=indexed,
                    source="upload",
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

                files = await self.app.state.redis_storage_service.list_user_files(
                    user_id
                )

                files.sort(key=lambda x: x.get("created_at", 0), reverse=True)

                return JSONResponse(status_code=200, content={"documents": files})

            except Exception as e:
                print(f"[/files] Error retrieving files: {str(e)}")
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

                file_data, file_metadata = (
                    await self.app.state.redis_storage_service.get_file(
                        user_id, file_id
                    )
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

                result = await self.app.state.redis_storage_service.delete_file(
                    user_id, file_id
                )

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

                await self.app.state.redis_storage_service.set_user_api_key(
                    user_id, keys
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
