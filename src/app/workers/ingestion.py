"""Asynchronous in-process ingestion worker pool."""

from __future__ import annotations

import asyncio
import logging
import uuid
from dataclasses import dataclass
from typing import Final

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.settings import Settings, get_settings
from app.db.models.document_chunks import DocumentChunk
from app.db.models.documents import Document, DocumentStatus
from app.db.models.ingestion_jobs import IngestionJob, IngestionJobStatus
from app.db.session import AsyncSessionMaker
from app.repositories.chunk_repository import ChunkRepository
from app.repositories.types import ChunkWithEmbedding
from app.services.embeddings import embed_documents
from app.utils.chunking import chunk_text

logger = logging.getLogger(__name__)

_STOP_SENTINEL: Final[object] = object()
_MAX_ERROR_MESSAGE_LEN: Final[int] = 2000


@dataclass(slots=True, frozen=True)
class ClaimedJob:
    """A job that was successfully claimed for processing."""

    job_id: uuid.UUID
    document_id: uuid.UUID
    extracted_text: str


class IngestionManager:
    """Manage async ingestion workers backed by an in-memory queue and DB jobs."""

    def __init__(
        self,
        *,
        settings: Settings | None = None,
        session_maker: async_sessionmaker[AsyncSession] = AsyncSessionMaker,
    ) -> None:
        self._settings = settings or get_settings()
        self._session_maker = session_maker
        self._queue: asyncio.Queue[uuid.UUID | object] = asyncio.Queue()
        self._workers: list[asyncio.Task[None]] = []
        self._queue_lock = asyncio.Lock()
        self._enqueued_job_ids: set[uuid.UUID] = set()
        self._running = False
        self._accept_new_jobs = False

    async def start(self) -> None:
        """Start workers and re-enqueue any non-terminal jobs persisted in DB."""
        if self._running:
            return

        self._running = True
        self._accept_new_jobs = True

        worker_count = int(getattr(self._settings, "ingest_workers", 2))
        if worker_count <= 0:
            raise ValueError("INGEST_WORKERS must be greater than 0.")
        await self._recover_jobs_on_startup()

        for index in range(worker_count):
            task = asyncio.create_task(
                self._worker_loop(worker_idx=index + 1),
                name=f"ingestion-worker-{index + 1}",
            )
            self._workers.append(task)

        logger.info("Started ingestion worker pool with %s workers.", worker_count)

    async def stop(self) -> None:
        """Drain queue and stop workers gracefully."""
        if not self._running:
            return

        self._accept_new_jobs = False
        await self._queue.join()

        for _ in self._workers:
            self._queue.put_nowait(_STOP_SENTINEL)

        if self._workers:
            await asyncio.gather(*self._workers, return_exceptions=True)

        self._workers.clear()
        async with self._queue_lock:
            self._enqueued_job_ids.clear()

        self._running = False
        logger.info("Stopped ingestion worker pool.")

    async def enqueue(
        self,
        *,
        document_id: uuid.UUID | str | None = None,
        job_id: uuid.UUID | str | None = None,
    ) -> int:
        """Enqueue one job by id or enqueue all pending jobs for a document."""
        if not self._accept_new_jobs:
            raise RuntimeError("Ingestion manager is not running.")

        if job_id is not None:
            job_ids = [self._to_uuid(job_id)]
        elif document_id is not None:
            job_ids = await self._pending_job_ids_for_document(self._to_uuid(document_id))
        else:
            raise ValueError("Either job_id or document_id must be provided.")

        enqueued = 0
        for resolved_job_id in job_ids:
            if await self._enqueue_job_id(resolved_job_id):
                enqueued += 1

        return enqueued

    async def _recover_jobs_on_startup(self) -> None:
        """Reset in-flight jobs and enqueue all pending jobs from DB."""
        async with self._session_maker() as session:
            async with session.begin():
                await session.execute(
                    update(IngestionJob)
                    .where(IngestionJob.status == IngestionJobStatus.PROCESSING)
                    .values(status=IngestionJobStatus.PENDING)
                )

                pending_or_processing_document_ids = (
                    select(IngestionJob.document_id)
                    .where(
                        IngestionJob.status.in_(
                            (IngestionJobStatus.PENDING, IngestionJobStatus.PROCESSING)
                        )
                    )
                    .scalar_subquery()
                )
                await session.execute(
                    update(Document)
                    .where(Document.id.in_(pending_or_processing_document_ids))
                    .where(Document.status == DocumentStatus.PROCESSING)
                    .values(status=DocumentStatus.PENDING, error_message=None)
                )

                pending_result = await session.scalars(
                    select(IngestionJob.id)
                    .where(IngestionJob.status == IngestionJobStatus.PENDING)
                    .order_by(IngestionJob.created_at.asc())
                )
                pending_job_ids = list(pending_result.all())

        for pending_job_id in pending_job_ids:
            await self._enqueue_job_id(pending_job_id)

        if pending_job_ids:
            logger.info("Recovered and re-enqueued %s pending ingestion jobs.", len(pending_job_ids))

    async def _worker_loop(self, *, worker_idx: int) -> None:
        """Continuously process queued jobs until a stop sentinel is received."""
        while True:
            item = await self._queue.get()
            try:
                if item is _STOP_SENTINEL:
                    return

                if not isinstance(item, uuid.UUID):
                    logger.error(
                        "Worker %s received unsupported queue item type: %s",
                        worker_idx,
                        type(item).__name__,
                    )
                    continue

                await self._process_job(item, worker_idx=worker_idx)
            except Exception:
                logger.exception("Ingestion worker %s crashed while processing queue item.", worker_idx)
            finally:
                if isinstance(item, uuid.UUID):
                    async with self._queue_lock:
                        self._enqueued_job_ids.discard(item)
                self._queue.task_done()

    async def _process_job(self, job_id: uuid.UUID, *, worker_idx: int) -> None:
        claimed = await self._claim_job(job_id)
        if claimed is None:
            logger.debug("Worker %s skipped job %s (not claimable).", worker_idx, job_id)
            return

        logger.info(
            "Worker %s processing ingestion job %s for document %s.",
            worker_idx,
            claimed.job_id,
            claimed.document_id,
        )

        try:
            chunks = chunk_text(claimed.extracted_text)
            embeddings = await embed_documents(chunks)
            if len(chunks) != len(embeddings):
                raise RuntimeError(
                    "Embedding count mismatch for ingestion job "
                    f"{claimed.job_id}: expected {len(chunks)}, got {len(embeddings)}."
                )

            chunk_rows = [
                ChunkWithEmbedding(
                    chunk_index=index,
                    content=chunk,
                    embedding=embedding,
                )
                for index, (chunk, embedding) in enumerate(zip(chunks, embeddings, strict=True))
            ]

            await self._persist_success(
                job_id=claimed.job_id,
                document_id=claimed.document_id,
                chunks=chunk_rows,
            )
            logger.info(
                "Worker %s completed ingestion job %s (%s chunks).",
                worker_idx,
                claimed.job_id,
                len(chunk_rows),
            )
        except Exception as exc:
            await self._persist_failure(
                job_id=claimed.job_id,
                document_id=claimed.document_id,
                error=exc,
            )
            logger.exception(
                "Worker %s failed ingestion job %s for document %s.",
                worker_idx,
                claimed.job_id,
                claimed.document_id,
            )

    async def _claim_job(self, job_id: uuid.UUID) -> ClaimedJob | None:
        """Atomically claim a single pending job using row locks."""
        async with self._session_maker() as session:
            async with session.begin():
                result = await session.scalars(
                    select(IngestionJob)
                    .where(IngestionJob.id == job_id)
                    .with_for_update(skip_locked=True)
                )
                job = result.first()
                if job is None or job.status != IngestionJobStatus.PENDING:
                    return None

                document = await session.get(
                    Document,
                    job.document_id,
                    with_for_update=True,
                )
                if document is None:
                    job.status = IngestionJobStatus.FAILED
                    job.error_message = "Document not found for ingestion job."
                    return None

                job.status = IngestionJobStatus.PROCESSING
                job.error_message = None
                document.status = DocumentStatus.PROCESSING
                document.error_message = None

                return ClaimedJob(
                    job_id=job.id,
                    document_id=document.id,
                    extracted_text=document.extracted_text,
                )

    async def _persist_success(
        self,
        *,
        job_id: uuid.UUID,
        document_id: uuid.UUID,
        chunks: list[ChunkWithEmbedding],
    ) -> None:
        """Persist chunks and finalize statuses as DONE/READY atomically."""
        async with self._session_maker() as session:
            async with session.begin():
                await session.execute(
                    delete(DocumentChunk).where(DocumentChunk.document_id == document_id)
                )

                if chunks:
                    chunk_repository = ChunkRepository(session)
                    await chunk_repository.bulk_insert_chunks(document_id, chunks)

                job = await session.get(IngestionJob, job_id, with_for_update=True)
                document = await session.get(Document, document_id, with_for_update=True)
                if job is None or document is None:
                    raise RuntimeError("Ingestion job or document disappeared during finalization.")

                job.status = IngestionJobStatus.DONE
                job.error_message = None
                document.status = DocumentStatus.READY
                document.error_message = None

    async def _persist_failure(
        self,
        *,
        job_id: uuid.UUID,
        document_id: uuid.UUID,
        error: Exception,
    ) -> None:
        """Persist failure details for both the job and document."""
        error_message = self._error_message(error)
        async with self._session_maker() as session:
            async with session.begin():
                job = await session.get(IngestionJob, job_id, with_for_update=True)
                if job is not None and job.status != IngestionJobStatus.DONE:
                    job.status = IngestionJobStatus.FAILED
                    job.error_message = error_message

                document = await session.get(Document, document_id, with_for_update=True)
                if document is not None and document.status != DocumentStatus.READY:
                    document.status = DocumentStatus.FAILED
                    document.error_message = error_message

    async def _pending_job_ids_for_document(self, document_id: uuid.UUID) -> list[uuid.UUID]:
        """Load non-terminal ingestion jobs for a given document id."""
        async with self._session_maker() as session:
            result = await session.scalars(
                select(IngestionJob.id)
                .where(IngestionJob.document_id == document_id)
                .where(
                    IngestionJob.status.in_(
                        (IngestionJobStatus.PENDING, IngestionJobStatus.PROCESSING)
                    )
                )
                .order_by(IngestionJob.created_at.asc())
            )
            return list(result.all())

    async def _enqueue_job_id(self, job_id: uuid.UUID) -> bool:
        """Add a job id to the in-memory queue if not already queued/in-flight."""
        async with self._queue_lock:
            if job_id in self._enqueued_job_ids:
                return False
            self._enqueued_job_ids.add(job_id)

        self._queue.put_nowait(job_id)
        return True

    @staticmethod
    def _to_uuid(value: uuid.UUID | str) -> uuid.UUID:
        if isinstance(value, uuid.UUID):
            return value
        return uuid.UUID(value)

    @staticmethod
    def _error_message(error: Exception) -> str:
        message = f"{type(error).__name__}: {error}".strip()
        if len(message) <= _MAX_ERROR_MESSAGE_LEN:
            return message
        return message[: _MAX_ERROR_MESSAGE_LEN - 3] + "..."


__all__ = ["IngestionManager"]
