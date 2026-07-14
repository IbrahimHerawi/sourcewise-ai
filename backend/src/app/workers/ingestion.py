"""Asynchronous in-process ingestion worker pool."""

from __future__ import annotations

import asyncio
import logging
import uuid
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter
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
from app.utils.files import extract_text

logger = logging.getLogger(__name__)

_STOP_SENTINEL: Final[object] = object()

STORED_FILE_READ_ERROR: Final[str] = "Stored document file could not be read."
TEXT_EXTRACTION_ERROR: Final[str] = "Document text extraction failed."
NO_EXTRACTABLE_TEXT_ERROR: Final[str] = "Document contains no extractable text."
EMBEDDING_GENERATION_ERROR: Final[str] = "Document embedding generation failed."
INGESTION_ERROR: Final[str] = "Document ingestion failed."

_SAFE_FAILURE_MESSAGES: Final[frozenset[str]] = frozenset(
    {
        STORED_FILE_READ_ERROR,
        TEXT_EXTRACTION_ERROR,
        NO_EXTRACTABLE_TEXT_ERROR,
        EMBEDDING_GENERATION_ERROR,
        INGESTION_ERROR,
    }
)


class _IngestionStageError(RuntimeError):
    """Carry an approved user-safe failure message across processing stages."""

    def __init__(self, safe_message: str) -> None:
        super().__init__(safe_message)
        self.safe_message = safe_message


@dataclass(slots=True, frozen=True)
class ClaimedJob:
    """A job that was successfully claimed for processing."""

    job_id: uuid.UUID
    document_id: uuid.UUID
    storage_path: str
    original_extension: str


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
        """Drain workers within the configured deadline, then cancel them."""
        if not self._running:
            return

        self._accept_new_jobs = False
        shutdown_timeout = float(getattr(self._settings, "ingest_shutdown_timeout_s", 30.0))
        timed_out = False
        try:
            await asyncio.wait_for(self._queue.join(), timeout=shutdown_timeout)
        except TimeoutError:
            timed_out = True
            logger.warning(
                "Ingestion shutdown exceeded %.1f seconds; cancelling workers. "
                "Interrupted jobs will be recovered on startup.",
                shutdown_timeout,
            )

        if timed_out:
            for worker in self._workers:
                worker.cancel()
        else:
            for _ in self._workers:
                self._queue.put_nowait(_STOP_SENTINEL)

        if self._workers:
            await asyncio.gather(*self._workers, return_exceptions=True)

        self._workers.clear()
        async with self._queue_lock:
            self._enqueued_job_ids.clear()
        # A timed-out queue can still contain unclaimed PENDING jobs. Replace it so a
        # later start relies solely on persisted startup recovery and cannot duplicate work.
        self._queue = asyncio.Queue()

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
                    .values(status=IngestionJobStatus.PENDING, error_message=None)
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
            logger.info(
                "Recovered and re-enqueued %s pending ingestion jobs.", len(pending_job_ids)
            )

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
                logger.error(
                    "Ingestion worker status=failure worker=%s.",
                    worker_idx,
                )
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
            extracted_text = await self._read_and_extract(claimed)
            if not extracted_text.strip():
                raise _IngestionStageError(NO_EXTRACTABLE_TEXT_ERROR)

            try:
                chunks = [chunk for chunk in chunk_text(extracted_text) if chunk.strip()]
            except Exception as exc:
                raise _IngestionStageError(INGESTION_ERROR) from exc

            if not chunks:
                raise _IngestionStageError(NO_EXTRACTABLE_TEXT_ERROR)

            try:
                embeddings = await embed_documents(
                    chunks,
                    job_id=claimed.job_id,
                    document_id=claimed.document_id,
                )
            except Exception as exc:
                raise _IngestionStageError(EMBEDDING_GENERATION_ERROR) from exc

            if len(chunks) != len(embeddings):
                raise _IngestionStageError(EMBEDDING_GENERATION_ERROR)

            chunk_rows = [
                ChunkWithEmbedding(
                    chunk_index=index,
                    content=chunk,
                    embedding=embedding,
                )
                for index, (chunk, embedding) in enumerate(zip(chunks, embeddings, strict=True))
            ]

            persistence_started_at = perf_counter()
            persistence_status = "failure"
            try:
                await self._persist_success(
                    job_id=claimed.job_id,
                    document_id=claimed.document_id,
                    extracted_text=extracted_text,
                    chunks=chunk_rows,
                )
                persistence_status = "success"
            finally:
                logger.info(
                    "Ingestion persistence summary job_id=%s document_id=%s chunk_count=%s "
                    "duration_s=%.6f status=%s",
                    claimed.job_id,
                    claimed.document_id,
                    len(chunk_rows),
                    perf_counter() - persistence_started_at,
                    persistence_status,
                )
            logger.info(
                "Worker %s completed ingestion job %s (%s chunks).",
                worker_idx,
                claimed.job_id,
                len(chunk_rows),
            )
        except Exception as exc:
            logger.error(
                "Ingestion job status=failure worker=%s job_id=%s document_id=%s.",
                worker_idx,
                claimed.job_id,
                claimed.document_id,
            )
            await self._persist_failure(
                job_id=claimed.job_id,
                document_id=claimed.document_id,
                error_message=self._safe_error_message(exc),
            )

    @staticmethod
    async def _read_and_extract(claimed: ClaimedJob) -> str:
        try:
            content = await asyncio.to_thread(Path(claimed.storage_path).read_bytes)
        except Exception as exc:
            raise _IngestionStageError(STORED_FILE_READ_ERROR) from exc

        try:
            return await asyncio.to_thread(
                extract_text,
                claimed.original_extension,
                content,
            )
        except Exception as exc:
            raise _IngestionStageError(TEXT_EXTRACTION_ERROR) from exc

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
                    job.error_message = INGESTION_ERROR
                    return None

                if document.status != DocumentStatus.PENDING:
                    return None

                job.status = IngestionJobStatus.PROCESSING
                job.error_message = None
                document.status = DocumentStatus.PROCESSING
                document.error_message = None

                return ClaimedJob(
                    job_id=job.id,
                    document_id=document.id,
                    storage_path=document.storage_path,
                    original_extension=document.original_extension,
                )

    async def _persist_success(
        self,
        *,
        job_id: uuid.UUID,
        document_id: uuid.UUID,
        extracted_text: str,
        chunks: list[ChunkWithEmbedding],
    ) -> None:
        """Persist chunks and finalize statuses as DONE/READY atomically."""
        async with self._session_maker() as session:
            async with session.begin():
                job = await session.get(IngestionJob, job_id, with_for_update=True)
                document = await session.get(Document, document_id, with_for_update=True)
                if job is None or document is None:
                    raise RuntimeError("Ingestion job or document disappeared during finalization.")
                if (
                    job.status != IngestionJobStatus.PROCESSING
                    or document.status != DocumentStatus.PROCESSING
                ):
                    raise RuntimeError("Ingestion state changed during finalization.")

                await session.execute(
                    delete(DocumentChunk).where(DocumentChunk.document_id == document_id)
                )

                chunk_repository = ChunkRepository(session)
                await chunk_repository.bulk_insert_chunks(document_id, chunks)

                job.status = IngestionJobStatus.DONE
                job.error_message = None
                document.extracted_text = extracted_text
                document.status = DocumentStatus.READY
                document.error_message = None

    async def _persist_failure(
        self,
        *,
        job_id: uuid.UUID,
        document_id: uuid.UUID,
        error_message: str,
    ) -> None:
        """Persist an approved failure message for both the job and document."""
        if error_message not in _SAFE_FAILURE_MESSAGES:
            raise ValueError("Ingestion failure message is not approved for persistence.")

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
    def _safe_error_message(error: Exception) -> str:
        if isinstance(error, _IngestionStageError):
            return error.safe_message
        return INGESTION_ERROR


__all__ = ["IngestionManager"]
