"""Repository for question-context chunk linkage rows."""

from __future__ import annotations

import math
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
        """Bulk insert citation snapshots and return them in rank order."""
        if not rows:
            return []

        self._validate_rows(rows)
        payload = [
            {
                "question_id": question_id,
                "rank": row.rank,
                "document_id": row.document_id,
                "document_filename": row.document_filename,
                "chunk_id": row.chunk_id,
                "chunk_index": row.chunk_index,
                "chunk_content": row.chunk_content,
                "similarity_score": row.similarity_score,
            }
            for row in rows
        ]
        stmt = insert(QuestionContextChunk).values(payload).returning(QuestionContextChunk)
        result = await self._session.scalars(stmt)
        inserted_rows = list(result.all())
        inserted_rows.sort(key=lambda row: row.rank)
        return inserted_rows

    @staticmethod
    def _validate_rows(rows: Sequence[QuestionContextRow]) -> None:
        ranks: set[int] = set()

        for row in rows:
            if row.rank < 1:
                raise ValueError("rank must be greater than or equal to 1")
            if row.rank in ranks:
                raise ValueError(f"duplicate rank: {row.rank}")
            if not row.document_filename.strip():
                raise ValueError("document_filename must not be blank")
            if not row.chunk_content.strip():
                raise ValueError("chunk_content must not be blank")
            if not math.isfinite(row.similarity_score):
                raise ValueError("similarity_score must be finite")

            ranks.add(row.rank)


__all__ = ["QuestionContextRepository"]
