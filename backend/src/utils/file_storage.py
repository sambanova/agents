import base64
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# Simple file storage directory
STORAGE_DIR = Path("file_storage")
STORAGE_DIR.mkdir(exist_ok=True)

# In-memory metadata store for quick testing
file_metadata = {}

async def put_file(user_id: str, file_id: str, *, data: bytes, title: str, format: str):
    """Put a file in simple file storage."""
    try:
        # Ensure data is bytes
        if isinstance(data, str):
            data = data.encode('utf-8')
        
        # Create user directory
        user_dir = STORAGE_DIR / user_id
        user_dir.mkdir(exist_ok=True)
        
        # Save file data
        file_path = user_dir / f"{file_id}.{format}"
        with open(file_path, 'wb') as f:
            f.write(data)
        
        # Store metadata
        file_metadata[file_id] = {
            'user_id': user_id,
            'title': title,
            'format': format,
            'created_at': datetime.now(timezone.utc).isoformat(),
            'file_path': str(file_path)
        }
        
        print(f"File stored: {file_id} -> {file_path}")
        
    except Exception as e:
        print(f"Error storing file {file_id}: {e}")
        raise

async def get_file(user_id: str, file_id: str) -> Optional[bytes]:
    """Get a file from simple file storage."""
    try:
        metadata = file_metadata.get(file_id)
        if not metadata or metadata['user_id'] != user_id:
            return None
        
        file_path = Path(metadata['file_path'])
        if not file_path.exists():
            return None
        
        with open(file_path, 'rb') as f:
            return f.read()
            
    except Exception as e:
        print(f"Error retrieving file {file_id}: {e}")
        return None

async def get_file_as_base64(user_id: str, file_id: str) -> Optional[str]:
    """Get a file as base64 string."""
    data = await get_file(user_id, file_id)
    if data:
        return base64.b64encode(data).decode('utf-8')
    return None

def get_file_url(file_id: str) -> str:
    """Get a URL for accessing the file (for testing, we'll use data URLs)."""
    metadata = file_metadata.get(file_id)
    if metadata:
        # For PNG files, create a data URL
        if metadata['format'].lower() in ['png', 'jpg', 'jpeg', 'gif']:
            return f"/api/files/{file_id}"  # This would be served by your API
    return None

# Alternative: For testing, we can just return data URLs directly
async def get_file_data_url(user_id: str, file_id: str) -> Optional[str]:
    """Get file as data URL for direct embedding."""
    try:
        metadata = file_metadata.get(file_id)
        if not metadata or metadata['user_id'] != user_id:
            return None
        
        file_path = Path(metadata['file_path'])
        if not file_path.exists():
            return None
        
        with open(file_path, 'rb') as f:
            data = f.read()
            base64_data = base64.b64encode(data).decode('utf-8')
            
            # Determine MIME type
            format_lower = metadata['format'].lower()
            mime_types = {
                'png': 'image/png',
                'jpg': 'image/jpeg', 
                'jpeg': 'image/jpeg',
                'gif': 'image/gif',
                'svg': 'image/svg+xml'
            }
            mime_type = mime_types.get(format_lower, 'application/octet-stream')
            
            return f"data:{mime_type};base64,{base64_data}"
            
    except Exception as e:
        print(f"Error creating data URL for {file_id}: {e}")
        return None 