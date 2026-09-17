"""Key Management Service (KMS) abstraction for envelope encryption.

Data is encrypted under a random per-user data encryption key (DEK). The DEK is
not persisted in the clear: it is wrapped by a key encryption key (KEK) held in
the KMS, and unwrapping it requires a live, authenticated call to the KMS.

Two backends are provided:

* ``AWSKMSService``  -- production; the KEK is an AWS KMS key (never exported).
* ``LocalKMSService`` -- local/dev; the KEK is a Fernet key derived from the
  environment so the ``kms`` provider can be exercised without real AWS access.
"""

from __future__ import annotations

import base64
import hashlib
import os
from abc import ABC, abstractmethod
from typing import Tuple

import structlog
from cryptography.fernet import Fernet

logger = structlog.get_logger(__name__)


class KeyManagementService(ABC):
    """Wraps/unwraps data encryption keys using a KEK that never leaves the KMS."""

    @abstractmethod
    def generate_data_key(self) -> Tuple[bytes, bytes]:
        """Return a new ``(plaintext_dek, wrapped_dek)`` pair.

        ``plaintext_dek`` is 32 raw bytes (suitable for a Fernet key once
        url-safe base64 encoded). ``wrapped_dek`` is the KMS-encrypted form that
        is safe to store at rest.
        """

    @abstractmethod
    def unwrap_data_key(self, wrapped_dek: bytes) -> bytes:
        """Return the 32-byte plaintext DEK for a previously wrapped DEK."""


class AWSKMSService(KeyManagementService):
    """AWS KMS backend. The KEK (``key_id``) never leaves KMS."""

    def __init__(self, key_id: str, region_name: str | None = None):
        if not key_id:
            raise ValueError(
                "AWS KMS requires a key id/ARN (set KMS_KEY_ID)."
            )
        # Imported lazily so deployments using the salt provider do not need
        # boto3 available at import time.
        import boto3

        self._key_id = key_id
        self._client = boto3.client(
            "kms", region_name=region_name or os.getenv("AWS_REGION")
        )

    def generate_data_key(self) -> Tuple[bytes, bytes]:
        resp = self._client.generate_data_key(KeyId=self._key_id, KeySpec="AES_256")
        return resp["Plaintext"], resp["CiphertextBlob"]

    def unwrap_data_key(self, wrapped_dek: bytes) -> bytes:
        resp = self._client.decrypt(KeyId=self._key_id, CiphertextBlob=wrapped_dek)
        return resp["Plaintext"]


class LocalKMSService(KeyManagementService):
    """Local/dev KMS backend.

    Wraps DEKs with a Fernet KEK derived from the environment. This is not a
    real KMS (the KEK lives in the process), so it exists only to exercise the
    ``kms`` code path locally without AWS. Do not use in production.
    """

    def __init__(self, kek: bytes | None = None):
        self._fernet = Fernet(kek or self._derive_kek())
        logger.warning(
            "Using LocalKMSService (dev only) -- the KEK lives in-process and "
            "does NOT provide KMS-grade protection. Set ENCRYPTION_PROVIDER=kms "
            "with KMS_BACKEND=aws in production."
        )

    @staticmethod
    def _derive_kek() -> bytes:
        # Prefer an explicit dev key; otherwise derive a stable key from the
        # existing salt so v2 data written locally survives restarts.
        explicit = os.getenv("LOCAL_KMS_KEY")
        if explicit:
            return explicit.encode() if isinstance(explicit, str) else explicit
        seed = os.getenv("REDIS_MASTER_SALT", "local-dev-kms-seed")
        digest = hashlib.sha256(seed.encode()).digest()
        return base64.urlsafe_b64encode(digest)

    def generate_data_key(self) -> Tuple[bytes, bytes]:
        dek = os.urandom(32)
        return dek, self._fernet.encrypt(dek)

    def unwrap_data_key(self, wrapped_dek: bytes) -> bytes:
        return self._fernet.decrypt(wrapped_dek)


def get_kms() -> KeyManagementService:
    """Construct the configured KMS backend.

    ``KMS_BACKEND`` selects ``aws`` (default when ENCRYPTION_PROVIDER=kms) or
    ``local`` (dev). AWS requires ``KMS_KEY_ID``.
    """
    backend = os.getenv("KMS_BACKEND", "aws").lower()
    if backend == "local":
        return LocalKMSService()
    if backend == "aws":
        return AWSKMSService(
            key_id=os.getenv("KMS_KEY_ID", ""),
            region_name=os.getenv("AWS_REGION"),
        )
    raise ValueError(f"Unknown KMS_BACKEND: {backend!r} (expected 'aws' or 'local')")
