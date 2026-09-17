"""Opaque tenant identity derived from a raw API key."""

from __future__ import annotations

import hashlib


def api_key_identity(api_key: str) -> str:
    """Return a stable, non-secret user_id for ``api_key``.

    The programmatic routes authenticate with a bare API key, so the key is the
    only identifier available. Hashing it keeps the credential out of Redis key
    names, log fields, agent output and the encryption KDF. Safe because the key
    space is a UUID; use an HMAC instead if the key format ever gets smaller.
    """
    if not api_key:
        raise ValueError("Cannot derive an identity from an empty API key")
    return f"apikey_{hashlib.sha256(api_key.encode()).hexdigest()[:32]}"
