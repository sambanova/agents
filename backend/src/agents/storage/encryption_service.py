import base64
import hmac
import os
from typing import Any, Dict, Optional, TypeVar

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

T = TypeVar("T")


class EncryptionService:
    def __init__(self):
        """Initialize encryption service."""
        # Get master salt from environment or generate a new one
        self.master_salt = os.getenv("REDIS_MASTER_SALT")
        if not self.master_salt:
            self.master_salt = base64.b64encode(os.urandom(16)).decode("utf-8")
            print(
                "WARNING: No REDIS_MASTER_SALT found in environment. Generated new salt."
            )

        if isinstance(self.master_salt, str):
            self.master_salt = self.master_salt.encode()

        self._fernet_instances = {}

    def _derive_key(self, user_id: str) -> bytes:
        """
        Derive an encryption key from the user_id using PBKDF2.

        Args:
            user_id: The user's ID to derive key from

        Returns:
            bytes: A 32-byte key suitable for Fernet
        """
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=self.master_salt,
            iterations=100000,
        )
        key = base64.b64encode(kdf.derive(user_id.encode()))
        return key

    def _get_fernet(self, user_id: str) -> Fernet:
        """
        Get or create a Fernet instance for the given user_id.

        Args:
            user_id: The user's ID

        Returns:
            Fernet: A Fernet instance for encryption/decryption
        """
        if user_id not in self._fernet_instances:
            key = self._derive_key(user_id)
            self._fernet_instances[user_id] = Fernet(key)
        return self._fernet_instances[user_id]

    def encrypt(self, data: Any, user_id: str) -> Optional[bytes]:
        """
        Encrypt data using a key derived from the user_id.

        Args:
            data: Data to encrypt
            user_id: The user's ID

        Returns:
            bytes: Encrypted data or None if input was None
        """
        if data is None:
            return None

        # Convert data to bytes if it's not already
        if not isinstance(data, bytes):
            data = str(data).encode()

        fernet = self._get_fernet(user_id)
        return fernet.encrypt(data)

    def decrypt(self, encrypted_data: Optional[bytes], user_id: str) -> Any:
        """
        Decrypt data using a key derived from the user_id.

        Args:
            encrypted_data: Encrypted data as bytes
            user_id: The user's ID

        Returns:
            The decrypted data
        """
        if encrypted_data is None:
            return None

        fernet = self._get_fernet(user_id)
        return fernet.decrypt(encrypted_data)

    def encrypt_dict(self, data: Dict[str, Any], user_id: str) -> Dict[str, bytes]:
        """
        Encrypt all values in a dictionary.

        Args:
            data: Dictionary with values to encrypt
            user_id: The user's ID

        Returns:
            dict: Dictionary with encrypted values
        """
        return {k: self.encrypt(v, user_id) for k, v in data.items()}

    def decrypt_dict(self, data: Dict[str, bytes], user_id: str) -> Dict[str, Any]:
        """
        Decrypt all values in a dictionary.

        Args:
            data: Dictionary with encrypted values
            user_id: The user's ID

        Returns:
            dict: Dictionary with decrypted values
        """
        return {k: self.decrypt(v, user_id) for k, v in data.items()}
