import asyncio
import json
import smtplib
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional

import structlog
from agents.auth.auth0_config import get_current_user_id, get_token_payload
from agents.services.export_service import ExportService
from fastapi import APIRouter, BackgroundTasks, Depends, Request
from fastapi.responses import JSONResponse, Response

logger = structlog.get_logger(__name__)

router = APIRouter(
    prefix="/export",
)


async def get_export_ttl_hours(request: Request, user_id: str) -> Optional[float]:
    """Get the remaining TTL for export data in hours"""
    try:
        export_key = f"export:{user_id}:latest"
        redis_client = request.app.state.redis_storage_service.redis_client
        ttl_seconds = await super(type(redis_client), redis_client).ttl(export_key)
        
        if ttl_seconds > 0:
            return round(ttl_seconds / 3600, 1)  # Convert to hours
        return None
    except Exception:
        return None


async def send_email_notification(user_email: str, user_id: str, export_size: int):
    """Send email notification when export is ready (placeholder - requires email service setup)"""
    try:
        # This is a placeholder for email functionality
        # In a real implementation, you would use:
        # 1. Auth0 Management API to send emails
        # 2. A service like SendGrid, AWS SES, etc.
        # 3. Or integrate with your existing email infrastructure
        
        logger.info(
            "Email notification would be sent",
            user_email=user_email,
            user_id=user_id,
            export_size=export_size
        )
        
        # For now, we'll just log that the email would be sent
        # TODO: Implement actual email sending using preferred service
        
    except Exception as e:
        logger.error("Error sending email notification", error=str(e))


async def process_export_background(
    user_id: str, 
    token: str, 
    redis_storage_service, 
    user_email: Optional[str] = None
):
    """Background task to process export and send email"""
    try:
        logger.info(f"Processing background export for user {user_id}")
        
        export_service = ExportService(redis_storage_service)
        zip_data, filename, detected_email = await export_service.export_user_data(user_id, token)
        
        email_to_use = user_email or detected_email
        
        if email_to_use:
            await send_email_notification(email_to_use, user_id, len(zip_data))
        
        # Store the export temporarily in Redis for download
        # Using a TTL of 24 hours
        export_key = f"export:{user_id}:latest"
        
        # Store binary data using the same pattern as existing file storage
        # This handles encryption properly and works with binary data
        redis_client = redis_storage_service.redis_client
        
        # Store export data with TTL (using encrypted storage like other files)
        await redis_client.set(export_key, zip_data, user_id)
        
        # Store metadata separately
        metadata_key = f"export_meta:{user_id}:latest" 
        metadata = {
            "filename": filename,
            "size": len(zip_data),
            "created_at": asyncio.get_event_loop().time(),
            "email_sent": email_to_use is not None,
            "email_address": email_to_use
        }
        
        # Store metadata with encryption
        await redis_client.set(metadata_key, json.dumps(metadata), user_id)
        
        # Set TTL for both keys to auto-delete after 24 hours
        ttl_seconds = 24 * 60 * 60  # 24 hours
        await super(type(redis_client), redis_client).expire(export_key, ttl_seconds)
        await super(type(redis_client), redis_client).expire(metadata_key, ttl_seconds)
        
        logger.info(f"Export completed and stored for user {user_id} with 24-hour TTL for automatic cleanup")
        
    except Exception as e:
        logger.error("Error in background export processing", user_id=user_id, error=str(e))


@router.post("/request")
async def request_export(
    request: Request,
    background_tasks: BackgroundTasks,
    user_id: str = Depends(get_current_user_id),
    token_payload: dict = Depends(get_token_payload)
):
    """
    Request a data export. This will process the export in the background
    and either email it to the user or make it available for download.
    """
    try:
        logger.info(f"Export requested by user {user_id}")
        
        # Get the access token from the request headers
        auth_header = request.headers.get("authorization", "")
        if not auth_header.startswith("Bearer "):
            return JSONResponse(
                status_code=401,
                content={"error": "Invalid authorization header"}
            )
        
        token = auth_header[7:]  # Remove "Bearer " prefix
        
        # Start background processing
        background_tasks.add_task(
            process_export_background,
            user_id,
            token,
            request.app.state.redis_storage_service
        )
        
        return JSONResponse(
            status_code=202,
            content={
                "message": "Export request received. You will be notified when your export is ready.",
                "status": "processing",
                "estimated_time": "5-10 minutes"
            }
        )
        
    except Exception as e:
        logger.error("Error processing export request", user_id=user_id, error=str(e))
        return JSONResponse(
            status_code=500,
            content={"error": f"Failed to process export request: {str(e)}"}
        )


@router.get("/status")
async def get_export_status(
    request: Request,
    user_id: str = Depends(get_current_user_id)
):
    """Get the status of the latest export request"""
    try:
        metadata_key = f"export_meta:{user_id}:latest"
        metadata_raw = await request.app.state.redis_storage_service.redis_client.get(metadata_key, user_id)
        
        if not metadata_raw:
            return JSONResponse(
                status_code=404,
                content={"status": "no_export", "message": "No recent export found"}
            )
        
        # Parse metadata (stored as JSON string)
        try:
            metadata_str = metadata_raw.decode('utf-8') if isinstance(metadata_raw, bytes) else metadata_raw
            metadata = json.loads(metadata_str)
        except:
            metadata = {"status": "error", "message": "Could not parse export metadata"}
        
        return JSONResponse(
            status_code=200,
            content={
                "status": "ready",
                "filename": metadata.get("filename"),
                "size": metadata.get("size"),
                "created_at": metadata.get("created_at"),
                "email_sent": metadata.get("email_sent", False),
                "email_address": metadata.get("email_address"),
                "ttl_hours": await get_export_ttl_hours(request, user_id)
            }
        )
        
    except Exception as e:
        logger.error("Error getting export status", user_id=user_id, error=str(e))
        return JSONResponse(
            status_code=500,
            content={"error": f"Failed to get export status: {str(e)}"}
        )


@router.get("/download")
async def download_export(
    request: Request,
    user_id: str = Depends(get_current_user_id)
):
    """Download the latest export file"""
    try:
        export_key = f"export:{user_id}:latest"
        metadata_key = f"export_meta:{user_id}:latest"
        
        # Get export data and metadata using the same pattern as existing file retrieval
        redis_client = request.app.state.redis_storage_service.redis_client
        
        # Get both encrypted export data and metadata 
        export_data = await redis_client.get(export_key, user_id)
        metadata_raw = await redis_client.get(metadata_key, user_id)
        
        logger.info(f"Retrieved export data: {len(export_data) if export_data else 0} bytes, metadata: {bool(metadata_raw)}")
        
        if not export_data or not metadata_raw:
            return JSONResponse(
                status_code=404,
                content={"error": "Export not found or expired"}
            )
        
        # Handle binary data properly (same as existing file retrieval)
        if isinstance(export_data, str):
            export_data = export_data.encode("utf-8")
        
        # Parse metadata
        try:
            metadata_str = metadata_raw.decode('utf-8') if isinstance(metadata_raw, bytes) else metadata_raw
            metadata = json.loads(metadata_str)
            filename = metadata.get("filename", "export.zip")
        except:
            filename = "samba_copilot_export.zip"
        
        # Return binary data directly (same pattern as existing file download)
        return Response(
            content=export_data,
            media_type="application/zip",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "Content-Length": str(len(export_data))
            }
        )
        
    except Exception as e:
        logger.error("Error downloading export", user_id=user_id, error=str(e))
        return JSONResponse(
            status_code=500,
            content={"error": f"Failed to download export: {str(e)}"}
        )


@router.delete("/clear")
async def clear_export(
    request: Request,
    user_id: str = Depends(get_current_user_id)
):
    """Clear the stored export data"""
    try:
        export_key = f"export:{user_id}:latest"
        metadata_key = f"export_meta:{user_id}:latest"
        
        # Delete both keys (delete doesn't require user_id as it's not overridden)
        redis_client = request.app.state.redis_storage_service.redis_client
        await redis_client.delete(export_key)
        await redis_client.delete(metadata_key)
        
        return JSONResponse(
            status_code=200,
            content={"message": "Export data cleared successfully"}
        )
        
    except Exception as e:
        logger.error("Error clearing export", user_id=user_id, error=str(e))
        return JSONResponse(
            status_code=500,
            content={"error": f"Failed to clear export: {str(e)}"}
        )