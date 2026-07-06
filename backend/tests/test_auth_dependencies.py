from __future__ import annotations

from collections.abc import AsyncGenerator, Generator
from typing import Annotated
from uuid import uuid4

import httpx
import pytest
import pytest_asyncio
from fastapi import Depends, FastAPI
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import (
    get_current_active_user,
    get_current_user,
    get_current_verified_user,
)
from app.core.errors import register_exception_handlers
from app.core.security import create_access_token
from app.core.settings import get_settings
from app.db.models.auth import User
from app.db.session import get_db_session
from app.repositories.user_repository import UserRepository


@pytest.fixture
def auth_settings(monkeypatch: pytest.MonkeyPatch) -> Generator[None]:
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("SECRET_KEY", "test-secret-key-with-enough-length")
    monkeypatch.setenv("JWT_ALGORITHM", "HS256")
    monkeypatch.setenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30")
    get_settings.cache_clear()

    yield

    get_settings.cache_clear()


@pytest_asyncio.fixture
async def auth_client(
    auth_settings: None,
    db_session: AsyncSession,
) -> AsyncGenerator[httpx.AsyncClient]:
    async def _override_get_db_session() -> AsyncGenerator[AsyncSession]:
        yield db_session

    test_app = FastAPI()
    register_exception_handlers(test_app)
    test_app.dependency_overrides[get_db_session] = _override_get_db_session

    @test_app.get("/current")
    async def read_current_user(
        current_user: Annotated[User, Depends(get_current_user)],
    ) -> dict[str, str]:
        return {"user_id": str(current_user.id), "email": current_user.email}

    @test_app.get("/active")
    async def read_active_user(
        current_user: Annotated[User, Depends(get_current_active_user)],
    ) -> dict[str, str]:
        return {"user_id": str(current_user.id)}

    @test_app.get("/verified")
    async def read_verified_user(
        current_user: Annotated[User, Depends(get_current_verified_user)],
    ) -> dict[str, str]:
        return {"user_id": str(current_user.id)}

    @test_app.get("/stacked")
    async def read_stacked_dependencies(
        active_user: Annotated[User, Depends(get_current_active_user)],
        verified_user: Annotated[User, Depends(get_current_verified_user)],
    ) -> dict[str, str]:
        return {
            "active_user_id": str(active_user.id),
            "verified_user_id": str(verified_user.id),
        }

    transport = httpx.ASGITransport(app=test_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client


async def _create_user(
    session: AsyncSession,
    *,
    email: str,
    is_active: bool = True,
    is_email_verified: bool = True,
) -> User:
    user = await UserRepository(session).create_user(email, "hashed-password")
    await session.execute(
        update(User)
        .where(User.id == user.id)
        .values(is_active=is_active, is_email_verified=is_email_verified)
    )
    await session.flush()
    await session.refresh(user)
    return user


def _auth_headers(user: User) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(user.id)}"}


@pytest.mark.asyncio
async def test_get_current_user_rejects_missing_token(auth_client: httpx.AsyncClient) -> None:
    response = await auth_client.get("/current")

    assert response.status_code == 401
    assert response.json() == {
        "error": {
            "code": "unauthorized",
            "message": "Authentication credentials could not be validated.",
        }
    }


@pytest.mark.asyncio
async def test_get_current_user_rejects_invalid_token(auth_client: httpx.AsyncClient) -> None:
    response = await auth_client.get(
        "/current",
        headers={"Authorization": "Bearer not-a-valid-jwt"},
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthorized"
    assert "token" not in response.text.lower()


@pytest.mark.asyncio
async def test_get_current_user_rejects_missing_user(auth_client: httpx.AsyncClient) -> None:
    response = await auth_client.get(
        "/current",
        headers={"Authorization": f"Bearer {create_access_token(uuid4())}"},
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthorized"


@pytest.mark.asyncio
async def test_get_current_active_user_rejects_inactive_user(
    auth_client: httpx.AsyncClient,
    db_session: AsyncSession,
) -> None:
    user = await _create_user(
        db_session,
        email="inactive-auth-dependency@example.com",
        is_active=False,
        is_email_verified=True,
    )

    response = await auth_client.get("/active", headers=_auth_headers(user))

    assert response.status_code == 403
    assert response.json() == {
        "error": {
            "code": "forbidden",
            "message": "User account is inactive.",
        }
    }


@pytest.mark.asyncio
async def test_get_current_verified_user_rejects_unverified_user(
    auth_client: httpx.AsyncClient,
    db_session: AsyncSession,
) -> None:
    user = await _create_user(
        db_session,
        email="unverified-auth-dependency@example.com",
        is_active=True,
        is_email_verified=False,
    )

    response = await auth_client.get("/verified", headers=_auth_headers(user))

    assert response.status_code == 403
    assert response.json() == {
        "error": {
            "code": "forbidden",
            "message": "User email is not verified.",
        }
    }


@pytest.mark.asyncio
async def test_get_current_verified_user_accepts_verified_active_user(
    auth_client: httpx.AsyncClient,
    db_session: AsyncSession,
) -> None:
    user = await _create_user(
        db_session,
        email="verified-auth-dependency@example.com",
        is_active=True,
        is_email_verified=True,
    )

    response = await auth_client.get("/verified", headers=_auth_headers(user))

    assert response.status_code == 200
    assert response.json() == {"user_id": str(user.id)}


@pytest.mark.asyncio
async def test_nested_auth_dependencies_share_one_user_lookup(
    auth_client: httpx.AsyncClient,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user = await _create_user(
        db_session,
        email="stacked-auth-dependency@example.com",
        is_active=True,
        is_email_verified=True,
    )
    lookup_count = 0
    original_get_user_by_id = UserRepository.get_user_by_id

    async def counted_get_user_by_id(
        self: UserRepository,
        user_id,
    ) -> User | None:
        nonlocal lookup_count
        lookup_count += 1
        return await original_get_user_by_id(self, user_id)

    monkeypatch.setattr(UserRepository, "get_user_by_id", counted_get_user_by_id)

    response = await auth_client.get("/stacked", headers=_auth_headers(user))

    assert response.status_code == 200
    assert response.json() == {
        "active_user_id": str(user.id),
        "verified_user_id": str(user.id),
    }
    assert lookup_count == 1
