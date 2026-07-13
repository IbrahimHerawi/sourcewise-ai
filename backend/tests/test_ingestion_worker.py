from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from pypdf import PdfWriter
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import app.workers.ingestion as ingestion_worker
from app.db.models.auth import User
from app.db.models.document_chunks import DocumentChunk
from app.db.models.documents import Document, DocumentStatus
from app.db.models.ingestion_jobs import IngestionJob, IngestionJobStatus
from app.repositories.chunk_repository import ChunkRepository
from app.workers.ingestion import (
    EMBEDDING_GENERATION_ERROR,
    INGESTION_ERROR,
    NO_EXTRACTABLE_TEXT_ERROR,
    STORED_FILE_READ_ERROR,
    TEXT_EXTRACTION_ERROR,
    IngestionManager,
)

_EMBEDDING_DIM = 768


@dataclass(slots=True, frozen=True)
class WorkerDatabase:
    session_maker: async_sessionmaker[AsyncSession]
    user_id: UUID


@pytest_asyncio.fixture
async def worker_database(
    postgres_database_url: str,
    migrated_database: None,
) -> AsyncGenerator[WorkerDatabase]:
    engine = create_async_engine(postgres_database_url, pool_pre_ping=True)
    session_maker = async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )
    user_id = uuid4()
    async with session_maker() as session, session.begin():
        session.add(
            User(
                id=user_id,
                email=f"worker-{user_id}@example.com",
                password_hash="test-password-hash",
                first_name="Ingestion",
                last_name="Worker",
                is_email_verified=True,
                is_active=True,
            )
        )

    try:
        yield WorkerDatabase(session_maker=session_maker, user_id=user_id)
    finally:
        async with session_maker() as session, session.begin():
            await session.execute(delete(User).where(User.id == user_id))
        await engine.dispose()


def _settings(*, shutdown_timeout: float = 30.0) -> SimpleNamespace:
    return SimpleNamespace(
        ingest_workers=1,
        ingest_shutdown_timeout_s=shutdown_timeout,
    )


async def _create_job(
    database: WorkerDatabase,
    storage_path: Path,
    *,
    original_extension: str = ".txt",
    document_status: DocumentStatus = DocumentStatus.PENDING,
    job_status: IngestionJobStatus = IngestionJobStatus.PENDING,
) -> tuple[UUID, UUID]:
    document_id = uuid4()
    job_id = uuid4()
    async with database.session_maker() as session, session.begin():
        session.add(
            Document(
                id=document_id,
                user_id=database.user_id,
                collection_id=None,
                filename=storage_path.name,
                original_extension=original_extension,
                content_type="application/pdf" if original_extension == ".pdf" else "text/plain",
                size_bytes=storage_path.stat().st_size if storage_path.exists() else 1,
                storage_path=str(storage_path),
                extracted_text=None,
                status=document_status,
                error_message=None,
            )
        )
        session.add(
            IngestionJob(
                id=job_id,
                document_id=document_id,
                status=job_status,
                error_message=None,
            )
        )
    return document_id, job_id


async def _load_result(
    database: WorkerDatabase,
    *,
    document_id: UUID,
    job_id: UUID,
) -> tuple[Document, IngestionJob, list[DocumentChunk]]:
    async with database.session_maker() as session:
        document = await session.get(Document, document_id)
        job = await session.get(IngestionJob, job_id)
        chunks = list(
            (
                await session.scalars(
                    select(DocumentChunk)
                    .where(DocumentChunk.document_id == document_id)
                    .order_by(DocumentChunk.chunk_index)
                )
            ).all()
        )
    assert document is not None
    assert job is not None
    return document, job, chunks


def _blank_pdf_bytes() -> bytes:
    output = BytesIO()
    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    writer.write(output)
    return output.getvalue()


@pytest.mark.asyncio
async def test_worker_extracts_chunks_embeds_once_per_chunk_and_finalizes_atomically(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    worker_database: WorkerDatabase,
) -> None:
    extracted_text = "alpha source text\nbeta source text"
    storage_path = tmp_path / "source.txt"
    storage_path.write_text(extracted_text, encoding="utf-8")
    document_id, job_id = await _create_job(worker_database, storage_path)
    manager = IngestionManager(
        settings=_settings(),
        session_maker=worker_database.session_maker,
    )
    monkeypatch.setattr(
        ingestion_worker,
        "chunk_text",
        lambda text: ["alpha source text", "   ", "beta source text"],
    )
    embed_mock = AsyncMock(
        return_value=[
            [0.1] * _EMBEDDING_DIM,
            [0.2] * _EMBEDDING_DIM,
        ]
    )
    monkeypatch.setattr(ingestion_worker, "embed_documents", embed_mock)

    await manager._process_job(job_id, worker_idx=1)

    document, job, chunks = await _load_result(
        worker_database,
        document_id=document_id,
        job_id=job_id,
    )
    assert document.status == DocumentStatus.READY
    assert document.extracted_text == extracted_text
    assert document.error_message is None
    assert job.status == IngestionJobStatus.DONE
    assert job.error_message is None
    assert [chunk.content for chunk in chunks] == ["alpha source text", "beta source text"]
    assert [chunk.chunk_index for chunk in chunks] == [0, 1]
    embed_mock.assert_awaited_once_with(["alpha source text", "beta source text"])


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("failure_case", "expected_message"),
    [
        ("unreadable", STORED_FILE_READ_ERROR),
        ("extraction", TEXT_EXTRACTION_ERROR),
        ("blank", NO_EXTRACTABLE_TEXT_ERROR),
        ("image_only_pdf", NO_EXTRACTABLE_TEXT_ERROR),
        ("zero_chunks", NO_EXTRACTABLE_TEXT_ERROR),
        ("chunking", INGESTION_ERROR),
        ("embedding", EMBEDDING_GENERATION_ERROR),
        ("embedding_count", EMBEDDING_GENERATION_ERROR),
        ("finalization", INGESTION_ERROR),
    ],
)
async def test_worker_failure_paths_store_only_approved_messages(
    failure_case: str,
    expected_message: str,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    worker_database: WorkerDatabase,
) -> None:
    extension = ".pdf" if failure_case == "image_only_pdf" else ".txt"
    storage_path = tmp_path / f"{failure_case}{extension}"
    if failure_case == "image_only_pdf":
        storage_path.write_bytes(_blank_pdf_bytes())
    elif failure_case == "blank":
        storage_path.write_text(" \n\t", encoding="utf-8")
    elif failure_case != "unreadable":
        storage_path.write_text("extractable source text", encoding="utf-8")

    document_id, job_id = await _create_job(
        worker_database,
        storage_path,
        original_extension=extension,
    )
    manager = IngestionManager(
        settings=_settings(),
        session_maker=worker_database.session_maker,
    )

    async def _successful_embeddings(chunks: list[str]) -> list[list[float]]:
        return [[0.1] * _EMBEDDING_DIM for _ in chunks]

    monkeypatch.setattr(ingestion_worker, "embed_documents", _successful_embeddings)

    if failure_case == "extraction":

        def _fail_extraction(extension: str, content: bytes) -> str:
            raise RuntimeError("password=raw-extraction-secret")

        monkeypatch.setattr(ingestion_worker, "extract_text", _fail_extraction)
    elif failure_case == "zero_chunks":
        monkeypatch.setattr(ingestion_worker, "chunk_text", lambda text: [])
    elif failure_case == "chunking":

        def _fail_chunking(text: str) -> list[str]:
            raise RuntimeError("token=raw-chunking-secret")

        monkeypatch.setattr(ingestion_worker, "chunk_text", _fail_chunking)
    elif failure_case == "embedding":
        monkeypatch.setattr(
            ingestion_worker,
            "embed_documents",
            AsyncMock(side_effect=RuntimeError("api_key=raw-embedding-secret")),
        )
    elif failure_case == "embedding_count":
        monkeypatch.setattr(ingestion_worker, "embed_documents", AsyncMock(return_value=[]))
    elif failure_case == "finalization":
        monkeypatch.setattr(
            ChunkRepository,
            "bulk_insert_chunks",
            AsyncMock(side_effect=RuntimeError("secret=raw-database-secret")),
        )

    await manager._process_job(job_id, worker_idx=1)

    document, job, chunks = await _load_result(
        worker_database,
        document_id=document_id,
        job_id=job_id,
    )
    assert document.status == DocumentStatus.FAILED
    assert job.status == IngestionJobStatus.FAILED
    assert document.error_message == expected_message
    assert job.error_message == expected_message
    assert document.extracted_text is None
    assert chunks == []
    assert "raw-" not in document.error_message
    assert "raw-" not in job.error_message


@pytest.mark.asyncio
async def test_row_lock_claim_allows_only_one_worker_and_requires_pending_document(
    tmp_path: Path,
    worker_database: WorkerDatabase,
) -> None:
    storage_path = tmp_path / "claim.txt"
    storage_path.write_text("claimable", encoding="utf-8")
    document_id, job_id = await _create_job(worker_database, storage_path)
    first_manager = IngestionManager(
        settings=_settings(),
        session_maker=worker_database.session_maker,
    )
    second_manager = IngestionManager(
        settings=_settings(),
        session_maker=worker_database.session_maker,
    )

    claims = await asyncio.gather(
        first_manager._claim_job(job_id),
        second_manager._claim_job(job_id),
    )

    assert sum(claim is not None for claim in claims) == 1
    claimed = next(claim for claim in claims if claim is not None)
    assert claimed.storage_path == str(storage_path)
    assert claimed.original_extension == ".txt"
    document, job, _ = await _load_result(
        worker_database,
        document_id=document_id,
        job_id=job_id,
    )
    assert document.status == DocumentStatus.PROCESSING
    assert job.status == IngestionJobStatus.PROCESSING

    ready_path = tmp_path / "ready.txt"
    ready_path.write_text("already ready", encoding="utf-8")
    ready_document_id, pending_job_id = await _create_job(
        worker_database,
        ready_path,
        document_status=DocumentStatus.READY,
    )
    assert await first_manager._claim_job(pending_job_id) is None
    ready_document, pending_job, _ = await _load_result(
        worker_database,
        document_id=ready_document_id,
        job_id=pending_job_id,
    )
    assert ready_document.status == DocumentStatus.READY
    assert pending_job.status == IngestionJobStatus.PENDING


@pytest.mark.asyncio
async def test_startup_recovers_pending_and_interrupted_jobs_but_not_failed_jobs(
    tmp_path: Path,
    worker_database: WorkerDatabase,
) -> None:
    paths = [tmp_path / f"recovery-{index}.txt" for index in range(4)]
    for path in paths:
        path.write_text("recoverable", encoding="utf-8")

    pending_document_id, pending_job_id = await _create_job(worker_database, paths[0])
    interrupted_document_id, interrupted_job_id = await _create_job(
        worker_database,
        paths[1],
        document_status=DocumentStatus.PROCESSING,
        job_status=IngestionJobStatus.PROCESSING,
    )
    failed_document_id, failed_job_id = await _create_job(
        worker_database,
        paths[2],
        document_status=DocumentStatus.FAILED,
        job_status=IngestionJobStatus.FAILED,
    )
    done_document_id, done_job_id = await _create_job(
        worker_database,
        paths[3],
        document_status=DocumentStatus.READY,
        job_status=IngestionJobStatus.DONE,
    )
    manager = IngestionManager(
        settings=_settings(),
        session_maker=worker_database.session_maker,
    )

    await manager._recover_jobs_on_startup()

    queued_job_ids = {manager._queue.get_nowait(), manager._queue.get_nowait()}
    assert queued_job_ids == {pending_job_id, interrupted_job_id}
    assert manager._queue.empty()

    pending_document, pending_job, _ = await _load_result(
        worker_database,
        document_id=pending_document_id,
        job_id=pending_job_id,
    )
    interrupted_document, interrupted_job, _ = await _load_result(
        worker_database,
        document_id=interrupted_document_id,
        job_id=interrupted_job_id,
    )
    failed_document, failed_job, _ = await _load_result(
        worker_database,
        document_id=failed_document_id,
        job_id=failed_job_id,
    )
    done_document, done_job, _ = await _load_result(
        worker_database,
        document_id=done_document_id,
        job_id=done_job_id,
    )
    assert (pending_document.status, pending_job.status) == (
        DocumentStatus.PENDING,
        IngestionJobStatus.PENDING,
    )
    assert (interrupted_document.status, interrupted_job.status) == (
        DocumentStatus.PENDING,
        IngestionJobStatus.PENDING,
    )
    assert (failed_document.status, failed_job.status) == (
        DocumentStatus.FAILED,
        IngestionJobStatus.FAILED,
    )
    assert (done_document.status, done_job.status) == (
        DocumentStatus.READY,
        IngestionJobStatus.DONE,
    )


@pytest.mark.asyncio
async def test_shutdown_timeout_cancels_worker_and_leaves_claimed_job_processing(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    worker_database: WorkerDatabase,
) -> None:
    storage_path = tmp_path / "interrupted.txt"
    storage_path.write_text("processing at shutdown", encoding="utf-8")
    document_id, job_id = await _create_job(worker_database, storage_path)
    manager = IngestionManager(
        settings=_settings(shutdown_timeout=0.01),
        session_maker=worker_database.session_maker,
    )
    processing_started = asyncio.Event()
    worker_cancelled = asyncio.Event()

    async def _block_after_claim(claimed: ingestion_worker.ClaimedJob) -> str:
        processing_started.set()
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            worker_cancelled.set()
            raise

    monkeypatch.setattr(manager, "_read_and_extract", _block_after_claim)

    await manager.start()
    await asyncio.wait_for(processing_started.wait(), timeout=1.0)
    await manager.stop()

    assert worker_cancelled.is_set()
    assert manager._workers == []
    assert manager._queue.empty()
    document, job, _ = await _load_result(
        worker_database,
        document_id=document_id,
        job_id=job_id,
    )
    assert document.status == DocumentStatus.PROCESSING
    assert job.status == IngestionJobStatus.PROCESSING


@pytest.mark.asyncio
async def test_failure_persistence_rejects_unapproved_message(
    worker_database: WorkerDatabase,
) -> None:
    manager = IngestionManager(
        settings=_settings(),
        session_maker=worker_database.session_maker,
    )

    with pytest.raises(ValueError, match="not approved"):
        await manager._persist_failure(
            job_id=uuid4(),
            document_id=uuid4(),
            error_message="RuntimeError: raw internal detail",
        )
