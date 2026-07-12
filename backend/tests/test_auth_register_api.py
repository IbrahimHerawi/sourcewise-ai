from __future__ import annotations

from collections.abc import AsyncGenerator, Generator
from datetime import UTC, datetime
from uuid import UUID

import httpx
import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_token, verify_password
from app.core.settings import get_settings
from app.db.models.auth import EmailVerificationToken
from app.db.session import get_db_session
from app.main import app
from app.repositories.user_repository import UserRepository


@pytest.fixture
def register_settings(monkeypatch: pytest.MonkeyPatch) -> Generator[None]:
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("SECRET_KEY", "test-secret-key-with-enough-length")
    monkeypatch.setenv("EMAIL_VERIFICATION_TOKEN_EXPIRE_MINUTES", "60")
    get_settings.cache_clear()

    yield

    get_settings.cache_clear()


@pytest_asyncio.fixture
async def auth_client(
    register_settings: None,
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


def _registration_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "first_name": "Ibrahim",
        "last_name": "Herawi",
        "email": "USER@Example.COM",
        "password": "StrongPassword123!",
    }
    payload.update(overrides)
    return payload


async def _register(
    client: httpx.AsyncClient,
    **overrides: object,
) -> httpx.Response:
    return await client.post(
        "/api/v1/auth/register",
        json=_registration_payload(**overrides),
    )


async def _get_user(session: AsyncSession, email: str):
    return await UserRepository(session).get_user_by_email(email)


@pytest.mark.asyncio
async def test_register_success_creates_user_hashes_password_and_token(
    auth_client: httpx.AsyncClient,
    db_session: AsyncSession,
) -> None:
    response = await _register(auth_client)

    assert response.status_code == 200
    payload = response.json()
    user_payload = payload["user"]
    user_id = UUID(user_payload["id"])
    verification_token = payload["verification_token"]

    assert payload["message"] == "Registration successful. Please verify your email."
    assert user_payload == {
        "id": str(user_id),
        "first_name": "Ibrahim",
        "last_name": "Herawi",
        "email": "user@example.com",
        "is_email_verified": False,
        "is_active": True,
        "created_at": user_payload["created_at"],
    }
    assert "password_hash" not in response.text
    assert "token_hash" not in response.text

    user = await _get_user(db_session, "user@example.com")
    assert user is not None
    assert user.id == user_id
    assert user.password_hash != "StrongPassword123!"
    assert verify_password("StrongPassword123!", user.password_hash) is True
    assert user.first_name == "Ibrahim"
    assert user.last_name == "Herawi"
    assert user.is_email_verified is False
    assert user.is_active is True

    token_rows = list(
        (
            await db_session.scalars(
                select(EmailVerificationToken).where(EmailVerificationToken.user_id == user.id)
            )
        ).all()
    )
    assert len(token_rows) == 1
    assert token_rows[0].token_hash == hash_token(verification_token)
    assert token_rows[0].token_hash != verification_token
    assert token_rows[0].used_at is None
    assert token_rows[0].expires_at > datetime.now(UTC)


@pytest.mark.asyncio
async def test_register_trims_first_name_and_last_name_before_saving(
    auth_client: httpx.AsyncClient,
    db_session: AsyncSession,
) -> None:
    response = await _register(
        auth_client,
        email="trimmed@example.com",
        first_name="  Ibrahim  ",
        last_name="\tHerawi\n",
    )

    assert response.status_code == 200
    assert response.json()["user"]["first_name"] == "Ibrahim"
    assert response.json()["user"]["last_name"] == "Herawi"

    user = await _get_user(db_session, "trimmed@example.com")
    assert user is not None
    assert user.first_name == "Ibrahim"
    assert user.last_name == "Herawi"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "field",
    ["first_name", "last_name"],
)
async def test_register_rejects_missing_required_name_fields(
    auth_client: httpx.AsyncClient,
    field: str,
) -> None:
    payload = _registration_payload(email=f"missing-{field}@example.com")
    payload.pop(field)

    response = await auth_client.post("/api/v1/auth/register", json=payload)

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "field",
    ["first_name", "last_name"],
)
async def test_register_rejects_empty_required_name_fields_after_trimming(
    auth_client: httpx.AsyncClient,
    field: str,
) -> None:
    response = await _register(
        auth_client,
        email=f"empty-{field}@example.com",
        **{field: "   "},
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


@pytest.mark.asyncio
async def test_register_rejects_invalid_email(auth_client: httpx.AsyncClient) -> None:
    response = await _register(auth_client, email="not-an-email")

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "password",
    ["short", "longenoughbutweak", "NoNumberSymbol", "NoSymbol123"],
)
async def test_register_rejects_weak_or_too_short_password(
    auth_client: httpx.AsyncClient,
    password: str,
) -> None:
    response = await _register(
        auth_client,
        email=f"weak-{password.lower()}@example.com",
        password=password,
    )

    assert response.status_code == 400
    assert response.json() == {
        "error": {
            "code": "validation_error",
            "message": (
                "Password must be 12 to 72 bytes and include uppercase, lowercase, "
                "number, and symbol characters."
            ),
        }
    }
    assert password not in response.text


@pytest.mark.asyncio
async def test_register_rejects_duplicate_email(
    auth_client: httpx.AsyncClient,
) -> None:
    first_response = await _register(
        auth_client,
        email="duplicate@example.com",
    )
    second_response = await _register(
        auth_client,
        email="DUPLICATE@example.com",
    )

    assert first_response.status_code == 200
    assert second_response.status_code == 409
    assert second_response.json() == {
        "error": {
            "code": "conflict",
            "message": "A user with this email already exists.",
        }
    }


@pytest.mark.asyncio
async def test_register_omits_verification_token_outside_local_or_test_env(
    auth_client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("SECRET_KEY", "production-secret-key-with-enough-length")
    get_settings.cache_clear()

    response = await _register(
        auth_client,
        email="production-token@example.com",
    )

    assert response.status_code == 200
    assert "verification_token" not in response.json()


def test_auth_register_route_exists_only_under_api_v1_auth() -> None:
    paths = {getattr(route, "path", "") for route in app.routes}

    assert "/api/v1/auth/register" in paths
    assert "/api/auth/register" not in paths
    assert "/auth/register" not in paths
