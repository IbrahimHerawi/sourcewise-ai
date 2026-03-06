"""Repository for question-context chunk linkage rows."""

from __future__ import annotations

import uuid
from collections.abc import Sequence

from sqlalchemy import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.question_context_chunks import QuestionContextChunk
from app.repositories.types import QuestionContextRow


class QuestionContextRepository:
    """Data access methods for question context chunk links."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def bulk_insert_question_context(
        self,
        question_id: uuid.UUID,
        rows: Sequence[QuestionContextRow],
    ) -> list[QuestionContextChunk]:
        """Bulk insert question-context links and return inserted ORM rows."""
        if not rows:
            return []

        payload = [
            {
                "question_id": question_id,
                "chunk_id": row.chunk_id,
                "similarity_score": row.similarity_score,
                "rank": row.rank,
            }
            for row in rows
        ]
        stmt = insert(QuestionContextChunk).values(payload).returning(QuestionContextChunk)
        result = await self._session.scalars(stmt)
        return list(result.all())


__all__ = ["QuestionContextRepository"]
