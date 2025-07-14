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


def get_global_redis_storage_service() -> Optional[RedisStorage]:
    """Get the global Redis storage service."""
    global _global_redis_storage_service
    return _global_redis_storage_service
