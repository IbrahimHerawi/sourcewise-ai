from __future__ import annotations

from collections.abc import AsyncGenerator, Generator
from datetime import UTC, datetime
from urllib.parse import parse_qs, urlparse
from uuid import UUID

import httpx
import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ExternalServiceError
from app.core.security import hash_token, verify_password
from app.core.settings import get_settings
from app.db.models.auth import EmailVerificationToken, User
from app.db.session import get_db_session
from app.main import app
from app.repositories.user_repository import UserRepository


@pytest.fixture
def register_settings(monkeypatch: pytest.MonkeyPatch) -> Generator[None]:
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
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sent_emails: list[dict[str, object]] = []

    async def fake_send_registration_verification_email(**kwargs: object) -> None:
        sent_emails.append(kwargs)

    monkeypatch.setattr(
        "app.api.v1.endpoints.auth.send_registration_verification_email",
        fake_send_registration_verification_email,
    )

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
    assert len(sent_emails) == 1


@pytest.mark.asyncio
async def test_register_sends_email_with_raw_token_only_inside_verification_link(
    auth_client: httpx.AsyncClient,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sent_emails: list[dict[str, object]] = []

    async def fake_send_registration_verification_email(**kwargs: object) -> None:
        sent_emails.append(kwargs)

    monkeypatch.setenv("APP_ENV", "docker")
    monkeypatch.setenv("SECRET_KEY", "docker-secret-key-with-enough-length")
    monkeypatch.setenv("FRONTEND_BASE_URL", "https://frontend.example.test")
    monkeypatch.setattr(
        "app.api.v1.endpoints.auth.send_registration_verification_email",
        fake_send_registration_verification_email,
    )
    get_settings.cache_clear()

    response = await _register(
        auth_client,
        email="email-send@example.com",
    )

    assert response.status_code == 200
    assert "verification_token" not in response.json()
    assert len(sent_emails) == 1
    sent_email = sent_emails[0]
    assert sent_email["to_email"] == "email-send@example.com"

    verification_link = str(sent_email["verification_link"])
    parsed_link = urlparse(verification_link)
    raw_token = parse_qs(parsed_link.query)["token"][0]
    assert verification_link.startswith("https://frontend.example.test/verify-email?token=")
    assert raw_token
    assert raw_token not in response.text

    user = await _get_user(db_session, "email-send@example.com")
    assert user is not None
    token_row = await db_session.scalar(
        select(EmailVerificationToken).where(EmailVerificationToken.user_id == user.id)
    )
    assert token_row is not None
    assert token_row.token_hash == hash_token(raw_token)
    assert token_row.token_hash != raw_token


@pytest.mark.asyncio
@pytest.mark.parametrize("app_env", ["docker", "staging", "production"])
async def test_register_omits_verification_token_in_deployed_envs(
    auth_client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
    app_env: str,
) -> None:
    async def fake_send_registration_verification_email(**_: object) -> None:
        return None

    monkeypatch.setenv("APP_ENV", app_env)
    monkeypatch.setenv("SECRET_KEY", f"{app_env}-secret-key-with-enough-length")
    if app_env in {"staging", "production"}:
        monkeypatch.setenv("RESEND_API_KEY", f"re-{app_env}-key")
    monkeypatch.setattr(
        "app.api.v1.endpoints.auth.send_registration_verification_email",
        fake_send_registration_verification_email,
    )
    get_settings.cache_clear()

    response = await _register(
        auth_client,
        email=f"{app_env}-token@example.com",
    )

    assert response.status_code == 200
    assert "verification_token" not in response.json()


@pytest.mark.asyncio
async def test_register_email_failure_persists_user_and_resend_replaces_token(
    auth_client: httpx.AsyncClient,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    initial_token = "initial-raw-token-secret"
    replacement_token = "replacement-raw-token-secret"
    api_key = "re-api-key-secret"
    generated_tokens = iter([initial_token, replacement_token])
    send_attempts: list[dict[str, object]] = []
    delivery_transaction_states: list[bool] = []
    logged_calls: list[tuple[object, ...]] = []

    async def flaky_send_registration_verification_email(**kwargs: object) -> None:
        send_attempts.append(kwargs)
        delivery_transaction_states.append(db_session.in_transaction())
        if len(send_attempts) == 1:
            raise ExternalServiceError("Email delivery failed.")

    def record_warning(*args: object, **_: object) -> None:
        logged_calls.append(args)

    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("SECRET_KEY", "production-secret-key-with-enough-length")
    monkeypatch.setenv("RESEND_API_KEY", api_key)
    monkeypatch.setenv("FRONTEND_BASE_URL", "https://frontend.example.test")
    monkeypatch.setattr(
        "app.api.v1.endpoints.auth.generate_secure_token",
        lambda: next(generated_tokens),
    )
    monkeypatch.setattr(
        "app.api.v1.endpoints.auth.send_registration_verification_email",
        flaky_send_registration_verification_email,
    )
    monkeypatch.setattr("app.api.v1.endpoints.auth.logger.warning", record_warning)
    get_settings.cache_clear()

    registration_response = await _register(
        auth_client,
        email="email-failure@example.com",
        password="StrongPassword123!",
    )
    user_id = UUID(registration_response.json()["user"]["id"])

    assert registration_response.status_code == 200
    assert registration_response.json()["message"] == (
        "Registration successful. Please verify your email."
    )
    assert "verification_token" not in registration_response.json()
    assert delivery_transaction_states == [False]
    assert logged_calls == [
        (
            "Registration verification email delivery failed for user_id=%s.",
            user_id,
        )
    ]

    resend_response = await auth_client.post(
        "/api/v1/auth/resend-verification",
        json={"email": "EMAIL-FAILURE@example.com"},
    )

    assert resend_response.status_code == 200
    assert resend_response.json() == {
        "message": (
            "If the account exists and requires verification, a verification email has been sent."
        )
    }
    assert len(send_attempts) == 2
    assert delivery_transaction_states == [False, False]
    replacement_link = str(send_attempts[1]["verification_link"])
    delivered_token = parse_qs(urlparse(replacement_link).query)["token"][0]
    assert delivered_token == replacement_token

    verification_response = await auth_client.post(
        "/api/v1/auth/verify-email",
        json={"token": replacement_token},
    )

    assert verification_response.status_code == 200
    assert verification_response.json() == {"message": "Email verified successfully."}
    users = list(
        (
            await db_session.scalars(select(User).where(User.email == "email-failure@example.com"))
        ).all()
    )
    assert len(users) == 1
    user = users[0]
    assert user.id == user_id
    assert user.is_email_verified is True

    token_rows = list(
        (
            await db_session.scalars(
                select(EmailVerificationToken).where(EmailVerificationToken.user_id == user.id)
            )
        ).all()
    )
    initial_row = next(row for row in token_rows if row.token_hash == hash_token(initial_token))
    replacement_row = next(
        row for row in token_rows if row.token_hash == hash_token(replacement_token)
    )
    assert len(token_rows) == 2
    assert initial_row.used_at is not None
    assert replacement_row.used_at is not None

    await db_session.commit()
    duplicate_response = await _register(
        auth_client,
        email="EMAIL-FAILURE@example.com",
    )
    assert duplicate_response.status_code == 409
    assert len(send_attempts) == 2

    logged_text = repr(logged_calls)
    for sensitive_value in [
        initial_token,
        replacement_token,
        hash_token(initial_token),
        hash_token(replacement_token),
        "StrongPassword123!",
        api_key,
    ]:
        assert sensitive_value not in registration_response.text
        assert sensitive_value not in resend_response.text
        assert sensitive_value not in logged_text


def test_auth_register_route_exists_only_under_api_v1_auth() -> None:
    paths = {getattr(route, "path", "") for route in app.routes}

    assert "/api/v1/auth/register" in paths
    assert "/api/auth/register" not in paths
    assert "/auth/register" not in paths
