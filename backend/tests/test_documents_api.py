from __future__ import annotations

from collections.abc import AsyncGenerator, Sequence
from dataclasses import dataclass
from pathlib import Path
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import httpx
import pytest
import pytest_asyncio
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import DeclarativeBase

from app.core.security import create_access_token
from app.core.settings import get_settings
from app.db.models.auth import User
from app.db.models.documents import Document, DocumentStatus
from app.db.models.ingestion_jobs import IngestionJob, IngestionJobStatus
from app.db.session import get_db_session
from app.main import app
from app.repositories.document_repository import DocumentRepository
from app.repositories.user_repository import UserRepository
from app.workers.ingestion import IngestionManager

SAFE_DOCUMENT_FIELDS = {
    "id",
    "collection_id",
    "filename",
    "original_extension",
    "content_type",
    "size_bytes",
    "status",
    "error_message",
    "created_at",
    "updated_at",
}


@dataclass(slots=True)
class ApiTestContext:
    client: httpx.AsyncClient
    enqueue_mock: AsyncMock
    upload_root_dir: Path
    current_user: User

    @property
    def auth_headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {create_access_token(self.current_user.id)}"}


@pytest.fixture
def upload_test_settings(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> Path:
    monkeypatch.setenv("UPLOAD_ROOT_DIR", str(tmp_path))
    monkeypatch.setenv("MAX_UPLOAD_MB", "1")
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("SECRET_KEY", "test-secret-key-with-enough-length")
    monkeypatch.setenv("JWT_ALGORITHM", "HS256")
    monkeypatch.setenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30")
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
    current_user = await UserRepository(db_session).create_user(
        email=f"documents-api-{uuid4()}@example.com",
        password_hash="test-password-hash",
        first_name="Document",
        last_name="Tester",
        is_active=True,
        is_email_verified=True,
    )

    app.state.ingestion_manager = ingestion_manager
    app.dependency_overrides[get_db_session] = _override_get_db_session

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield ApiTestContext(
            client=client,
            enqueue_mock=enqueue_mock,
            upload_root_dir=upload_test_settings,
            current_user=current_user,
        )

    app.state.ingestion_manager = original_manager
    app.dependency_overrides.clear()
    app.dependency_overrides.update(original_overrides)


async def _upload_text_file(
    client: httpx.AsyncClient,
    *,
    headers: dict[str, str],
    filename: str,
    content: str,
) -> httpx.Response:
    return await client.post(
        "/api/v1/documents/upload",
        headers=headers,
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
        headers=api_context.auth_headers,
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
    assert document.user_id == api_context.current_user.id
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
        "/api/v1/documents",
        headers={**api_context.auth_headers, "X-Request-ID": request_id},
    )

    assert response.status_code == 200
    assert response.headers.get("X-Request-ID") == request_id


@pytest.mark.asyncio
async def test_get_document_returns_uploaded_document_metadata(
    api_context: ApiTestContext,
) -> None:
    upload_response = await _upload_text_file(
        api_context.client,
        headers=api_context.auth_headers,
        filename="details.txt",
        content="document details text",
    )
    document_id = UUID(upload_response.json()["document_id"])

    response = await api_context.client.get(
        f"/api/v1/documents/{document_id}",
        headers=api_context.auth_headers,
    )

    assert response.status_code == 200

    payload = response.json()
    assert set(payload) == SAFE_DOCUMENT_FIELDS
    assert payload["id"] == str(document_id)
    assert payload["collection_id"] is None
    assert payload["filename"] == "details.txt"
    assert payload["original_extension"] == ".txt"
    assert payload["content_type"] == "text/plain"
    assert payload["size_bytes"] == len(b"document details text")
    assert payload["status"] == DocumentStatus.PENDING.value
    assert payload["error_message"] is None
    assert payload["created_at"]
    assert payload["updated_at"]


@pytest.mark.asyncio
async def test_upload_document_rejects_unsupported_extension(
    api_context: ApiTestContext,
    db_session: AsyncSession,
) -> None:
    response = await api_context.client.post(
        "/api/v1/documents/upload",
        headers=api_context.auth_headers,
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
        "/api/v1/documents/upload",
        headers=api_context.auth_headers,
        files={"file": ("too-large.txt", oversized_file, "text/plain")},
    )

    assert response.status_code == 413
    payload = response.json()
    assert payload["error"]["code"] == "validation_error"
    assert "MAX_UPLOAD_MB" in payload["error"]["message"]
    assert await _count_rows(db_session, Document) == 0
    assert await _count_rows(db_session, IngestionJob) == 0
    api_context.enqueue_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_document_endpoints_require_authentication(
    api_context: ApiTestContext,
) -> None:
    responses = (
        await api_context.client.get("/api/v1/documents"),
        await api_context.client.get(f"/api/v1/documents/{uuid4()}"),
        await api_context.client.post(
            "/api/v1/documents/upload",
            files={"file": ("unauthenticated.txt", b"private", "text/plain")},
        ),
    )

    for response in responses:
        assert response.status_code == 401
        assert response.json() == {
            "error": {
                "code": "unauthorized",
                "message": "Authentication credentials could not be validated.",
            }
        }

    missing_file_response = await api_context.client.post("/api/v1/documents/upload")
    assert missing_file_response.status_code == 401


@pytest.mark.asyncio
async def test_document_endpoints_require_verified_user(
    api_context: ApiTestContext,
    db_session: AsyncSession,
) -> None:
    unverified_user = await UserRepository(db_session).create_user(
        email=f"unverified-documents-{uuid4()}@example.com",
        password_hash="test-password-hash",
        first_name="Unverified",
        last_name="Tester",
        is_active=True,
        is_email_verified=False,
    )
    headers = {
        "Authorization": f"Bearer {create_access_token(unverified_user.id)}",
    }
    responses = (
        await api_context.client.get("/api/v1/documents", headers=headers),
        await api_context.client.get(
            f"/api/v1/documents/{uuid4()}",
            headers=headers,
        ),
        await api_context.client.post(
            "/api/v1/documents/upload",
            headers=headers,
            files={"file": ("unverified.txt", b"private", "text/plain")},
        ),
    )

    for response in responses:
        assert response.status_code == 403
        assert response.json() == {
            "error": {
                "code": "forbidden",
                "message": "User email is not verified.",
            }
        }


@pytest.mark.asyncio
async def test_get_document_returns_same_404_for_foreign_and_missing_ids(
    api_context: ApiTestContext,
    db_session: AsyncSession,
) -> None:
    other_user = await UserRepository(db_session).create_user(
        email=f"foreign-document-{uuid4()}@example.com",
        password_hash="test-password-hash",
        first_name="Foreign",
        last_name="Owner",
        is_active=True,
        is_email_verified=True,
    )
    foreign_document = await DocumentRepository(db_session).create_document(
        other_user.id,
        filename="foreign.txt",
        original_extension=".txt",
        content_type="text/plain",
        size_bytes=7,
        storage_path="/private/foreign.txt",
        extracted_text="private",
    )

    foreign_response = await api_context.client.get(
        f"/api/v1/documents/{foreign_document.id}",
        headers=api_context.auth_headers,
    )
    missing_response = await api_context.client.get(
        f"/api/v1/documents/{uuid4()}",
        headers=api_context.auth_headers,
    )

    assert foreign_response.status_code == 404
    assert foreign_response.json() == missing_response.json() == {
        "error": {
            "code": "not_found",
            "message": "Document not found.",
        }
    }
