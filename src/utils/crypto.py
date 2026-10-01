"""Hashing and token helpers.

Nothing here holds a secret: keys come from the environment via `config.Settings`.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets


def hash_token(token: str) -> str:
    """Return a stable SHA-256 digest of a token, for storage and lookup."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def new_idempotency_key() -> str:
    """Return a fresh, unguessable idempotency key."""
    return secrets.token_urlsafe(24)


def verify_signature(payload: bytes, signature: str, secret: str) -> bool:
    """Return True when the webhook signature matches, in constant time."""
    expected = hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)
