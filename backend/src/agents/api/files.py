
from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from src.agents.utils.file_storage import get_file, file_metadata
import mimetypes
from pathlib import Path

router = APIRouter()

@router.get("/files/{file_id}")
async def get_file_endpoint(file_id: str):
    """Serve files from the file storage."""
    try:
        print(f"File API: Requesting file_id: {file_id}")
        print(f"File API: Available file IDs: {list(file_metadata.keys())}")
        
        # Get file metadata
        metadata = file_metadata.get(file_id)
        if not metadata:
            print(f"File API: File metadata not found for {file_id}")
            raise HTTPException(status_code=404, detail=f"File not found: {file_id}")
        
        print(f"File API: Found metadata: {metadata}")
        
        # Read file content
        file_path = Path(metadata['file_path'])
        if not file_path.exists():
            print(f"File API: File path does not exist: {file_path}")
            raise HTTPException(status_code=404, detail="File not found on disk")
        
        with open(file_path, 'rb') as f:
            content = f.read()
        
        # Determine content type
        format_lower = metadata['format'].lower()
        mime_types = {
            'png': 'image/png',
            'jpg': 'image/jpeg', 
            'jpeg': 'image/jpeg',
            'gif': 'image/gif',
            'svg': 'image/svg+xml',
            'txt': 'text/plain',
            'json': 'application/json'
        }
        content_type = mime_types.get(format_lower, 'application/octet-stream')
        
        return Response(
            content=content,
            media_type=content_type,
            headers={
                "Content-Disposition": f"inline; filename=\"{metadata['title']}\"",
                "Cache-Control": "public, max-age=3600"  # Cache for 1 hour
            }
        )
        
    except Exception as e:
        print(f"Error serving file {file_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error") 
