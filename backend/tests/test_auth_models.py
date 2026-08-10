from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

import pytest
from sqlalchemy import delete, inspect, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas.auth import UserResponse
from app.db.models import EmailVerificationToken, PasswordResetToken, RefreshToken, User


@pytest.mark.asyncio
async def test_auth_models_persist_defaults_and_hashed_token_fields(
    db_session: AsyncSession,
) -> None:
    expires_at = datetime.now(UTC) + timedelta(hours=1)
    user = User(
        email="user@example.com",
        password_hash="hashed-password",
        first_name="Source",
        last_name="Wise",
    )
    email_token = EmailVerificationToken(
        token_hash="hashed-email-token",
        expires_at=expires_at,
    )
    reset_token = PasswordResetToken(
        token_hash="hashed-reset-token",
        expires_at=expires_at,
    )
    refresh_token = RefreshToken(
        family_id=uuid4(),
        token_hash="hashed-refresh-token",
        expires_at=expires_at,
    )
    user.email_verification_tokens.append(email_token)
    user.password_reset_tokens.append(reset_token)
    user.refresh_tokens.append(refresh_token)

    db_session.add(user)
    await db_session.flush()

    assert user.id is not None
    assert user.is_email_verified is False
    assert user.is_active is True
    assert user.created_at is not None
    assert user.updated_at is not None
    assert email_token.user_id == user.id
    assert email_token.token_hash == "hashed-email-token"
    assert reset_token.user_id == user.id
    assert reset_token.token_hash == "hashed-reset-token"
    assert refresh_token.user_id == user.id
    assert refresh_token.token_hash == "hashed-refresh-token"
    assert refresh_token.created_at is not None
    assert refresh_token.used_at is None
    assert refresh_token.revoked_at is None
    assert refresh_token.replaced_by_id is None

    assert "token" not in EmailVerificationToken.__table__.columns
    assert "token" not in PasswordResetToken.__table__.columns
    assert "token" not in RefreshToken.__table__.columns
    assert "refresh_tokens" not in UserResponse.model_validate(user).model_dump()


@pytest.mark.asyncio
async def test_auth_migration_creates_tables_indexes_and_cascade_fks(
    db_session: AsyncSession,
) -> None:
    async_connection = await db_session.connection()

    def inspect_schema(connection: Any) -> dict[str, Any]:
        inspector = inspect(connection)
        return {
            "tables": set(inspector.get_table_names()),
            "indexes": {
                table_name: {
                    index["name"]: index
                    for index in inspector.get_indexes(table_name)
                }
                for table_name in (
                    "users",
                    "email_verification_tokens",
                    "password_reset_tokens",
                    "refresh_tokens",
                )
            },
            "foreign_keys": {
                table_name: inspector.get_foreign_keys(table_name)
                for table_name in (
                    "email_verification_tokens",
                    "password_reset_tokens",
                    "refresh_tokens",
                )
            },
        }

    schema = await async_connection.run_sync(inspect_schema)

    assert {
        "users",
        "email_verification_tokens",
        "password_reset_tokens",
        "refresh_tokens",
    }.issubset(schema["tables"])

    assert schema["indexes"]["users"]["ix_users_email"]["unique"] is True
    assert (
        schema["indexes"]["email_verification_tokens"][
            "ix_email_verification_tokens_token_hash"
        ]["unique"]
        is True
    )
    assert "ix_email_verification_tokens_user_id" in schema["indexes"][
        "email_verification_tokens"
    ]
    assert (
        schema["indexes"]["password_reset_tokens"]["ix_password_reset_tokens_token_hash"][
            "unique"
        ]
        is True
    )
    assert "ix_password_reset_tokens_user_id" in schema["indexes"]["password_reset_tokens"]

    refresh_indexes = schema["indexes"]["refresh_tokens"]
    assert set(refresh_indexes) == {
        "ix_refresh_tokens_expires_at",
        "ix_refresh_tokens_family_id",
        "ix_refresh_tokens_token_hash",
        "ix_refresh_tokens_user_id",
    }
    assert refresh_indexes["ix_refresh_tokens_token_hash"]["unique"] is True

    for table_name in (
        "email_verification_tokens",
        "password_reset_tokens",
        "refresh_tokens",
    ):
        user_fks = [
            foreign_key
            for foreign_key in schema["foreign_keys"][table_name]
            if foreign_key["referred_table"] == "users"
        ]
        assert len(user_fks) == 1
        assert user_fks[0]["options"]["ondelete"] == "CASCADE"

    replacement_fks = [
        foreign_key
        for foreign_key in schema["foreign_keys"]["refresh_tokens"]
        if foreign_key["referred_table"] == "refresh_tokens"
    ]
    assert len(replacement_fks) == 1
    assert replacement_fks[0]["options"]["ondelete"] == "SET NULL"


@pytest.mark.asyncio
async def test_deleting_user_cascades_refresh_token_rows(db_session: AsyncSession) -> None:
    user = User(
        email="refresh-cascade@example.com",
        password_hash="hashed-password",
        first_name="Refresh",
        last_name="Cascade",
    )
    refresh_token = RefreshToken(
        family_id=uuid4(),
        token_hash="refresh-cascade-token-hash",
        expires_at=datetime.now(UTC) + timedelta(days=1),
    )
    user.refresh_tokens.append(refresh_token)
    db_session.add(user)
    await db_session.flush()
    refresh_token_id = refresh_token.id

    await db_session.execute(
        delete(User).where(User.id == user.id).execution_options(synchronize_session=False)
    )

    assert await db_session.scalar(
        select(RefreshToken).where(RefreshToken.id == refresh_token_id)
    ) is None
