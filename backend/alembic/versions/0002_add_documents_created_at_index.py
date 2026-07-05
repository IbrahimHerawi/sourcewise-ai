"""Add an index for document list ordering by created_at."""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0002_docs_created_at_ix"
down_revision: str | None = "0001_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create the created_at index used by document list pagination."""
    op.create_index("ix_documents_created_at", "documents", ["created_at"], unique=False)


def downgrade() -> None:
    """Drop the created_at index."""
    op.drop_index("ix_documents_created_at", table_name="documents")
