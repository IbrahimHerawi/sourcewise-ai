"""V1 authentication endpoints."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas.auth import RegisterRequest, RegisterResponse, UserResponse
from app.core.errors import AppError, ValidationError
from app.core.security import (
    SecurityError,
    generate_secure_token,
    hash_password,
    hash_token,
)
from app.core.settings import get_settings
from app.db.session import get_db_session
from app.repositories.user_repository import DuplicateUserEmailError, UserRepository

router = APIRouter()

_LOCAL_OR_TEST_ENVS = {"local", "test", "testing", "docker"}
_MIN_PASSWORD_LENGTH = 12
_MAX_PASSWORD_BYTES = 72
_REGISTERED_MESSAGE = "Registration successful. Please verify your email."


def _validate_password_strength(password: str) -> None:
    password_bytes = password.encode("utf-8")
    has_lower = any(character.islower() for character in password)
    has_upper = any(character.isupper() for character in password)
    has_digit = any(character.isdigit() for character in password)
    has_symbol = any(not character.isalnum() for character in password)

    if (
        len(password) < _MIN_PASSWORD_LENGTH
        or len(password_bytes) > _MAX_PASSWORD_BYTES
        or not has_lower
        or not has_upper
        or not has_digit
        or not has_symbol
    ):
        raise ValidationError(
            "Password must be 12 to 72 bytes and include uppercase, lowercase, "
            "number, and symbol characters.",
            status_code=status.HTTP_400_BAD_REQUEST,
        )


def _should_return_verification_token(app_env: str) -> bool:
    return app_env.strip().lower() in _LOCAL_OR_TEST_ENVS


@router.post(
    "/register",
    response_model=RegisterResponse,
    response_model_exclude_none=True,
)
async def register(
    payload: RegisterRequest,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> RegisterResponse:
    """Register a user and persist a hashed email verification token."""
    _validate_password_strength(payload.password)

    settings = get_settings()

    try:
        password_hash = hash_password(payload.password)
        raw_verification_token = generate_secure_token()
        verification_token_hash = hash_token(raw_verification_token)
    except SecurityError as exc:
        raise AppError(
            "Registration could not be completed.",
            code="internal_server_error",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        ) from exc

    token_expires_at = datetime.now(UTC) + timedelta(
        minutes=settings.email_verification_token_expire_minutes
    )
    repository = UserRepository(session)

    try:
        async with session.begin():
            user = await repository.create_user(
                email=payload.email,
                password_hash=password_hash,
                first_name=payload.first_name,
                last_name=payload.last_name,
                is_email_verified=False,
                is_active=True,
            )
            await repository.create_email_verification_token(
                user.id,
                verification_token_hash,
                token_expires_at,
            )
    except DuplicateUserEmailError as exc:
        raise AppError(
            "A user with this email already exists.",
            code="conflict",
            status_code=status.HTTP_409_CONFLICT,
        ) from exc

    verification_token = (
        raw_verification_token if _should_return_verification_token(settings.app_env) else None
    )
    return RegisterResponse(
        user=UserResponse.model_validate(user),
        message=_REGISTERED_MESSAGE,
        verification_token=verification_token,
    )
