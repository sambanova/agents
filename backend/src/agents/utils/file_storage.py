import base64
import os
import uuid
from datetime import datetime, timezone
from typing import Optional
import json
import redis
from agents.storage.redis_service import SecureRedisService

# Initialize Redis client for file storage
def get_redis_client() -> SecureRedisService:
    """Get Redis client for file storage"""
    redis_host = os.getenv("REDIS_HOST", "localhost")
    redis_port = int(os.getenv("REDIS_PORT", "6379"))
    redis_db = int(os.getenv("REDIS_DB", "0"))
    
    return SecureRedisService(
        host=redis_host,
        port=redis_port,
        db=redis_db,
        decode_responses=False  # Keep as bytes for file storage
    )

# Global Redis client instance
_redis_client = None

def get_file_redis_client():
    """Get or create the global Redis client instance"""
    global _redis_client
    if _redis_client is None:
        _redis_client = get_redis_client()
    return _redis_client

async def put_file(user_id: str, file_id: str, *, data: bytes, title: str, format: str):
    """Put a file in Redis storage."""
    try:
        # Ensure data is bytes
        if isinstance(data, str):
            data = data.encode('utf-8')
        
        redis_client = get_file_redis_client()
        
        # Store file data with user-namespaced key
        file_data_key = f"file_data:{user_id}:{file_id}"
        redis_client.set(file_data_key, data, user_id)
        
        # Store metadata
        metadata = {
            'user_id': user_id,
            'title': title,
            'format': format,
            'created_at': datetime.now(timezone.utc).isoformat(),
            'file_size': len(data)
        }
        
        file_metadata_key = f"file_metadata:{user_id}:{file_id}"
        redis_client.set(file_metadata_key, json.dumps(metadata), user_id)
        
        # Also maintain an index of all files for a user
        user_files_key = f"user_files:{user_id}"
        redis_client.sadd(user_files_key, file_id)
        
        print(f"File stored in Redis: {file_id} -> {len(data)} bytes for user {user_id}")
        
    except Exception as e:
        print(f"Error storing file {file_id} in Redis: {e}")
        raise

async def get_file(user_id: str, file_id: str) -> Optional[bytes]:
    """Get a file from Redis storage."""
    try:
        redis_client = get_file_redis_client()
        
        # Check if file exists by trying to get metadata first
        file_metadata_key = f"file_metadata:{user_id}:{file_id}"
        metadata_str = redis_client.get(file_metadata_key, user_id)
        
        if not metadata_str:
            return None
        
        # Get file data
        file_data_key = f"file_data:{user_id}:{file_id}"
        file_data = redis_client.get(file_data_key, user_id)
        
        if isinstance(file_data, str):
            file_data = file_data.encode('utf-8')
            
        return file_data
            
    except Exception as e:
        print(f"Error retrieving file {file_id} from Redis: {e}")
        return None

async def get_file_metadata(user_id: str, file_id: str) -> Optional[dict]:
    """Get file metadata from Redis storage."""
    try:
        redis_client = get_file_redis_client()
        
        file_metadata_key = f"file_metadata:{user_id}:{file_id}"
        metadata_str = redis_client.get(file_metadata_key, user_id)
        
        if not metadata_str:
            return None
            
        return json.loads(metadata_str)
            
    except Exception as e:
        print(f"Error retrieving file metadata {file_id} from Redis: {e}")
        return None

async def get_file_as_base64(user_id: str, file_id: str) -> Optional[str]:
    """Get a file as base64 string."""
    data = await get_file(user_id, file_id)
    if data:
        return base64.b64encode(data).decode('utf-8')
    return None

def get_file_url(file_id: str) -> str:
    """Get a URL for accessing the file."""
    return f"/api/files/{file_id}"

async def get_file_data_url(user_id: str, file_id: str) -> Optional[str]:
    """Get file as data URL for direct embedding."""
    try:
        # Get metadata to determine MIME type
        metadata = await get_file_metadata(user_id, file_id)
        if not metadata:
            return None
        
        # Get file data
        data = await get_file(user_id, file_id)
        if not data:
            return None
        
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

async def delete_file(user_id: str, file_id: str) -> bool:
    """Delete a file from Redis storage."""
    try:
        redis_client = get_file_redis_client()
        
        # Delete file data and metadata
        file_data_key = f"file_data:{user_id}:{file_id}"
        file_metadata_key = f"file_metadata:{user_id}:{file_id}"
        user_files_key = f"user_files:{user_id}"
        
        # Remove from all locations
        redis_client.delete(file_data_key)
        redis_client.delete(file_metadata_key)
        redis_client.srem(user_files_key, file_id)
        
        print(f"File deleted from Redis: {file_id} for user {user_id}")
        return True
        
    except Exception as e:
        print(f"Error deleting file {file_id} from Redis: {e}")
        return False

async def list_user_files(user_id: str) -> list:
    """List all files for a user."""
    try:
        redis_client = get_file_redis_client()
        
        user_files_key = f"user_files:{user_id}"
        file_ids = redis_client.smembers(user_files_key)
        
        if not file_ids:
            return []
        
        # Get metadata for each file
        files = []
        for file_id in file_ids:
            if isinstance(file_id, bytes):
                file_id = file_id.decode('utf-8')
            metadata = await get_file_metadata(user_id, file_id)
            if metadata:
                metadata['file_id'] = file_id
                files.append(metadata)
        
        return files
        
    except Exception as e:
        print(f"Error listing files for user {user_id}: {e}")
        return []

async def migrate_local_files_to_redis():
    """
    Migrate existing files from local storage to Redis.
    This is a one-time migration function.
    """
    from pathlib import Path
    import json
    
    # Old storage directory
    STORAGE_DIR = Path("file_storage")
    
    if not STORAGE_DIR.exists():
        print("No local file storage directory found. Migration not needed.")
        return
    
    print("Starting migration from local file storage to Redis...")
    
    migrated_count = 0
    error_count = 0
    
    try:
        # Walk through all user directories
        for user_dir in STORAGE_DIR.iterdir():
            if not user_dir.is_dir():
                continue
                
            user_id = user_dir.name
            print(f"Migrating files for user: {user_id}")
            
            # Get all files in the user directory
            for file_path in user_dir.iterdir():
                if not file_path.is_file():
                    continue
                
                try:
                    # Extract file_id and format from filename
                    file_name = file_path.name
                    if '.' in file_name:
                        file_id, format = file_name.rsplit('.', 1)
                    else:
                        file_id = file_name
                        format = 'unknown'
                    
                    # Read file data
                    with open(file_path, 'rb') as f:
                        data = f.read()
                    
                    # Create a title from the filename
                    title = file_name
                    
                    # Store in Redis
                    await put_file(user_id, file_id, data=data, title=title, format=format)
                    migrated_count += 1
                    print(f"  Migrated: {file_name}")
                    
                except Exception as e:
                    print(f"  Error migrating {file_path}: {e}")
                    error_count += 1
    
    except Exception as e:
        print(f"Migration error: {e}")
    
    print(f"Migration completed. {migrated_count} files migrated, {error_count} errors.")
    
    if migrated_count > 0:
        print("You can now safely delete the 'file_storage' directory if desired.")

# Backward compatibility: provide empty implementations for old in-memory metadata
# This ensures any remaining code that tries to access file_metadata won't crash
file_metadata = {} 