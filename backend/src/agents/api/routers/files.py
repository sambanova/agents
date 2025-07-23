import time

import structlog
from agents.auth.auth0_config import get_current_user_id
from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import JSONResponse

logger = structlog.get_logger(__name__)

router = APIRouter(
    prefix="/files",
)


@router.get("")
async def get_user_files(
    request: Request,
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

        files = await request.app.state.redis_storage_service.list_user_files(user_id)

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


@router.get("/{file_id}")
async def get_file(
    request: Request,
    file_id: str,
    user_id: str = Depends(get_current_user_id),
):
    """Serve a file by its ID for authenticated users."""
    try:
        file_data, file_metadata = (
            await request.app.state.redis_storage_service.get_file(user_id, file_id)
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


@router.delete("/{file_id}")
async def delete_file(
    request: Request,
    file_id: str,
    user_id: str = Depends(get_current_user_id),
):
    """Delete a file (document or uploaded file) and its associated data."""
    try:
        # If the file is indexed, delete its vectors from the vector store
        metadata = await request.app.state.redis_storage_service.get_file_metadata(
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
                api_keys = (
                    await request.app.state.redis_storage_service.get_user_api_key(
                        user_id
                    )
                )
                if api_keys and api_keys.sambanova_key:
                    await request.app.state.redis_storage_service.delete_vectors(
                        vector_ids
                    )

        result = await request.app.state.redis_storage_service.delete_file(
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
        logger.error(f"Error deleting file: {str(e)}", file_id=file_id)
        return JSONResponse(status_code=500, content={"error": str(e)})
