from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncGenerator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from uuid import UUID

import httpx
import pytest
import pytest_asyncio
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import app.api.v1.endpoints.auth as auth_endpoints
import app.db.session as db_session_module
import app.services.embeddings as embeddings_service
import app.services.question_answering as question_answering_service
from app.core.settings import get_settings
from app.db.models.document_chunks import DocumentChunk
from app.db.models.documents import Document, DocumentStatus
from app.db.models.ingestion_jobs import IngestionJob, IngestionJobStatus
from app.main import app
from app.repositories.chunk_repository import ChunkRepository
from app.repositories.document_repository import DocumentRepository
from app.repositories.types import ChunkWithEmbedding
from app.services.embeddings import OllamaEmbeddingClient
from app.services.llm import FALLBACK_ANSWER, GeneratedAnswer
from app.workers.ingestion import IngestionManager

PROJECT_ROOT = Path(__file__).resolve().parents[1]
ALEMBIC_INI_PATH = PROJECT_ROOT / "alembic.ini"
PDF_FIXTURE_PATH = Path(__file__).parent / "assets" / "sample.pdf"
EMBEDDING_DIM = 768
DOCUMENT_PREFIX = "search_document: "
QUERY_PREFIX = "search_query: "
TRUNCATE_TABLES_SQL = text(
    "TRUNCATE TABLE question_context_chunks, questions, document_chunks, ingestion_jobs, "
    "documents, collections, users RESTART IDENTITY CASCADE"
)


@dataclass(slots=True)
class EmbedRequest:
    path: str
    inputs: list[str]
    vectors: list[list[float]]


@dataclass(slots=True)
class EndToEndContext:
    client: httpx.AsyncClient
    manager: IngestionManager
    session_maker: async_sessionmaker[AsyncSession]
    upload_root: Path
    embed_requests: list[EmbedRequest] = field(default_factory=list)
    first_document_batch_started: asyncio.Event = field(default_factory=asyncio.Event)
    release_document_batches: asyncio.Event = field(default_factory=asyncio.Event)
    verification_delivery_attempts: int = 0
    verification_links: list[str] = field(default_factory=list)
    password_reset_links: list[str] = field(default_factory=list)
    llm_calls: list[dict[str, object]] = field(default_factory=list)


def _auth_headers(access_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {access_token}"}


def _embedding_for_prompt(prompt: str) -> list[float]:
    vector = [0.0] * EMBEDDING_DIM
    if prompt.startswith(QUERY_PREFIX):
        vector[0 if "ORBIT778" in prompt else 1] = 1.0
    elif "ORBIT778" in prompt or "ARCHIVE42" in prompt:
        vector[0] = 1.0
    else:
        vector[2] = 1.0
    return vector


async def _truncate_all_tables(database_url: str) -> None:
    engine = create_async_engine(database_url, pool_pre_ping=True)
    try:
        async with engine.begin() as connection:
            await connection.execute(TRUNCATE_TABLES_SQL)
    finally:
        await engine.dispose()


async def _assert_database_is_at_migration_head(database_url: str) -> None:
    config = Config(str(ALEMBIC_INI_PATH))
    expected_heads = set(ScriptDirectory.from_config(config).get_heads())
    engine = create_async_engine(database_url, pool_pre_ping=True)
    try:
        async with engine.connect() as connection:
            applied_heads = set(
                (await connection.execute(text("SELECT version_num FROM alembic_version")))
                .scalars()
                .all()
            )
    finally:
        await engine.dispose()
    assert applied_heads == expected_heads


async def _dispose_app_database() -> None:
    if db_session_module._engine is not None:
        await db_session_module._engine.dispose()
    db_session_module._engine = None
    db_session_module._session_maker = None


@pytest_asyncio.fixture
async def end_to_end_context(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    postgres_database_url: str,
    migrated_database: None,
) -> AsyncGenerator[EndToEndContext]:
    del migrated_database
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("SECRET_KEY", "test-secret-key-with-enough-length")
    monkeypatch.setenv("UPLOAD_ROOT_DIR", str(tmp_path))
    monkeypatch.setenv("INGEST_WORKERS", "1")
    monkeypatch.setenv("INGEST_SHUTDOWN_TIMEOUT_S", "5")
    monkeypatch.setenv("CHUNK_SIZE_CHARS", "96")
    monkeypatch.setenv("CHUNK_OVERLAP_CHARS", "0")
    monkeypatch.setenv("OLLAMA_OPENAI_BASE_URL", "http://ollama.test:11434/v1")
    monkeypatch.setenv("OLLAMA_EMBED_BATCH_SIZE", "2")
    monkeypatch.setenv("OLLAMA_EMBED_RETRY_ATTEMPTS", "1")
    monkeypatch.setenv("RETRIEVAL_MAX_COSINE_DISTANCE", "0.75")
    monkeypatch.setenv("AI_PROVIDER", "ollama")
    monkeypatch.setenv("OLLAMA_CHAT_MODEL", "mock-chat-model")
    monkeypatch.setenv("OLLAMA_EMBED_MODEL", "mock-embed-model")
    monkeypatch.setenv("EMBEDDING_DIM", str(EMBEDDING_DIM))
    get_settings.cache_clear()

    await _dispose_app_database()
    await embeddings_service.close_embeddings_client()
    await _truncate_all_tables(postgres_database_url)

    engine = create_async_engine(postgres_database_url, pool_pre_ping=True)
    session_maker = async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )
    manager = IngestionManager(settings=get_settings(), session_maker=session_maker)
    context = EndToEndContext(
        client=None,  # type: ignore[arg-type]
        manager=manager,
        session_maker=session_maker,
        upload_root=tmp_path,
    )

    async def embed_handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content.decode("utf-8"))
        inputs = payload["input"]
        assert isinstance(inputs, list)
        assert all(isinstance(item, str) for item in inputs)
        vectors = [_embedding_for_prompt(item) for item in inputs]
        context.embed_requests.append(
            EmbedRequest(path=request.url.path, inputs=list(inputs), vectors=vectors)
        )
        if inputs and inputs[0].startswith(DOCUMENT_PREFIX):
            if not context.first_document_batch_started.is_set():
                context.first_document_batch_started.set()
                await context.release_document_batches.wait()
        return httpx.Response(200, json={"embeddings": vectors})

    embedding_http_client = httpx.AsyncClient(transport=httpx.MockTransport(embed_handler))
    embeddings_service._DEFAULT_EMBEDDINGS_CLIENT = OllamaEmbeddingClient(
        settings=get_settings(),
        http_client=embedding_http_client,
    )

    async def fake_verification_email(**kwargs: object) -> None:
        context.verification_delivery_attempts += 1
        if context.verification_delivery_attempts == 1:
            raise RuntimeError("simulated initial verification-email failure")
        context.verification_links.append(str(kwargs["verification_link"]))

    async def fake_password_reset_email(**kwargs: object) -> None:
        context.password_reset_links.append(str(kwargs["reset_link"]))

    async def fake_generate_answer(
        context_chunks_text: str,
        question: str,
        available_context_entries: int,
        *,
        settings: object | None = None,
    ) -> GeneratedAnswer:
        context.llm_calls.append(
            {
                "context": context_chunks_text,
                "question": question,
                "available_context_entries": available_context_entries,
                "settings": settings,
            }
        )
        return GeneratedAnswer(
            answer_text="The deployment authorization is cobalt [1].",
            model_used="mock-grounded-model",
            citation_ranks=(1,),
        )

    monkeypatch.setattr(
        auth_endpoints,
        "send_registration_verification_email",
        fake_verification_email,
    )
    monkeypatch.setattr(auth_endpoints, "send_password_reset_email", fake_password_reset_email)
    monkeypatch.setattr(question_answering_service, "generate_answer", fake_generate_answer)

    original_manager = getattr(app.state, "ingestion_manager", None)
    original_overrides = app.dependency_overrides.copy()
    app.dependency_overrides.clear()
    app.state.ingestion_manager = manager

    transport = httpx.ASGITransport(app=app)
    try:
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as client:
            context.client = client
            yield context
    finally:
        context.release_document_batches.set()
        await manager.stop()
        app.state.ingestion_manager = original_manager
        app.dependency_overrides.clear()
        app.dependency_overrides.update(original_overrides)
        await embeddings_service.close_embeddings_client()
        await embedding_http_client.aclose()
        await _truncate_all_tables(postgres_database_url)
        await engine.dispose()
        await _dispose_app_database()
        get_settings.cache_clear()


async def _seed_legacy_ready_document(
    context: EndToEndContext,
    *,
    user_id: UUID,
    collection_id: UUID,
) -> tuple[UUID, UUID]:
    extracted_text = "ARCHIVE42 is a pre-batch source that must remain searchable."
    storage_path = context.upload_root / "legacy-ready.txt"
    storage_path.write_text(extracted_text, encoding="utf-8")
    async with context.session_maker() as session, session.begin():
        document = await DocumentRepository(session).create_document(
            user_id,
            collection_id=collection_id,
            filename=storage_path.name,
            original_extension=".txt",
            content_type="text/plain",
            size_bytes=storage_path.stat().st_size,
            storage_path=str(storage_path),
            extracted_text=extracted_text,
            status=DocumentStatus.READY,
        )
        chunks = await ChunkRepository(session).bulk_insert_chunks(
            document.id,
            [
                ChunkWithEmbedding(
                    chunk_index=0,
                    content=extracted_text,
                    embedding=_embedding_for_prompt(f"{DOCUMENT_PREFIX}{extracted_text}"),
                )
            ],
        )
        return document.id, chunks[0].id


async def _register_verify_and_login(
    client: httpx.AsyncClient,
    *,
    email: str,
    password: str,
    first_name: str,
) -> tuple[UUID, str]:
    register_response = await client.post(
        "/api/v1/auth/register",
        json={
            "first_name": first_name,
            "last_name": "Tester",
            "email": email,
            "password": password,
        },
    )
    assert register_response.status_code == 200
    register_payload = register_response.json()
    verify_response = await client.post(
        "/api/v1/auth/verify-email",
        json={"token": register_payload["verification_token"]},
    )
    assert verify_response.status_code == 200
    login_response = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert login_response.status_code == 200
    return UUID(register_payload["user"]["id"]), login_response.json()["access_token"]


@pytest.mark.asyncio
async def test_final_backend_end_to_end(
    end_to_end_context: EndToEndContext,
    postgres_database_url: str,
) -> None:
    context = end_to_end_context
    client = context.client
    user_a_email = "user-a-e2e@example.com"
    old_password = "InitialPassword123!"
    new_password = "ReplacementPassword456!"

    await _assert_database_is_at_migration_head(postgres_database_url)

    register_response = await client.post(
        "/api/v1/auth/register",
        json={
            "first_name": "User",
            "last_name": "Alpha",
            "email": user_a_email,
            "password": old_password,
        },
    )
    assert register_response.status_code == 200
    register_payload = register_response.json()
    user_a_id = UUID(register_payload["user"]["id"])
    assert register_payload["message"] == "Registration successful. Please verify your email."
    assert register_payload["user"]["is_email_verified"] is False
    assert context.verification_delivery_attempts == 1
    assert context.verification_links == []

    resend_response = await client.post(
        "/api/v1/auth/resend-verification",
        json={"email": user_a_email},
    )
    assert resend_response.status_code == 200
    resend_token = resend_response.json()["verification_token"]
    assert resend_token != register_payload["verification_token"]
    assert context.verification_delivery_attempts == 2
    assert len(context.verification_links) == 1

    verify_response = await client.post(
        "/api/v1/auth/verify-email",
        json={"token": resend_token},
    )
    assert verify_response.status_code == 200
    assert verify_response.json() == {"message": "Email verified successfully."}

    login_response = await client.post(
        "/api/v1/auth/login",
        json={"email": user_a_email, "password": old_password},
    )
    assert login_response.status_code == 200
    user_a_token = login_response.json()["access_token"]
    user_a_headers = _auth_headers(user_a_token)
    me_response = await client.get("/api/v1/auth/me", headers=user_a_headers)
    assert me_response.status_code == 200
    assert UUID(me_response.json()["id"]) == user_a_id
    assert me_response.json()["is_email_verified"] is True

    collection_response = await client.post(
        "/api/v1/collections",
        headers=user_a_headers,
        json={"name": "End-to-end sources", "description": "Task 28 coverage"},
    )
    assert collection_response.status_code == 201
    collection_id = UUID(collection_response.json()["id"])

    legacy_document_id, legacy_chunk_id = await _seed_legacy_ready_document(
        context,
        user_id=user_a_id,
        collection_id=collection_id,
    )
    await context.manager.start()
    async with context.session_maker() as session:
        legacy_document = await session.get(Document, legacy_document_id)
        legacy_jobs = list(
            (
                await session.scalars(
                    select(IngestionJob).where(IngestionJob.document_id == legacy_document_id)
                )
            ).all()
        )
        assert legacy_document is not None
        assert legacy_document.status == DocumentStatus.READY
        assert legacy_document.extracted_text == (
            "ARCHIVE42 is a pre-batch source that must remain searchable."
        )
        assert legacy_jobs == []

    txt_content = (
        "ORBIT778 deployment authorization is cobalt for the blue release.\n"
        "Operations teams validate the release manifest before every deployment. "
        "The audit record includes the approver, environment, checksum, and rollback owner. "
        "A second reviewer confirms that the artifact came from the trusted build pipeline. "
        "Deployment notes are retained with the incident-response contact and maintenance "
        "window. This deliberately spans several small embedding batches."
    )
    md_content = (
        "# Release checklist\n\nConfirm the artifact checksum and record the deployment owner.\n"
    )
    pdf_content = PDF_FIXTURE_PATH.read_bytes()
    upload_response = await client.post(
        "/api/v1/documents/upload",
        headers=user_a_headers,
        data={"collection_id": str(collection_id)},
        files=[
            ("files", ("operations.txt", txt_content.encode("utf-8"), "text/plain")),
            ("files", ("checklist.md", md_content.encode("utf-8"), "text/markdown")),
            ("files", ("sample.pdf", pdf_content, "application/pdf")),
        ],
    )
    assert upload_response.status_code == 202
    upload_items = upload_response.json()["items"]
    assert [item["filename"] for item in upload_items] == [
        "operations.txt",
        "checklist.md",
        "sample.pdf",
    ]
    assert all(item["status"] == DocumentStatus.PENDING.value for item in upload_items)
    assert all(item["collection_id"] == str(collection_id) for item in upload_items)
    uploaded_document_ids = [UUID(item["document_id"]) for item in upload_items]

    await asyncio.wait_for(context.first_document_batch_started.wait(), timeout=5)
    processing_response = await client.get(
        f"/api/v1/documents/{uploaded_document_ids[0]}",
        headers=user_a_headers,
    )
    assert processing_response.status_code == 200
    assert processing_response.json()["status"] == DocumentStatus.PROCESSING.value
    for pending_document_id in uploaded_document_ids[1:]:
        pending_response = await client.get(
            f"/api/v1/documents/{pending_document_id}",
            headers=user_a_headers,
        )
        assert pending_response.status_code == 200
        assert pending_response.json()["status"] == DocumentStatus.PENDING.value

    context.release_document_batches.set()
    await asyncio.wait_for(context.manager._queue.join(), timeout=10)
    for document_id in uploaded_document_ids:
        ready_response = await client.get(
            f"/api/v1/documents/{document_id}",
            headers=user_a_headers,
        )
        assert ready_response.status_code == 200
        assert ready_response.json()["status"] == DocumentStatus.READY.value
        assert ready_response.json()["error_message"] is None

    documents_by_id: dict[UUID, Document] = {}
    chunks_by_document: dict[UUID, list[DocumentChunk]] = {}
    async with context.session_maker() as session:
        documents = list(
            (
                await session.scalars(
                    select(Document).where(Document.id.in_(uploaded_document_ids))
                )
            ).all()
        )
        documents_by_id = {document.id: document for document in documents}
        for document_id in uploaded_document_ids:
            chunks_by_document[document_id] = list(
                (
                    await session.scalars(
                        select(DocumentChunk)
                        .where(DocumentChunk.document_id == document_id)
                        .order_by(DocumentChunk.chunk_index)
                    )
                ).all()
            )
        jobs = list(
            (
                await session.scalars(
                    select(IngestionJob).where(IngestionJob.document_id.in_(uploaded_document_ids))
                )
            ).all()
        )

    expected_text_by_filename = {
        "operations.txt": txt_content,
        "checklist.md": md_content,
        "sample.pdf": "Sample PDF fixture text.",
    }
    assert len(documents_by_id) == 3
    assert len(jobs) == 3
    assert all(job.status == IngestionJobStatus.DONE for job in jobs)
    for document_id in uploaded_document_ids:
        document = documents_by_id[document_id]
        chunks = chunks_by_document[document_id]
        assert document.status == DocumentStatus.READY
        assert document.extracted_text is not None
        if document.filename == "sample.pdf":
            assert document.extracted_text.strip() == expected_text_by_filename[document.filename]
        else:
            assert document.extracted_text == expected_text_by_filename[document.filename]
        assert chunks
        assert [chunk.chunk_index for chunk in chunks] == list(range(len(chunks)))
        assert "".join(chunk.content for chunk in chunks) == document.extracted_text

    document_requests = [
        request
        for request in context.embed_requests
        if request.inputs[0].startswith(DOCUMENT_PREFIX)
    ]
    expected_chunk_texts = [
        chunk.content
        for document_id in uploaded_document_ids
        for chunk in chunks_by_document[document_id]
    ]
    submitted_chunk_texts = [
        prompt.removeprefix(DOCUMENT_PREFIX)
        for request in document_requests
        for prompt in request.inputs
    ]
    returned_vectors = [vector for request in document_requests for vector in request.vectors]
    assert all(request.path == "/api/embed" for request in document_requests)
    assert all(1 <= len(request.inputs) <= 2 for request in document_requests)
    assert sum(len(request.inputs) for request in document_requests) == len(expected_chunk_texts)
    assert len(returned_vectors) == len(expected_chunk_texts)
    assert submitted_chunk_texts == expected_chunk_texts
    assert any(len(request.inputs) == 2 for request in document_requests)
    assert len(document_requests) >= 3
    for document_id in uploaded_document_ids:
        for chunk in chunks_by_document[document_id]:
            expected_vector = _embedding_for_prompt(f"{DOCUMENT_PREFIX}{chunk.content}")
            assert list(chunk.embedding) == pytest.approx(expected_vector)

    async with context.session_maker() as session:
        compatibility_results = await ChunkRepository(session).similarity_search(
            user_a_id,
            _embedding_for_prompt(f"{QUERY_PREFIX}ORBIT778 and ARCHIVE42"),
            top_k=10,
            collection_id=collection_id,
            max_distance=get_settings().retrieval_max_cosine_distance,
        )
        current_legacy_document = await session.get(Document, legacy_document_id)
        current_legacy_chunk = await session.get(DocumentChunk, legacy_chunk_id)
        legacy_job_count = int(
            await session.scalar(
                select(func.count())
                .select_from(IngestionJob)
                .where(IngestionJob.document_id == legacy_document_id)
            )
            or 0
        )
    result_filenames = {result.document_filename for result in compatibility_results}
    assert {"legacy-ready.txt", "operations.txt"} <= result_filenames
    assert current_legacy_document is not None
    assert current_legacy_document.status == DocumentStatus.READY
    assert current_legacy_chunk is not None
    assert legacy_job_count == 0

    supported_question = "What is the ORBIT778 deployment authorization?"
    supported_response = await client.post(
        "/api/v1/questions/ask",
        headers=user_a_headers,
        json={"question": supported_question, "collection_id": str(collection_id)},
    )
    assert supported_response.status_code == 200
    supported_payload = supported_response.json()
    supported_question_id = UUID(supported_payload["question_id"])
    assert supported_payload["answer"] == "The deployment authorization is cobalt [1]."
    assert supported_payload["collection_id"] == str(collection_id)
    assert supported_payload["provider"] == "ollama"
    assert supported_payload["model"] == "mock-grounded-model"
    assert len(supported_payload["citations"]) == 1
    citation_snapshot = supported_payload["citations"][0]
    assert citation_snapshot["rank"] == 1
    assert citation_snapshot["excerpt"]
    assert context.llm_calls[0]["question"] == supported_question
    assert context.llm_calls[0]["available_context_entries"] >= 2
    llm_context = str(context.llm_calls[0]["context"])
    assert "ARCHIVE42" in llm_context
    assert "ORBIT778" in llm_context

    unsupported_question = "What color are the lunar observatory doors?"
    unsupported_response = await client.post(
        "/api/v1/questions/ask",
        headers=user_a_headers,
        json={"question": unsupported_question, "collection_id": str(collection_id)},
    )
    assert unsupported_response.status_code == 200
    unsupported_payload = unsupported_response.json()
    unsupported_question_id = UUID(unsupported_payload["question_id"])
    assert unsupported_payload["answer"] == FALLBACK_ANSWER
    assert unsupported_payload["citations"] == []
    assert unsupported_payload["provider"] is None
    assert unsupported_payload["model"] is None
    assert len(context.llm_calls) == 1

    query_requests = [
        request for request in context.embed_requests if request.inputs[0].startswith(QUERY_PREFIX)
    ]
    assert [request.path for request in query_requests] == ["/api/embed", "/api/embed"]
    assert [request.inputs for request in query_requests] == [
        [f"{QUERY_PREFIX}{supported_question}"],
        [f"{QUERY_PREFIX}{unsupported_question}"],
    ]
    assert all(len(request.vectors) == 1 for request in query_requests)

    history_response = await client.get(
        "/api/v1/questions/history",
        headers=user_a_headers,
    )
    assert history_response.status_code == 200
    history_payload = history_response.json()
    assert history_payload["total"] == 2
    assert {UUID(item["question_id"]) for item in history_payload["items"]} == {
        supported_question_id,
        unsupported_question_id,
    }
    details: dict[UUID, dict[str, Any]] = {}
    for question_id in (supported_question_id, unsupported_question_id):
        detail_response = await client.get(
            f"/api/v1/questions/history/{question_id}",
            headers=user_a_headers,
        )
        assert detail_response.status_code == 200
        details[question_id] = detail_response.json()
    assert details[supported_question_id]["citations"] == [citation_snapshot]
    assert details[unsupported_question_id]["answer"] == FALLBACK_ANSWER

    delete_history_response = await client.delete(
        f"/api/v1/questions/history/{unsupported_question_id}",
        headers=user_a_headers,
    )
    assert delete_history_response.status_code == 204
    deleted_history_response = await client.get(
        f"/api/v1/questions/history/{unsupported_question_id}",
        headers=user_a_headers,
    )
    assert deleted_history_response.status_code == 404

    cited_document_id = UUID(citation_snapshot["document_id"])
    delete_document_response = await client.delete(
        f"/api/v1/documents/{cited_document_id}",
        headers=user_a_headers,
    )
    assert delete_document_response.status_code == 204
    preserved_history_response = await client.get(
        f"/api/v1/questions/history/{supported_question_id}",
        headers=user_a_headers,
    )
    assert preserved_history_response.status_code == 200
    assert preserved_history_response.json()["citations"] == [citation_snapshot]

    delete_collection_response = await client.delete(
        f"/api/v1/collections/{collection_id}",
        headers=user_a_headers,
    )
    assert delete_collection_response.status_code == 204
    remaining_document_ids = {legacy_document_id, *uploaded_document_ids} - {cited_document_id}
    for document_id in remaining_document_ids:
        document_response = await client.get(
            f"/api/v1/documents/{document_id}",
            headers=user_a_headers,
        )
        assert document_response.status_code == 200
        assert document_response.json()["collection_id"] is None
    remaining_history_response = await client.get(
        f"/api/v1/questions/history/{supported_question_id}",
        headers=user_a_headers,
    )
    assert remaining_history_response.status_code == 200
    assert remaining_history_response.json()["collection_id"] is None
    assert remaining_history_response.json()["citations"] == [citation_snapshot]

    user_b_id, user_b_token = await _register_verify_and_login(
        client,
        email="user-b-e2e@example.com",
        password="UserBPassword123!",
        first_name="UserB",
    )
    assert user_b_id != user_a_id
    user_b_headers = _auth_headers(user_b_token)
    for document_id in remaining_document_ids:
        foreign_document_response = await client.get(
            f"/api/v1/documents/{document_id}",
            headers=user_b_headers,
        )
        assert foreign_document_response.status_code == 404
    foreign_history_response = await client.get(
        f"/api/v1/questions/history/{supported_question_id}",
        headers=user_b_headers,
    )
    foreign_delete_history_response = await client.delete(
        f"/api/v1/questions/history/{supported_question_id}",
        headers=user_b_headers,
    )
    assert foreign_history_response.status_code == 404
    assert foreign_delete_history_response.status_code == 404
    user_b_documents = await client.get("/api/v1/documents", headers=user_b_headers)
    user_b_history = await client.get("/api/v1/questions/history", headers=user_b_headers)
    assert user_b_documents.status_code == 200
    assert user_b_documents.json()["total"] == 0
    assert user_b_history.status_code == 200
    assert user_b_history.json()["total"] == 0

    forgot_response = await client.post(
        "/api/v1/auth/forgot-password",
        json={"email": user_a_email},
    )
    assert forgot_response.status_code == 200
    reset_token = forgot_response.json()["reset_token"]
    assert reset_token
    assert len(context.password_reset_links) == 1
    reset_response = await client.post(
        "/api/v1/auth/reset-password",
        json={"token": reset_token, "new_password": new_password},
    )
    assert reset_response.status_code == 200
    assert reset_response.json() == {"message": "Password reset successfully."}

    old_password_login = await client.post(
        "/api/v1/auth/login",
        json={"email": user_a_email, "password": old_password},
    )
    new_password_login = await client.post(
        "/api/v1/auth/login",
        json={"email": user_a_email, "password": new_password},
    )
    assert old_password_login.status_code == 401
    assert old_password_login.json()["error"]["code"] == "invalid_credentials"
    assert new_password_login.status_code == 200
    assert UUID(new_password_login.json()["user"]["id"]) == user_a_id
