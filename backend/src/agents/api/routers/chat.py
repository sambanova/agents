import asyncio
import json
import os
import time
import uuid
from typing import Optional

import structlog
from agents.auth.auth0_config import (
    extract_user_id,
    get_current_user_id,
    token_verifier,
)
from fastapi import APIRouter, Depends, Query, Request, WebSocket
from fastapi.responses import JSONResponse
from fastapi.websockets import WebSocketDisconnect, WebSocketState

logger = structlog.get_logger(__name__)

router = APIRouter(
    prefix="/chat",
)


# WebSocket endpoint to handle user messages
@router.websocket("")
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

            # Extract the JWT token (remove "Bearer " prefix)
            jwt_token = token[7:]  # Remove "Bearer " prefix

            try:
                # Verify the token and get the payload
                token_payload = token_verifier.verify(jwt_token)
                # Extract user ID from the payload
                user_id = extract_user_id(token_payload)
            except Exception as auth_error:
                logger.error(f"Token verification failed: {str(auth_error)}")
                try:
                    await websocket.close(
                        code=4001, reason="Invalid authentication token"
                    )
                except Exception as close_error:
                    logger.error(f"Error closing WebSocket: {str(close_error)}")
                return

            # Verify conversation exists and belongs to user
            if not await websocket.app.state.redis_storage_service.verify_conversation_exists(
                user_id, conversation_id
            ):
                try:
                    await websocket.close(code=4004, reason="Conversation not found")
                except Exception as close_error:
                    logger.error(f"Error closing WebSocket: {str(close_error)}")
                return

            await websocket.app.state.manager.handle_websocket(
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


@router.post("/init")
async def init_chat(
    request: Request,
    chat_name: Optional[str] = None,
    user_id: str = Depends(get_current_user_id),
):
    """
    Initializes a new chat session and stores the provided API keys.
    Returns a chat ID for subsequent interactions.

    Args:
        chat_name (Optional[str]): Optional name for the chat. If not provided, a default will be used.
        token_data (HTTPAuthorizationCredentials): The authentication token data
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
            "user_id": user_id,
        }
        chat_meta_key = f"chat_metadata:{user_id}:{conversation_id}"
        await request.app.state.redis_client.set(
            chat_meta_key, json.dumps(metadata), user_id
        )

        # Add to user's conversation list
        user_chats_key = f"user_chats:{user_id}"
        await request.app.state.redis_client.zadd(
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
        logger.error(f"Error initializing chat: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"error": f"Failed to initialize chat: {str(e)}"},
        )


@router.get("/history/{conversation_id}")
async def get_conversation_messages(
    request: Request,
    conversation_id: str,
    user_id: str = Depends(get_current_user_id),
):
    """
    Retrieve all messages for a specific conversation.

    Args:
        user_id (str): The ID of the user
        conversation_id (str): The ID of the conversation
        token_data (HTTPAuthorizationCredentials): The authentication token data
    """
    try:
        # Verify chat exists and belongs to user
        if not await request.app.state.redis_storage_service.verify_conversation_exists(
            user_id, conversation_id
        ):
            return JSONResponse(
                status_code=404,
                content={"error": "Chat not found or access denied"},
            )

        messages = await request.app.state.redis_storage_service.get_messages(
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


@router.get("/list")
async def list_chats(
    request: Request,
    user_id: str = Depends(get_current_user_id),
):
    """
    Get list of all chats for a user, sorted by most recent first.

    Args:
        user_id (str): The ID of the user
        token_data (HTTPAuthorizationCredentials): The authentication token data
    """
    try:
        start_time = time.time()
        if not user_id:
            return JSONResponse(
                status_code=401,
                content={"error": "Invalid authentication token"},
            )

        # Get all conversation IDs for the user, sorted by most recent
        user_chats_key = f"user_chats:{user_id}"
        conversation_ids = await request.app.state.redis_client.zrevrange(
            user_chats_key, 0, -1
        )

        if not conversation_ids:
            return JSONResponse(status_code=200, content={"chats": []})

        # Optimize: Use controlled concurrent Redis calls to avoid connection pool exhaustion
        meta_keys = [
            f"chat_metadata:{user_id}:{conv_id}" for conv_id in conversation_ids
        ]

        # Limit concurrent connections to prevent pool exhaustion
        # Use environment variable or default to 5 for safety
        max_concurrent_connections = int(
            os.getenv("REDIS_MAX_CONCURRENT_CONNECTIONS", "5")
        )
        semaphore = asyncio.Semaphore(max_concurrent_connections)

        logger.debug(
            f"Using max {max_concurrent_connections} concurrent Redis connections for user {user_id}"
        )

        async def get_metadata_with_semaphore(meta_key):
            async with semaphore:
                return await request.app.state.redis_client.get(meta_key, user_id)

        # Try concurrent approach first
        try:
            # Execute metadata retrieval calls with controlled concurrency
            meta_data_tasks = [
                get_metadata_with_semaphore(meta_key) for meta_key in meta_keys
            ]
            meta_data_results = await asyncio.gather(
                *meta_data_tasks, return_exceptions=True
            )

            # Check if we got connection errors
            connection_errors = [
                r
                for r in meta_data_results
                if isinstance(r, Exception) and "Too many connections" in str(r)
            ]
            if connection_errors:
                logger.warning(
                    f"Connection pool exhausted, falling back to sequential calls for user {user_id}"
                )
                raise Exception("Connection pool exhausted")

        except Exception as e:
            # Fallback to sequential calls if concurrent approach fails
            logger.info(f"Using sequential Redis calls for user {user_id}")
            meta_data_results = []
            for meta_key in meta_keys:
                try:
                    result = await request.app.state.redis_client.get(meta_key, user_id)
                    meta_data_results.append(result)
                except Exception as get_error:
                    logger.error(
                        f"Failed to get metadata for key {meta_key}: {get_error}"
                    )
                    meta_data_results.append(None)

        # Process results
        chats = []
        for i, meta_data in enumerate(meta_data_results):
            if isinstance(meta_data, Exception):
                logger.error(
                    f"Failed to get metadata for conversation {conversation_ids[i]}: {meta_data}"
                )
                continue

            if meta_data:
                try:
                    data = json.loads(meta_data)
                    if "name" not in data:
                        data["name"] = ""
                    chats.append(data)
                except json.JSONDecodeError:
                    logger.error(
                        f"Failed to parse metadata for conversation {conversation_ids[i]}"
                    )
                    continue

        duration = time.time() - start_time
        logger.info(
            f"Retrieved {len(chats)} chats for user {user_id} in {duration:.3f}s",
            user_id=user_id,
            chat_count=len(chats),
            duration_ms=round(duration * 1000, 2),
        )

        return JSONResponse(status_code=200, content={"chats": chats})

    except Exception as e:
        logger.error(f"Error retrieving chats: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"error": f"Failed to retrieve chats: {str(e)}"},
        )


@router.delete("/{conversation_id}")
async def delete_chat(
    request: Request,
    conversation_id: str,
    user_id: str = Depends(get_current_user_id),
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
        if not await request.app.state.redis_storage_service.verify_conversation_exists(
            user_id, conversation_id
        ):
            return JSONResponse(
                status_code=404,
                content={"error": "Chat not found or access denied"},
            )

        # Get all messages in the conversation to find file references
        conversation_messages = (
            await request.app.state.redis_storage_service.get_messages(
                user_id, conversation_id
            )
        )

        # Collect all file IDs referenced in the conversation
        file_ids_to_delete = set()

        for message in conversation_messages:
            # Check files in additional_kwargs
            files = message.get("additional_kwargs", {}).get("files", [])
            file_ids_to_delete.update(files)

        # Delete all referenced files
        deleted_files = []
        failed_files = []

        for file_id in file_ids_to_delete:
            try:
                # Delete the file directly
                result = await request.app.state.redis_storage_service.delete_file(
                    user_id, file_id
                )
                if result:
                    deleted_files.append(file_id)
                    logger.info(f"Deleted file {file_id} as part of chat deletion")
                else:
                    failed_files.append(file_id)
                    logger.warning(
                        f"Failed to delete file {file_id} as part of chat deletion"
                    )

            except Exception as e:
                failed_files.append(file_id)
                logger.error(
                    f"Error deleting file {file_id} as part of chat deletion: {str(e)}"
                )

        # Close any active WebSocket connections for this chat
        connection = request.app.state.manager.get_connection(user_id, conversation_id)
        if connection:
            await connection.close(code=4000, reason="Chat deleted")
            request.app.state.manager.remove_connection(user_id, conversation_id)

        # Delete chat metadata
        await request.app.state.redis_storage_service.delete_all_user_data(
            user_id, conversation_id
        )

        # Log deletion summary
        logger.info(
            f"Chat deletion completed for {conversation_id}. "
            f"Deleted {len(deleted_files)} files, {len(failed_files)} files failed to delete",
            conversation_id=conversation_id,
            deleted_files_count=len(deleted_files),
            failed_files_count=len(failed_files),
        )

        return JSONResponse(
            status_code=200,
            content={
                "message": "Chat deleted successfully",
                "deleted_files_count": len(deleted_files),
                "failed_files_count": len(failed_files),
            },
        )

    except Exception as e:
        logger.error(f"Error deleting chat: {str(e)}", conversation_id=conversation_id)
        return JSONResponse(
            status_code=500,
            content={"error": f"Failed to delete chat: {str(e)}"},
        )
