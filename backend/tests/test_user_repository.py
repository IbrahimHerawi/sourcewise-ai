from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.user_repository import DuplicateUserEmailError, UserRepository


@pytest.mark.asyncio
async def test_user_repository_creates_gets_and_updates_user(db_session: AsyncSession) -> None:
    repository = UserRepository(db_session)

    created = await repository.create_user(
        "user@example.com",
        "hash-v1",
        first_name="Source",
        last_name="Wise",
    )
    by_email = await repository.get_user_by_email("user@example.com")
    by_id = await repository.get_user_by_id(created.id)
    verified = await repository.mark_email_verified(created.id)
    updated_password = await repository.update_password(created.id, "hash-v2")

    assert by_email is not None
    assert by_email.id == created.id
    assert by_id is not None
    assert by_id.email == "user@example.com"
    assert created.first_name == "Source"
    assert created.last_name == "Wise"
    assert verified is not None
    assert verified.is_email_verified is True
    assert updated_password is not None
    assert updated_password.password_hash == "hash-v2"


@pytest.mark.asyncio
async def test_user_repository_duplicate_email_raises_clean_error(
    db_session: AsyncSession,
) -> None:
    repository = UserRepository(db_session)

    created = await repository.create_user("duplicate@example.com", "hash-v1")

    with pytest.raises(DuplicateUserEmailError) as exc_info:
        await repository.create_user("duplicate@example.com", "hash-v2")

    fetched = await repository.get_user_by_email("duplicate@example.com")
    assert exc_info.value.email == "duplicate@example.com"
    assert fetched is not None
    assert fetched.id == created.id
    assert fetched.password_hash == "hash-v1"


@pytest.mark.asyncio
async def test_user_repository_valid_email_verification_token_lookup(
    db_session: AsyncSession,
) -> None:
    repository = UserRepository(db_session)
    user = await repository.create_user("verify@example.com", "hash")
    expires_at = datetime.now(UTC) + timedelta(hours=1)

    token = await repository.create_email_verification_token(
        user.id,
        "valid-email-token-hash",
        expires_at,
    )
    valid = await repository.get_valid_email_verification_token("valid-email-token-hash")

    assert valid is not None
    assert valid.id == token.id
    assert valid.user.id == user.id


@pytest.mark.asyncio
async def test_user_repository_used_email_verification_token_is_not_valid(
    db_session: AsyncSession,
) -> None:
    repository = UserRepository(db_session)
    user = await repository.create_user("used-email-token@example.com", "hash")
    token = await repository.create_email_verification_token(
        user.id,
        "used-email-token-hash",
        datetime.now(UTC) + timedelta(hours=1),
    )

    used = await repository.mark_email_verification_token_used(token.id)
    valid_after_use = await repository.get_valid_email_verification_token("used-email-token-hash")

    assert used is not None
    assert used.used_at is not None
    assert valid_after_use is None


@pytest.mark.asyncio
async def test_user_repository_expired_email_verification_token_is_not_valid(
    db_session: AsyncSession,
) -> None:
    repository = UserRepository(db_session)
    user = await repository.create_user("expired-email-token@example.com", "hash")

    await repository.create_email_verification_token(
        user.id,
        "expired-email-token-hash",
        datetime.now(UTC) - timedelta(seconds=1),
    )
    valid = await repository.get_valid_email_verification_token("expired-email-token-hash")

    assert valid is None


@pytest.mark.asyncio
async def test_user_repository_password_reset_token_validity_and_invalidation(
    db_session: AsyncSession,
) -> None:
    repository = UserRepository(db_session)
    user = await repository.create_user("reset@example.com", "hash")
    valid_token = await repository.create_password_reset_token(
        user.id,
        "valid-reset-token-hash",
        datetime.now(UTC) + timedelta(hours=1),
    )
    expired_token = await repository.create_password_reset_token(
        user.id,
        "expired-reset-token-hash",
        datetime.now(UTC) - timedelta(seconds=1),
    )

    valid = await repository.get_valid_password_reset_token("valid-reset-token-hash")
    expired = await repository.get_valid_password_reset_token("expired-reset-token-hash")
    used = await repository.mark_password_reset_token_used(valid_token.id)
    valid_after_use = await repository.get_valid_password_reset_token("valid-reset-token-hash")
    invalidated_count = await repository.invalidate_unused_password_reset_tokens(user.id)
    expired_after_invalidation = await repository.get_valid_password_reset_token(
        expired_token.token_hash
    )

    assert valid is not None
    assert valid.id == valid_token.id
    assert valid.user.id == user.id
    assert expired is None
    assert used is not None
    assert used.used_at is not None
    assert valid_after_use is None
    assert invalidated_count == 1
    assert expired_after_invalidation is None
