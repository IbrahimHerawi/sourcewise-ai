from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncGenerator, Generator
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import httpx
import pytest
import pytest_asyncio
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.security import hash_password, hash_token
from app.core.settings import get_settings
from app.db.models.auth import RefreshToken, User
from app.db.session import get_db_session
from app.main import app
from app.repositories.user_repository import UserRepository

_PASSWORD = "StrongPassword123!"
_NEW_PASSWORD = "NewStrongPassword123!"
_INVALID_REFRESH_RESPONSE = {
    "error": {
        "code": "invalid_refresh_token",
        "message": "Refresh token is invalid or expired.",
    }
}


@pytest.fixture
def refresh_settings(monkeypatch: pytest.MonkeyPatch) -> Generator[None]:
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("SECRET_KEY", "test-secret-key-with-enough-length")
    monkeypatch.setenv("JWT_ALGORITHM", "HS256")
    monkeypatch.setenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30")
    monkeypatch.setenv("REFRESH_TOKEN_EXPIRE_DAYS", "30")
    get_settings.cache_clear()

    yield

    get_settings.cache_clear()


@pytest_asyncio.fixture
async def refresh_client(
    refresh_settings: None,
    db_session: AsyncSession,
) -> AsyncGenerator[httpx.AsyncClient]:
    async def _override_get_db_session() -> AsyncGenerator[AsyncSession]:
        yield db_session

    original_overrides = app.dependency_overrides.copy()
    app.dependency_overrides[get_db_session] = _override_get_db_session
    transport = httpx.ASGITransport(app=app)
    try:
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as client:
            yield client
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(original_overrides)


async def _create_user(
    session: AsyncSession,
    *,
    email: str,
    is_active: bool = True,
    is_email_verified: bool = True,
) -> User:
    user = await UserRepository(session).create_user(
        email=email,
        password_hash=hash_password(_PASSWORD),
        first_name="Refresh",
        last_name="User",
        is_active=is_active,
        is_email_verified=is_email_verified,
    )
    await session.commit()
    return user


async def _login(client: httpx.AsyncClient, email: str) -> httpx.Response:
    return await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": _PASSWORD},
    )


async def _refresh(client: httpx.AsyncClient, token: str) -> httpx.Response:
    return await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": token},
    )


async def _stored_tokens(session: AsyncSession, user_id: object) -> list[RefreshToken]:
    return list(
        (
            await session.scalars(
                select(RefreshToken)
                .where(RefreshToken.user_id == user_id)
                .order_by(RefreshToken.created_at, RefreshToken.id)
            )
        ).all()
    )


@pytest.mark.asyncio
async def test_refresh_rotates_repeatedly_without_extending_family_lifetime_and_replay_revokes(
    refresh_client: httpx.AsyncClient,
    db_session: AsyncSession,
) -> None:
    user = await _create_user(db_session, email="rotation@example.com")
    login_response = await _login(refresh_client, user.email)
    original_raw_token = login_response.json()["refresh_token"]

    first_rotation = await _refresh(refresh_client, f"  {original_raw_token}  ")
    first_payload = first_rotation.json()
    second_rotation = await _refresh(refresh_client, first_payload["refresh_token"])
    second_payload = second_rotation.json()
    replay = await _refresh(refresh_client, original_raw_token)

    tokens = await _stored_tokens(db_session, user.id)
    assert login_response.status_code == 200
    assert first_rotation.status_code == 200
    assert second_rotation.status_code == 200
    assert replay.status_code == 401
    assert replay.json() == _INVALID_REFRESH_RESPONSE
    assert first_rotation.headers["cache-control"] == "no-store"
    assert first_rotation.headers["pragma"] == "no-cache"
    assert first_payload["token_type"] == "bearer"
    assert first_payload["access_token_expires_in"] == 1800
    assert 0 < second_payload["refresh_token_expires_in"] <= first_payload[
        "refresh_token_expires_in"
    ]
    assert len(tokens) == 3
    assert len({token.family_id for token in tokens}) == 1
    assert len({token.expires_at for token in tokens}) == 1
    tokens_by_hash = {token.token_hash: token for token in tokens}
    original = tokens_by_hash[hash_token(original_raw_token)]
    first_replacement = tokens_by_hash[hash_token(first_payload["refresh_token"])]
    second_replacement = tokens_by_hash[hash_token(second_payload["refresh_token"])]
    assert original.used_at is not None
    assert original.replaced_by_id == first_replacement.id
    assert first_replacement.used_at is not None
    assert first_replacement.replaced_by_id == second_replacement.id
    assert all(token.revoked_at is not None for token in tokens)
    assert all(token.token_hash not in {original_raw_token, first_payload["refresh_token"]} for token in tokens)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "state",
    ["unknown", "expired", "revoked", "inactive", "unverified"],
)
async def test_refresh_uses_one_public_error_for_all_invalid_states(
    refresh_client: httpx.AsyncClient,
    db_session: AsyncSession,
    state: str,
) -> None:
    raw_token = f"refresh-token-{state}-with-at-least-thirty-two-characters"
    if state != "unknown":
        user = await _create_user(
            db_session,
            email=f"refresh-{state}@example.com",
            is_active=state != "inactive",
            is_email_verified=state != "unverified",
        )
        token = await UserRepository(db_session).create_refresh_token(
            user.id,
            uuid4(),
            hash_token(raw_token),
            datetime.now(UTC)
            + (timedelta(seconds=-1) if state == "expired" else timedelta(days=30)),
        )
        if state == "revoked":
            await UserRepository(db_session).revoke_refresh_token_family(token.family_id)
        await db_session.commit()

    response = await _refresh(refresh_client, raw_token)

    assert response.status_code == 401
    assert response.json() == _INVALID_REFRESH_RESPONSE
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["pragma"] == "no-cache"
    assert raw_token not in response.text

    if state not in {"unknown", "revoked"}:
        stored = await db_session.scalar(
            select(RefreshToken).where(RefreshToken.token_hash == hash_token(raw_token))
        )
        assert stored is not None
        assert stored.revoked_at is not None


@pytest.mark.asyncio
async def test_refresh_generation_failure_preserves_current_token(
    refresh_client: httpx.AsyncClient,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user = await _create_user(db_session, email="refresh-generation-failure@example.com")
    login_response = await _login(refresh_client, user.email)
    raw_token = login_response.json()["refresh_token"]

    def fail_generation() -> str:
        raise RuntimeError("sentinel token generation failure")

    monkeypatch.setattr("app.api.v1.endpoints.auth.generate_secure_token", fail_generation)
    response = await _refresh(refresh_client, raw_token)
    stored = await db_session.scalar(
        select(RefreshToken).where(RefreshToken.token_hash == hash_token(raw_token))
    )

    assert response.status_code == 500
    assert "sentinel" not in response.text
    assert stored is not None
    assert stored.used_at is None
    assert stored.revoked_at is None


@pytest.mark.asyncio
async def test_refresh_persistence_failure_rolls_back_and_preserves_current_token(
    refresh_settings: None,
    postgres_database_url: str,
    migrated_database: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = create_async_engine(postgres_database_url, pool_pre_ping=True)
    session_maker = async_sessionmaker(engine, expire_on_commit=False, autoflush=False)

    async def _override_get_db_session() -> AsyncGenerator[AsyncSession]:
        async with session_maker() as session:
            yield session

    original_overrides = app.dependency_overrides.copy()
    app.dependency_overrides[get_db_session] = _override_get_db_session
    email = f"refresh-persistence-failure-{uuid4()}@example.com"
    try:
        async with session_maker() as session:
            await UserRepository(session).create_user(
                email=email,
                password_hash=hash_password(_PASSWORD),
                first_name="Persistence",
                last_name="Failure",
                is_active=True,
                is_email_verified=True,
            )
            await session.commit()

        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as client:
            login_response = await _login(client, email)
            raw_token = login_response.json()["refresh_token"]

            async def fail_create_refresh_token(*_: object, **__: object) -> RefreshToken:
                raise RuntimeError("sentinel persistence failure")

            monkeypatch.setattr(
                UserRepository,
                "create_refresh_token",
                fail_create_refresh_token,
            )
            response = await _refresh(client, raw_token)

        async with session_maker() as session:
            stored = await session.scalar(
                select(RefreshToken).where(
                    RefreshToken.token_hash == hash_token(raw_token)
                )
            )

        assert response.status_code == 500
        assert "sentinel" not in response.text
        assert stored is not None
        assert stored.used_at is None
        assert stored.revoked_at is None
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(original_overrides)
        await engine.dispose()


@pytest.mark.asyncio
async def test_logout_revokes_only_its_family_and_is_idempotent_for_unknown_tokens(
    refresh_client: httpx.AsyncClient,
    db_session: AsyncSession,
) -> None:
    user = await _create_user(db_session, email="logout@example.com")
    first_login = await _login(refresh_client, user.email)
    second_login = await _login(refresh_client, user.email)
    first_token = first_login.json()["refresh_token"]
    second_token = second_login.json()["refresh_token"]

    first_logout = await refresh_client.post(
        "/api/v1/auth/logout",
        json={"refresh_token": first_token},
    )
    second_logout = await refresh_client.post(
        "/api/v1/auth/logout",
        json={"refresh_token": first_token},
    )
    unknown_logout = await refresh_client.post(
        "/api/v1/auth/logout",
        json={"refresh_token": "unknown-refresh-token-with-at-least-thirty-two-characters"},
    )
    revoked_refresh = await _refresh(refresh_client, first_token)
    active_refresh = await _refresh(refresh_client, second_token)

    assert first_logout.status_code == 204
    assert second_logout.status_code == 204
    assert unknown_logout.status_code == 204
    assert first_logout.content == b""
    assert first_logout.headers["cache-control"] == "no-store"
    assert revoked_refresh.status_code == 401
    assert active_refresh.status_code == 200


@pytest.mark.asyncio
async def test_password_reset_revokes_all_user_families_without_affecting_other_users(
    refresh_client: httpx.AsyncClient,
    db_session: AsyncSession,
) -> None:
    first_user = await _create_user(db_session, email="reset-refresh-a@example.com")
    second_user = await _create_user(db_session, email="reset-refresh-b@example.com")
    first_login = await _login(refresh_client, first_user.email)
    second_first_login = await _login(refresh_client, first_user.email)
    other_login = await _login(refresh_client, second_user.email)

    forgot_response = await refresh_client.post(
        "/api/v1/auth/forgot-password",
        json={"email": first_user.email},
    )
    reset_response = await refresh_client.post(
        "/api/v1/auth/reset-password",
        json={
            "token": forgot_response.json()["reset_token"],
            "new_password": _NEW_PASSWORD,
        },
    )

    first_family_refresh = await _refresh(
        refresh_client, first_login.json()["refresh_token"]
    )
    second_family_refresh = await _refresh(
        refresh_client, second_first_login.json()["refresh_token"]
    )
    other_user_refresh = await _refresh(refresh_client, other_login.json()["refresh_token"])

    assert reset_response.status_code == 200
    assert first_family_refresh.status_code == 401
    assert second_family_refresh.status_code == 401
    assert other_user_refresh.status_code == 200


@pytest.mark.asyncio
async def test_refresh_token_sentinel_is_absent_from_errors_logs_and_public_hash_output(
    refresh_client: httpx.AsyncClient,
    caplog: pytest.LogCaptureFixture,
) -> None:
    raw_token = "SENTINEL_REFRESH_TOKEN_27_WITH_SUFFICIENT_LENGTH"
    token_hash = hash_token(raw_token)

    with caplog.at_level("INFO"):
        response = await _refresh(refresh_client, raw_token)

    rendered = response.text + json.dumps(dict(response.headers)) + caplog.text
    assert response.status_code == 401
    assert raw_token not in rendered
    assert token_hash not in rendered


@pytest.mark.asyncio
async def test_refresh_and_logout_request_validation_is_bounded_and_forbids_extras(
    refresh_client: httpx.AsyncClient,
) -> None:
    for path in ("/api/v1/auth/refresh", "/api/v1/auth/logout"):
        for payload in (
            {},
            {"refresh_token": "short"},
            {"refresh_token": "x" * 513},
            {"refresh_token": "x" * 32, "unexpected": True},
        ):
            response = await refresh_client.post(path, json=payload)
            assert response.status_code == 422
            assert response.json()["error"]["code"] == "validation_error"
            assert "x" * 32 not in response.text


@pytest.mark.asyncio
async def test_concurrent_refresh_serializes_and_replay_revokes_the_descendant(
    refresh_settings: None,
    postgres_database_url: str,
    migrated_database: None,
) -> None:
    engine = create_async_engine(postgres_database_url, pool_pre_ping=True)
    session_maker = async_sessionmaker(engine, expire_on_commit=False, autoflush=False)

    async def _override_get_db_session() -> AsyncGenerator[AsyncSession]:
        async with session_maker() as session:
            yield session

    original_overrides = app.dependency_overrides.copy()
    app.dependency_overrides[get_db_session] = _override_get_db_session
    email = f"concurrent-refresh-{uuid4()}@example.com"
    try:
        async with session_maker() as session:
            user = await UserRepository(session).create_user(
                email=email,
                password_hash=hash_password(_PASSWORD),
                first_name="Concurrent",
                last_name="Refresh",
                is_active=True,
                is_email_verified=True,
            )
            await session.commit()
            user_id = user.id

        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as client:
            login_response = await _login(client, email)
            raw_token = login_response.json()["refresh_token"]
            responses = await asyncio.gather(
                _refresh(client, raw_token),
                _refresh(client, raw_token),
            )

        assert sorted(response.status_code for response in responses) == [200, 401]
        assert next(
            response for response in responses if response.status_code == 401
        ).json() == _INVALID_REFRESH_RESPONSE

        async with session_maker() as session:
            tokens = await _stored_tokens(session, user_id)
            assert len(tokens) == 2
            assert tokens[0].used_at is not None
            assert tokens[0].replaced_by_id == tokens[1].id
            assert all(token.revoked_at is not None for token in tokens)
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(original_overrides)
        async with session_maker() as session:
            await session.execute(update(User).where(User.email == email).values(is_active=False))
            await session.commit()
        await engine.dispose()
