"""Question ORM model."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from pgvector.sqlalchemy import Vector
from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.settings import get_settings
from app.db.base import Base

if TYPE_CHECKING:
    from app.db.models.auth import User
    from app.db.models.collections import Collection
    from app.db.models.question_context_chunks import QuestionContextChunk

EMBEDDING_DIM = get_settings().embedding_dim


class Question(Base):
    """Asked question and generated answer metadata."""

    __tablename__ = "questions"
    __table_args__ = (
        CheckConstraint(
            "ai_provider IN ('openai', 'ollama')",
            name="ai_provider",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    collection_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("collections.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    question_text: Mapped[str] = mapped_column(Text, nullable=False)
    question_embedding: Mapped[list[float]] = mapped_column(Vector(EMBEDDING_DIM), nullable=False)
    answer_text: Mapped[str] = mapped_column(Text, nullable=False)
    ai_provider: Mapped[str] = mapped_column(String(length=32), nullable=False)
    model_used: Mapped[str] = mapped_column(String(length=255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    )

    user: Mapped[User] = relationship(back_populates="questions")
    collection: Mapped[Collection | None] = relationship(back_populates="questions")
    context_chunks: Mapped[list[QuestionContextChunk]] = relationship(
        back_populates="question",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
