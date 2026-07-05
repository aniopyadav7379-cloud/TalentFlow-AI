import time

import pytest

from app.core.security import TokenError, create_access_token, decode_access_token, hash_password, verify_password


def test_hash_password_produces_verifiable_hash():
    hashed = hash_password("correct-horse-battery-staple")
    assert verify_password("correct-horse-battery-staple", hashed) is True


def test_verify_password_rejects_wrong_password():
    hashed = hash_password("correct-horse-battery-staple")
    assert verify_password("wrong-password", hashed) is False


def test_hash_password_truncates_over_72_bytes_without_raising():
    long_password = "a" * 200
    hashed = hash_password(long_password)
    assert verify_password(long_password, hashed) is True


def test_verify_password_returns_false_for_malformed_hash():
    assert verify_password("anything", "not-a-real-bcrypt-hash") is False


def test_create_and_decode_access_token_roundtrip():
    token = create_access_token(subject="user-123")
    assert decode_access_token(token) == "user-123"


def test_decode_access_token_rejects_garbage_token():
    with pytest.raises(TokenError):
        decode_access_token("not.a.valid.jwt")


def test_decode_access_token_rejects_expired_token():
    token = create_access_token(subject="user-123", expires_minutes=-1)  # already expired
    with pytest.raises(TokenError):
        decode_access_token(token)


def test_decode_access_token_rejects_tampered_signature():
    token = create_access_token(subject="user-123")
    tampered = token[:-4] + "abcd"
    with pytest.raises(TokenError):
        decode_access_token(tampered)
