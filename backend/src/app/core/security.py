"""Security helpers for passwords and tokens."""

from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

import bcrypt
from jose import JWTError, jwt

from app.core.settings import get_settings

_BCRYPT_ROUNDS = 12
_BCRYPT_MAX_PASSWORD_BYTES = 72
_SECURE_TOKEN_BYTES = 32


class SecurityError(ValueError):
    """Raised when security processing fails."""


class InvalidAccessTokenError(SecurityError):
    """Raised when an access token is invalid or expired."""


def _get_secret_key() -> str:
    settings = get_settings()
    if settings.secret_key is None:
        raise SecurityError("Security settings are not configured.")
    return settings.secret_key.get_secret_value()


def hash_password(password: str) -> str:
    """Hash a plaintext password for persistent storage."""
    try:
        password_bytes = password.encode("utf-8")
        if len(password_bytes) > _BCRYPT_MAX_PASSWORD_BYTES:
            raise ValueError("Password is too long for bcrypt.")
        return bcrypt.hashpw(
            password_bytes,
            bcrypt.gensalt(rounds=_BCRYPT_ROUNDS),
        ).decode("utf-8")
    except Exception as exc:
        raise SecurityError("Password could not be hashed.") from exc


def verify_password(plain_password: str, password_hash: str) -> bool:
    """Return whether a plaintext password matches a stored password hash."""
    try:
        password_bytes = plain_password.encode("utf-8")
        if len(password_bytes) > _BCRYPT_MAX_PASSWORD_BYTES:
            return False
        return bcrypt.checkpw(password_bytes, password_hash.encode("utf-8"))
    except Exception:
        return False


def create_access_token(user_id: UUID) -> str:
    """Create a signed JWT access token for a user."""
    settings = get_settings()
    expires_at = datetime.now(UTC) + timedelta(minutes=settings.access_token_expire_minutes)
    claims: dict[str, Any] = {
        "sub": str(user_id),
        "exp": expires_at,
    }

    try:
        return jwt.encode(
            claims,
            _get_secret_key(),
            algorithm=settings.jwt_algorithm,
        )
    except JWTError as exc:
        raise SecurityError("Access token could not be created.") from exc


def decode_access_token(token: str) -> dict[str, Any]:
    """Decode and validate a signed JWT access token."""
    settings = get_settings()

    try:
        payload = jwt.decode(
            token,
            _get_secret_key(),
            algorithms=[settings.jwt_algorithm],
        )
    except JWTError as exc:
        raise InvalidAccessTokenError("Access token is invalid or expired.") from exc

    subject = payload.get("sub")
    if not isinstance(subject, str) or not subject:
        raise InvalidAccessTokenError("Access token is invalid or expired.")

    return payload


def generate_secure_token() -> str:
    """Generate a URL-safe random token for immediate one-time use."""
    return secrets.token_urlsafe(_SECURE_TOKEN_BYTES)


def hash_token(token: str) -> str:
    """Return a deterministic HMAC-SHA256 hash for token lookup."""
    secret_key = _get_secret_key().encode("utf-8")
    return hmac.new(secret_key, token.encode("utf-8"), hashlib.sha256).hexdigest()


__all__ = [
    "InvalidAccessTokenError",
    "SecurityError",
    "create_access_token",
    "decode_access_token",
    "generate_secure_token",
    "hash_password",
    "hash_token",
    "verify_password",
]
