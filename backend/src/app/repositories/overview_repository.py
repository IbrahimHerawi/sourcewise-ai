"""Single-statement owner-scoped overview aggregation."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.collections import Collection
from app.db.models.documents import Document
from app.db.models.questions import Question


@dataclass(frozen=True, slots=True)
class OverviewCounts:
    """Immutable owner-scoped resource totals."""

    total_documents: int
    total_questions: int
    total_collections: int


class OverviewRepository:
    """Read-only aggregation for an authenticated user's resources."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_counts(self, user_id: UUID) -> OverviewCounts:
        """Return three owner-filtered counts from one SQL statement."""
        if user_id is None:
            raise ValueError("user_id is required")

        document_count = (
            select(func.count())
            .select_from(Document)
            .where(Document.user_id == user_id)
            .scalar_subquery()
        )
        question_count = (
            select(func.count())
            .select_from(Question)
            .where(Question.user_id == user_id)
            .scalar_subquery()
        )
        collection_count = (
            select(func.count())
            .select_from(Collection)
            .where(Collection.user_id == user_id)
            .scalar_subquery()
        )
        statement = select(
            document_count.label("total_documents"),
            question_count.label("total_questions"),
            collection_count.label("total_collections"),
        )

        row = (await self._session.execute(statement)).one()
        return OverviewCounts(
            total_documents=int(row.total_documents or 0),
            total_questions=int(row.total_questions or 0),
            total_collections=int(row.total_collections or 0),
        )


__all__ = ["OverviewCounts", "OverviewRepository"]
