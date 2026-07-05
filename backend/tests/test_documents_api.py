from __future__ import annotations

from collections.abc import AsyncGenerator, Sequence
from dataclasses import dataclass
from pathlib import Path
from unittest.mock import AsyncMock
from uuid import UUID

import httpx
import pytest
import pytest_asyncio
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import DeclarativeBase

from app.core.settings import get_settings
from app.db.models.documents import Document, DocumentStatus
from app.db.models.ingestion_jobs import IngestionJob, IngestionJobStatus
from app.db.session import get_db_session
from app.main import app
from app.workers.ingestion import IngestionManager


@dataclass(slots=True)
class ApiTestContext:
    client: httpx.AsyncClient
    enqueue_mock: AsyncMock
    upload_root_dir: Path


@pytest.fixture
def upload_test_settings(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> Path:
    monkeypatch.setenv("UPLOAD_ROOT_DIR", str(tmp_path))
    monkeypatch.setenv("MAX_UPLOAD_MB", "1")
    get_settings.cache_clear()
    try:
        yield tmp_path
    finally:
        get_settings.cache_clear()


@pytest_asyncio.fixture
async def api_context(
    db_session: AsyncSession,
    upload_test_settings: Path,
) -> AsyncGenerator[ApiTestContext]:
    async def _override_get_db_session() -> AsyncGenerator[AsyncSession]:
        yield db_session

    original_overrides = app.dependency_overrides.copy()
    original_manager = getattr(app.state, "ingestion_manager", None)

    ingestion_manager = IngestionManager(settings=get_settings())
    enqueue_mock = AsyncMock(return_value=1)
    ingestion_manager.enqueue = enqueue_mock

    app.state.ingestion_manager = ingestion_manager
    app.dependency_overrides[get_db_session] = _override_get_db_session

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield ApiTestContext(
            client=client,
            enqueue_mock=enqueue_mock,
            upload_root_dir=upload_test_settings,
        )

    app.state.ingestion_manager = original_manager
    app.dependency_overrides.clear()
    app.dependency_overrides.update(original_overrides)


async def _upload_text_file(
    client: httpx.AsyncClient,
    *,
    filename: str,
    content: str,
) -> httpx.Response:
    return await client.post(
        "/api/documents/upload",
        files={"file": (filename, content.encode("utf-8"), "text/plain")},
    )


async def _count_rows(session: AsyncSession, model: type[DeclarativeBase]) -> int:
    return int(await session.scalar(select(func.count()).select_from(model)) or 0)


@pytest.mark.asyncio
async def test_upload_document_persists_document_and_pending_job(
    api_context: ApiTestContext,
    db_session: AsyncSession,
) -> None:
    response = await _upload_text_file(
        api_context.client,
        filename="notes.txt",
        content="hello from the upload api test",
    )

    assert response.status_code == 200
    assert response.headers.get("X-Request-ID")

    payload = response.json()
    document_id = UUID(payload["document_id"])
    assert payload["filename"] == "notes.txt"
    assert payload["status"] == DocumentStatus.PENDING.value

    document = await db_session.get(Document, document_id)
    jobs: Sequence[IngestionJob] = list(
        (
            await db_session.scalars(
                select(IngestionJob).where(IngestionJob.document_id == document_id)
            )
        ).all()
    )

    assert document is not None
    assert document.filename == "notes.txt"
    assert document.original_extension == ".txt"
    assert document.size_bytes == len(b"hello from the upload api test")
    assert document.status == DocumentStatus.PENDING
    assert len(jobs) == 1
    assert jobs[0].status == IngestionJobStatus.PENDING

    saved_path = api_context.upload_root_dir / str(document_id) / "notes.txt"
    assert saved_path.exists()
    assert saved_path.read_text(encoding="utf-8") == "hello from the upload api test"

    api_context.enqueue_mock.assert_awaited_once_with(job_id=jobs[0].id)


@pytest.mark.asyncio
async def test_request_id_header_is_echoed(api_context: ApiTestContext) -> None:
    request_id = "integration-test-request-id"
    response = await api_context.client.get(
        "/api/documents",
        headers={"X-Request-ID": request_id},
    )

    assert response.status_code == 200
    assert response.headers.get("X-Request-ID") == request_id


@pytest.mark.asyncio
async def test_get_document_returns_uploaded_document_metadata(
    api_context: ApiTestContext,
) -> None:
    upload_response = await _upload_text_file(
        api_context.client,
        filename="details.txt",
        content="document details text",
    )
    document_id = UUID(upload_response.json()["document_id"])

    response = await api_context.client.get(f"/api/documents/{document_id}")

    assert response.status_code == 200

    payload = response.json()
    assert payload["id"] == str(document_id)
    assert payload["filename"] == "details.txt"
    assert payload["status"] == DocumentStatus.PENDING.value
    assert payload["error_message"] is None
    assert payload["text_length"] == len("document details text")
    assert payload["created_at"]
    assert payload["updated_at"]


@pytest.mark.asyncio
async def test_upload_document_rejects_unsupported_extension(
    api_context: ApiTestContext,
    db_session: AsyncSession,
) -> None:
    response = await api_context.client.post(
        "/api/documents/upload",
        files={"file": ("malware.exe", b"MZ", "application/octet-stream")},
    )

    assert response.status_code == 400
    payload = response.json()
    assert payload["error"]["code"] == "validation_error"
    assert "Unsupported file extension" in payload["error"]["message"]
    assert await _count_rows(db_session, Document) == 0
    assert await _count_rows(db_session, IngestionJob) == 0
    api_context.enqueue_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_upload_document_rejects_file_over_max_upload_size(
    api_context: ApiTestContext,
    db_session: AsyncSession,
) -> None:
    oversized_file = b"a" * ((1024 * 1024) + 1)

    response = await api_context.client.post(
        "/api/documents/upload",
        files={"file": ("too-large.txt", oversized_file, "text/plain")},
    )

    assert response.status_code == 413
    payload = response.json()
    assert payload["error"]["code"] == "validation_error"
    assert "MAX_UPLOAD_MB" in payload["error"]["message"]
    assert await _count_rows(db_session, Document) == 0
    assert await _count_rows(db_session, IngestionJob) == 0
    api_context.enqueue_mock.assert_not_awaited()
