from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from jose import jwt

from app.core.security import (
    InvalidAccessTokenError,
    create_access_token,
    decode_access_token,
    generate_secure_token,
    hash_password,
    hash_token,
    verify_password,
)
from app.core.settings import get_settings


@pytest.fixture(autouse=True)
def security_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("SECRET_KEY", "test-secret-key-with-enough-length")
    monkeypatch.setenv("JWT_ALGORITHM", "HS256")
    monkeypatch.setenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30")
    get_settings.cache_clear()

    yield

    get_settings.cache_clear()


def test_password_hash_verifies_correct_password() -> None:
    password = "correct horse battery staple"

    password_hash = hash_password(password)

    assert password_hash != password
    assert verify_password(password, password_hash) is True


def test_password_hash_rejects_wrong_password() -> None:
    password_hash = hash_password("correct-password")

    assert verify_password("wrong-password", password_hash) is False


def test_jwt_decodes_valid_token() -> None:
    user_id = uuid4()

    token = create_access_token(user_id)
    payload = decode_access_token(token)

    assert payload["sub"] == str(user_id)
    assert "exp" in payload


def test_jwt_rejects_invalid_token() -> None:
    with pytest.raises(InvalidAccessTokenError, match="invalid or expired"):
        decode_access_token("not-a-valid-jwt")


def test_jwt_rejects_expired_token() -> None:
    settings = get_settings()
    assert settings.secret_key is not None
    expired_token = jwt.encode(
        {
            "sub": str(uuid4()),
            "exp": datetime.now(UTC) - timedelta(minutes=1),
        },
        settings.secret_key.get_secret_value(),
        algorithm=settings.jwt_algorithm,
    )

    with pytest.raises(InvalidAccessTokenError, match="invalid or expired"):
        decode_access_token(expired_token)


def test_token_hashing_is_deterministic() -> None:
    token = generate_secure_token()

    assert hash_token(token) == hash_token(token)


def test_raw_token_and_hash_are_different() -> None:
    token = generate_secure_token()
    token_hash = hash_token(token)

    assert token_hash != token
    assert len(token_hash) == 64
