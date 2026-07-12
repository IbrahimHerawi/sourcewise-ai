from __future__ import annotations

import json
import ssl
from email.message import EmailMessage
from pathlib import Path
from typing import Any

import httpx
import pytest

from app.core.errors import ExternalServiceError
from app.core.settings import Settings
from app.services.email import (
    REGISTRATION_VERIFICATION_SUBJECT,
    DisabledEmailClient,
    OutboundEmail,
    ResendEmailClient,
    SmtpEmailClient,
    build_email_verification_link,
    build_registration_verification_email,
    get_email_client,
)


@pytest.fixture(autouse=True)
def clear_email_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for env_var in [
        "RESEND_API_KEY",
        "RESEND_API_KEY_FILE",
        "SMTP_PASSWORD",
        "SMTP_PASSWORD_FILE",
    ]:
        monkeypatch.delenv(env_var, raising=False)


def _email_payload(**overrides: str) -> OutboundEmail:
    payload = {
        "from_email": "Sourcewise <no-reply@notifications.ibrahimherawi.com>",
        "to_email": "user@example.com",
        "subject": REGISTRATION_VERIFICATION_SUBJECT,
        "text": "Verify at http://localhost:3000/verify-email?token=raw-token",
        "html": '<a href="http://localhost:3000/verify-email?token=raw-token">Verify</a>',
    }
    payload.update(overrides)
    return OutboundEmail(**payload)


@pytest.mark.parametrize("app_env", ["test", "testing"])
def test_test_env_selects_disabled_email_client(app_env: str) -> None:
    settings = Settings(app_env=app_env, smtp_host="", _env_file=None)

    assert isinstance(get_email_client(settings), DisabledEmailClient)


@pytest.mark.parametrize("app_env", ["local", "docker"])
def test_local_and_docker_env_select_smtp_client(app_env: str) -> None:
    kwargs: dict[str, object] = {"app_env": app_env, "_env_file": None}
    if app_env == "docker":
        kwargs["secret_key"] = "s" * 40
    settings = Settings(**kwargs)

    assert isinstance(get_email_client(settings), SmtpEmailClient)


@pytest.mark.parametrize("app_env", ["staging", "production"])
def test_staging_and_production_env_select_resend_client(app_env: str) -> None:
    settings = Settings(
        app_env=app_env,
        secret_key="s" * 40,
        resend_api_key="re-api-key",
        _env_file=None,
    )

    assert isinstance(get_email_client(settings), ResendEmailClient)


@pytest.mark.asyncio
async def test_resend_client_sends_expected_payload_and_authorization_header() -> None:
    captured_requests: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        captured_requests.append(request)
        return httpx.Response(200, json={"id": "email-id"})

    http_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    client = ResendEmailClient(api_key="re-secret", http_client=http_client)
    email = _email_payload()

    try:
        await client.send(email)
    finally:
        await http_client.aclose()

    assert len(captured_requests) == 1
    request = captured_requests[0]
    assert str(request.url) == "https://api.resend.com/emails"
    assert request.headers["Authorization"] == "Bearer re-secret"
    assert json.loads(request.content) == {
        "from": "Sourcewise <no-reply@notifications.ibrahimherawi.com>",
        "to": "user@example.com",
        "subject": REGISTRATION_VERIFICATION_SUBJECT,
        "text": "Verify at http://localhost:3000/verify-email?token=raw-token",
        "html": '<a href="http://localhost:3000/verify-email?token=raw-token">Verify</a>',
    }


@pytest.mark.asyncio
async def test_resend_client_failures_raise_clean_external_service_error() -> None:
    async def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"error": "raw-token-secret"})

    http_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    client = ResendEmailClient(api_key="re-secret", http_client=http_client)

    try:
        with pytest.raises(ExternalServiceError) as exc_info:
            await client.send(_email_payload(text="raw-token-secret", html="raw-token-secret"))
    finally:
        await http_client.aclose()

    assert exc_info.value.message == "Email delivery failed."
    assert "raw-token-secret" not in str(exc_info.value)
    assert exc_info.value.details == {"provider": "resend", "status_code": 500}


@pytest.mark.asyncio
async def test_smtp_client_sends_valid_email_message_to_mailpit_settings() -> None:
    sent_messages: list[dict[str, Any]] = []

    class FakeSmtp:
        def __init__(self, host: str, port: int, *, timeout: int) -> None:
            self._call = {"host": host, "port": port, "timeout": timeout}
            sent_messages.append(self._call)

        def __enter__(self) -> FakeSmtp:
            return self

        def __exit__(self, *_: object) -> None:
            return None

        def starttls(self, *, context: ssl.SSLContext) -> None:
            self._call["tls"] = isinstance(context, ssl.SSLContext)

        def login(self, username: str, password: str) -> None:
            self._call["login"] = (username, password)

        def send_message(self, message: EmailMessage) -> None:
            self._call["message"] = message

    settings = Settings(app_env="local", _env_file=None)
    client = SmtpEmailClient(
        host=settings.smtp_host,
        port=settings.smtp_port,
        use_tls=settings.smtp_use_tls,
        smtp_factory=FakeSmtp,
    )
    email = _email_payload()

    await client.send(email)

    assert len(sent_messages) == 1
    sent = sent_messages[0]
    assert sent["host"] == "mailpit"
    assert sent["port"] == 1025
    assert sent["timeout"] == 10
    assert "tls" not in sent
    assert "login" not in sent
    message = sent["message"]
    assert message["From"] == "Sourcewise <no-reply@notifications.ibrahimherawi.com>"
    assert message["To"] == "user@example.com"
    assert message["Subject"] == REGISTRATION_VERIFICATION_SUBJECT
    assert message.get_body(("plain",)) is not None
    assert message.get_body(("html",)) is not None
    assert "http://localhost:3000/verify-email?token=raw-token" in (
        message.get_body(("plain",)).get_content()
    )


@pytest.mark.asyncio
async def test_disabled_client_does_not_send() -> None:
    await DisabledEmailClient().send(_email_payload())


def test_build_registration_verification_email_uses_configured_sender_and_frontend_url(
    tmp_path: Path,
) -> None:
    key_file = tmp_path / "resend_api_key.txt"
    key_file.write_text("re-api-key", encoding="utf-8")
    settings = Settings(
        app_env="production",
        secret_key="s" * 40,
        resend_api_key_file=str(key_file),
        frontend_base_url="https://sourcewise.ibrahimherawi.com",
        _env_file=None,
    )
    verification_link = build_email_verification_link(raw_token="raw token", settings=settings)

    email = build_registration_verification_email(
        to_email="user@example.com",
        verification_link=verification_link,
        settings=settings,
    )

    assert (
        verification_link == "https://sourcewise.ibrahimherawi.com/verify-email?token=raw%20token"
    )
    assert email.from_email == "Sourcewise <no-reply@notifications.ibrahimherawi.com>"
    assert email.to_email == "user@example.com"
    assert email.subject == REGISTRATION_VERIFICATION_SUBJECT
    assert verification_link in email.text
    assert verification_link in email.html
