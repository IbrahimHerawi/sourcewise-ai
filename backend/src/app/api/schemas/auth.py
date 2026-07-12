"""Schemas for authentication endpoints."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, StringConstraints, field_validator

NameText = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=100),
]


class RegisterRequest(BaseModel):
    """Request payload for registering a new user account."""

    model_config = ConfigDict(extra="forbid")

    first_name: NameText
    last_name: NameText
    email: EmailStr
    password: str

    @field_validator("email", mode="after")
    @classmethod
    def normalize_email(cls, value: EmailStr) -> str:
        """Normalize email addresses before persistence."""
        return str(value).lower()


class LoginRequest(BaseModel):
    """Credentials for signing in to an existing account."""

    model_config = ConfigDict(extra="forbid")

    email: EmailStr
    password: str

    @field_validator("email", mode="after")
    @classmethod
    def normalize_email(cls, value: EmailStr) -> str:
        """Normalize email addresses before account lookup."""
        return str(value).lower()


class UserResponse(BaseModel):
    """API-safe user response payload."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    first_name: str
    last_name: str
    email: str
    is_email_verified: bool
    is_active: bool
    created_at: datetime


AuthUserResponse = UserResponse


class RegisterResponse(BaseModel):
    """Response payload after successful account registration."""

    user: UserResponse
    message: str
    verification_token: str | None = None


class LoginResponse(BaseModel):
    """Access token and API-safe authenticated user payload."""

    access_token: str
    token_type: Literal["bearer"] = "bearer"
    user: UserResponse


class VerifyEmailRequest(BaseModel):
    """Request payload for consuming an email verification token."""

    model_config = ConfigDict(extra="forbid")

    token: str


class MessageResponse(BaseModel):
    """Response containing a user-safe status message."""

    message: str


class ResendVerificationRequest(BaseModel):
    """Request payload for resending an email verification message."""

    model_config = ConfigDict(extra="forbid")

    email: EmailStr

    @field_validator("email", mode="after")
    @classmethod
    def normalize_email(cls, value: EmailStr) -> str:
        """Normalize email addresses using the registration rules."""
        return str(value).lower()


class ResendVerificationResponse(MessageResponse):
    """Generic resend response with an optional development token."""

    verification_token: str | None = None


class ForgotPasswordRequest(BaseModel):
    """Request payload for starting a password reset."""

    model_config = ConfigDict(extra="forbid")

    email: EmailStr

    @field_validator("email", mode="after")
    @classmethod
    def normalize_email(cls, value: EmailStr) -> str:
        """Normalize email addresses using the registration rules."""
        return str(value).lower()


class ForgotPasswordResponse(MessageResponse):
    """Generic forgot-password response with an optional development token."""

    reset_token: str | None = None


class ResetPasswordRequest(BaseModel):
    """Request payload for completing a password reset."""

    model_config = ConfigDict(extra="forbid")

    token: str
    new_password: str
