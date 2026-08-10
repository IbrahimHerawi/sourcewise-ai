"""Repository for ingestion job persistence."""

from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.ingestion_jobs import IngestionJob, IngestionJobStatus


class IngestionJobRepository:
    """Data access methods for ingestion job rows."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_job(
        self,
        *,
        document_id: uuid.UUID,
        status: IngestionJobStatus = IngestionJobStatus.PENDING,
        error_message: str | None = None,
    ) -> IngestionJob:
        """Create and flush one ingestion job row."""
        job = IngestionJob(
            document_id=document_id,
            status=status,
            error_message=error_message,
        )
        self._session.add(job)
        await self._session.flush()
        await self._session.refresh(job)
        return job


__all__ = ["IngestionJobRepository"]
