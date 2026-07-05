from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from sqlalchemy import inspect
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import EmailVerificationToken, PasswordResetToken, User


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
    user.email_verification_tokens.append(email_token)
    user.password_reset_tokens.append(reset_token)

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

    assert "token" not in EmailVerificationToken.__table__.columns
    assert "token" not in PasswordResetToken.__table__.columns


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
                )
            },
            "foreign_keys": {
                table_name: inspector.get_foreign_keys(table_name)
                for table_name in (
                    "email_verification_tokens",
                    "password_reset_tokens",
                )
            },
        }

    schema = await async_connection.run_sync(inspect_schema)

    assert {
        "users",
        "email_verification_tokens",
        "password_reset_tokens",
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

    for table_name in ("email_verification_tokens", "password_reset_tokens"):
        user_fks = [
            foreign_key
            for foreign_key in schema["foreign_keys"][table_name]
            if foreign_key["referred_table"] == "users"
        ]
        assert len(user_fks) == 1
        assert user_fks[0]["options"]["ondelete"] == "CASCADE"
