import base64
import os
import threading
from typing import Any, Dict, Optional, Tuple, TypeVar

import structlog
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from agents.storage.kms import KeyManagementService, get_kms

logger = structlog.get_logger(__name__)

T = TypeVar("T")

# Marker prefix for KMS envelope-encrypted values. Legacy (salt-derived) values
# are raw Fernet tokens and never start with this, so decryption can reliably
# tell the two formats apart and stay backward compatible regardless of which
# provider is configured for writes.
_ENVELOPE_PREFIX = b"ENVv2:"


class EncryptionService:
    """At-rest encryption with a configurable key source.

    ``ENCRYPTION_PROVIDER`` selects how *new* values are encrypted:

    * ``salt`` (default) -- a per-user Fernet key derived via PBKDF2 from the
      user_id and a global ``REDIS_MASTER_SALT``. Kept for backward
      compatibility.
    * ``kms`` -- envelope encryption: data is encrypted with a random per-user
      DEK; the DEK is wrapped by a KEK held in the KMS (see ``kms.py``) and the
      wrapped DEK travels with the ciphertext, so reading requires a live KMS
      unwrap call.

    Decryption dispatches on the ciphertext *format*, not the configured
    provider, so switching providers never orphans existing data.
    """

    def __init__(self):
        self.provider = os.getenv("ENCRYPTION_PROVIDER", "salt").lower()

        # --- legacy salt-derived key material (always available for reads) ---
        self.master_salt = os.getenv("REDIS_MASTER_SALT")
        if not self.master_salt:
            self.master_salt = base64.b64encode(os.urandom(16)).decode("utf-8")
            logger.warning(
                "WARNING: No REDIS_MASTER_SALT found in environment. Generated new salt."
            )
        if isinstance(self.master_salt, str):
            self.master_salt = self.master_salt.encode()
        self._fernet_instances: Dict[str, Fernet] = {}

        # --- KMS envelope material (lazily initialised) ---
        self._kms: Optional[KeyManagementService] = None
        self._lock = threading.Lock()
        # Per-user DEK reused for writes: {user_id: (plaintext_dek, wrapped_dek)}
        self._enc_deks: Dict[str, Tuple[bytes, bytes]] = {}
        # Unwrapped DEK cache for reads: {wrapped_dek: plaintext_dek}
        self._dek_cache: Dict[bytes, bytes] = {}

        if self.provider == "kms":
            # Fail fast at startup if KMS is misconfigured, rather than on the
            # first encrypt of real user data.
            self._get_kms()
        elif self.provider != "salt":
            raise ValueError(
                f"Unknown ENCRYPTION_PROVIDER: {self.provider!r} (expected 'salt' or 'kms')"
            )

    # ------------------------------------------------------------------ #
    # Legacy salt-derived key path
    # ------------------------------------------------------------------ #
    def _derive_key(self, user_id: str) -> bytes:
        """Derive a Fernet key from the user_id using PBKDF2 (legacy scheme)."""
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=self.master_salt,
            iterations=100000,
        )
        return base64.b64encode(kdf.derive(user_id.encode()))

    def _get_fernet(self, user_id: str) -> Fernet:
        if user_id not in self._fernet_instances:
            self._fernet_instances[user_id] = Fernet(self._derive_key(user_id))
        return self._fernet_instances[user_id]

    # ------------------------------------------------------------------ #
    # KMS envelope path
    # ------------------------------------------------------------------ #
    def _get_kms(self) -> KeyManagementService:
        if self._kms is None:
            self._kms = get_kms()
        return self._kms

    @staticmethod
    def _fernet_for_dek(dek: bytes) -> Fernet:
        return Fernet(base64.urlsafe_b64encode(dek))

    def _get_encryption_dek(self, user_id: str) -> Tuple[bytes, bytes]:
        """Return the ``(plaintext_dek, wrapped_dek)`` to encrypt this user's data.

        A single DEK is generated per user per process and reused for all of
        that user's writes, so KMS ``GenerateDataKey`` is called at most once per
        user rather than per value.
        """
        cached = self._enc_deks.get(user_id)
        if cached is not None:
            return cached
        with self._lock:
            cached = self._enc_deks.get(user_id)
            if cached is not None:
                return cached
            plaintext_dek, wrapped_dek = self._get_kms().generate_data_key()
            self._enc_deks[user_id] = (plaintext_dek, wrapped_dek)
            self._dek_cache[wrapped_dek] = plaintext_dek
            return plaintext_dek, wrapped_dek

    def _unwrap_dek(self, wrapped_dek: bytes) -> bytes:
        dek = self._dek_cache.get(wrapped_dek)
        if dek is not None:
            return dek
        with self._lock:
            dek = self._dek_cache.get(wrapped_dek)
            if dek is not None:
                return dek
            dek = self._get_kms().unwrap_data_key(wrapped_dek)
            self._dek_cache[wrapped_dek] = dek
            return dek

    def _envelope_encrypt(self, data: bytes, user_id: str) -> bytes:
        plaintext_dek, wrapped_dek = self._get_encryption_dek(user_id)
        token = self._fernet_for_dek(plaintext_dek).encrypt(data)
        return (
            _ENVELOPE_PREFIX
            + base64.urlsafe_b64encode(wrapped_dek)
            + b":"
            + token
        )

    def _envelope_decrypt(self, encrypted_data: bytes) -> bytes:
        body = encrypted_data[len(_ENVELOPE_PREFIX):]
        wrapped_b64, _, token = body.partition(b":")
        wrapped_dek = base64.urlsafe_b64decode(wrapped_b64)
        dek = self._unwrap_dek(wrapped_dek)
        return self._fernet_for_dek(dek).decrypt(token)

    # ------------------------------------------------------------------ #
    # Public API (unchanged signatures)
    # ------------------------------------------------------------------ #
    def encrypt(self, data: Any, user_id: str) -> Optional[bytes]:
        """Encrypt data using the configured provider."""
        if data is None:
            return None
        if not isinstance(data, bytes):
            data = str(data).encode()

        if self.provider == "kms":
            return self._envelope_encrypt(data, user_id)
        return self._get_fernet(user_id).encrypt(data)

    def decrypt(self, encrypted_data: Optional[bytes], user_id: str) -> Any:
        """Decrypt data, dispatching on the stored format for compatibility."""
        if encrypted_data is None:
            return None

        raw = encrypted_data
        if isinstance(raw, str):
            raw = raw.encode()

        if raw.startswith(_ENVELOPE_PREFIX):
            # KMS envelope value -- readable only via a live KMS unwrap.
            return self._envelope_decrypt(raw)
        # Legacy salt-derived value.
        return self._get_fernet(user_id).decrypt(raw)

    def encrypt_dict(self, data: Dict[str, Any], user_id: str) -> Dict[str, bytes]:
        """Encrypt all values in a dictionary."""
        encrypted = {}
        for k, v in data.items():
            encrypted_value = self.encrypt(v, user_id)
            # Only include non-None values (Redis doesn't accept None)
            if encrypted_value is not None:
                encrypted[k] = encrypted_value
        return encrypted

    def decrypt_dict(self, data: Dict[str, bytes], user_id: str) -> Dict[str, Any]:
        """Decrypt all values in a dictionary."""
        return {k: self.decrypt(v, user_id) for k, v in data.items()}
