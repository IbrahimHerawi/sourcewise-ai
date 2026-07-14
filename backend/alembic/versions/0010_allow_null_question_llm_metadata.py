"""Allow questions recorded without an LLM call to omit LLM metadata."""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0010_nullable_question_llm"
down_revision: str | None = "0009_durable_citations"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Allow deterministic fallback answers to omit provider and model metadata."""
    op.alter_column(
        "questions",
        "ai_provider",
        existing_type=sa.String(length=32),
        nullable=True,
    )
    op.alter_column(
        "questions",
        "model_used",
        existing_type=sa.String(length=255),
        nullable=True,
    )


def downgrade() -> None:
    """Restore required LLM metadata only when every question has both values."""
    op.execute(sa.text("LOCK TABLE questions IN SHARE ROW EXCLUSIVE MODE"))
    null_metadata_count = (
        op.get_bind()
        .execute(
            sa.text(
                """
                SELECT count(*)
                FROM questions
                WHERE ai_provider IS NULL OR model_used IS NULL
                """
            )
        )
        .scalar_one()
    )
    if null_metadata_count:
        raise RuntimeError(
            "Cannot make question LLM metadata non-nullable: "
            f"{null_metadata_count} question record(s) have a null provider or model. "
            "Populate both metadata fields for every affected record, then rerun "
            "the downgrade."
        )

    op.alter_column(
        "questions",
        "ai_provider",
        existing_type=sa.String(length=32),
        nullable=False,
    )
    op.alter_column(
        "questions",
        "model_used",
        existing_type=sa.String(length=255),
        nullable=False,
    )
