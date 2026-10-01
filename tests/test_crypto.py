"""Tests for hashing and token helpers."""

from src.utils.crypto import hash_token, new_idempotency_key, verify_signature


def test_hash_is_stable():
    assert hash_token("abc") == hash_token("abc")


def test_keys_are_unique():
    assert new_idempotency_key() != new_idempotency_key()


def test_signature_roundtrip():
    import hashlib
    import hmac

    secret = "shhh"
    payload = b"{}"
    sig = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
    assert verify_signature(payload, sig, secret) is True
    assert verify_signature(payload, "wrong", secret) is False
