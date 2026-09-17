"""Encryption for LangGraph Redis checkpoints.

The LangGraph ``AsyncRedisSaver`` writes checkpoint state to Redis without going
through ``SecureRedisService`` (it uses RedisJSON + a search index directly), so
its payloads are not covered by the main at-rest encryption path.

This module encrypts the sensitive *value payloads* while leaving the fields the
checkpointer needs to query (thread_id, checkpoint_ns, channel, version,
``$.checkpoint.channel_versions``, source/step) in plaintext so ``FT.SEARCH``
keeps working:

* ``EncryptingSerde`` wraps the serializer and encrypts the string produced by
  ``dumps_typed`` (used for channel-value blobs and pending writes), decrypting
  it back in ``loads_typed``. A ``CKENC:`` marker makes the transformation
  self-describing, so checkpoints written before encryption was enabled still
  load unchanged.
* ``EncryptedAsyncRedisSaver`` drops the redundant inline plaintext copy of
  ``channel_values`` from the checkpoint document (it is persisted separately as
  encrypted blobs and overwritten from those on load).

Encryption uses the shared :class:`EncryptionService`, so it honours
``ENCRYPTION_PROVIDER`` (salt or kms). Checkpoints are not per-user keyed (one
checkpointer serves all threads and the serde has no user context), so a fixed
context string is used; the encryption strength does not depend on the context
value.

NOTE (known residual): ``metadata['writes']`` -- a per-step summary of node
outputs -- is stored in the checkpoint doc's ``$.metadata`` and remains
plaintext here, because encrypting it safely requires field-level handling that
would risk the metadata load path / source-step search. The authoritative
channel values and write blobs (the bulk of sensitive content) are encrypted.
"""

from __future__ import annotations

import json
import os
from typing import Any, Tuple

import structlog
from langgraph.checkpoint.redis.aio import AsyncRedisSaver

from agents.storage.encryption_service import EncryptionService

logger = structlog.get_logger(__name__)

_CK_PREFIX = "CKENC:"
_CK_CONTEXT = "__checkpoints__"


class EncryptingSerde:
    """Serde wrapper that encrypts value payloads (``*_typed``) at rest."""

    def __init__(self, inner: Any, encryption: EncryptionService, context: str = _CK_CONTEXT):
        self.inner = inner
        self._enc = encryption
        self._ctx = context

    # Metadata / custom-type serialization is left untouched so the stored
    # documents remain valid JSON (the loader json.loads() them and the search
    # index reads source/step out of them).
    def dumps(self, obj: Any) -> bytes:
        return self.inner.dumps(obj)

    def loads(self, data: Any) -> Any:
        return self.inner.loads(data)

    def dumps_typed(self, obj: Any) -> Tuple[str, str]:
        type_, data = self.inner.dumps_typed(obj)  # data is a str
        token = self._enc.encrypt(data, self._ctx).decode()
        return type_, _CK_PREFIX + token

    def loads_typed(self, data: Tuple[str, Any]) -> Any:
        type_, blob = data
        b = blob.decode() if isinstance(blob, (bytes, bytearray)) else blob
        if isinstance(b, str) and b.startswith(_CK_PREFIX):
            plaintext = self._enc.decrypt(b[len(_CK_PREFIX):], self._ctx)
            return self.inner.loads_typed((type_, plaintext))
        # Legacy (pre-encryption) plaintext checkpoint -- load unchanged.
        return self.inner.loads_typed((type_, blob))

    def __getattr__(self, name: str) -> Any:
        # Forward anything else (e.g. the serde's own helpers) to the inner serde.
        return getattr(self.inner, name)


class EncryptedAsyncRedisSaver(AsyncRedisSaver):
    """AsyncRedisSaver that does not store channel values in plaintext.

    The channel values are persisted separately as encrypted blobs (via the
    EncryptingSerde) and overwritten from those on load, so the redundant inline
    copy in the checkpoint document is dropped to avoid a plaintext leak.
    """

    def _dump_checkpoint(self, checkpoint: dict) -> dict[str, Any]:
        cp = dict(checkpoint)
        cp["channel_values"] = {}
        # Use the underlying serde (not the encrypting wrapper) so the checkpoint
        # document stays valid JSON -- the loader json.loads() it and queries
        # $.checkpoint.channel_versions, which must remain in the clear.
        inner = getattr(self.serde, "inner", self.serde)
        type_, data = inner.dumps_typed(cp)
        checkpoint_data = json.loads(data)
        return {"type": type_, **checkpoint_data, "pending_sends": []}


def checkpoint_encryption_enabled() -> bool:
    """Whether checkpoint payloads should be encrypted (default: on)."""
    return os.getenv("ENCRYPT_CHECKPOINTS", "true").lower() == "true"
