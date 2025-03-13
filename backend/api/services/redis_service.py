import redis
from typing import Any, Dict, List, Optional
from .encryption_service import EncryptionService

class SecureRedisService(redis.Redis):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.expiry_seconds = 600
        self.encryption = EncryptionService()

    def set(self, key: str, value: Any, user_id: str) -> bool:
        encrypted_value = self.encryption.encrypt(value, user_id)
        return super().set(key, encrypted_value, ex=self.expiry_seconds)

    def get(self, key: str, user_id: str) -> Any:
        encrypted_value = super().get(key)
        if encrypted_value is None:
            return None
        return self.encryption.decrypt(encrypted_value, user_id)

    def hset(self, name: str, mapping: Dict[str, Any], user_id: str) -> int:
        encrypted_mapping = self.encryption.encrypt_dict(mapping, user_id)
        result = super().hset(name, mapping=encrypted_mapping)
        if self.expiry_seconds is not None:
            super().expire(name, self.expiry_seconds)
        return result

    def hget(self, name: str, key: str, user_id: str) -> Any:
        encrypted_value = super().hget(name, key)
        if encrypted_value is None:
            return None
        return self.encryption.decrypt(encrypted_value, user_id)

    def hgetall(self, name: str, user_id: str) -> Dict[str, Any]:
        encrypted_dict = super().hgetall(name)
        if not encrypted_dict:
            return {}
        return self.encryption.decrypt_dict(encrypted_dict, user_id)

    def lrange(self, name: str, start: int, end: int, user_id: str) -> List[Any]:
        encrypted_values = super().lrange(name, start, end)
        if not encrypted_values:
            return []
        return [self.encryption.decrypt(v, user_id) for v in encrypted_values]

    def rpush(self, name: str, value: Any, user_id: str) -> int:
        encrypted_value = self.encryption.encrypt(value, user_id)
        result = super().rpush(name, encrypted_value)
        if self.expiry_seconds is not None:
            super().expire(name, self.expiry_seconds)
        return result

    def zadd(self, name, *args, **kwargs):
        result = super().zadd(name, *args, **kwargs)
        if self.expiry_seconds is not None:
            super().expire(name, self.expiry_seconds)
        return result
    
    def sadd(self, name: str, *values) -> int:
         result = super().sadd(name, *values)
         if self.expiry_seconds is not None:
             super().expire(name, self.expiry_seconds)
         return result

    def expire(self, name: str, time: int) -> bool:
        """Set an expiration time (in seconds) on a key"""
        return super().expire(name, time)

    def ttl(self, name: str) -> int:
        """Get the time to live for a key in seconds"""
        return super().ttl(name) 
    
