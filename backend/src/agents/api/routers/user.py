import structlog
from agents.auth.auth0_config import get_current_user_id
from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

logger = structlog.get_logger(__name__)


router = APIRouter(
    prefix="/user",
)


@router.delete("/data")
async def delete_user_data(
    request: Request,
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
        conversation_ids = await request.app.state.redis_client.zrange(
            user_chats_key, 0, -1
        )

        for conversation_id in conversation_ids:
            # Close any active WebSocket connections
            connection = request.app.state.manager.get_connection(
                user_id, conversation_id
            )
            if connection:
                await connection.close(code=4000, reason="User data deleted")
                request.app.state.manager.remove_connection(user_id, conversation_id)

            # Delete chat metadata and messages
            meta_key = f"chat_metadata:{user_id}:{conversation_id}"
            message_key = f"messages:{user_id}:{conversation_id}"
            await request.app.state.redis_client.delete(meta_key)
            await request.app.state.redis_client.delete(message_key)

        # Delete the user's chat list
        await request.app.state.redis_client.delete(user_chats_key)

        # 2. Delete all documents
        user_docs_key = f"user_documents:{user_id}"
        doc_ids = await request.app.state.redis_client.smembers(user_docs_key)

        for doc_id in doc_ids:
            # Delete document metadata and chunks
            doc_key = f"document:{doc_id}"
            chunks_key = f"document_chunks:{doc_id}"
            await request.app.state.redis_client.delete(doc_key)
            await request.app.state.redis_client.delete(chunks_key)

        # Delete the user's document list
        await request.app.state.redis_client.delete(user_docs_key)

        # 3. Delete API keys
        key_prefix = f"api_keys:{user_id}"
        await request.app.state.redis_client.delete(key_prefix)

        return JSONResponse(
            status_code=200,
            content={"message": "All user data deleted successfully"},
        )

    except Exception as e:
        logger.error(f"Error deleting user data: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"error": "An internal error occurred"},
        )
