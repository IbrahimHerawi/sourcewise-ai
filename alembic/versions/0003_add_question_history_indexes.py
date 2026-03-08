"""Add indexes used by question history listing/filtering queries."""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0003_question_history_ix"
down_revision: str | None = "0002_docs_created_at_ix"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create indexes that support history ordering and document filters."""
    op.create_index("ix_questions_created_at", "questions", ["created_at"], unique=False)
    op.create_index(
        "ix_question_context_chunks_chunk_id",
        "question_context_chunks",
        ["chunk_id"],
        unique=False,
    )


def downgrade() -> None:
    """Drop question history query indexes."""
    op.drop_index("ix_question_context_chunks_chunk_id", table_name="question_context_chunks")
    op.drop_index("ix_questions_created_at", table_name="questions")
