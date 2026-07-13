"""Add user and optional collection ownership to documents and questions."""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0006_content_ownership"
down_revision: str | None = "0005_add_collections"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

LEGACY_USER_ID = "a592a7d1-8dfa-4a7f-9203-6413f7b23713"
LEGACY_USER_EMAIL = "legacy@sourcewise.local"
FALLBACK_LEGACY_USER_ID = "d9143ee1-df49-42b9-a34e-3c60f62550d2"
FALLBACK_LEGACY_USER_EMAIL = "legacy-content@sourcewise.local"
LEGACY_PASSWORD_HASH = "!sourcewise-legacy-content-owner-0006!"


def _add_ownership_columns(table_name: str) -> None:
    """Add nullable ownership columns, constraints, and lookup indexes."""
    op.add_column(
        table_name,
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        table_name,
        sa.Column("collection_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        f"fk_{table_name}_user_id_users",
        table_name,
        "users",
        ["user_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        f"fk_{table_name}_collection_id_collections",
        table_name,
        "collections",
        ["collection_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(f"ix_{table_name}_user_id", table_name, ["user_id"], unique=False)
    op.create_index(
        f"ix_{table_name}_collection_id",
        table_name,
        ["collection_id"],
        unique=False,
    )


def _insert_legacy_user(user_id: str, email: str) -> None:
    """Insert one unmistakably disabled legacy owner when its identity is free."""
    op.execute(
        sa.text(
            f"""
            INSERT INTO users (
                id,
                email,
                password_hash,
                first_name,
                last_name,
                is_email_verified,
                is_active
            )
            SELECT
                CAST('{user_id}' AS uuid),
                '{email}',
                '{LEGACY_PASSWORD_HASH}',
                'Legacy',
                'Content',
                FALSE,
                FALSE
            WHERE (EXISTS (SELECT 1 FROM documents)
                OR EXISTS (SELECT 1 FROM questions))
              AND NOT EXISTS (
                  SELECT 1 FROM users WHERE id = CAST('{user_id}' AS uuid)
              )
              AND NOT EXISTS (
                  SELECT 1 FROM users WHERE email = '{email}'
              )
              AND NOT EXISTS (
                  SELECT 1
                  FROM users
                  WHERE password_hash = '{LEGACY_PASSWORD_HASH}'
                    AND is_email_verified = FALSE
                    AND is_active = FALSE
              )
            """
        )
    )


def upgrade() -> None:
    """Add ownership and backfill existing content through a disabled legacy user."""
    for table_name in ("documents", "questions"):
        _add_ownership_columns(table_name)

    _insert_legacy_user(LEGACY_USER_ID, LEGACY_USER_EMAIL)
    _insert_legacy_user(FALLBACK_LEGACY_USER_ID, FALLBACK_LEGACY_USER_EMAIL)
    for table_name in ("documents", "questions"):
        op.execute(
            sa.text(
                f"""
                UPDATE {table_name}
                SET user_id = (
                    SELECT id
                    FROM users
                    WHERE email IN (
                        '{LEGACY_USER_EMAIL}',
                        '{FALLBACK_LEGACY_USER_EMAIL}'
                    )
                      AND password_hash = '{LEGACY_PASSWORD_HASH}'
                      AND is_email_verified = FALSE
                      AND is_active = FALSE
                    ORDER BY CASE email
                        WHEN '{LEGACY_USER_EMAIL}' THEN 0
                        ELSE 1
                    END
                    LIMIT 1
                )
                WHERE user_id IS NULL
                """
            )
        )
        op.alter_column(
            table_name,
            "user_id",
            existing_type=postgresql.UUID(as_uuid=True),
            nullable=False,
        )


def downgrade() -> None:
    """Remove content ownership columns and their supporting schema objects."""
    for table_name in ("questions", "documents"):
        op.drop_index(f"ix_{table_name}_collection_id", table_name=table_name)
        op.drop_index(f"ix_{table_name}_user_id", table_name=table_name)
        op.drop_constraint(
            f"fk_{table_name}_collection_id_collections",
            table_name,
            type_="foreignkey",
        )
        op.drop_constraint(
            f"fk_{table_name}_user_id_users",
            table_name,
            type_="foreignkey",
        )
        op.drop_column(table_name, "collection_id")
        op.drop_column(table_name, "user_id")

    op.execute(
        sa.text(
            f"""
            DELETE FROM users
            WHERE (id, email) IN (
                (CAST('{LEGACY_USER_ID}' AS uuid), '{LEGACY_USER_EMAIL}'),
                (
                    CAST('{FALLBACK_LEGACY_USER_ID}' AS uuid),
                    '{FALLBACK_LEGACY_USER_EMAIL}'
                )
            )
              AND password_hash = '{LEGACY_PASSWORD_HASH}'
              AND first_name = 'Legacy'
              AND last_name = 'Content'
              AND is_email_verified = FALSE
              AND is_active = FALSE
              AND NOT EXISTS (
                  SELECT 1 FROM collections WHERE collections.user_id = users.id
              )
              AND NOT EXISTS (
                  SELECT 1
                  FROM email_verification_tokens
                  WHERE email_verification_tokens.user_id = users.id
              )
              AND NOT EXISTS (
                  SELECT 1
                  FROM password_reset_tokens
                  WHERE password_reset_tokens.user_id = users.id
              )
            """
        )
    )
