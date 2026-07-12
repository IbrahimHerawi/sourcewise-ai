from __future__ import annotations

from collections.abc import AsyncGenerator, Generator
from datetime import UTC, datetime

import httpx
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decode_access_token, hash_password
from app.core.settings import get_settings
from app.db.models.auth import User
from app.db.session import get_db_session
from app.main import app
from app.repositories.user_repository import UserRepository

_PASSWORD = "StrongPassword123!"


@pytest.fixture
def login_settings(monkeypatch: pytest.MonkeyPatch) -> Generator[None]:
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("SECRET_KEY", "test-secret-key-with-enough-length")
    monkeypatch.setenv("JWT_ALGORITHM", "HS256")
    monkeypatch.setenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30")
    get_settings.cache_clear()

    yield

    get_settings.cache_clear()


@pytest_asyncio.fixture
async def auth_client(
    login_settings: None,
    db_session: AsyncSession,
) -> AsyncGenerator[httpx.AsyncClient]:
    async def _override_get_db_session() -> AsyncGenerator[AsyncSession]:
        yield db_session

    original_overrides = app.dependency_overrides.copy()
    app.dependency_overrides[get_db_session] = _override_get_db_session

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client

    app.dependency_overrides.clear()
    app.dependency_overrides.update(original_overrides)


async def _create_user(
    session: AsyncSession,
    *,
    email: str,
    is_email_verified: bool = True,
    is_active: bool = True,
) -> User:
    return await UserRepository(session).create_user(
        email=email,
        password_hash=hash_password(_PASSWORD),
        first_name="Ibrahim",
        last_name="Herawi",
        is_email_verified=is_email_verified,
        is_active=is_active,
    )


async def _login(
    client: httpx.AsyncClient,
    *,
    email: str,
    password: str = _PASSWORD,
) -> httpx.Response:
    return await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )


@pytest.mark.asyncio
async def test_login_rejected_before_email_verification(
    auth_client: httpx.AsyncClient,
    db_session: AsyncSession,
) -> None:
    await _create_user(
        db_session,
        email="unverified-login@example.com",
        is_email_verified=False,
    )

    response = await _login(auth_client, email="unverified-login@example.com")

    assert response.status_code == 403
    assert response.json() == {
        "error": {
            "code": "email_not_verified",
            "message": "User email is not verified.",
        }
    }
    assert "access_token" not in response.text
    assert "password_hash" not in response.text


@pytest.mark.asyncio
async def test_login_rejects_wrong_password_with_generic_credentials_error(
    auth_client: httpx.AsyncClient,
    db_session: AsyncSession,
) -> None:
    await _create_user(db_session, email="wrong-password@example.com")

    wrong_password_response = await _login(
        auth_client,
        email="wrong-password@example.com",
        password="WrongPassword123!",
    )
    missing_user_response = await _login(
        auth_client,
        email="missing-user@example.com",
        password="WrongPassword123!",
    )

    expected_error = {
        "error": {
            "code": "invalid_credentials",
            "message": "Invalid email or password.",
        }
    }
    assert wrong_password_response.status_code == 401
    assert missing_user_response.status_code == 401
    assert wrong_password_response.json() == expected_error
    assert missing_user_response.json() == expected_error
    assert "WrongPassword123!" not in wrong_password_response.text


@pytest.mark.asyncio
async def test_login_rejects_inactive_user(
    auth_client: httpx.AsyncClient,
    db_session: AsyncSession,
) -> None:
    await _create_user(
        db_session,
        email="inactive-login@example.com",
        is_active=False,
    )

    response = await _login(auth_client, email="inactive-login@example.com")

    assert response.status_code == 403
    assert response.json() == {
        "error": {
            "code": "account_inactive",
            "message": "User account is inactive.",
        }
    }


@pytest.mark.asyncio
async def test_login_succeeds_after_verification_with_one_normalized_lookup(
    auth_client: httpx.AsyncClient,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user = await _create_user(
        db_session,
        email="verified-login@example.com",
        is_email_verified=False,
    )
    await UserRepository(db_session).mark_email_verified(user.id)

    lookup_count = 0
    original_get_user_by_email = UserRepository.get_user_by_email

    async def counted_get_user_by_email(
        self: UserRepository,
        email: str,
    ) -> User | None:
        nonlocal lookup_count
        lookup_count += 1
        return await original_get_user_by_email(self, email)

    monkeypatch.setattr(UserRepository, "get_user_by_email", counted_get_user_by_email)

    response = await _login(auth_client, email="VERIFIED-LOGIN@EXAMPLE.COM")

    assert response.status_code == 200
    payload = response.json()
    assert payload == {
        "access_token": payload["access_token"],
        "token_type": "bearer",
        "user": {
            "id": str(user.id),
            "first_name": "Ibrahim",
            "last_name": "Herawi",
            "email": "verified-login@example.com",
            "is_email_verified": True,
            "is_active": True,
            "created_at": payload["user"]["created_at"],
        },
    }
    assert lookup_count == 1
    assert "password_hash" not in response.text

    token_payload = decode_access_token(payload["access_token"])
    assert token_payload["sub"] == str(user.id)
    assert datetime.fromtimestamp(token_payload["exp"], tz=UTC) > datetime.now(UTC)


@pytest.mark.asyncio
async def test_me_rejected_without_token(auth_client: httpx.AsyncClient) -> None:
    response = await auth_client.get("/api/v1/auth/me")

    assert response.status_code == 401
    assert response.json() == {
        "error": {
            "code": "unauthorized",
            "message": "Authentication credentials could not be validated.",
        }
    }


@pytest.mark.asyncio
async def test_me_returns_safe_user_for_valid_login_token(
    auth_client: httpx.AsyncClient,
    db_session: AsyncSession,
) -> None:
    user = await _create_user(db_session, email="current-user@example.com")
    login_response = await _login(auth_client, email=user.email)
    access_token = login_response.json()["access_token"]

    response = await auth_client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {access_token}"},
    )

    assert response.status_code == 200
    assert response.json() == login_response.json()["user"]
    assert "password_hash" not in response.text


def test_login_and_me_routes_exist_only_under_api_v1_auth() -> None:
    paths = {getattr(route, "path", "") for route in app.routes}

    for endpoint in ["login", "me"]:
        assert f"/api/v1/auth/{endpoint}" in paths
        assert f"/api/auth/{endpoint}" not in paths
        assert f"/auth/{endpoint}" not in paths
