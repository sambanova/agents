import structlog
from agents.auth.auth0_config import get_current_user_id
from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import JSONResponse

logger = structlog.get_logger(__name__)

router = APIRouter(
    prefix="/share",
)


@router.get("/{share_token}")
async def get_shared_conversation(request: Request, share_token: str):
    """Get shared conversation (public access, no authentication required)"""
    try:
        shared_conversation = (
            await request.app.state.redis_storage_service.get_shared_conversation(
                share_token
            )
        )

        if not shared_conversation:
            return JSONResponse(
                status_code=404, content={"error": "Shared conversation not found"}
            )

        return JSONResponse(status_code=200, content=shared_conversation)

    except Exception as e:
        logger.error(f"Error accessing shared conversation: {str(e)}")
        return JSONResponse(status_code=500, content={"error": str(e)})


@router.get("/{share_token}/files/{file_id}")
async def get_shared_file(
    request: Request,
    share_token: str,
    file_id: str,
):
    """Get file from shared conversation (public access, no authentication required)"""
    try:
        # First verify the share token is valid and get the original user/conversation
        shared_conversation = (
            await request.app.state.redis_storage_service.get_shared_conversation(
                share_token
            )
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
        conversation_messages = (
            await request.app.state.redis_storage_service.get_messages(
                original_user_id, conversation_id
            )
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
        file_data, file_metadata = (
            await request.app.state.redis_storage_service.get_file(
                original_user_id, file_id
            )
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


@router.delete("/{share_token}")
async def delete_share(
    request: Request,
    share_token: str,
    user_id: str = Depends(get_current_user_id),
):
    """Delete a share (owner only)"""
    try:
        success = await request.app.state.redis_storage_service.delete_share(
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
