from typing import Any, Dict, List

import redis.asyncio as redis
from agents.storage.encryption_service import EncryptionService


class SecureRedisService(redis.Redis):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.encryption = EncryptionService()

    async def set(self, key: str, value: Any, user_id: str) -> bool:
        encrypted_value = self.encryption.encrypt(value, user_id)
        return await super().set(key, encrypted_value)

    async def get(self, key: str, user_id: str) -> Any:
        encrypted_value = await super().get(key)
        if encrypted_value is None:
            return None
        return self.encryption.decrypt(encrypted_value, user_id)

    async def hset(self, name: str, mapping: Dict[str, Any], user_id: str) -> int:
        encrypted_mapping = self.encryption.encrypt_dict(mapping, user_id)
        return await super().hset(name, mapping=encrypted_mapping)

    async def hget(self, name: str, key: str, user_id: str) -> Any:
        encrypted_value = await super().hget(name, key)
        if encrypted_value is None:
            return None
        return self.encryption.decrypt(encrypted_value, user_id)

    async def hgetall(self, name: str, user_id: str) -> Dict[str, Any]:
        encrypted_dict = await super().hgetall(name)
        if not encrypted_dict:
            return {}
        return self.encryption.decrypt_dict(encrypted_dict, user_id)

    async def lrange(self, name: str, start: int, end: int, user_id: str) -> List[Any]:
        encrypted_values = await super().lrange(name, start, end)
        if not encrypted_values:
            return []
        return [self.encryption.decrypt(v, user_id) for v in encrypted_values]

    async def rpush(self, name: str, value: Any, user_id: str) -> int:
        encrypted_value = self.encryption.encrypt(value, user_id)
        return await super().rpush(name, encrypted_value)

    async def hsetnx(self, name: str, key: str, value: Any, user_id: str) -> bool:
        """Set hash field only if it doesn't exist. Returns True if set, False if already existed."""
        encrypted_value = self.encryption.encrypt(value, user_id)
        return bool(await super().hsetnx(name, key, encrypted_value))
