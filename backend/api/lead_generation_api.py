from fastapi import Depends, FastAPI, File, HTTPException, Query, Request, UploadFile, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
import jwt
from pydantic import BaseModel
import json
import uvicorn
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import time
import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import Annotated, Optional, Dict, Any, List
from contextlib import asynccontextmanager

from api.agents.user_proxy import UserProxyAgent
from api.websocket_manager import WebSocketConnectionManager

from api.data_types import APIKeys
from api.auth import decode_access_token
from utils.logging import logger
import os
import sys

import redis
import uuid
from fastapi import FastAPI, WebSocket


# SSE support
from sse_starlette.sse import EventSourceResponse

from api.agents.route import SemanticRouterAgent
parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

# Import the new chat logic
from agent.convo_newsletter_crew import crew_chat

# Original Services
from services.query_router_service import QueryRouterService
from services.user_prompt_extractor_service import UserPromptExtractor
from agent.lead_generation_crew import ResearchCrew
from agent.samba_research_flow.samba_research_flow import SambaResearchFlow

# For financial analysis
from services.financial_user_prompt_extractor_service import FinancialPromptExtractor
from agent.financial_analysis.financial_analysis_crew import FinancialAnalysisCrew
# For document processing
from services.document_processing_service import DocumentProcessingService

class QueryRequest(BaseModel):
    query: str
    document_ids: Optional[List[str]] = None

class EduContentRequest(BaseModel):
    topic: str
    audience_level: str = "intermediate"
    additional_context: Optional[Dict[str, List[str]]] = None

class ChatRequest(BaseModel):
    message: str

security = HTTPBearer()

## Given a JWT token in Authorization header, return the user_id
async def get_current_user(token: Annotated[str, Depends(security)]):
    """Validate the bearer token and return the current user."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        # Extract the token from the authorization header
        if isinstance(token, HTTPAuthorizationCredentials):
            token_cred = token.credentials
        elif isinstance(token, str):
            token_cred = token

        payload = decode_access_token(token_cred)
        if payload is None:
            raise credentials_exception
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception

        return user_id
    except Exception as e:
        logger.error(f"Error getting current user: {str(e)}")
        raise credentials_exception


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Handles the startup and shutdown lifespan events for the FastAPI application.

    Initializes the agent runtime and registers the UserProxyAgent.
    """

    redis_host = os.getenv("REDIS_HOST", "localhost")
    redis_port = int(os.getenv("REDIS_PORT", "6379"))
    app.state.context_length_summariser = 100_000
    
    # Create a Redis connection pool
    pool = redis.ConnectionPool(
        host=redis_host,
        port=redis_port,
        db=0,
        decode_responses=True,
        max_connections=100,
        socket_timeout=5,  # Add timeout to prevent hanging connections
        socket_connect_timeout=5,  # Add connection timeout
        health_check_interval=30  # Add health check to remove stale connections
    )
    
    # Create Redis client with connection pool
    app.state.redis_client = redis.Redis(
        connection_pool=pool,
        decode_responses=True
    )
    print(f"[LeadGenerationAPI] Using Redis at {redis_host}:{redis_port} with connection pool")

    app.state.manager = WebSocketConnectionManager(
        redis_client=app.state.redis_client,
        context_length_summariser=app.state.context_length_summariser
    )
    UserProxyAgent.connection_manager = app.state.manager
    SemanticRouterAgent.connection_manager = app.state.manager

    yield  # This separates the startup and shutdown logic

    # Close Redis connection pool
    app.state.redis_client.close()
    pool.disconnect()

    # Cleanup default agent runtime
    await app.state.agent_runtime.close()

def get_user_id_from_token(token: HTTPAuthorizationCredentials) -> str:
    try:
        decoded_token = jwt.decode(token.credentials, options={"verify_signature": False})
        return decoded_token.get("sub", "anonymous")
    except Exception as e:
        logger.error(f"Error decoding token: {str(e)}")
        return "anonymous"

class LeadGenerationAPI:
    def __init__(self):
        self.app = FastAPI(lifespan=lifespan, root_path="/api")
        self.setup_cors()
        self.setup_routes()
        self.executor = ThreadPoolExecutor(max_workers=2)

    def setup_cors(self):
        allowed_origins = os.getenv('ALLOWED_ORIGINS', '*').split(',')
        if not allowed_origins or (len(allowed_origins) == 1 and allowed_origins[0] == '*'):
            allowed_origins = ["*"]
        else:
            allowed_origins.extend([
                "http://localhost:5173",
                "http://localhost:5174",
                "http://localhost:8000"
            ])

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
                "x-run-id"
            ],
            expose_headers=["content-type", "content-length"]
        )

    def setup_routes(self):
        @self.app.get("/health")
        async def health_check():
            """Health check endpoint for Kubernetes liveness and readiness probes."""
            try:
                # Check Redis connection
                self.app.state.redis_client.ping()
                return JSONResponse(
                    status_code=200,
                    content={"status": "healthy", "message": "Service is running"}
                )
            except Exception as e:
                return JSONResponse(
                    status_code=503,
                    content={"status": "unhealthy", "message": str(e)}
                )

        # WebSocket endpoint to handle user messages
        @self.app.websocket("/chat")
        async def websocket_endpoint(
            websocket: WebSocket,
            conversation_id: str = Query(..., description="Conversation ID")
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
                    if auth_data.get('type') != 'auth':
                        await websocket.close(code=4001, reason="Authentication message expected")
                        return
                    
                    token = auth_data.get('token', '')
                    if not token.startswith('Bearer '):
                        await websocket.close(code=4001, reason="Invalid authentication token format")
                        return
                    
                    token_data = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token.split(' ')[1])
                    try:
                        user_id = await get_current_user(token_data)
                    except HTTPException:
                        await websocket.close(code=4001, reason="Invalid authentication token")
                        return

                    # Verify conversation exists and belongs to user
                    meta_key = f"chat_metadata:{user_id}:{conversation_id}"
                    if not self.app.state.redis_client.exists(meta_key):
                        await websocket.close(code=4004, reason="Conversation not found")
                        return

                    await self.app.state.manager.handle_websocket(
                        websocket, 
                        user_id, 
                        conversation_id
                    )
                except json.JSONDecodeError:
                    await websocket.close(code=4001, reason="Invalid authentication message format")
                    return
            except Exception as e:
                logger.error(f"[/chat/websocket] Error in WebSocket connection: {str(e)}")
                await websocket.close(code=4000, reason="Internal server error")

        @self.app.post("/route")
        async def determine_route(request: Request, query_request: QueryRequest):
            sambanova_key = request.headers.get("x-sambanova-key")
            if not sambanova_key:
                return JSONResponse(
                    status_code=401,
                    content={"error": "Missing required SambaNova API key"}
                )
            try:
                router = QueryRouterService(sambanova_key)
                route_result = router.route_query(query_request.query)
                return JSONResponse(
                    status_code=200,
                    content={
                        "type": route_result.type,
                        "parameters": route_result.parameters
                    }
                )
            except Exception as e:
                print(f"[/route] Error determining route: {str(e)}")
                return JSONResponse(status_code=500, content={"error": str(e)})

        @self.app.post("/chat/init")
        async def init_chat(
            chat_name: Optional[str] = None,
            user_id: str = Depends(get_current_user)
        ):
            """
            Initializes a new chat session and stores the provided API keys.
            Returns a chat ID for subsequent interactions.
            
            Args:
                chat_name (Optional[str]): Optional name for the chat. If not provided, a default will be used.
                user_id (str): The ID of the user
            """

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
                    "user_id": user_id
                }
                chat_meta_key = f"chat_metadata:{user_id}:{conversation_id}"
                self.app.state.redis_client.set(chat_meta_key, json.dumps(metadata))

                # Add to user's conversation list
                user_chats_key = f"user_chats:{user_id}"
                self.app.state.redis_client.zadd(user_chats_key, {conversation_id: timestamp})

                # TODO: init autogen agent

                return JSONResponse(
                    status_code=200,
                    content={
                        "conversation_id": conversation_id,
                        "name": chat_name,
                        "created_at": timestamp,
                        "assistant_message": "Hello! How can I help you today?"
                    }
                )

            except Exception as e:
                print(f"[/chat/init] Error initializing chat: {str(e)}")
                return JSONResponse(
                    status_code=500,
                    content={"error": f"Failed to initialize chat: {str(e)}"}
                )

        @self.app.get("/chat/history/{conversation_id}")
        async def get_conversation_messages(
            conversation_id: str,
            user_id: str = Depends(get_current_user)
        ):
            """
            Retrieve all messages for a specific conversation.
            
            Args:
                user_id (str): The ID of the user
                conversation_id (str): The ID of the conversation
            """

            try:
                # Verify conversation exists and belongs to user
                meta_key = f"chat_metadata:{user_id}:{conversation_id}"
                if not self.app.state.redis_client.exists(meta_key):
                    return JSONResponse(
                        status_code=404,
                        content={"error": "Conversation not found"}
                    )

                message_key = f"messages:{user_id}:{conversation_id}"
                messages = self.app.state.redis_client.lrange(message_key, 0, -1)

                if not messages:
                    return JSONResponse(
                        status_code=200,
                        content={"messages": []}
                    )

                # Parse JSON strings back into objects
                parsed_messages = [json.loads(msg) for msg in messages]

                # Sort messages by timestamp
                parsed_messages.sort(key=lambda x: x.get("timestamp", ""))

                return JSONResponse(
                    status_code=200,
                    content={"messages": parsed_messages}
                )

            except Exception as e:
                print(f"[/messages] Error retrieving messages: {str(e)}")
                return JSONResponse(
                    status_code=500,
                    content={"error": f"Failed to retrieve messages: {str(e)}"}
                )

        @self.app.get("/chat/list")
        async def list_chats(
            user_id: str = Depends(get_current_user)
        ):
            """
            Get list of all chats for a user, sorted by most recent first.
            
            Args:
                user_id (str): The ID of the user
                token_data (HTTPAuthorizationCredentials): The authentication token data
            """
            try:

                # Get conversation IDs from sorted set, newest first
                user_chats_key = f"user_chats:{user_id}"
                conversation_ids = self.app.state.redis_client.zrevrange(user_chats_key, 0, -1)

                if not conversation_ids:
                    return JSONResponse(
                        status_code=200,
                        content={"chats": []}
                    )

                # Get metadata for each conversation
                chats = []
                for conv_id in conversation_ids:
                    meta_key = f"chat_metadata:{user_id}:{conv_id}"
                    meta_data = self.app.state.redis_client.get(meta_key)
                    if meta_data:
                        data = json.loads(meta_data)
                        if "name" not in data:
                            data["name"] = ""
                        chats.append(data)

                return JSONResponse(
                    status_code=200,
                    content={"chats": chats}
                )

            except Exception as e:
                print(f"[/chat/list] Error retrieving chats: {str(e)}")
                return JSONResponse(
                    status_code=500,
                    content={"error": f"Failed to retrieve chats: {str(e)}"}
                )

        @self.app.delete("/chat/{conversation_id}")
        async def delete_chat(
            conversation_id: str,
            user_id: str = Depends(get_current_user)
        ):
            """
            Delete a chat conversation and all its associated data.
            
            Args:
                user_id (str): The ID of the user
                conversation_id (str): The ID of the conversation to delete
                token_data (HTTPAuthorizationCredentials): The authentication token data
            """
            try:
                # Verify chat exists and belongs to user
                meta_key = f"chat_metadata:{user_id}:{conversation_id}"
                if not self.app.state.redis_client.exists(meta_key):
                    return JSONResponse(
                        status_code=404,
                        content={"error": "Chat not found or access denied"}
                    )

                # Close any active WebSocket connections for this chat
                connection = self.app.state.manager.get_connection(user_id, conversation_id)
                if connection:
                    await connection.close(code=4000, reason="Chat deleted")
                    self.app.state.manager.remove_connection(user_id, conversation_id)

                # Delete chat metadata
                self.app.state.redis_client.delete(meta_key)

                # Delete chat messages
                message_key = f"messages:{user_id}:{conversation_id}"
                self.app.state.redis_client.delete(message_key)

                # Remove from user's chat list
                user_chats_key = f"user_chats:{user_id}"
                self.app.state.redis_client.zrem(user_chats_key, conversation_id)

                return JSONResponse(
                    status_code=200,
                    content={"message": "Chat deleted successfully"}
                )

            except Exception as e:
                print(f"[/chat/delete] Error deleting chat: {str(e)}")
                return JSONResponse(
                    status_code=500,
                    content={"error": f"Failed to delete chat: {str(e)}"}
                )

        @self.app.post("/upload")
        async def upload_document(
            file: UploadFile = File(...),
            user_id: str = Depends(get_current_user)
        ):
            """Upload and process a document."""
            try:

                # Generate unique document ID
                document_id = str(uuid.uuid4())

                # Read file content
                content = await file.read()

                # Process document
                doc_processor = DocumentProcessingService()
                chunks = doc_processor.process_document(content, file.filename)

                # Store document metadata
                document_metadata = {
                    "id": document_id,
                    "filename": file.filename,
                    "upload_timestamp": time.time(),
                    "num_chunks": len(chunks),
                    "user_id":  user_id
                }

                # Store document metadata
                doc_key = f"document:{document_id}"
                self.app.state.redis_client.set(doc_key, json.dumps(document_metadata))

                # Add to user's document list
                user_docs_key = f"user_documents:{user_id}"
                self.app.state.redis_client.sadd(user_docs_key, document_id)

                # Store document chunks
                chunks_key = f"document_chunks:{document_id}"
                chunks_data = [
                    {
                        "text": chunk.page_content,
                        "metadata": {
                            **chunk.metadata,
                            "document_id": document_id
                        }
                    }
                    for chunk in chunks
                ]
                self.app.state.redis_client.set(chunks_key, json.dumps(chunks_data))

                return JSONResponse(
                    status_code=200,
                    content={
                        "message": "Document processed successfully",
                        "document": document_metadata
                    },
                )

            except Exception as e:
                print(f"[/upload] Error processing document: {str(e)}")
                return JSONResponse(status_code=500, content={"error": str(e)})

        @self.app.get("/documents")
        async def get_user_documents(
            user_id: str = Depends(get_current_user)
        ):
            """Retrieve all documents for a user."""
            try:

                # Get all document IDs for the user
                user_docs_key = f"user_documents:{user_id}"
                doc_ids = self.app.state.redis_client.smembers(user_docs_key)

                if not doc_ids:
                    return JSONResponse(
                        status_code=200,
                        content={"documents": []}
                    )

                # Get metadata for each document
                documents = []
                for doc_id in doc_ids:
                    doc_key = f"document:{doc_id}"
                    doc_data = self.app.state.redis_client.get(doc_key)
                    if doc_data:
                        documents.append(json.loads(doc_data))

                return JSONResponse(
                    status_code=200,
                    content={"documents": documents}
                )

            except Exception as e:
                print(f"[/documents] Error retrieving documents: {str(e)}")
                return JSONResponse(status_code=500, content={"error": str(e)})

        @self.app.get("/documents/{document_id}/chunks")
        async def get_document_chunks_by_id(
            document_id: str,
            user_id: str = Depends(get_current_user)
        ):
            """Retrieve chunks for a specific document."""
            try:

                # Verify document belongs to user
                user_docs_key = f"user_documents:{user_id}"
                if not self.app.state.redis_client.sismember(user_docs_key, document_id):
                    return JSONResponse(
                        status_code=404,
                        content={"error": "Document not found or access denied"}
                    )

                # Get document chunks
                chunks_key = f"document_chunks:{document_id}"
                chunks_data = self.app.state.redis_client.get(chunks_key)

                if not chunks_data:
                    return JSONResponse(
                        status_code=404,
                        content={"error": "Document chunks not found"}
                    )

                return JSONResponse(
                    status_code=200,
                    content=json.loads(chunks_data)
                )

            except Exception as e:
                print(f"[/documents/chunks] Error retrieving chunks: {str(e)}")
                return JSONResponse(status_code=500, content={"error": str(e)})

        @self.app.delete("/documents/{document_id}")
        async def delete_document(
            document_id: str,
            user_id: str = Depends(get_current_user)
        ):
            """Delete a document and its associated data from the database."""
            try:
                # Verify document belongs to user
                user_docs_key = f"user_documents:{user_id}"
                if not self.app.state.redis_client.sismember(user_docs_key, document_id):
                    return JSONResponse(
                        status_code=404,
                        content={"error": "Document not found or access denied"}
                    )

                # Delete document metadata
                doc_key = f"document:{document_id}"
                self.app.state.redis_client.delete(doc_key)

                # Delete document chunks
                chunks_key = f"document_chunks:{document_id}"
                self.app.state.redis_client.delete(chunks_key)

                # Remove from user's document list
                self.app.state.redis_client.srem(user_docs_key, document_id)

                return JSONResponse(
                    status_code=200,
                    content={"message": "Document deleted successfully"}
                )

            except Exception as e:
                print(f"[/documents/delete] Error deleting document: {str(e)}")
                return JSONResponse(status_code=500, content={"error": str(e)})

        @self.app.post("/set_api_keys")
        async def set_api_keys(
            keys: APIKeys,
            user_id: str = Depends(get_current_user)
        ):
            """
            Store API keys for a user in Redis.
            
            Args:
                user_id (str): The ID of the user
                keys (APIKeys): The API keys to store
            """
            try:
                # Store keys in Redis with user-specific prefix
                key_prefix = f"api_keys:{user_id}"
                self.app.state.redis_client.hset(
                    key_prefix,
                    mapping={
                        "sambanova_key": keys.sambanova_key,
                        "serper_key": keys.serper_key,
                        "exa_key": keys.exa_key,
                        "fireworks_key": keys.fireworks_key
                    }
                )

                return JSONResponse(
                    status_code=200,
                    content={"message": "API keys stored successfully"}
                )

            except Exception as e:
                print(f"[/set_api_keys] Error storing API keys: {str(e)}")
                return JSONResponse(
                    status_code=500,
                    content={"error": f"Failed to store API keys: {str(e)}"}
                )

        @self.app.get("/get_api_keys")
        async def get_api_keys(
            user_id: str = Depends(get_current_user)
        ):
            """
            Retrieve stored API keys for a user.
            
            Args:
                user_id (str): The ID of the user
            """
            try:
                key_prefix = f"api_keys:{user_id}"
                stored_keys = self.app.state.redis_client.hgetall(key_prefix)

                if not stored_keys:
                    return JSONResponse(
                        status_code=404,
                        content={"error": "No API keys found for this user"}
                    )

                return JSONResponse(
                    status_code=200,
                    content={
                        "sambanova_key": stored_keys.get("sambanova_key", ""),
                        "serper_key": stored_keys.get("serper_key", ""),
                        "exa_key": stored_keys.get("exa_key", ""),
                        "fireworks_key": stored_keys.get("fireworks_key", "")
                    }
                )

            except Exception as e:
                print(f"[/get_api_keys] Error retrieving API keys: {str(e)}")
                return JSONResponse(
                    status_code=500,
                    content={"error": f"Failed to retrieve API keys: {str(e)}"}
                )

    async def execute_research(self, crew: ResearchCrew, parameters: Dict[str, Any]):
        extractor = UserPromptExtractor(crew.llm.api_key)
        combined_text = " ".join([
            parameters.get("industry", ""),
            parameters.get("company_stage", ""),
            parameters.get("geography", ""),
            parameters.get("funding_stage", ""),
            parameters.get("product", ""),
        ]).strip()
        extracted_info = extractor.extract_lead_info(combined_text)

        raw_result, _ = await asyncio.to_thread(crew.execute_research, extracted_info)
        return raw_result

    async def execute_financial(self, crew: FinancialAnalysisCrew, parameters: Dict[str,Any], provider: str):
        fextractor = FinancialPromptExtractor(crew.llm.api_key, provider)
        query_text = parameters.get("query_text","")
        extracted_ticker, extracted_company = fextractor.extract_info(query_text)

        if not extracted_ticker:
            extracted_ticker = parameters.get("ticker","")
        if not extracted_company:
            extracted_company = parameters.get("company_name","")

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
    app = create_app()
    uvicorn.run(app, host="127.0.0.1", port=8000)