"""Repository for user accounts and auth token persistence."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.db.models.auth import EmailVerificationToken, PasswordResetToken, User


class DuplicateUserEmailError(ValueError):
    """Raised when creating a user with an email that already exists."""

    def __init__(self, email: str) -> None:
        super().__init__("A user with this email already exists.")
        self.email = email


class UserRepository:
    """Data access methods for users and authentication tokens."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_user_by_id(self, user_id: uuid.UUID) -> User | None:
        """Get one user by primary key."""
        return await self._session.get(User, user_id)

    async def get_user_by_email(self, email: str) -> User | None:
        """Get one user by email address."""
        stmt = select(User).where(User.email == email)
        return await self._session.scalar(stmt)

    async def create_user(
        self,
        email: str,
        password_hash: str,
        *,
        first_name: str = "",
        last_name: str = "",
        is_email_verified: bool = False,
        is_active: bool = True,
    ) -> User:
        """Create a user row, raising a domain error for duplicate email."""
        stmt = (
            insert(User)
            .values(
                email=email,
                password_hash=password_hash,
                first_name=first_name,
                last_name=last_name,
                is_email_verified=is_email_verified,
                is_active=is_active,
            )
            .on_conflict_do_nothing(index_elements=[User.email])
            .returning(User)
        )
        user = await self._session.scalar(stmt)
        if user is None:
            raise DuplicateUserEmailError(email)
        return user

    async def mark_email_verified(self, user_id: uuid.UUID) -> User | None:
        """Mark a user's email address as verified."""
        stmt = (
            update(User)
            .where(User.id == user_id)
            .values(is_email_verified=True, updated_at=func.now())
            .returning(User)
        )
        return await self._session.scalar(stmt)

    async def update_password(self, user_id: uuid.UUID, password_hash: str) -> User | None:
        """Update a user's stored password hash."""
        stmt = (
            update(User)
            .where(User.id == user_id)
            .values(password_hash=password_hash, updated_at=func.now())
            .returning(User)
        )
        return await self._session.scalar(stmt)

    async def create_email_verification_token(
        self,
        user_id: uuid.UUID,
        token_hash: str,
        expires_at: datetime,
    ) -> EmailVerificationToken:
        """Create and flush a hashed email verification token."""
        token = EmailVerificationToken(
            user_id=user_id,
            token_hash=token_hash,
            expires_at=expires_at,
        )
        self._session.add(token)
        await self._session.flush()
        await self._session.refresh(token)
        return token

    async def get_valid_email_verification_token(
        self,
        token_hash: str,
    ) -> EmailVerificationToken | None:
        """Get an unused, unexpired email verification token by hash."""
        stmt = (
            select(EmailVerificationToken)
            .options(joinedload(EmailVerificationToken.user))
            .where(
                EmailVerificationToken.token_hash == token_hash,
                EmailVerificationToken.used_at.is_(None),
                EmailVerificationToken.expires_at > func.now(),
            )
        )
        return await self._session.scalar(stmt)

    async def mark_email_verification_token_used(
        self,
        token_id: uuid.UUID,
    ) -> EmailVerificationToken | None:
        """Mark an email verification token as used."""
        stmt = (
            update(EmailVerificationToken)
            .where(
                EmailVerificationToken.id == token_id,
                EmailVerificationToken.used_at.is_(None),
            )
            .values(used_at=func.now())
            .returning(EmailVerificationToken)
        )
        return await self._session.scalar(stmt)

    async def create_password_reset_token(
        self,
        user_id: uuid.UUID,
        token_hash: str,
        expires_at: datetime,
    ) -> PasswordResetToken:
        """Create and flush a hashed password reset token."""
        token = PasswordResetToken(
            user_id=user_id,
            token_hash=token_hash,
            expires_at=expires_at,
        )
        self._session.add(token)
        await self._session.flush()
        await self._session.refresh(token)
        return token

    async def get_valid_password_reset_token(
        self,
        token_hash: str,
    ) -> PasswordResetToken | None:
        """Get an unused, unexpired password reset token by hash."""
        stmt = (
            select(PasswordResetToken)
            .options(joinedload(PasswordResetToken.user))
            .where(
                PasswordResetToken.token_hash == token_hash,
                PasswordResetToken.used_at.is_(None),
                PasswordResetToken.expires_at > func.now(),
            )
        )
        return await self._session.scalar(stmt)

    async def mark_password_reset_token_used(
        self,
        token_id: uuid.UUID,
    ) -> PasswordResetToken | None:
        """Mark a password reset token as used."""
        stmt = (
            update(PasswordResetToken)
            .where(
                PasswordResetToken.id == token_id,
                PasswordResetToken.used_at.is_(None),
            )
            .values(used_at=func.now())
            .returning(PasswordResetToken)
        )
        return await self._session.scalar(stmt)

    async def invalidate_unused_password_reset_tokens(self, user_id: uuid.UUID) -> int:
        """Mark all unused password reset tokens for a user as used."""
        stmt = (
            update(PasswordResetToken)
            .where(
                PasswordResetToken.user_id == user_id,
                PasswordResetToken.used_at.is_(None),
            )
            .values(used_at=func.now())
        )
        result = await self._session.execute(stmt)
        return result.rowcount


__all__ = ["DuplicateUserEmailError", "UserRepository"]
