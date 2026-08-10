"""Convert question context chunks into durable citation snapshots."""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0009_durable_citations"
down_revision: str | None = "0008_nullable_document_text"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLE_NAME = "question_context_chunks"
PRIMARY_KEY_NAME = "pk_question_context_chunks"
CHUNK_FOREIGN_KEY_NAME = "fk_question_context_chunks_chunk_id_document_chunks"
CHUNK_INDEX_NAME = "ix_question_context_chunks_chunk_id"
RANK_CHECK_NAME = "rank_positive"


def _verify_backfill() -> None:
    missing_count = op.get_bind().execute(
        sa.text(
            """
            SELECT count(*)
            FROM question_context_chunks
            WHERE document_id IS NULL
               OR document_filename IS NULL
               OR chunk_index IS NULL
               OR chunk_content IS NULL
            """
        )
    ).scalar_one()
    if missing_count:
        raise RuntimeError(
            "Cannot convert question_context_chunks to durable citation snapshots: "
            f"{missing_count} citation row(s) could not be backfilled from "
            "document_chunks and documents. Restore the referenced live chunk and "
            "document rows, then rerun the migration. No citation history was changed."
        )


def _verify_ranks_support_new_constraints() -> None:
    invalid_rank_count = op.get_bind().execute(
        sa.text("SELECT count(*) FROM question_context_chunks WHERE rank <= 0")
    ).scalar_one()
    duplicate_rank_count = op.get_bind().execute(
        sa.text(
            """
            SELECT count(*)
            FROM (
                SELECT question_id, rank
                FROM question_context_chunks
                GROUP BY question_id, rank
                HAVING count(*) > 1
            ) AS duplicate_ranks
            """
        )
    ).scalar_one()
    if invalid_rank_count or duplicate_rank_count:
        raise RuntimeError(
            "Cannot make (question_id, rank) the citation primary key: "
            f"found {invalid_rank_count} citation row(s) with a non-positive rank "
            f"and {duplicate_rank_count} duplicate question/rank pair(s). Correct "
            "the affected ranks without deleting citation history, then rerun the "
            "migration. No citation history was changed."
        )


def upgrade() -> None:
    """Snapshot live citation data and remove live document/chunk dependencies."""
    op.add_column(
        TABLE_NAME,
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        TABLE_NAME,
        sa.Column("document_filename", sa.String(length=512), nullable=True),
    )
    op.add_column(
        TABLE_NAME,
        sa.Column("chunk_index", sa.Integer(), nullable=True),
    )
    op.add_column(
        TABLE_NAME,
        sa.Column("chunk_content", sa.Text(), nullable=True),
    )

    op.execute(
        sa.text(
            """
            UPDATE question_context_chunks AS citation
            SET document_id = chunk.document_id,
                document_filename = document.filename,
                chunk_index = chunk.chunk_index,
                chunk_content = chunk.content
            FROM document_chunks AS chunk
            JOIN documents AS document ON document.id = chunk.document_id
            WHERE citation.chunk_id = chunk.id
            """
        )
    )
    _verify_backfill()
    _verify_ranks_support_new_constraints()

    op.drop_constraint(PRIMARY_KEY_NAME, TABLE_NAME, type_="primary")
    op.drop_constraint(CHUNK_FOREIGN_KEY_NAME, TABLE_NAME, type_="foreignkey")

    op.alter_column(
        TABLE_NAME,
        "document_id",
        existing_type=postgresql.UUID(as_uuid=True),
        nullable=False,
    )
    op.alter_column(
        TABLE_NAME,
        "document_filename",
        existing_type=sa.String(length=512),
        nullable=False,
    )
    op.alter_column(
        TABLE_NAME,
        "chunk_index",
        existing_type=sa.Integer(),
        nullable=False,
    )
    op.alter_column(
        TABLE_NAME,
        "chunk_content",
        existing_type=sa.Text(),
        nullable=False,
    )

    op.create_primary_key(PRIMARY_KEY_NAME, TABLE_NAME, ["question_id", "rank"])
    op.create_check_constraint(RANK_CHECK_NAME, TABLE_NAME, "rank > 0")
    op.drop_index(CHUNK_INDEX_NAME, table_name=TABLE_NAME)


def _verify_chunks_exist_for_downgrade() -> None:
    bind = op.get_bind()
    missing_count = bind.execute(
        sa.text(
            """
            SELECT count(DISTINCT citation.chunk_id)
            FROM question_context_chunks AS citation
            LEFT JOIN document_chunks AS chunk ON chunk.id = citation.chunk_id
            WHERE chunk.id IS NULL
            """
        )
    ).scalar_one()
    if missing_count:
        missing_chunk_ids = (
            bind.execute(
                sa.text(
                    """
                    SELECT DISTINCT CAST(citation.chunk_id AS text) AS chunk_id
                    FROM question_context_chunks AS citation
                    LEFT JOIN document_chunks AS chunk ON chunk.id = citation.chunk_id
                    WHERE chunk.id IS NULL
                    ORDER BY chunk_id
                    LIMIT 10
                    """
                )
            )
            .scalars()
            .all()
        )
        displayed_ids = ", ".join(missing_chunk_ids)
        remaining_count = missing_count - len(missing_chunk_ids)
        suffix = f" (and {remaining_count} more)" if remaining_count > 0 else ""
        raise RuntimeError(
            "Cannot restore the live document_chunks foreign key because "
            f"{missing_count} snapshot chunk_id value(s) no longer exist: "
            f"{displayed_ids}{suffix}. Restore those document_chunks rows with their "
            "original IDs, or remain on the durable citation revision. No citation "
            "history was deleted or changed."
        )


def _verify_chunk_keys_support_old_primary_key() -> None:
    duplicate_count = op.get_bind().execute(
        sa.text(
            """
            SELECT count(*)
            FROM (
                SELECT question_id, chunk_id
                FROM question_context_chunks
                GROUP BY question_id, chunk_id
                HAVING count(*) > 1
            ) AS duplicate_chunks
            """
        )
    ).scalar_one()
    if duplicate_count:
        raise RuntimeError(
            "Cannot restore (question_id, chunk_id) as the citation primary key: "
            f"found {duplicate_count} duplicate question/chunk pair(s). Resolve the "
            "duplicate references without deleting citation history, or remain on the "
            "durable citation revision. No citation history was changed."
        )


def downgrade() -> None:
    """Restore live chunk links only when every snapshot remains representable."""
    op.execute(
        sa.text(
            "LOCK TABLE question_context_chunks, document_chunks "
            "IN SHARE ROW EXCLUSIVE MODE"
        )
    )
    _verify_chunks_exist_for_downgrade()
    _verify_chunk_keys_support_old_primary_key()

    op.drop_constraint(PRIMARY_KEY_NAME, TABLE_NAME, type_="primary")
    op.drop_constraint(RANK_CHECK_NAME, TABLE_NAME, type_="check")
    op.create_primary_key(PRIMARY_KEY_NAME, TABLE_NAME, ["question_id", "chunk_id"])
    op.create_foreign_key(
        CHUNK_FOREIGN_KEY_NAME,
        TABLE_NAME,
        "document_chunks",
        ["chunk_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index(CHUNK_INDEX_NAME, TABLE_NAME, ["chunk_id"], unique=False)

    op.drop_column(TABLE_NAME, "chunk_content")
    op.drop_column(TABLE_NAME, "chunk_index")
    op.drop_column(TABLE_NAME, "document_filename")
    op.drop_column(TABLE_NAME, "document_id")
