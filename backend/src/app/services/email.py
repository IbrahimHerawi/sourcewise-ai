"""Email delivery for account and notification flows."""

from __future__ import annotations

import asyncio
import smtplib
import ssl
from dataclasses import dataclass
from email.message import EmailMessage as StdlibEmailMessage
from html import escape
from typing import Any, Protocol
from urllib.parse import quote

import httpx

from app.core.errors import ExternalServiceError
from app.core.settings import Settings, get_settings

RESEND_EMAILS_ENDPOINT = "https://api.resend.com/emails"
REGISTRATION_VERIFICATION_SUBJECT = "Verify your Sourcewise email"

_DISABLED_EMAIL_ENVS = {"test", "testing"}
_SMTP_EMAIL_ENVS = {"local", "docker"}
_RESEND_EMAIL_ENVS = {"staging", "production"}


@dataclass(frozen=True, slots=True)
class OutboundEmail:
    """Provider-neutral email payload."""

    from_email: str
    to_email: str
    subject: str
    text: str
    html: str


class EmailClient(Protocol):
    """Provider-neutral async email client interface."""

    async def send(self, email: OutboundEmail) -> None:
        """Send one email message."""


class ResendEmailClient:
    """Email client backed by the Resend HTTP API."""

    def __init__(
        self,
        *,
        api_key: str,
        endpoint: str = RESEND_EMAILS_ENDPOINT,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._api_key = api_key
        self._endpoint = endpoint
        self._http_client = http_client

    async def send(self, email: OutboundEmail) -> None:
        """Send an email through Resend."""
        payload = {
            "from": email.from_email,
            "to": email.to_email,
            "subject": email.subject,
            "text": email.text,
            "html": email.html,
        }
        headers = {"Authorization": f"Bearer {self._api_key}"}

        try:
            if self._http_client is not None:
                response = await self._http_client.post(
                    self._endpoint,
                    headers=headers,
                    json=payload,
                )
            else:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    response = await client.post(
                        self._endpoint,
                        headers=headers,
                        json=payload,
                    )
        except httpx.HTTPError as exc:
            raise ExternalServiceError("Email delivery failed.") from exc

        if response.is_error:
            raise ExternalServiceError(
                "Email delivery failed.",
                details={"provider": "resend", "status_code": response.status_code},
            )


class SmtpEmailClient:
    """Email client backed by standard SMTP."""

    def __init__(
        self,
        *,
        host: str,
        port: int,
        use_tls: bool = False,
        username: str | None = None,
        password: str | None = None,
        smtp_factory: Any = smtplib.SMTP,
    ) -> None:
        self._host = host
        self._port = port
        self._use_tls = use_tls
        self._username = username
        self._password = password
        self._smtp_factory = smtp_factory

    async def send(self, email: OutboundEmail) -> None:
        """Send an email through SMTP without blocking the event loop."""
        await asyncio.to_thread(self._send_sync, email)

    def _send_sync(self, email: OutboundEmail) -> None:
        message = StdlibEmailMessage()
        message["From"] = email.from_email
        message["To"] = email.to_email
        message["Subject"] = email.subject
        message.set_content(email.text)
        message.add_alternative(email.html, subtype="html")

        try:
            with self._smtp_factory(self._host, self._port, timeout=10) as server:
                if self._use_tls:
                    server.starttls(context=ssl.create_default_context())
                if self._username:
                    server.login(self._username, self._password or "")
                server.send_message(message)
        except (OSError, smtplib.SMTPException) as exc:
            raise ExternalServiceError("Email delivery failed.") from exc


class DisabledEmailClient:
    """No-op email client used in tests."""

    async def send(self, email: OutboundEmail) -> None:
        """Do not send email."""


def get_email_client(settings: Settings | None = None) -> EmailClient:
    """Build an email client for the active APP_ENV."""
    resolved_settings = settings or get_settings()
    app_env = resolved_settings.app_env.strip().lower()

    if app_env in _DISABLED_EMAIL_ENVS:
        return DisabledEmailClient()

    if app_env in _SMTP_EMAIL_ENVS:
        smtp_password = (
            resolved_settings.smtp_password.get_secret_value()
            if resolved_settings.smtp_password is not None
            else None
        )
        return SmtpEmailClient(
            host=resolved_settings.smtp_host,
            port=resolved_settings.smtp_port,
            use_tls=resolved_settings.smtp_use_tls,
            username=resolved_settings.smtp_username,
            password=smtp_password,
        )

    if app_env in _RESEND_EMAIL_ENVS:
        if resolved_settings.resend_api_key is None:
            raise ValueError("RESEND_API_KEY must be configured for Resend email delivery.")
        return ResendEmailClient(api_key=resolved_settings.resend_api_key.get_secret_value())

    raise ValueError(f"Unsupported APP_ENV for email delivery: {resolved_settings.app_env}")


def build_email_verification_link(
    *,
    raw_token: str,
    settings: Settings | None = None,
) -> str:
    """Build the frontend email verification URL for a raw one-time token."""
    resolved_settings = settings or get_settings()
    base_url = resolved_settings.frontend_base_url.rstrip("/")
    token = quote(raw_token, safe="")
    return f"{base_url}/verify-email?token={token}"


def build_registration_verification_email(
    *,
    to_email: str,
    verification_link: str,
    settings: Settings | None = None,
) -> OutboundEmail:
    """Build the registration verification email message."""
    resolved_settings = settings or get_settings()
    escaped_link = escape(verification_link, quote=True)
    text = (
        "Welcome to Sourcewise.\n\n"
        "Verify your email address by opening this link:\n"
        f"{verification_link}\n\n"
        "If you did not create a Sourcewise account, you can ignore this email."
    )
    html = (
        "<p>Welcome to Sourcewise.</p>"
        "<p>Verify your email address by opening this link:</p>"
        f'<p><a href="{escaped_link}">{escaped_link}</a></p>'
        "<p>If you did not create a Sourcewise account, you can ignore this email.</p>"
    )
    return OutboundEmail(
        from_email=resolved_settings.email_from,
        to_email=to_email,
        subject=REGISTRATION_VERIFICATION_SUBJECT,
        text=text,
        html=html,
    )


async def send_registration_verification_email(
    *,
    to_email: str,
    verification_link: str,
    settings: Settings | None = None,
    client: EmailClient | None = None,
) -> None:
    """Send the registration verification email through the configured provider."""
    resolved_settings = settings or get_settings()
    resolved_client = client or get_email_client(resolved_settings)
    email = build_registration_verification_email(
        to_email=to_email,
        verification_link=verification_link,
        settings=resolved_settings,
    )
    await resolved_client.send(email)


__all__ = [
    "DisabledEmailClient",
    "EmailClient",
    "OutboundEmail",
    "REGISTRATION_VERIFICATION_SUBJECT",
    "ResendEmailClient",
    "SmtpEmailClient",
    "build_email_verification_link",
    "build_registration_verification_email",
    "get_email_client",
    "send_registration_verification_email",
]
