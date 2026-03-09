"""Initial schema for documents, chunks, questions, and ingestion jobs."""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import context, op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

from app.core.settings import get_settings

# revision identifiers, used by Alembic.
revision: str = "0001_initial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

EMBEDDING_DIM = get_settings().embedding_dim


def _supports_hnsw() -> bool:
    """Return whether the installed pgvector extension supports HNSW indexes."""
    if context.is_offline_mode():
        return True

    bind = op.get_bind()
    if bind is None:
        return True

    ext_version = bind.execute(
        sa.text("SELECT extversion FROM pg_extension WHERE extname = 'vector'")
    ).scalar_one_or_none()
    if ext_version is None:
        return False

    try:
        version_parts = ext_version.split(".")
        major = int(version_parts[0])
        minor = int(version_parts[1]) if len(version_parts) > 1 else 0
    except ValueError:
        return False

    return major > 0 or minor >= 5


def _create_chunk_embedding_index() -> None:
    """Create a cosine-distance vector index, preferring HNSW when possible."""
    if _supports_hnsw():
        op.create_index(
            "ix_document_chunks_embedding_cosine",
            "document_chunks",
            ["embedding"],
            unique=False,
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"},
        )
        return

    op.create_index(
        "ix_document_chunks_embedding_cosine",
        "document_chunks",
        ["embedding"],
        unique=False,
        postgresql_using="ivfflat",
        postgresql_with={"lists": 100},
        postgresql_ops={"embedding": "vector_cosine_ops"},
    )
    op.execute(
        "COMMENT ON INDEX ix_document_chunks_embedding_cosine IS "
        "'IVFFlat index uses lists=100. Run ANALYZE document_chunks after bulk "
        "inserts so the planner can make better index choices.'"
    )


def upgrade() -> None:
    """Apply initial schema objects."""
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "documents",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("filename", sa.String(length=512), nullable=False),
        sa.Column("original_extension", sa.String(length=16), nullable=False),
        sa.Column("content_type", sa.String(length=255), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("storage_path", sa.String(length=1024), nullable=False),
        sa.Column("extracted_text", sa.Text(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "PENDING",
                "PROCESSING",
                "READY",
                "FAILED",
                name="document_status",
            ),
            server_default="PENDING",
            nullable=False,
        ),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_documents"),
    )

    op.create_table(
        "document_chunks",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("embedding", Vector(EMBEDDING_DIM), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["documents.id"],
            name="fk_document_chunks_document_id_documents",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_document_chunks"),
        sa.UniqueConstraint(
            "document_id",
            "chunk_index",
            name="uq_document_chunks_document_id_chunk_index",
        ),
    )
    op.create_index(
        "ix_document_chunks_document_id",
        "document_chunks",
        ["document_id"],
        unique=False,
    )
    _create_chunk_embedding_index()

    op.create_table(
        "questions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("question_text", sa.Text(), nullable=False),
        sa.Column("question_embedding", Vector(EMBEDDING_DIM), nullable=False),
        sa.Column("answer_text", sa.Text(), nullable=False),
        sa.Column("ai_provider", sa.String(length=32), nullable=False),
        sa.Column("model_used", sa.String(length=255), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "ai_provider IN ('openai', 'ollama')",
            name="ai_provider",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_questions"),
    )

    op.create_table(
        "question_context_chunks",
        sa.Column("question_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("chunk_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("similarity_score", sa.Float(), nullable=False),
        sa.Column("rank", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["chunk_id"],
            ["document_chunks.id"],
            name="fk_question_context_chunks_chunk_id_document_chunks",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["question_id"],
            ["questions.id"],
            name="fk_question_context_chunks_question_id_questions",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "question_id",
            "chunk_id",
            name="pk_question_context_chunks",
        ),
    )

    op.create_table(
        "ingestion_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "PENDING",
                "PROCESSING",
                "DONE",
                "FAILED",
                name="ingestion_job_status",
            ),
            server_default="PENDING",
            nullable=False,
        ),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["documents.id"],
            name="fk_ingestion_jobs_document_id_documents",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_ingestion_jobs"),
    )
    op.create_index(
        "ix_ingestion_jobs_document_id",
        "ingestion_jobs",
        ["document_id"],
        unique=False,
    )


def downgrade() -> None:
    """Revert initial schema objects."""
    op.drop_index("ix_ingestion_jobs_document_id", table_name="ingestion_jobs")
    op.drop_table("ingestion_jobs")

    op.drop_table("question_context_chunks")
    op.drop_table("questions")

    op.drop_index(
        "ix_document_chunks_embedding_cosine",
        table_name="document_chunks",
    )
    op.drop_index("ix_document_chunks_document_id", table_name="document_chunks")
    op.drop_table("document_chunks")
    op.drop_table("documents")

    op.execute("DROP TYPE IF EXISTS ingestion_job_status")
    op.execute("DROP TYPE IF EXISTS document_status")
