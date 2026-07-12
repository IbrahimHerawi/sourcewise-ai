from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator, Generator
from datetime import UTC, datetime, timedelta

import httpx
import pytest
import pytest_asyncio
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.errors import ExternalServiceError
from app.core.security import hash_password, hash_token, verify_password
from app.core.settings import get_settings
from app.db.models.auth import PasswordResetToken, User
from app.db.session import get_db_session
from app.main import app
from app.repositories.user_repository import UserRepository

_OLD_PASSWORD = "OldStrongPassword123!"
_NEW_PASSWORD = "NewStrongPassword123!"
_GENERIC_RESPONSE = {
    "message": "If an eligible account exists, password reset instructions have been sent."
}
_INVALID_TOKEN_RESPONSE = {
    "error": {
        "code": "invalid_password_reset_token",
        "message": "Password reset token is invalid or expired.",
    }
}


@pytest.fixture
def password_reset_settings(monkeypatch: pytest.MonkeyPatch) -> Generator[None]:
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("SECRET_KEY", "test-secret-key-with-enough-length")
    monkeypatch.setenv("PASSWORD_RESET_TOKEN_EXPIRE_MINUTES", "60")
    monkeypatch.setenv("FRONTEND_BASE_URL", "https://frontend.example.test")
    for env_var in [
        "RESEND_API_KEY",
        "RESEND_API_KEY_FILE",
        "SMTP_PASSWORD",
        "SMTP_PASSWORD_FILE",
    ]:
        monkeypatch.delenv(env_var, raising=False)
    get_settings.cache_clear()

    yield

    get_settings.cache_clear()


@pytest_asyncio.fixture
async def auth_client(
    password_reset_settings: None,
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
    is_active: bool = True,
    is_email_verified: bool = True,
) -> User:
    user = await UserRepository(session).create_user(
        email=email,
        password_hash=hash_password(_OLD_PASSWORD),
        first_name="Source",
        last_name="Wise",
        is_active=is_active,
        is_email_verified=is_email_verified,
    )
    await session.commit()
    return user


async def _create_reset_token(
    session: AsyncSession,
    *,
    user: User,
    raw_token: str,
    expires_at: datetime | None = None,
) -> PasswordResetToken:
    token = await UserRepository(session).create_password_reset_token(
        user.id,
        hash_token(raw_token),
        expires_at or datetime.now(UTC) + timedelta(hours=1),
    )
    await session.commit()
    return token


@pytest.mark.asyncio
async def test_forgot_password_creates_only_hashed_token_invalidates_previous_and_sends(
    auth_client: httpx.AsyncClient,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sent_emails: list[dict[str, object]] = []

    async def fake_send_password_reset_email(**kwargs: object) -> None:
        sent_emails.append(kwargs)

    user = await _create_user(db_session, email="eligible-reset@example.com")
    previous_token = await _create_reset_token(
        db_session,
        user=user,
        raw_token="previous-raw-reset-token",
    )
    monkeypatch.setattr(
        "app.api.v1.endpoints.auth.generate_secure_token",
        lambda: "new-raw-reset-token",
    )
    monkeypatch.setattr(
        "app.api.v1.endpoints.auth.send_password_reset_email",
        fake_send_password_reset_email,
    )

    response = await auth_client.post(
        "/api/v1/auth/forgot-password",
        json={"email": "ELIGIBLE-RESET@EXAMPLE.COM"},
    )

    await db_session.refresh(previous_token)
    tokens = list(
        (
            await db_session.scalars(
                select(PasswordResetToken).where(PasswordResetToken.user_id == user.id)
            )
        ).all()
    )
    new_token = next(token for token in tokens if token.id != previous_token.id)
    assert response.status_code == 200
    assert response.json() == {**_GENERIC_RESPONSE, "reset_token": "new-raw-reset-token"}
    assert previous_token.used_at is not None
    assert new_token.used_at is None
    assert new_token.token_hash == hash_token("new-raw-reset-token")
    assert new_token.token_hash != "new-raw-reset-token"
    assert len(sent_emails) == 1
    assert sent_emails[0]["to_email"] == user.email
    assert sent_emails[0]["reset_link"] == (
        "https://frontend.example.test/reset-password?token=new-raw-reset-token"
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("email", "is_active", "is_email_verified"),
    [
        ("missing-reset@example.com", None, None),
        ("inactive-reset@example.com", False, True),
        ("unverified-reset@example.com", True, False),
    ],
)
async def test_forgot_password_ineligible_accounts_do_not_create_token_or_send(
    auth_client: httpx.AsyncClient,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
    email: str,
    is_active: bool | None,
    is_email_verified: bool | None,
) -> None:
    send_count = 0

    async def fake_send_password_reset_email(**_: object) -> None:
        nonlocal send_count
        send_count += 1

    monkeypatch.setattr(
        "app.api.v1.endpoints.auth.send_password_reset_email",
        fake_send_password_reset_email,
    )
    if is_active is not None and is_email_verified is not None:
        await _create_user(
            db_session,
            email=email,
            is_active=is_active,
            is_email_verified=is_email_verified,
        )

    response = await auth_client.post(
        "/api/v1/auth/forgot-password",
        json={"email": email},
    )

    token_count = await db_session.scalar(select(func.count()).select_from(PasswordResetToken))
    assert response.status_code == 200
    assert response.json() == _GENERIC_RESPONSE
    assert token_count == 0
    assert send_count == 0


@pytest.mark.asyncio
async def test_forgot_password_email_failure_is_concealed_and_safely_logged(
    auth_client: httpx.AsyncClient,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    raw_token = "raw-reset-token-secret"
    api_key = "re-reset-api-key-secret"
    logged_calls: list[tuple[object, ...]] = []

    async def fail_send_password_reset_email(**_: object) -> None:
        raise ExternalServiceError("Email delivery failed.")

    def record_warning(*args: object, **_: object) -> None:
        logged_calls.append(args)

    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("SECRET_KEY", "production-secret-key-with-enough-length")
    monkeypatch.setenv("RESEND_API_KEY", api_key)
    monkeypatch.setattr("app.api.v1.endpoints.auth.generate_secure_token", lambda: raw_token)
    monkeypatch.setattr(
        "app.api.v1.endpoints.auth.send_password_reset_email",
        fail_send_password_reset_email,
    )
    monkeypatch.setattr("app.api.v1.endpoints.auth.logger.warning", record_warning)
    get_settings.cache_clear()
    user = await _create_user(db_session, email="delivery-failure-reset@example.com")
    token_hash = hash_token(raw_token)
    reset_link = f"https://frontend.example.test/reset-password?token={raw_token}"
    response = await auth_client.post(
        "/api/v1/auth/forgot-password",
        json={"email": user.email},
    )

    assert response.status_code == 200
    assert response.json() == _GENERIC_RESPONSE
    assert logged_calls == [("Password reset email delivery failed for user_id=%s.", user.id)]
    logged_text = repr(logged_calls)
    for sensitive_value in [raw_token, token_hash, reset_link, api_key, _OLD_PASSWORD]:
        assert sensitive_value not in response.text
        assert sensitive_value not in logged_text


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("app_env", "should_return_token"),
    [
        ("local", True),
        ("test", True),
        ("testing", True),
        ("docker", False),
        ("staging", False),
        ("production", False),
    ],
)
async def test_forgot_password_token_visibility_depends_on_environment(
    auth_client: httpx.AsyncClient,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
    app_env: str,
    should_return_token: bool,
) -> None:
    async def fake_send_password_reset_email(**_: object) -> None:
        return None

    monkeypatch.setenv("APP_ENV", app_env)
    monkeypatch.setenv("SECRET_KEY", f"{app_env}-secret-key-with-enough-length")
    if app_env in {"staging", "production"}:
        monkeypatch.setenv("RESEND_API_KEY", f"re-{app_env}-key")
    monkeypatch.setattr(
        "app.api.v1.endpoints.auth.generate_secure_token",
        lambda: f"{app_env}-raw-reset-token",
    )
    monkeypatch.setattr(
        "app.api.v1.endpoints.auth.send_password_reset_email",
        fake_send_password_reset_email,
    )
    get_settings.cache_clear()
    email = f"visibility-{app_env}@example.com"
    await _create_user(db_session, email=email)

    response = await auth_client.post(
        "/api/v1/auth/forgot-password",
        json={"email": email},
    )

    assert response.status_code == 200
    assert response.json()["message"] == _GENERIC_RESPONSE["message"]
    assert ("reset_token" in response.json()) is should_return_token


@pytest.mark.asyncio
async def test_reset_password_changes_hash_updates_login_and_invalidates_other_tokens(
    auth_client: httpx.AsyncClient,
    db_session: AsyncSession,
) -> None:
    user = await _create_user(db_session, email="successful-reset@example.com")
    original_password_hash = user.password_hash
    used_token = await _create_reset_token(
        db_session,
        user=user,
        raw_token="successful-raw-reset-token",
    )
    other_token = await _create_reset_token(
        db_session,
        user=user,
        raw_token="other-raw-reset-token",
    )

    response = await auth_client.post(
        "/api/v1/auth/reset-password",
        json={"token": "successful-raw-reset-token", "new_password": _NEW_PASSWORD},
    )

    reuse_response = await auth_client.post(
        "/api/v1/auth/reset-password",
        json={"token": "successful-raw-reset-token", "new_password": _OLD_PASSWORD},
    )

    await db_session.refresh(user)
    await db_session.refresh(used_token)
    await db_session.refresh(other_token)
    old_login = await auth_client.post(
        "/api/v1/auth/login",
        json={"email": user.email, "password": _OLD_PASSWORD},
    )
    new_login = await auth_client.post(
        "/api/v1/auth/login",
        json={"email": user.email, "password": _NEW_PASSWORD},
    )

    assert response.status_code == 200
    assert response.json() == {"message": "Password reset successfully."}
    assert user.password_hash != original_password_hash
    assert verify_password(_NEW_PASSWORD, user.password_hash)
    assert used_token.used_at is not None
    assert other_token.used_at is not None
    assert old_login.status_code == 401
    assert new_login.status_code == 200
    assert reuse_response.status_code == 400
    assert reuse_response.json() == _INVALID_TOKEN_RESPONSE


@pytest.mark.asyncio
async def test_reset_password_rejects_weak_password_without_consuming_token(
    auth_client: httpx.AsyncClient,
    db_session: AsyncSession,
) -> None:
    user = await _create_user(db_session, email="weak-password-reset@example.com")
    token = await _create_reset_token(
        db_session,
        user=user,
        raw_token="weak-password-raw-token",
    )

    response = await auth_client.post(
        "/api/v1/auth/reset-password",
        json={"token": "weak-password-raw-token", "new_password": "too-weak"},
    )

    await db_session.refresh(token)
    await db_session.refresh(user)
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "validation_error"
    assert token.used_at is None
    assert verify_password(_OLD_PASSWORD, user.password_hash)


@pytest.mark.asyncio
@pytest.mark.parametrize("token_state", ["invalid", "expired", "used", "empty", "whitespace"])
async def test_reset_password_uses_same_error_for_unusable_tokens(
    auth_client: httpx.AsyncClient,
    db_session: AsyncSession,
    token_state: str,
) -> None:
    raw_token = f"{token_state}-raw-reset-token"
    request_token = raw_token
    if token_state in {"expired", "used"}:
        user = await _create_user(db_session, email=f"{token_state}-reset@example.com")
        token = await _create_reset_token(
            db_session,
            user=user,
            raw_token=raw_token,
            expires_at=(
                datetime.now(UTC) - timedelta(seconds=1) if token_state == "expired" else None
            ),
        )
        if token_state == "used":
            await UserRepository(db_session).mark_password_reset_token_used(token.id)
            await db_session.commit()
    elif token_state == "empty":
        request_token = ""
    elif token_state == "whitespace":
        request_token = "   "

    response = await auth_client.post(
        "/api/v1/auth/reset-password",
        json={"token": request_token, "new_password": _NEW_PASSWORD},
    )

    assert response.status_code == 400
    assert response.json() == _INVALID_TOKEN_RESPONSE


@pytest.mark.asyncio
async def test_concurrent_reset_attempts_cannot_both_succeed(
    postgres_database_url: str,
    migrated_database: None,
    password_reset_settings: None,
) -> None:
    engine = create_async_engine(postgres_database_url, pool_pre_ping=True)
    session_maker = async_sessionmaker(engine, expire_on_commit=False, autoflush=False)
    raw_token = "concurrent-password-reset-token"

    async with session_maker() as setup_session:
        repository = UserRepository(setup_session)
        user = await repository.create_user(
            "concurrent-password-reset@example.com",
            hash_password(_OLD_PASSWORD),
            first_name="Source",
            last_name="Wise",
            is_email_verified=True,
        )
        await repository.create_password_reset_token(
            user.id,
            hash_token(raw_token),
            datetime.now(UTC) + timedelta(hours=1),
        )
        await setup_session.commit()
        user_id = user.id

    async def _override_get_db_session() -> AsyncGenerator[AsyncSession]:
        async with session_maker() as session:
            yield session

    original_overrides = app.dependency_overrides.copy()
    app.dependency_overrides[get_db_session] = _override_get_db_session
    transport = httpx.ASGITransport(app=app)

    async def attempt_reset() -> httpx.Response:
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            return await client.post(
                "/api/v1/auth/reset-password",
                json={"token": raw_token, "new_password": _NEW_PASSWORD},
            )

    try:
        responses = await asyncio.gather(attempt_reset(), attempt_reset())
        assert sorted(response.status_code for response in responses) == [200, 400]
        failed_response = next(response for response in responses if response.status_code == 400)
        assert failed_response.json() == _INVALID_TOKEN_RESPONSE
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(original_overrides)
        async with session_maker() as cleanup_session:
            await cleanup_session.execute(delete(User).where(User.id == user_id))
            await cleanup_session.commit()
        await engine.dispose()


def test_password_reset_routes_exist_only_under_api_v1_auth() -> None:
    paths = {getattr(route, "path", "") for route in app.routes}

    for endpoint in ("forgot-password", "reset-password"):
        assert f"/api/v1/auth/{endpoint}" in paths
        assert f"/api/auth/{endpoint}" not in paths
        assert f"/auth/{endpoint}" not in paths
