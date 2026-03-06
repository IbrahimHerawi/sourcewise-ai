"""Repository for persisted question history."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models.document_chunks import DocumentChunk
from app.db.models.question_context_chunks import QuestionContextChunk
from app.db.models.questions import Question


class QuestionRepository:
    """Data access methods for questions and linked context chunks."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_question(
        self,
        question_text: str,
        embedding: list[float],
        answer_text: str,
        ai_provider: str,
        model_used: str,
    ) -> Question:
        """Create and flush a question row."""
        question = Question(
            question_text=question_text,
            question_embedding=embedding,
            answer_text=answer_text,
            ai_provider=ai_provider,
            model_used=model_used,
        )
        self._session.add(question)
        await self._session.flush()
        await self._session.refresh(question)
        return question

    async def list_questions(
        self,
        limit: int,
        offset: int,
        document_id: uuid.UUID | None = None,
    ) -> list[Question]:
        """List question history, optionally filtered by linked document id."""
        self._validate_pagination(limit=limit, offset=offset)

        stmt = (
            select(Question)
            .options(selectinload(Question.context_chunks).selectinload(QuestionContextChunk.chunk))
            .order_by(Question.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        if document_id is not None:
            matching_question_ids = (
                select(QuestionContextChunk.question_id)
                .join(DocumentChunk, DocumentChunk.id == QuestionContextChunk.chunk_id)
                .where(DocumentChunk.document_id == document_id)
                .distinct()
            )
            stmt = stmt.where(Question.id.in_(matching_question_ids))

        result = await self._session.scalars(stmt)
        return list(result.all())

    @staticmethod
    def _validate_pagination(*, limit: int, offset: int) -> None:
        if limit <= 0:
            raise ValueError("limit must be greater than 0")
        if offset < 0:
            raise ValueError("offset must be greater than or equal to 0")


__all__ = ["QuestionRepository"]
