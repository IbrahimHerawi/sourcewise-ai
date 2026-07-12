"""Schemas for authentication endpoints."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated
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
