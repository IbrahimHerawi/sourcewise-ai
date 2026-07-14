from __future__ import annotations

from collections.abc import AsyncGenerator
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, call
from uuid import UUID, uuid4

import httpx
import pytest
import pytest_asyncio
from fastapi import UploadFile
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import DeclarativeBase

from app.api.schemas.documents import DocumentUploadRequest
from app.api.v1.endpoints import documents as documents_endpoint
from app.core.security import create_access_token
from app.core.settings import get_settings
from app.db.models.auth import User
from app.db.models.document_chunks import DocumentChunk
from app.db.models.documents import Document, DocumentStatus
from app.db.models.ingestion_jobs import IngestionJob, IngestionJobStatus
from app.db.models.question_context_chunks import QuestionContextChunk
from app.db.models.questions import Question
from app.db.session import get_db_session
from app.main import app
from app.repositories.collection_repository import CollectionRepository
from app.repositories.document_repository import DocumentRepository
from app.repositories.ingestion_job_repository import IngestionJobRepository
from app.repositories.user_repository import UserRepository
from app.utils.files import UploadValidationError
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


async def _upload_text_files(
    client: httpx.AsyncClient,
    *,
    headers: dict[str, str],
    uploads: list[tuple[str, bytes]],
    collection_id: UUID | None = None,
) -> httpx.Response:
    data = {}
    if collection_id is not None:
        data["collection_id"] = str(collection_id)
    return await client.post(
        "/api/v1/documents/upload",
        headers=headers,
        data=data,
        files=[
            ("files", (filename, content, "application/octet-stream"))
            for filename, content in uploads
        ],
    )


async def _upload_text_file(
    client: httpx.AsyncClient,
    *,
    headers: dict[str, str],
    filename: str,
    content: str,
    collection_id: UUID | None = None,
) -> httpx.Response:
    return await _upload_text_files(
        client,
        headers=headers,
        uploads=[(filename, content.encode("utf-8"))],
        collection_id=collection_id,
    )


async def _count_rows(session: AsyncSession, model: type[DeclarativeBase]) -> int:
    return int(await session.scalar(select(func.count()).select_from(model)) or 0)


@pytest.mark.asyncio
async def test_upload_batch_persists_all_documents_and_pending_jobs(
    api_context: ApiTestContext,
    db_session: AsyncSession,
) -> None:
    collection = await CollectionRepository(db_session).create_collection(
        api_context.current_user.id,
        "Batch collection",
    )
    await db_session.commit()
    enqueue_transaction_states: list[bool] = []

    async def _record_enqueue(*, job_id: UUID) -> int:
        del job_id
        enqueue_transaction_states.append(db_session.in_transaction())
        return 1

    api_context.enqueue_mock.side_effect = _record_enqueue
    uploaded_files = [
        ("duplicate.txt", b"first duplicate"),
        ("duplicate.txt", b"second duplicate"),
        ("notes.md", b"batch notes"),
    ]
    response = await _upload_text_files(
        api_context.client,
        headers=api_context.auth_headers,
        uploads=uploaded_files,
        collection_id=collection.id,
    )

    assert response.status_code == 202
    assert response.headers.get("X-Request-ID")

    items = response.json()["items"]
    assert all(
        set(item) == {"document_id", "filename", "collection_id", "status"}
        for item in items
    )
    assert [item["filename"] for item in items] == [name for name, _ in uploaded_files]
    assert all(item["collection_id"] == str(collection.id) for item in items)
    assert all(item["status"] == DocumentStatus.PENDING.value for item in items)

    jobs = []
    for item, (filename, content) in zip(items, uploaded_files, strict=True):
        document_id = UUID(item["document_id"])
        document = await db_session.get(Document, document_id)
        job = await db_session.scalar(
            select(IngestionJob).where(IngestionJob.document_id == document_id)
        )

        assert document is not None
        assert document.user_id == api_context.current_user.id
        assert document.collection_id == collection.id
        assert document.filename == filename
        assert document.original_extension == Path(filename).suffix
        assert document.content_type in {"text/plain", "text/markdown"}
        assert document.size_bytes == len(content)
        assert document.extracted_text is None
        assert document.error_message is None
        assert document.status == DocumentStatus.PENDING
        assert job is not None
        assert job.status == IngestionJobStatus.PENDING
        assert job.error_message is None
        jobs.append(job)

        saved_path = api_context.upload_root_dir / str(document_id) / filename
        assert saved_path.read_bytes() == content

    assert enqueue_transaction_states == [False, False, False]
    assert api_context.enqueue_mock.await_args_list == [
        call(job_id=job.id) for job in jobs
    ]


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
    assert upload_response.status_code == 202
    document_id = UUID(upload_response.json()["items"][0]["document_id"])

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
@pytest.mark.parametrize("file_count", [0, 4])
async def test_upload_batch_rejects_file_count_outside_one_to_three(
    api_context: ApiTestContext,
    db_session: AsyncSession,
    file_count: int,
) -> None:
    request_kwargs = {}
    if file_count:
        request_kwargs["files"] = [
            ("files", (f"file-{index}.txt", b"content", "text/plain"))
            for index in range(file_count)
        ]

    response = await api_context.client.post(
        "/api/v1/documents/upload",
        headers=api_context.auth_headers,
        **request_kwargs,
    )

    assert response.status_code == 400
    assert response.json() == {
        "error": {
            "code": "validation_error",
            "message": "Multipart field 'files' must contain between 1 and 3 files.",
        }
    }
    assert await _count_rows(db_session, Document) == 0
    assert await _count_rows(db_session, IngestionJob) == 0
    assert not list(api_context.upload_root_dir.rglob("*"))
    api_context.enqueue_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_upload_batch_returns_same_404_for_missing_and_foreign_collection_before_staging(
    api_context: ApiTestContext,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    other_user = await UserRepository(db_session).create_user(
        email=f"foreign-collection-upload-{uuid4()}@example.com",
        password_hash="test-password-hash",
        first_name="Foreign",
        last_name="Owner",
        is_active=True,
        is_email_verified=True,
    )
    foreign_collection = await CollectionRepository(db_session).create_collection(
        other_user.id,
        "Foreign upload collection",
    )
    await db_session.commit()
    save_mock = AsyncMock()
    monkeypatch.setattr(documents_endpoint, "save_validated_upload", save_mock)

    responses = [
        await _upload_text_file(
            api_context.client,
            headers=api_context.auth_headers,
            filename="private.txt",
            content="private",
            collection_id=collection_id,
        )
        for collection_id in (foreign_collection.id, uuid4())
    ]

    for response in responses:
        assert response.status_code == 404
        assert response.json() == {
            "error": {
                "code": "not_found",
                "message": "Collection not found.",
            }
        }
    save_mock.assert_not_awaited()
    assert await _count_rows(db_session, Document) == 0
    assert await _count_rows(db_session, IngestionJob) == 0
    assert not list(api_context.upload_root_dir.rglob("*"))
    api_context.enqueue_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_upload_document_rejects_unsupported_extension(
    api_context: ApiTestContext,
    db_session: AsyncSession,
) -> None:
    response = await _upload_text_files(
        api_context.client,
        headers=api_context.auth_headers,
        uploads=[("valid.txt", b"staged first"), ("malware.exe", b"MZ")],
    )

    assert response.status_code == 400
    payload = response.json()
    assert payload["error"]["code"] == "validation_error"
    assert "Unsupported file extension" in payload["error"]["message"]
    assert await _count_rows(db_session, Document) == 0
    assert await _count_rows(db_session, IngestionJob) == 0
    assert not list(api_context.upload_root_dir.rglob("*"))
    api_context.enqueue_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_upload_document_rejects_file_over_max_upload_size(
    api_context: ApiTestContext,
    db_session: AsyncSession,
) -> None:
    oversized_file = b"a" * ((1024 * 1024) + 1)

    response = await _upload_text_files(
        api_context.client,
        headers=api_context.auth_headers,
        uploads=[("valid.txt", b"staged first"), ("too-large.txt", oversized_file)],
    )

    assert response.status_code == 413
    payload = response.json()
    assert payload["error"]["code"] == "validation_error"
    assert "MAX_UPLOAD_MB" in payload["error"]["message"]
    assert await _count_rows(db_session, Document) == 0
    assert await _count_rows(db_session, IngestionJob) == 0
    assert not list(api_context.upload_root_dir.rglob("*"))
    api_context.enqueue_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_upload_batch_cleans_staged_files_when_later_storage_write_fails(
    api_context: ApiTestContext,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_save = documents_endpoint.save_validated_upload
    save_count = 0

    async def _fail_second_save(upload: UploadFile, document_id: UUID):
        nonlocal save_count
        save_count += 1
        if save_count == 2:
            raise OSError("forced storage failure")
        return await original_save(upload, document_id)

    monkeypatch.setattr(
        documents_endpoint,
        "save_validated_upload",
        _fail_second_save,
    )

    response = await _upload_text_files(
        api_context.client,
        headers=api_context.auth_headers,
        uploads=[("first.txt", b"staged first"), ("second.txt", b"fails")],
    )

    assert response.status_code == 500
    assert response.json() == {
        "error": {
            "code": "file_persistence_error",
            "message": "Failed to persist uploaded file.",
        }
    }
    assert await _count_rows(db_session, Document) == 0
    assert await _count_rows(db_session, IngestionJob) == 0
    assert not list(api_context.upload_root_dir.rglob("*"))
    api_context.enqueue_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_upload_batch_rolls_back_all_rows_and_cleans_files_on_db_failure(
    api_context: ApiTestContext,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_create_job = IngestionJobRepository.create_job
    call_count = 0

    async def _fail_second_job(
        repository: IngestionJobRepository,
        *,
        document_id: UUID,
        status: IngestionJobStatus = IngestionJobStatus.PENDING,
        error_message: str | None = None,
    ) -> IngestionJob:
        nonlocal call_count
        call_count += 1
        if call_count == 2:
            raise RuntimeError("forced database failure")
        return await original_create_job(
            repository,
            document_id=document_id,
            status=status,
            error_message=error_message,
        )

    monkeypatch.setattr(IngestionJobRepository, "create_job", _fail_second_job)

    response = await _upload_text_files(
        api_context.client,
        headers=api_context.auth_headers,
        uploads=[("first.txt", b"first"), ("second.txt", b"second")],
    )

    assert response.status_code == 500
    assert response.json() == {
        "error": {
            "code": "internal_server_error",
            "message": "Failed to persist document metadata.",
        }
    }
    assert await _count_rows(db_session, Document) == 0
    assert await _count_rows(db_session, IngestionJob) == 0
    assert not list(api_context.upload_root_dir.rglob("*"))
    api_context.enqueue_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_upload_batch_returns_202_and_logs_redacted_warning_when_enqueue_fails(
    api_context: ApiTestContext,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    api_context.enqueue_mock.side_effect = RuntimeError(
        "secret failure mentioning redacted-name.txt"
    )
    warning_mock = MagicMock()
    monkeypatch.setattr(documents_endpoint.logger, "warning", warning_mock)

    response = await _upload_text_files(
        api_context.client,
        headers=api_context.auth_headers,
        uploads=[
            ("redacted-name.txt", b"first pending document"),
            ("also-redacted.md", b"second pending document"),
        ],
    )

    assert response.status_code == 202
    items = response.json()["items"]
    assert len(items) == 2
    assert api_context.enqueue_mock.await_count == 2

    for item in items:
        document_id = UUID(item["document_id"])
        document = await db_session.get(Document, document_id)
        job = await db_session.scalar(
            select(IngestionJob).where(IngestionJob.document_id == document_id)
        )
        assert document is not None
        assert document.status == DocumentStatus.PENDING
        assert job is not None
        assert job.status == IngestionJobStatus.PENDING

    warning_mock.assert_called_once_with(
        "One or more committed ingestion jobs could not be enqueued; "
        "startup recovery will retry them."
    )
    warning = warning_mock.call_args.args[0]
    assert "redacted-name.txt" not in warning
    assert "also-redacted.md" not in warning
    assert "secret failure" not in warning
    assert all(item["document_id"] not in warning for item in items)


@pytest.mark.asyncio
async def test_upload_document_always_closes_upload_file_after_validation_failure(
    api_context: ApiTestContext,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    uploads = [
        UploadFile(file=BytesIO(b"content"), filename="invalid.exe"),
        UploadFile(file=BytesIO(b"unread"), filename="unread.txt"),
    ]
    for upload in uploads:
        upload.close = AsyncMock(wraps=upload.close)

    async def _override_upload_request() -> DocumentUploadRequest:
        return DocumentUploadRequest(files=uploads)

    save_mock = AsyncMock(
        side_effect=UploadValidationError("Unsupported file extension."),
    )
    monkeypatch.setattr(documents_endpoint, "save_validated_upload", save_mock)
    app.dependency_overrides[documents_endpoint._build_upload_request] = (
        _override_upload_request
    )

    try:
        response = await api_context.client.post(
            "/api/v1/documents/upload",
            headers=api_context.auth_headers,
        )
    finally:
        app.dependency_overrides.pop(documents_endpoint._build_upload_request, None)

    assert response.status_code == 400
    save_mock.assert_awaited_once()
    for upload in uploads:
        upload.close.assert_awaited_once_with()


@pytest.mark.asyncio
async def test_document_endpoints_require_authentication(
    api_context: ApiTestContext,
) -> None:
    responses = (
        await api_context.client.get("/api/v1/documents"),
        await api_context.client.get(f"/api/v1/documents/{uuid4()}"),
        await api_context.client.post(
            "/api/v1/documents/upload",
            files={"files": ("unauthenticated.txt", b"private", "text/plain")},
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
        await api_context.client.delete(
            f"/api/v1/documents/{uuid4()}",
            headers=headers,
        ),
        await api_context.client.post(
            "/api/v1/documents/upload",
            headers=headers,
            files={"files": ("unverified.txt", b"private", "text/plain")},
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


@pytest.mark.asyncio
async def test_delete_document_cascades_live_rows_and_preserves_citation_history(
    api_context: ApiTestContext,
    db_session: AsyncSession,
) -> None:
    upload_response = await _upload_text_file(
        api_context.client,
        headers=api_context.auth_headers,
        filename="cited.txt",
        content="durable cited content",
    )
    document_id = UUID(upload_response.json()["items"][0]["document_id"])
    document_path = api_context.upload_root_dir / str(document_id) / "cited.txt"
    job_id = await db_session.scalar(
        select(IngestionJob.id).where(IngestionJob.document_id == document_id)
    )
    assert job_id is not None

    embedding = [0.0] * get_settings().embedding_dim
    chunk = DocumentChunk(
        document_id=document_id,
        chunk_index=0,
        content="durable cited content",
        embedding=embedding,
    )
    question = Question(
        user_id=api_context.current_user.id,
        collection_id=None,
        question_text="What is cited?",
        question_embedding=embedding,
        answer_text="The durable content.",
        ai_provider="ollama",
        model_used="test-model",
    )
    db_session.add_all([chunk, question])
    await db_session.flush()
    snapshot = QuestionContextChunk(
        question_id=question.id,
        rank=1,
        document_id=document_id,
        document_filename="cited.txt",
        chunk_id=chunk.id,
        chunk_index=0,
        chunk_content=chunk.content,
        similarity_score=0.99,
    )
    db_session.add(snapshot)
    await db_session.commit()

    response = await api_context.client.delete(
        f"/api/v1/documents/{document_id}",
        headers=api_context.auth_headers,
    )

    assert response.status_code == 204
    assert response.content == b""
    assert await db_session.scalar(
        select(Document.id).where(Document.id == document_id)
    ) is None
    assert await db_session.scalar(
        select(IngestionJob.id).where(IngestionJob.id == job_id)
    ) is None
    assert await db_session.scalar(
        select(DocumentChunk.id).where(DocumentChunk.id == chunk.id)
    ) is None
    assert await db_session.scalar(
        select(Question.id).where(Question.id == question.id)
    ) == question.id
    preserved_snapshot = await db_session.scalar(
        select(QuestionContextChunk).where(
            QuestionContextChunk.question_id == question.id,
            QuestionContextChunk.rank == 1,
        )
    )
    assert preserved_snapshot is not None
    assert preserved_snapshot.document_id == document_id
    assert preserved_snapshot.chunk_content == "durable cited content"
    assert not document_path.exists()
    assert not document_path.parent.exists()


@pytest.mark.asyncio
async def test_delete_document_returns_same_404_for_foreign_and_missing_ids(
    api_context: ApiTestContext,
    db_session: AsyncSession,
) -> None:
    other_user = await UserRepository(db_session).create_user(
        email=f"foreign-delete-{uuid4()}@example.com",
        password_hash="test-password-hash",
        first_name="Foreign",
        last_name="Owner",
        is_active=True,
        is_email_verified=True,
    )
    foreign_id = uuid4()
    foreign_dir = api_context.upload_root_dir / str(foreign_id)
    foreign_dir.mkdir()
    foreign_path = foreign_dir / "foreign.txt"
    foreign_path.write_text("private", encoding="utf-8")
    foreign_document = await DocumentRepository(db_session).create_document(
        other_user.id,
        id=foreign_id,
        filename=foreign_path.name,
        original_extension=".txt",
        content_type="text/plain",
        size_bytes=7,
        storage_path=str(foreign_path),
        extracted_text="private",
    )
    await db_session.commit()

    foreign_response = await api_context.client.delete(
        f"/api/v1/documents/{foreign_document.id}",
        headers=api_context.auth_headers,
    )
    missing_response = await api_context.client.delete(
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
    assert await db_session.get(Document, foreign_document.id) is not None
    assert foreign_path.read_text(encoding="utf-8") == "private"


@pytest.mark.asyncio
async def test_delete_document_succeeds_when_stored_file_is_missing(
    api_context: ApiTestContext,
    db_session: AsyncSession,
) -> None:
    document_id = uuid4()
    await DocumentRepository(db_session).create_document(
        api_context.current_user.id,
        id=document_id,
        filename="missing.txt",
        original_extension=".txt",
        content_type="text/plain",
        size_bytes=1,
        storage_path=str(
            api_context.upload_root_dir / str(document_id) / "missing.txt"
        ),
        extracted_text=None,
    )
    await db_session.commit()

    response = await api_context.client.delete(
        f"/api/v1/documents/{document_id}",
        headers=api_context.auth_headers,
    )

    assert response.status_code == 204
    assert await db_session.get(Document, document_id) is None


@pytest.mark.asyncio
async def test_delete_document_refuses_unsafe_path_after_database_commit(
    api_context: ApiTestContext,
    db_session: AsyncSession,
    caplog: pytest.LogCaptureFixture,
    tmp_path: Path,
) -> None:
    document_id = uuid4()
    unsafe_path = tmp_path / "outside.txt"
    unsafe_path.write_text("must remain", encoding="utf-8")
    await DocumentRepository(db_session).create_document(
        api_context.current_user.id,
        id=document_id,
        filename=unsafe_path.name,
        original_extension=".txt",
        content_type="text/plain",
        size_bytes=11,
        storage_path=str(unsafe_path),
        extracted_text="must remain",
    )
    await db_session.commit()

    with caplog.at_level("WARNING", logger=documents_endpoint.__name__):
        response = await api_context.client.delete(
            f"/api/v1/documents/{document_id}",
            headers=api_context.auth_headers,
        )

    assert response.status_code == 204
    assert await db_session.get(Document, document_id) is None
    assert unsafe_path.read_text(encoding="utf-8") == "must remain"
    assert str(unsafe_path) not in caplog.text


@pytest.mark.asyncio
async def test_delete_document_database_rollback_leaves_stored_file(
    api_context: ApiTestContext,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    upload_response = await _upload_text_file(
        api_context.client,
        headers=api_context.auth_headers,
        filename="rollback.txt",
        content="must remain after rollback",
    )
    document_id = UUID(upload_response.json()["items"][0]["document_id"])
    document_path = api_context.upload_root_dir / str(document_id) / "rollback.txt"
    original_delete_document = DocumentRepository.delete_document

    async def _fail_delete_in_savepoint(
        repository: DocumentRepository,
        user_id: UUID,
        requested_document_id: UUID,
    ) -> None:
        async with db_session.begin_nested():
            deleted = await original_delete_document(
                repository,
                user_id,
                requested_document_id,
            )
            assert deleted is not None
            raise RuntimeError("forced database failure")

    monkeypatch.setattr(
        DocumentRepository,
        "delete_document",
        _fail_delete_in_savepoint,
    )

    with pytest.raises(RuntimeError, match="forced database failure"):
        await api_context.client.delete(
            f"/api/v1/documents/{document_id}",
            headers=api_context.auth_headers,
        )

    assert await db_session.scalar(
        select(Document.id).where(Document.id == document_id)
    ) == document_id
    assert document_path.read_text(encoding="utf-8") == "must remain after rollback"


@pytest.mark.asyncio
async def test_delete_document_cleanup_failure_is_redacted_and_returns_204(
    api_context: ApiTestContext,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    upload_response = await _upload_text_file(
        api_context.client,
        headers=api_context.auth_headers,
        filename="cleanup.txt",
        content="committed first",
    )
    document_id = UUID(upload_response.json()["items"][0]["document_id"])
    document_path = api_context.upload_root_dir / str(document_id) / "cleanup.txt"
    monkeypatch.setattr(
        documents_endpoint,
        "delete_stored_upload",
        MagicMock(side_effect=OSError(f"failed to remove {document_path}")),
    )

    with caplog.at_level("WARNING", logger=documents_endpoint.__name__):
        response = await api_context.client.delete(
            f"/api/v1/documents/{document_id}",
            headers=api_context.auth_headers,
        )

    assert response.status_code == 204
    assert await db_session.scalar(
        select(Document.id).where(Document.id == document_id)
    ) is None
    assert document_path.exists()
    assert str(document_path) not in caplog.text
