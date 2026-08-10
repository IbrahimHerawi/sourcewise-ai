"""Repository for persisted question history."""

from __future__ import annotations

import uuid

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models.questions import Question


class QuestionRepository:
    """Owner-scoped data access methods for persisted question history."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_question(
        self,
        user_id: uuid.UUID,
        *,
        collection_id: uuid.UUID | None = None,
        question_text: str,
        embedding: list[float],
        answer_text: str,
        ai_provider: str | None,
        model_used: str | None,
    ) -> Question:
        """Create and flush an owner-scoped question row."""
        self._validate_required_id(user_id, "user_id")
        if (ai_provider is None) != (model_used is None):
            raise ValueError("ai_provider and model_used must both be null or both be non-null")

        question = Question(
            user_id=user_id,
            collection_id=collection_id,
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
        user_id: uuid.UUID,
        limit: int,
        offset: int,
        collection_id: uuid.UUID | None = None,
    ) -> list[Question]:
        """List one owner's history, optionally filtered by collection."""
        self._validate_required_id(user_id, "user_id")
        self._validate_pagination(limit=limit, offset=offset)

        stmt = (
            select(Question)
            .options(selectinload(Question.context_chunks))
            .where(Question.user_id == user_id)
            .order_by(Question.created_at.desc(), Question.id.desc())
            .limit(limit)
            .offset(offset)
        )
        if collection_id is not None:
            stmt = stmt.where(Question.collection_id == collection_id)

        result = await self._session.scalars(stmt)
        return list(result.all())

    async def count_questions(
        self,
        user_id: uuid.UUID,
        collection_id: uuid.UUID | None = None,
    ) -> int:
        """Count one owner's questions, optionally filtered by collection."""
        self._validate_required_id(user_id, "user_id")
        stmt = (
            select(func.count())
            .select_from(Question)
            .where(Question.user_id == user_id)
        )
        if collection_id is not None:
            stmt = stmt.where(Question.collection_id == collection_id)

        total = await self._session.scalar(stmt)
        return int(total or 0)

    async def get_question(
        self,
        user_id: uuid.UUID,
        question_id: uuid.UUID,
    ) -> Question | None:
        """Get one owner-scoped question with its citation snapshots."""
        self._validate_required_id(user_id, "user_id")
        self._validate_required_id(question_id, "question_id")
        stmt = (
            select(Question)
            .options(selectinload(Question.context_chunks))
            .where(
                Question.user_id == user_id,
                Question.id == question_id,
            )
        )
        return await self._session.scalar(stmt)

    async def delete_question(
        self,
        user_id: uuid.UUID,
        question_id: uuid.UUID,
    ) -> bool:
        """Delete an owner-scoped question and report whether it existed."""
        self._validate_required_id(user_id, "user_id")
        self._validate_required_id(question_id, "question_id")
        stmt = (
            delete(Question)
            .where(
                Question.user_id == user_id,
                Question.id == question_id,
            )
            .returning(Question.id)
        )
        deleted_id = await self._session.scalar(stmt)
        return deleted_id is not None

    @staticmethod
    def _validate_pagination(*, limit: int, offset: int) -> None:
        if limit <= 0:
            raise ValueError("limit must be greater than 0")
        if offset < 0:
            raise ValueError("offset must be greater than or equal to 0")

    @staticmethod
    def _validate_required_id(value: uuid.UUID | None, name: str) -> None:
        if value is None:
            raise ValueError(f"{name} is required")


__all__ = ["QuestionRepository"]
