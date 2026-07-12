from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator, Generator
from datetime import UTC, datetime, timedelta

import httpx
import pytest
import pytest_asyncio
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.errors import ExternalServiceError
from app.core.security import hash_token
from app.core.settings import get_settings
from app.db.models.auth import EmailVerificationToken, User
from app.db.session import get_db_session
from app.main import app
from app.repositories.user_repository import UserRepository

_GENERIC_RESEND_RESPONSE = {
    "message": (
        "If the account exists and requires verification, a verification email has been sent."
    )
}
_INVALID_TOKEN_RESPONSE = {
    "error": {
        "code": "invalid_verification_token",
        "message": "Verification token is invalid or expired.",
    }
}


@pytest.fixture
def verification_settings(monkeypatch: pytest.MonkeyPatch) -> Generator[None]:
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("SECRET_KEY", "test-secret-key-with-enough-length")
    monkeypatch.setenv("EMAIL_VERIFICATION_TOKEN_EXPIRE_MINUTES", "60")
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
    verification_settings: None,
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
    is_email_verified: bool = False,
) -> User:
    repository = UserRepository(session)
    user = await repository.create_user(
        email,
        "hashed-password",
        first_name="Source",
        last_name="Wise",
        is_email_verified=is_email_verified,
    )
    await session.commit()
    return user


async def _create_verification_token(
    session: AsyncSession,
    *,
    user: User,
    raw_token: str,
    expires_at: datetime | None = None,
) -> EmailVerificationToken:
    token = await UserRepository(session).create_email_verification_token(
        user.id,
        hash_token(raw_token),
        expires_at or datetime.now(UTC) + timedelta(hours=1),
    )
    await session.commit()
    return token


@pytest.mark.asyncio
async def test_verify_email_marks_user_and_token_used(
    auth_client: httpx.AsyncClient,
    db_session: AsyncSession,
) -> None:
    user = await _create_user(db_session, email="verify-success@example.com")
    token = await _create_verification_token(
        db_session,
        user=user,
        raw_token="valid-verification-token",
    )

    response = await auth_client.post(
        "/api/v1/auth/verify-email",
        json={"token": "valid-verification-token"},
    )

    await db_session.refresh(user)
    await db_session.refresh(token)
    assert response.status_code == 200
    assert response.json() == {"message": "Email verified successfully."}
    assert user.is_email_verified is True
    assert token.used_at is not None


@pytest.mark.asyncio
@pytest.mark.parametrize("raw_token", ["unknown-token", "", "   "])
async def test_verify_email_rejects_invalid_or_empty_token(
    auth_client: httpx.AsyncClient,
    raw_token: str,
) -> None:
    response = await auth_client.post(
        "/api/v1/auth/verify-email",
        json={"token": raw_token},
    )

    assert response.status_code == 400
    assert response.json() == _INVALID_TOKEN_RESPONSE


@pytest.mark.asyncio
async def test_verify_email_rejects_expired_token(
    auth_client: httpx.AsyncClient,
    db_session: AsyncSession,
) -> None:
    user = await _create_user(db_session, email="verify-expired@example.com")
    await _create_verification_token(
        db_session,
        user=user,
        raw_token="expired-verification-token",
        expires_at=datetime.now(UTC) - timedelta(seconds=1),
    )

    response = await auth_client.post(
        "/api/v1/auth/verify-email",
        json={"token": "expired-verification-token"},
    )

    await db_session.refresh(user)
    assert response.status_code == 400
    assert response.json() == _INVALID_TOKEN_RESPONSE
    assert user.is_email_verified is False


@pytest.mark.asyncio
async def test_verify_email_token_cannot_be_reused(
    auth_client: httpx.AsyncClient,
    db_session: AsyncSession,
) -> None:
    user = await _create_user(db_session, email="verify-once@example.com")
    await _create_verification_token(
        db_session,
        user=user,
        raw_token="one-time-verification-token",
    )

    first_response = await auth_client.post(
        "/api/v1/auth/verify-email",
        json={"token": "one-time-verification-token"},
    )
    second_response = await auth_client.post(
        "/api/v1/auth/verify-email",
        json={"token": "one-time-verification-token"},
    )

    assert first_response.status_code == 200
    assert second_response.status_code == 400
    assert second_response.json() == _INVALID_TOKEN_RESPONSE


@pytest.mark.asyncio
async def test_concurrent_verification_attempts_cannot_both_consume_token(
    postgres_database_url: str,
    migrated_database: None,
    verification_settings: None,
) -> None:
    engine = create_async_engine(postgres_database_url, pool_pre_ping=True)
    session_maker = async_sessionmaker(engine, expire_on_commit=False, autoflush=False)
    raw_token = "concurrent-verification-token"

    async with session_maker() as setup_session:
        repository = UserRepository(setup_session)
        user = await repository.create_user(
            "verify-concurrent@example.com",
            "hashed-password",
            first_name="Source",
            last_name="Wise",
        )
        await repository.create_email_verification_token(
            user.id,
            hash_token(raw_token),
            datetime.now(UTC) + timedelta(hours=1),
        )
        await setup_session.commit()
        user_id = user.id

    async def consume_token() -> bool:
        async with session_maker() as session:
            repository = UserRepository(session)
            async with session.begin():
                token = await repository.consume_valid_email_verification_token(
                    hash_token(raw_token)
                )
                if token is None:
                    return False
                await repository.mark_email_verified(token.user_id)
            return True

    try:
        results = await asyncio.gather(consume_token(), consume_token())
        assert sorted(results) == [False, True]
    finally:
        async with session_maker() as cleanup_session:
            await cleanup_session.execute(delete(User).where(User.id == user_id))
            await cleanup_session.commit()
        await engine.dispose()


@pytest.mark.asyncio
async def test_resend_creates_hashed_token_invalidates_previous_and_sends_email(
    auth_client: httpx.AsyncClient,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sent_emails: list[dict[str, object]] = []

    async def fake_send_registration_verification_email(**kwargs: object) -> None:
        sent_emails.append(kwargs)

    monkeypatch.setattr(
        "app.api.v1.endpoints.auth.generate_secure_token",
        lambda: "new-raw-verification-token",
    )
    monkeypatch.setattr(
        "app.api.v1.endpoints.auth.send_registration_verification_email",
        fake_send_registration_verification_email,
    )
    user = await _create_user(db_session, email="resend@example.com")
    previous_token = await _create_verification_token(
        db_session,
        user=user,
        raw_token="previous-raw-verification-token",
    )

    response = await auth_client.post(
        "/api/v1/auth/resend-verification",
        json={"email": "RESEND@Example.COM"},
    )

    await db_session.refresh(previous_token)
    token_rows = list(
        (
            await db_session.scalars(
                select(EmailVerificationToken).where(EmailVerificationToken.user_id == user.id)
            )
        ).all()
    )
    new_token = next(token for token in token_rows if token.id != previous_token.id)
    assert response.status_code == 200
    assert response.json() == {
        **_GENERIC_RESEND_RESPONSE,
        "verification_token": "new-raw-verification-token",
    }
    assert previous_token.used_at is not None
    assert new_token.used_at is None
    assert new_token.token_hash == hash_token("new-raw-verification-token")
    assert new_token.token_hash != "new-raw-verification-token"
    assert len(sent_emails) == 1
    assert sent_emails[0]["to_email"] == "resend@example.com"
    assert "new-raw-verification-token" in str(sent_emails[0]["verification_link"])


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("email", "verified"),
    [
        ("missing-resend@example.com", None),
        ("verified-resend@example.com", True),
    ],
)
async def test_resend_missing_or_verified_user_does_not_create_token_or_send_email(
    auth_client: httpx.AsyncClient,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
    email: str,
    verified: bool | None,
) -> None:
    send_count = 0

    async def fake_send_registration_verification_email(**_: object) -> None:
        nonlocal send_count
        send_count += 1

    monkeypatch.setattr(
        "app.api.v1.endpoints.auth.send_registration_verification_email",
        fake_send_registration_verification_email,
    )
    if verified is not None:
        await _create_user(db_session, email=email, is_email_verified=verified)

    response = await auth_client.post(
        "/api/v1/auth/resend-verification",
        json={"email": email},
    )

    token_count = await db_session.scalar(select(func.count()).select_from(EmailVerificationToken))
    assert response.status_code == 200
    assert response.json() == _GENERIC_RESEND_RESPONSE
    assert token_count == 0
    assert send_count == 0


@pytest.mark.asyncio
async def test_resend_email_failure_returns_generic_response_without_sensitive_logs(
    auth_client: httpx.AsyncClient,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    raw_token = "raw-resend-token-secret"
    api_key = "re-resend-api-key-secret"

    async def fail_send_registration_verification_email(**_: object) -> None:
        raise ExternalServiceError("Email delivery failed.")

    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("SECRET_KEY", "production-secret-key-with-enough-length")
    monkeypatch.setenv("RESEND_API_KEY", api_key)
    monkeypatch.setenv("FRONTEND_BASE_URL", "https://frontend.example.test")
    monkeypatch.setattr("app.api.v1.endpoints.auth.generate_secure_token", lambda: raw_token)
    monkeypatch.setattr(
        "app.api.v1.endpoints.auth.send_registration_verification_email",
        fail_send_registration_verification_email,
    )
    get_settings.cache_clear()
    await _create_user(db_session, email="resend-failure@example.com")
    token_hash = hash_token(raw_token)
    verification_link = f"https://frontend.example.test/verify-email?token={raw_token}"
    caplog.set_level("WARNING")

    response = await auth_client.post(
        "/api/v1/auth/resend-verification",
        json={"email": "resend-failure@example.com"},
    )

    assert response.status_code == 200
    assert response.json() == _GENERIC_RESEND_RESPONSE
    for sensitive_value in [raw_token, token_hash, verification_link, api_key, "hashed-password"]:
        assert sensitive_value not in response.text
        assert sensitive_value not in caplog.text


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
async def test_resend_raw_token_visibility_depends_on_app_env(
    auth_client: httpx.AsyncClient,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
    app_env: str,
    should_return_token: bool,
) -> None:
    async def fake_send_registration_verification_email(**_: object) -> None:
        return None

    monkeypatch.setenv("APP_ENV", app_env)
    monkeypatch.setenv("SECRET_KEY", f"{app_env}-secret-key-with-enough-length")
    if app_env in {"staging", "production"}:
        monkeypatch.setenv("RESEND_API_KEY", f"re-{app_env}-key")
    monkeypatch.setattr(
        "app.api.v1.endpoints.auth.generate_secure_token",
        lambda: f"{app_env}-raw-verification-token",
    )
    monkeypatch.setattr(
        "app.api.v1.endpoints.auth.send_registration_verification_email",
        fake_send_registration_verification_email,
    )
    get_settings.cache_clear()
    await _create_user(db_session, email=f"resend-{app_env}@example.com")

    response = await auth_client.post(
        "/api/v1/auth/resend-verification",
        json={"email": f"resend-{app_env}@example.com"},
    )

    assert response.status_code == 200
    assert response.json()["message"] == _GENERIC_RESEND_RESPONSE["message"]
    assert ("verification_token" in response.json()) is should_return_token


def test_email_verification_routes_exist_only_under_api_v1_auth() -> None:
    paths = {getattr(route, "path", "") for route in app.routes}

    for endpoint in ("verify-email", "resend-verification"):
        assert f"/api/v1/auth/{endpoint}" in paths
        assert f"/api/auth/{endpoint}" not in paths
        assert f"/auth/{endpoint}" not in paths
