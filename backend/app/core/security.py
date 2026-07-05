"""Password hashing and JWT token handling."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import bcrypt
from jose import JWTError, jwt

from app.core.config import get_settings


class TokenError(Exception):
    """Raised when a JWT is missing, expired, or otherwise invalid."""


def hash_password(plain_password: str) -> str:
    # bcrypt has a hard 72-byte input limit; truncate rather than let it raise,
    # since a user-supplied password could exceed it (encode first — byte
    # length, not character length, is what matters for multi-byte UTF-8).
    password_bytes = plain_password.encode("utf-8")[:72]
    return bcrypt.hashpw(password_bytes, bcrypt.gensalt()).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    password_bytes = plain_password.encode("utf-8")[:72]
    try:
        return bcrypt.checkpw(password_bytes, hashed_password.encode("utf-8"))
    except ValueError:
        # Malformed hash (e.g. corrupted/legacy data) — never a match.
        return False


def create_access_token(subject: str, expires_minutes: int | None = None) -> str:
    settings = get_settings()
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=expires_minutes if expires_minutes is not None else settings.ACCESS_TOKEN_EXPIRE_MINUTES
    )
    payload = {"sub": subject, "exp": expire}
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_access_token(token: str) -> str:
    """Return the subject (user id) encoded in a valid token, or raise TokenError."""
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
    except JWTError as exc:
        raise TokenError(f"Invalid or expired token: {exc}") from exc

    subject = payload.get("sub")
    if not subject:
        raise TokenError("Token payload missing 'sub' claim")
    return subject
