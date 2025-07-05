import os
from typing import Optional

import redis
import redis.asyncio as aioredis
from agents.storage.redis_service import SecureRedisService
from agents.storage.redis_storage import RedisStorage

# Global storage for shared services
_global_redis_storage_service: Optional[RedisStorage] = None
_global_redis_pool: Optional[aioredis.ConnectionPool] = None
_global_sync_redis_pool: Optional[redis.ConnectionPool] = None

# MCP-related global services
_global_mcp_server_manager: Optional["MCPServerManager"] = None
_global_dynamic_tool_loader: Optional["DynamicToolLoader"] = None


def get_redis_pool() -> aioredis.ConnectionPool:
    """Get or create the async Redis connection pool.

    This is cached so we only create one pool for the entire application.
    """
    global _global_redis_pool

    if _global_redis_pool is None:
        redis_host = os.getenv("REDIS_HOST", "localhost")
        redis_port = int(os.getenv("REDIS_PORT", "6379"))

        _global_redis_pool = aioredis.ConnectionPool(
            host=redis_host,
            port=redis_port,
            db=0,
            decode_responses=True,
            max_connections=100,
            socket_timeout=30,
            socket_connect_timeout=10,
            health_check_interval=30,
            retry_on_timeout=True,
        )

    return _global_redis_pool


def get_sync_redis_pool() -> redis.ConnectionPool:
    """Get or create the synchronous Redis connection pool."""
    global _global_sync_redis_pool

    if _global_sync_redis_pool is None:
        redis_host = os.getenv("REDIS_HOST", "localhost")
        redis_port = int(os.getenv("REDIS_PORT", "6379"))

        _global_sync_redis_pool = redis.ConnectionPool(
            host=redis_host,
            port=redis_port,
            db=0,
            decode_responses=True,
            max_connections=100,
            socket_timeout=30,
            socket_connect_timeout=10,
            health_check_interval=30,
            retry_on_timeout=True,
        )

    return _global_sync_redis_pool


def get_redis_client() -> aioredis.Redis:
    """Get an async Redis client using the shared connection pool."""
    return aioredis.Redis(connection_pool=get_redis_pool())


def get_sync_redis_client() -> redis.Redis:
    """Get a synchronous Redis client using the shared connection pool."""
    return redis.Redis(connection_pool=get_sync_redis_pool())


def get_secure_redis_client() -> SecureRedisService:
    """Get a secure Redis client using the shared connection pool."""
    return SecureRedisService(connection_pool=get_redis_pool())


def set_global_redis_storage_service(storage_service: RedisStorage) -> None:
    """Set the global Redis storage service for the application to use."""
    global _global_redis_storage_service
    _global_redis_storage_service = storage_service


def get_global_mcp_server_manager():
    """Get the global MCP server manager."""
    return _global_mcp_server_manager


def set_global_mcp_server_manager(manager: "MCPServerManager") -> None:
    """Set the global MCP server manager."""
    global _global_mcp_server_manager
    _global_mcp_server_manager = manager


def get_global_dynamic_tool_loader():
    """Get the global dynamic tool loader."""
    return _global_dynamic_tool_loader


def set_global_dynamic_tool_loader(loader: "DynamicToolLoader") -> None:
    """Set the global dynamic tool loader."""
    global _global_dynamic_tool_loader
    _global_dynamic_tool_loader = loader


def initialize_mcp_services(redis_storage: RedisStorage) -> None:
    """
    Initialize MCP-related services with lazy loading to avoid circular imports.
    
    Args:
        redis_storage: The Redis storage service to use
    """
    import structlog
    logger = structlog.get_logger(__name__)
    
    try:
        # Check if already initialized
        if _global_mcp_server_manager is not None and _global_dynamic_tool_loader is not None:
            logger.info("MCP services already initialized, skipping")
            return
        
        # Import here to avoid circular imports
        from agents.mcp.server_manager import MCPServerManager
        from agents.tools.dynamic_tool_loader import DynamicToolLoader, set_dynamic_tool_loader
        
        # Create MCP server manager
        mcp_manager = MCPServerManager(redis_storage)
        set_global_mcp_server_manager(mcp_manager)
        
        # Create dynamic tool loader
        tool_loader = DynamicToolLoader(redis_storage, mcp_manager)
        set_global_dynamic_tool_loader(tool_loader)
        set_dynamic_tool_loader(tool_loader)  # Set in the dynamic tool loader module too
        
        logger.info("MCP services initialized successfully")
        
    except ImportError as e:
        logger.warning(f"MCP services not available due to missing dependencies: {e}")
        # This is expected if MCP dependencies are not installed
    except Exception as e:
        logger.error("Failed to initialize MCP services", error=str(e), exc_info=True)
        # Don't raise - let the application continue without MCP services


def get_global_redis_storage_service() -> Optional[RedisStorage]:
    """Get the global Redis storage service."""
    global _global_redis_storage_service
    return _global_redis_storage_service


def ensure_mcp_services_initialized() -> bool:
    """
    Ensure MCP services are initialized, attempting lazy initialization if needed.
    
    Returns:
        bool: True if MCP services are available, False otherwise
    """
    global _global_mcp_server_manager, _global_dynamic_tool_loader
    
    # Check if already initialized
    if _global_mcp_server_manager is not None and _global_dynamic_tool_loader is not None:
        return True
        
    # Try to initialize if we have a Redis storage service
    redis_storage = get_global_redis_storage_service()
    if redis_storage is not None:
        try:
            initialize_mcp_services(redis_storage)
            return _global_mcp_server_manager is not None and _global_dynamic_tool_loader is not None
        except Exception:
            return False
    
    return False
