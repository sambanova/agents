from fastapi import FastAPI, File, Query, Request, BackgroundTasks, UploadFile
from pydantic import BaseModel
import json
import uvicorn
import re
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import time
import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import Optional, Dict, Any, List
from starlette.websockets import WebSocketState
from contextlib import asynccontextmanager
import logging

from api.agents.user_proxy import UserProxyAgent
from api.websocket_manager import WebSocketConnectionManager

from api.utils import initialize_agent_runtime
from utils.logging import logger
from autogen_core import MessageContext
from config.model_registry import model_registry
import os
import sys

import redis
import uuid

from autogen_core import (
    DefaultTopicId,
    RoutedAgent,
    default_subscription,
    message_handler,
)

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from api.data_types import APIKeys, EndUserMessage, AgentStructuredResponse, TestMessage


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

def estimate_tokens_regex(text: str) -> int:
        return len(re.findall(r"\w+|\S", text))

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Handles the startup and shutdown lifespan events for the FastAPI application.

    Initializes the agent runtime and registers the UserProxyAgent.
    """

    redis_host = os.getenv("REDIS_HOST", "localhost")
    redis_port = int(os.getenv("REDIS_PORT", "6379"))
    
    # Create a Redis connection pool
    pool = redis.ConnectionPool(
        host=redis_host,
        port=redis_port,
        db=0,
        decode_responses=True,
        max_connections=20  # Adjust based on expected concurrent connections
    )
    
    # Create Redis client with connection pool
    app.state.redis_client = redis.Redis(
        connection_pool=pool,
        decode_responses=True
    )
    print(f"[LeadGenerationAPI] Using Redis at {redis_host}:{redis_port} with connection pool")

    app.state.manager = WebSocketConnectionManager(
        redis_client=app.state.redis_client
    )
    UserProxyAgent.connection_manager = app.state.manager
    SemanticRouterAgent.connection_manager = app.state.manager

    yield  # This separates the startup and shutdown logic

    # Cleanup chat-specific agent runtimes
    chat_keys = app.state.redis_client.keys("chat_manager:*")
    for key in chat_keys:
        chat_data = app.state.redis_client.get(key)
        if chat_data:
            chat_info = json.loads(chat_data)
            # TODO: Add cleanup for chat-specific agent runtime
            app.state.redis_client.delete(key)

    # Close Redis connection pool
    app.state.redis_client.close()
    pool.disconnect()

    # Cleanup default agent runtime
    await app.state.agent_runtime.close()

class LeadGenerationAPI:
    def __init__(self):
        self.app = FastAPI(lifespan=lifespan)
        self.setup_cors()
        self.setup_routes()
        self.context_length_summariser = 64000
        self.executor = ThreadPoolExecutor(max_workers=2)

    def verify_conversation_exists(self, user_id: str, conversation_id: str) -> bool:
        """
        Verify if a conversation exists for the given user.
        
        Args:
            user_id (str): The ID of the user
            conversation_id (str): The ID of the conversation
            
        Returns:
            bool: True if conversation exists, False otherwise
        """
        meta_key = f"chat_metadata:{user_id}:{conversation_id}"
        return bool(self.app.state.redis_client.exists(meta_key))

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
        # WebSocket endpoint to handle user messages
        @self.app.websocket("/chat")
        async def websocket_endpoint(
            websocket: WebSocket,
            user_id: str = Query(..., description="User ID"),
            conversation_id: str = Query(..., description="Conversation ID")
        ):
            """
            WebSocket endpoint for handling user chat messages.

            Args:
                websocket (WebSocket): The WebSocket connection.
                user_id (str): The ID of the user.
                conversation_id (str): The ID of the conversation.
            """
            await self.app.state.manager.handle_websocket(
                websocket, 
                user_id, 
                conversation_id
            )

        @self.app.post("/route")
        async def determine_route(request: Request, query_request: QueryRequest):
            sambanova_key = request.headers.get("x-sambanova-key")
            if not sambanova_key:
                return JSONResponse(
                    status_code=401,
                    content={"error": "Missing required SambaNova API key"}
                )
            try:
                router = QueryRouterService(sambanova_key, "sambanova")
                route_result = await router.route_query(query_request.query)
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

        @self.app.post("/execute/{query_type}")
        async def execute_query(
            request: Request,
            query_type: str,
            parameters: Dict[str, Any]
        ):
            sambanova_key = request.headers.get("x-sambanova-key")
            serper_key = request.headers.get("x-serper-key")
            exa_key = request.headers.get("x-exa-key")

            user_id = request.headers.get("x-user-id", "")
            run_id = request.headers.get("x-run-id", "")

            try:
                # Load document chunks if document_ids are provided
                if "document_ids" in parameters:
                    doc_ids = parameters["document_ids"]
                    chunks_text = []

                    for doc_id in doc_ids:
                        # Verify document exists and belongs to user
                        user_docs_key = f"user_documents:{user_id}"
                        if not self.app.state.redis_client.sismember(user_docs_key, doc_id):
                            continue  # Skip if document doesn't belong to user

                        chunks_key = f"document_chunks:{doc_id}"
                        chunks_data = self.app.state.redis_client.get(chunks_key)

                        if chunks_data:
                            chunks = json.loads(chunks_data)
                            chunks_text.extend([chunk['text'] for chunk in chunks])

                    if chunks_text:
                        combined_text = "\n".join(chunks_text)
                        token_count = estimate_tokens_regex(combined_text)
                        # Check if combined document chunks exceed context length
                        if (
                            token_count > self.context_length_summariser
                        ): 
                            return JSONResponse(
                                status_code=400,
                                content={
                                    "error": "Combined document length exceeds maximum context window size. Please reduce the number or size of documents."
                                },
                            )
                        parameters["docs"] = combined_text

                if query_type == "sales_leads":
                    if not exa_key:
                        return JSONResponse(
                            status_code=401,
                            content={"error": "Missing required Exa API key for sales leads"}
                        )
                    crew = ResearchCrew(
                        llm_api_key=sambanova_key,
                        exa_key=exa_key,
                        user_id=user_id,
                        run_id=run_id,
                        provider="sambanova"
                    )
                    raw_result = await self.execute_research(crew, parameters)
                    parsed_result = json.loads(raw_result)
                    outreach_list = parsed_result.get("outreach_list", [])
                    return JSONResponse(content={"results": outreach_list})

                elif query_type == "educational_content" or query_type == "deep_research":                        
                    if not serper_key:
                        return JSONResponse(
                            status_code=401,
                            content={"error": "Missing required Serper API key for educational content"}
                        )
                    edu_flow = SambaResearchFlow(
                        llm_api_key=sambanova_key,
                        serper_key=serper_key,
                        user_id=user_id,
                        run_id=run_id,
                        provider="sambanova",
                        docs_included="docs" in parameters
                    )
                    edu_inputs = {
                        "topic": parameters["topic"] if query_type == "educational_content" else parameters["deep_research_topic"],
                        "audience_level": parameters.get("audience_level", "intermediate"),
                        "additional_context": ", ".join(parameters.get("focus_areas", []))
                    }
                    if "docs" in parameters:
                        edu_inputs["docs"] = parameters["docs"]
                    edu_flow.input_variables = edu_inputs
                    loop = asyncio.get_running_loop()
                    result = await loop.run_in_executor(None, edu_flow.kickoff)

                    if isinstance(result, str):
                        sections_with_content = json.loads(result)
                    else:
                        sections_with_content = result

                    return JSONResponse(content=sections_with_content)

                elif query_type == "financial_analysis":
                    if not exa_key or not serper_key:
                        return JSONResponse(
                            status_code=401,
                            content={"error": "Missing required Exa or Serper API keys for financial analysis"}
                        )
                    crew = FinancialAnalysisCrew(
                        llm_api_key=sambanova_key,
                        exa_key=exa_key,
                        serper_key=serper_key,
                        user_id=user_id,
                        run_id=run_id,
                        provider="sambanova",
                        docs_included="docs" in parameters
                    )
                    raw_result = await self.execute_financial(crew, parameters, "sambanova")
                    parsed_fin = json.loads(raw_result)
                    return JSONResponse(content=parsed_fin)

                else:
                    return JSONResponse(
                        status_code=400,
                        content={"error": f"Unknown query type: {query_type}"}
                    )

            except Exception as e:
                print(f"[/execute/{query_type}] Error executing query: {str(e)}")
                return JSONResponse(status_code=500, content={"error": str(e)})

        @self.app.get("/stream/logs")
        async def stream_logs(request: Request, user_id: str, run_id: str):
            """
            SSE endpoint that streams agent logs for the given user_id + run_id.
            """
            channel = f"agent_thoughts:{user_id}:{run_id}"
            print(f"[stream_logs] Starting SSE for user_id={user_id}, run_id={run_id}, channel={channel}")

            try:
                local_redis = self.app.state.redis_client

                pubsub = local_redis.pubsub(ignore_subscribe_messages=True)
                pubsub.subscribe(channel)

                async def event_generator():
                    try:
                        yield {
                            "event": "message",
                            "data": json.dumps({
                                "type": "connection_established",
                                "message": "Connected to SSE stream"
                            })
                        }
                        while True:
                            if await request.is_disconnected():
                                print("[stream_logs] Client disconnected")
                                break

                            message = pubsub.get_message(timeout=1.0)
                            if message and message["type"] == "message":
                                data_str = message["data"]
                                yield {
                                    "event": "message",
                                    "data": data_str
                                }

                            await asyncio.sleep(0.25)
                            yield {
                                "event": "ping",
                                "data": json.dumps({"type":"ping"})
                            }
                    except Exception as ex:
                        print(f"[stream_logs] Error in SSE generator: {ex}")
                    finally:
                        print("[stream_logs] unsubscribing, closing pubsub")
                        pubsub.unsubscribe()
                        pubsub.close()

                return EventSourceResponse(
                    event_generator(),
                    media_type="text/event-stream",
                    headers={"Cache-Control":"no-cache","Connection":"keep-alive"}
                )
            except Exception as e:
                print(f"[stream_logs] Error setting up SSE: {e}")
                return JSONResponse(status_code=500, content={"error": str(e)})

        @self.app.post("/chat/init")
        async def init_chat(request: Request, chat_name: Optional[str] = None):
            """
            Initializes a new chat session and stores the provided API keys.
            Returns a chat ID for subsequent interactions.
            
            Args:
                request (Request): The request object containing headers
                chat_name (Optional[str]): Optional name for the chat. If not provided, a default will be used.
            """
            user_id = request.headers.get("x-user-id", "anonymous")

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

                #TODO: init autogen agent

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
            
        @self.app.get("/chat/history/{user_id}/{conversation_id}")
        async def get_conversation_messages(user_id: str, conversation_id: str):
            """
            Retrieve all messages for a specific conversation.
            
            Args:
                user_id (str): The ID of the user
                conversation_id (str): The ID of the conversation
            """
            try:
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
            
        @self.app.get("/chat/list/{user_id}")
        async def list_chats(user_id: str):
            """
            Get list of all chats for a user, sorted by most recent first.
            
            Args:
                user_id (str): The ID of the user
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

        @self.app.delete("/chat/{user_id}/{conversation_id}")
        async def delete_chat(user_id: str, conversation_id: str):
            """
            Delete a chat conversation and all its associated data.
            
            Args:
                user_id (str): The ID of the user
                conversation_id (str): The ID of the conversation to delete
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

        # ----------------------------------------------------------------
        # NEW ENDPOINT: /newsletter_chat/init
        # ----------------------------------------------------------------
        @self.app.post("/newsletter_chat/init")
        def init_newsletter_chat(request: Request):
            """
            Initializes a conversation with ConvoNewsletterCrew using the provided keys.
            """
            sambanova_key = request.headers.get("x-sambanova-key","")
            serper_key = request.headers.get("x-serper-key","")
            exa_key = request.headers.get("x-exa-key","")
            user_id = request.headers.get("x-user-id","anonymous")
            run_id = request.headers.get("x-run-id","")

            try:
                init_data = crew_chat.api_init_conversation(
                    sambanova_key=sambanova_key,
                    serper_key=serper_key,
                    exa_key=exa_key,
                    user_id=user_id,
                    run_id=run_id
                )
                return JSONResponse(
                    status_code=200,
                    content={
                        "conversation_id": init_data["conversation_id"],
                        "assistant_message": init_data["assistant_message"]
                    }
                )
            except Exception as e:
                print(f"[/newsletter_chat/init] Error: {str(e)}")
                return JSONResponse(status_code=500, content={"error": str(e)})

        # ----------------------------------------------------------------
        # NEW ENDPOINT: /newsletter_chat/message/{conversation_id}
        # ----------------------------------------------------------------
        @self.app.post("/newsletter_chat/message/{conversation_id}")
        def newsletter_chat_message(conversation_id: str, body: ChatRequest, request: Request):
            """
            Sends a user message to an existing conversation, returning assistant's reply.
            """
            user_id = request.headers.get("x-user-id","anonymous")
            user_message = body.message.strip()
            if not user_message:
                return JSONResponse(
                    status_code=400,
                    content={"error": "Empty user message."}
                )
            try:
                response_text = crew_chat.api_process_message(
                    conversation_id,
                    user_message,
                    user_id=user_id
                )
                return JSONResponse(
                    status_code=200,
                    content={"assistant_response": response_text}
                )
            except ValueError as ve:
                print(f"[/newsletter_chat/message] Not found: {str(ve)}")
                return JSONResponse(
                    status_code=404,
                    content={"error": str(ve)}
                )
            except Exception as e:
                print(f"[/newsletter_chat/message] Error: {str(e)}")
                return JSONResponse(
                    status_code=500,
                    content={"error": str(e)}
                )

        # ----------------------------------------------------------------
        # NEW ENDPOINT: /newsletter_chat/history/{conversation_id}
        # ----------------------------------------------------------------
        @self.app.get("/newsletter_chat/history/{conversation_id}")
        def conversation_history(conversation_id: str, request: Request):
            """
            Returns the entire messages list for the specified conversation, 
            so the front end can show the entire conversation from start.
            """
            user_id = request.headers.get("x-user-id","anonymous")
            try:
                data = crew_chat.api_get_full_history(conversation_id, user_id)
                return JSONResponse(
                    status_code=200,
                    content=data
                )
            except ValueError as ve:
                return JSONResponse(
                    status_code=404,
                    content={"error":str(ve)}
                )
            except Exception as e:
                print(f"[/newsletter_chat/history] Error: {str(e)}")
                return JSONResponse(
                    status_code=500,
                    content={"error": str(e)}
                )

        # ~~~~ Existing Helper Methods for Sales Leads, Fin Analysis, etc. ~~~~

        @self.app.post("/upload")
        async def upload_document(
            request: Request,
            file: UploadFile = File(...),
        ):
            """Upload and process a document."""
            try:
                # Get user_id from headers
                user_id = request.headers.get("x-user-id", "")

                if not user_id:
                    return JSONResponse(
                        status_code=400,
                        content={"error": "x-user-id header is required"}
                    )

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
                    "user_id": user_id
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

        @self.app.get("/documents/{user_id}")
        async def get_user_documents(user_id: str):
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

        @self.app.get("/documents/{user_id}/{document_id}/chunks")
        async def get_document_chunks_by_id(user_id: str, document_id: str):
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

        @self.app.delete("/documents/{user_id}/{document_id}")
        async def delete_document(user_id: str, document_id: str):
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

        @self.app.post("/set_api_keys/{user_id}")
        async def set_api_keys(user_id: str, keys: APIKeys):
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

        @self.app.get("/get_api_keys/{user_id}")
        async def get_api_keys(user_id: str):
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
