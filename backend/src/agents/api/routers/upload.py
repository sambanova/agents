import os
import time
import uuid

import structlog
from agents.auth.auth0_config import get_current_user_id
from agents.rag.upload import convert_ingestion_input_to_blob, ingest_runnable
from fastapi import APIRouter, Depends, File, Request, UploadFile
from fastapi.responses import JSONResponse

logger = structlog.get_logger(__name__)

router = APIRouter(
    prefix="/upload",
)

ALLOWED_CONTENT_TYPES = {
    "application/pdf",
    "text/plain",
    "text/csv",
    "application/json",
    "image/png",
    "image/jpeg",
    "image/gif",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}


async def process_and_store_file(
    request: Request,
    file: UploadFile,
    user_id: str,
):
    # Generate unique file ID
    file_id = str(uuid.uuid4())

    # Sanitise filename — strip path components, reject traversal
    safe_filename = os.path.basename(file.filename or "unnamed").replace("\x00", "")
    safe_content_type = file.content_type if file.content_type in ALLOWED_CONTENT_TYPES else "application/octet-stream"

    # Read file content
    content = await file.read()
    indexed = False
    vector_ids = []

    upload_time = time.time()
    logger.info(f"[UPLOAD_TRACE] Processing file: {safe_filename}, content_type: {safe_content_type}, file_id: {file_id}")
    if safe_content_type == "application/pdf":
        logger.info(f"[UPLOAD_TRACE] File is PDF, starting indexing for {file_id}")
        file_blobs = await convert_ingestion_input_to_blob(content, safe_filename)
        api_keys = await request.app.state.redis_storage_service.get_user_api_key(
            user_id
        )
        vector_ids = await ingest_runnable.ainvoke(
            file_blobs,
            {
                "user_id": user_id,
                "document_id": file_id,
                "api_key": api_keys.sambanova_key,
                "redis_client": request.app.state.sync_redis_client,
            },
        )
        logger.info(f"[UPLOAD_TRACE] Indexed file successfully - file_id: {file_id}, vector_ids: {len(vector_ids)}")
        indexed = True
    else:
        logger.warning(f"[UPLOAD_TRACE] File is NOT PDF ({safe_content_type}), skipping indexing for {file_id}")

    logger.info(f"[UPLOAD_TRACE] Storing file in Redis - file_id: {file_id}, indexed: {indexed}")
    await request.app.state.redis_storage_service.put_file(
        user_id,
        file_id,
        data=content,
        filename=safe_filename,
        format=safe_content_type,
        upload_timestamp=upload_time,
        indexed=indexed,
        source="upload",
        vector_ids=vector_ids,
    )
    logger.info(f"[UPLOAD_TRACE] File stored successfully in Redis - file_id: {file_id}")
    return {
        "file_id": file_id,
        "filename": safe_filename,
        "type": safe_content_type,
        "created_at": upload_time,
        "user_id": user_id,
    }


@router.post("")
async def upload_document(
    request: Request,
    file: UploadFile = File(...),
    user_id: str = Depends(get_current_user_id),
):
    """Upload and process a document or image file."""
    try:
        upload_time = time.time()
        file_details = await process_and_store_file(request, file, user_id)
        duration = time.time() - upload_time
        logger.info(
            "File uploaded successfully",
            file_id=file_details["file_id"],
            duration_ms=round(duration * 1000, 2),
        )

        return JSONResponse(
            status_code=200,
            content={
                "message": "File uploaded successfully",
                "file": file_details,
            },
        )

    except Exception as e:
        logger.error(f"Error processing file: {str(e)}")
        return JSONResponse(status_code=500, content={"error": "An internal error occurred"})
