"""Allow pending documents to exist before text extraction completes."""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0008_nullable_document_text"
down_revision: str | None = "0007_collection_name_ci"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Allow documents to have no extracted text yet."""
    op.alter_column(
        "documents",
        "extracted_text",
        existing_type=sa.Text(),
        nullable=True,
    )


def downgrade() -> None:
    """Restore the non-null constraint only when every document has text."""
    op.execute(sa.text("LOCK TABLE documents IN SHARE ROW EXCLUSIVE MODE"))
    null_count = op.get_bind().execute(
        sa.text("SELECT count(*) FROM documents WHERE extracted_text IS NULL")
    ).scalar_one()
    if null_count:
        raise RuntimeError(
            "Cannot make documents.extracted_text non-nullable: "
            f"{null_count} document row(s) have null extracted_text. "
            "Extract or restore text for every affected document, or delete rows "
            "that should not be retained, then rerun the downgrade."
        )

    op.alter_column(
        "documents",
        "extracted_text",
        existing_type=sa.Text(),
        nullable=False,
    )
