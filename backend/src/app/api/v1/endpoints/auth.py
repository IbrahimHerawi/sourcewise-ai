"""V1 authentication endpoints."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_verified_user
from app.api.schemas.auth import (
    LoginRequest,
    LoginResponse,
    MessageResponse,
    RegisterRequest,
    RegisterResponse,
    ResendVerificationRequest,
    ResendVerificationResponse,
    UserResponse,
    VerifyEmailRequest,
)
from app.core.errors import AppError, ValidationError
from app.core.security import (
    SecurityError,
    create_access_token,
    generate_secure_token,
    hash_password,
    hash_token,
    verify_password,
)
from app.core.settings import get_settings
from app.db.models.auth import User
from app.db.session import get_db_session
from app.repositories.user_repository import DuplicateUserEmailError, UserRepository
from app.services.email import build_email_verification_link, send_registration_verification_email

router = APIRouter()
logger = logging.getLogger(__name__)

_VERIFICATION_TOKEN_RESPONSE_ENVS = {"local", "test", "testing"}
_MIN_PASSWORD_LENGTH = 12
_MAX_PASSWORD_BYTES = 72
_REGISTERED_MESSAGE = "Registration successful. Please verify your email."
_VERIFIED_MESSAGE = "Email verified successfully."
_INVALID_VERIFICATION_TOKEN_MESSAGE = "Verification token is invalid or expired."
_RESEND_VERIFICATION_MESSAGE = (
    "If the account exists and requires verification, a verification email has been sent."
)
_INVALID_CREDENTIALS_MESSAGE = "Invalid email or password."
_DUMMY_PASSWORD_HASH = "$2b$12$KIXx4aS2YFwpnH3fM3kKie1WdB0hRyPbUXxKkakHfHfHJnRGQfdjK"


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
    return app_env.strip().lower() in _VERIFICATION_TOKEN_RESPONSE_ENVS


@router.post("/login", response_model=LoginResponse)
async def login(
    payload: LoginRequest,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> LoginResponse:
    """Authenticate one verified, active user and issue an access token."""
    user = await UserRepository(session).get_user_by_email(payload.email)
    password_hash = user.password_hash if user is not None else _DUMMY_PASSWORD_HASH

    if not verify_password(payload.password, password_hash) or user is None:
        raise AppError(
            _INVALID_CREDENTIALS_MESSAGE,
            code="invalid_credentials",
            status_code=status.HTTP_401_UNAUTHORIZED,
        )

    if not user.is_active:
        raise AppError(
            "User account is inactive.",
            code="account_inactive",
            status_code=status.HTTP_403_FORBIDDEN,
        )

    if not user.is_email_verified:
        raise AppError(
            "User email is not verified.",
            code="email_not_verified",
            status_code=status.HTTP_403_FORBIDDEN,
        )

    try:
        access_token = create_access_token(user.id)
    except SecurityError as exc:
        raise AppError(
            "Login could not be completed.",
            code="internal_server_error",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        ) from exc

    return LoginResponse(
        access_token=access_token,
        user=UserResponse.model_validate(user),
    )


@router.get("/me", response_model=UserResponse)
async def get_me(
    current_user: Annotated[User, Depends(get_current_verified_user)],
) -> UserResponse:
    """Return the API-safe user represented by a valid bearer token."""
    return UserResponse.model_validate(current_user)


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
    except SecurityError as exc:
        raise AppError(
            "Registration could not be completed.",
            code="internal_server_error",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        ) from exc

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
            try:
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

    verification_link = build_email_verification_link(
        raw_token=raw_verification_token,
        settings=settings,
    )
    await send_registration_verification_email(
        to_email=user.email,
        verification_link=verification_link,
        settings=settings,
    )

    verification_token = (
        raw_verification_token if _should_return_verification_token(settings.app_env) else None
    )
    return RegisterResponse(
        user=UserResponse.model_validate(user),
        message=_REGISTERED_MESSAGE,
        verification_token=verification_token,
    )


@router.post("/verify-email", response_model=MessageResponse)
async def verify_email(
    payload: VerifyEmailRequest,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> MessageResponse:
    """Consume a verification token and verify its associated user once."""
    if not payload.token.strip():
        raise AppError(
            _INVALID_VERIFICATION_TOKEN_MESSAGE,
            code="invalid_verification_token",
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    try:
        token_hash = hash_token(payload.token)
    except SecurityError as exc:
        raise AppError(
            "Email verification could not be completed.",
            code="internal_server_error",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        ) from exc

    repository = UserRepository(session)
    async with session.begin():
        verification_token = await repository.consume_valid_email_verification_token(token_hash)
        if verification_token is not None:
            await repository.mark_email_verified(verification_token.user_id)

    if verification_token is None:
        raise AppError(
            _INVALID_VERIFICATION_TOKEN_MESSAGE,
            code="invalid_verification_token",
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    return MessageResponse(message=_VERIFIED_MESSAGE)


@router.post(
    "/resend-verification",
    response_model=ResendVerificationResponse,
    response_model_exclude_none=True,
)
async def resend_verification(
    payload: ResendVerificationRequest,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ResendVerificationResponse:
    """Replace an unverified user's tokens and send a generic resend response."""
    settings = get_settings()
    repository = UserRepository(session)
    raw_verification_token: str | None = None
    user = None

    async with session.begin():
        user = await repository.get_user_by_email(payload.email)
        if user is not None and not user.is_email_verified:
            await repository.invalidate_unused_email_verification_tokens(user.id)
            try:
                raw_verification_token = generate_secure_token()
                verification_token_hash = hash_token(raw_verification_token)
            except SecurityError as exc:
                raise AppError(
                    "Verification email could not be prepared.",
                    code="internal_server_error",
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                ) from exc

            token_expires_at = datetime.now(UTC) + timedelta(
                minutes=settings.email_verification_token_expire_minutes
            )
            await repository.create_email_verification_token(
                user.id,
                verification_token_hash,
                token_expires_at,
            )

    if user is None or raw_verification_token is None:
        return ResendVerificationResponse(message=_RESEND_VERIFICATION_MESSAGE)

    try:
        verification_link = build_email_verification_link(
            raw_token=raw_verification_token,
            settings=settings,
        )
        await send_registration_verification_email(
            to_email=user.email,
            verification_link=verification_link,
            settings=settings,
        )
    except Exception:
        logger.warning(
            "Verification email delivery failed for user_id=%s.",
            user.id,
        )

    verification_token = (
        raw_verification_token if _should_return_verification_token(settings.app_env) else None
    )
    return ResendVerificationResponse(
        message=_RESEND_VERIFICATION_MESSAGE,
        verification_token=verification_token,
    )
