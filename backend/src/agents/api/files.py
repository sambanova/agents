from fastapi import APIRouter, HTTPException, Depends, Query, Request
from fastapi.responses import Response
from fastapi.security import HTTPAuthorizationCredentials
from fastapi_clerk_auth import ClerkConfig, ClerkHTTPBearer
import jwt
import os
from agents.utils.logging import logger

# Auth setup
CLERK_JWT_ISSUER = os.environ.get("CLERK_JWT_ISSUER")
clerk_config = ClerkConfig(jwks_url=CLERK_JWT_ISSUER)
clerk_auth_guard = ClerkHTTPBearer(config=clerk_config)


def get_user_id_from_token(token: HTTPAuthorizationCredentials) -> str:
    try:
        decoded_token = jwt.decode(
            token.credentials, options={"verify_signature": False}
        )
        return decoded_token.get("sub", "anonymous")
    except Exception as e:
        logger.error(f"Error decoding token: {str(e)}")
        return "anonymous"


router = APIRouter()


@router.get("/files/{file_id}")
async def get_file_endpoint(
    file_id: str,
    request: Request,
    token_data: HTTPAuthorizationCredentials = Depends(clerk_auth_guard),
):
    """Serve files from Redis storage with user authentication."""
    try:
        # Extract user ID from token
        user_id = get_user_id_from_token(token_data)
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid authentication token")

        print(f"File API: Requesting file_id: {file_id} for user: {user_id}")

        # Access Redis storage service from app state
        redis_storage_service = request.app.state.redis_storage_service

        # Get file metadata first to check if file exists and belongs to user
        metadata = await redis_storage_service.get_file_metadata(user_id, file_id)
        if not metadata:
            print(f"File API: File metadata not found for {file_id} and user {user_id}")
            raise HTTPException(status_code=404, detail="File not found")

        print(f"File API: Found metadata: {metadata}")

        # Get file content
        content = await redis_storage_service.get_file(user_id, file_id)
        if not content:
            print(f"File API: File content not found for {file_id}")
            raise HTTPException(status_code=404, detail="File content not found")

        # Determine content type
        format_lower = metadata["format"].lower()
        mime_types = {
            "png": "image/png",
            "jpg": "image/jpeg",
            "jpeg": "image/jpeg",
            "gif": "image/gif",
            "svg": "image/svg+xml",
            "txt": "text/plain",
            "json": "application/json",
        }
        content_type = mime_types.get(format_lower, "application/octet-stream")

        return Response(
            content=content,
            media_type=content_type,
            headers={
                "Content-Disposition": f"inline; filename=\"{metadata['title']}\"",
                "Cache-Control": "public, max-age=3600",  # Cache for 1 hour
            },
        )

    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        print(f"Error serving file {file_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/files/{file_id}/public")
async def get_file_public_endpoint(
    file_id: str,
    request: Request,
    user_id: str = Query(..., description="User ID for file access"),
):
    """
    Public endpoint for accessing files (primarily for charts/images in chat).
    Requires user_id as query parameter for security.
    """
    try:
        print(f"Public File API: Requesting file_id: {file_id} for user: {user_id}")

        # Access Redis storage service from app state
        redis_storage_service = request.app.state.redis_storage_service

        # Get file metadata first to check if file exists and belongs to user
        metadata = await redis_storage_service.get_file_metadata(user_id, file_id)
        if not metadata:
            print(
                f"Public File API: File metadata not found for {file_id} and user {user_id}"
            )
            raise HTTPException(status_code=404, detail="File not found")

        # Only allow access to image files for security
        allowed_formats = {"png", "jpg", "jpeg", "gif", "svg"}
        if metadata["format"].lower() not in allowed_formats:
            print(
                f"Public File API: File format {metadata['format']} not allowed for public access"
            )
            raise HTTPException(
                status_code=403, detail="File type not allowed for public access"
            )

        print(f"Public File API: Found metadata: {metadata}")

        # Get file content
        content = await redis_storage_service.get_file(user_id, file_id)
        if not content:
            print(f"Public File API: File content not found for {file_id}")
            raise HTTPException(status_code=404, detail="File content not found")

        # Determine content type
        format_lower = metadata["format"].lower()
        mime_types = {
            "png": "image/png",
            "jpg": "image/jpeg",
            "jpeg": "image/jpeg",
            "gif": "image/gif",
            "svg": "image/svg+xml",
        }
        content_type = mime_types.get(format_lower, "application/octet-stream")

        return Response(
            content=content,
            media_type=content_type,
            headers={
                "Content-Disposition": f"inline; filename=\"{metadata['title']}\"",
                "Cache-Control": "public, max-age=3600",  # Cache for 1 hour
                "Access-Control-Allow-Origin": "*",  # Allow CORS for public files
            },
        )

    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        print(f"Error serving public file {file_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
