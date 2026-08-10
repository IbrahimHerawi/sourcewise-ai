"""Add indexes for final owner-scoped repository query shapes."""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0011_owner_scoped_indexes"
down_revision: str | None = "0010_nullable_question_llm"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

NEW_INDEXES: tuple[tuple[str, str, list[str | sa.TextClause]], ...] = (
    (
        "ix_documents_user_created_desc",
        "documents",
        ["user_id", sa.text("created_at DESC"), sa.text("id DESC")],
    ),
    (
        "ix_documents_user_collection_created_desc",
        "documents",
        [
            "user_id",
            "collection_id",
            sa.text("created_at DESC"),
            sa.text("id DESC"),
        ],
    ),
    (
        "ix_documents_user_status_collection",
        "documents",
        ["user_id", "status", "collection_id"],
    ),
    (
        "ix_questions_user_created_desc",
        "questions",
        ["user_id", sa.text("created_at DESC"), sa.text("id DESC")],
    ),
    (
        "ix_questions_user_collection_created_desc",
        "questions",
        [
            "user_id",
            "collection_id",
            sa.text("created_at DESC"),
            sa.text("id DESC"),
        ],
    ),
    (
        "ix_collections_user_created_desc",
        "collections",
        ["user_id", sa.text("created_at DESC"), sa.text("id DESC")],
    ),
)

REMOVED_INDEXES: tuple[tuple[str, str, list[str]], ...] = (
    ("ix_documents_user_id", "documents", ["user_id"]),
    ("ix_documents_created_at", "documents", ["created_at"]),
    ("ix_questions_user_id", "questions", ["user_id"]),
    ("ix_questions_created_at", "questions", ["created_at"]),
    ("ix_collections_user_id", "collections", ["user_id"]),
)


def upgrade() -> None:
    """Replace superseded standalone indexes with owner-scoped composites."""
    for index_name, table_name, columns in NEW_INDEXES:
        op.create_index(index_name, table_name, columns, unique=False)

    for index_name, table_name, _columns in REMOVED_INDEXES:
        op.drop_index(index_name, table_name=table_name)


def downgrade() -> None:
    """Restore every removed standalone index and drop the composites."""
    for index_name, table_name, columns in REMOVED_INDEXES:
        op.create_index(index_name, table_name, columns, unique=False)

    for index_name, table_name, _columns in reversed(NEW_INDEXES):
        op.drop_index(index_name, table_name=table_name)
