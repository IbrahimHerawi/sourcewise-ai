from __future__ import annotations

import asyncio
import hashlib
import math
import re
from collections.abc import AsyncGenerator
from dataclasses import dataclass
from pathlib import Path
from time import monotonic
from uuid import UUID

import httpx
import pytest
import pytest_asyncio
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import app.db.session as db_session_module
import app.services.question_answering as question_answering_service
import app.workers.ingestion as ingestion_worker
from app.core.settings import get_settings
from app.db.models.document_chunks import DocumentChunk
from app.main import app

_TRUNCATE_TABLES_SQL = text(
    "TRUNCATE TABLE question_context_chunks, questions, document_chunks, ingestion_jobs, documents "
    "RESTART IDENTITY CASCADE"
)
_TOKEN_PATTERN = re.compile(r"[A-Za-z0-9_-]+")


@dataclass(slots=True)
class SmokeContext:
    client: httpx.AsyncClient
    llm_context_capture: dict[str, str]


def _deterministic_embedding(text_value: str, *, dim: int) -> list[float]:
    tokens = _TOKEN_PATTERN.findall(text_value.lower())
    if not tokens:
        tokens = ["_empty"]

    vector = [0.0] * dim
    for token in tokens:
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        index = int.from_bytes(digest[:8], byteorder="big") % dim
        vector[index] += 1.0

    magnitude = math.sqrt(sum(value * value for value in vector))
    if magnitude == 0.0:
        vector[0] = 1.0
        return vector

    return [value / magnitude for value in vector]


async def _truncate_all_tables(database_url: str) -> None:
    engine = create_async_engine(database_url, pool_pre_ping=True)
    try:
        async with engine.begin() as connection:
            await connection.execute(_TRUNCATE_TABLES_SQL)
    finally:
        await engine.dispose()


async def _count_document_chunks(database_url: str, *, document_id: UUID) -> int:
    engine = create_async_engine(database_url, pool_pre_ping=True)
    session_maker = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    try:
        async with session_maker() as session:
            count = await session.scalar(
                select(func.count())
                .select_from(DocumentChunk)
                .where(DocumentChunk.document_id == document_id)
            )
            return int(count or 0)
    finally:
        await engine.dispose()


async def _wait_until_ready(
    client: httpx.AsyncClient,
    *,
    document_id: UUID,
    timeout_seconds: float = 8.0,
    poll_interval_seconds: float = 0.1,
) -> dict[str, object]:
    deadline = monotonic() + timeout_seconds
    last_payload: dict[str, object] | None = None

    while monotonic() < deadline:
        response = await client.get(f"/api/documents/{document_id}")
        assert response.status_code == 200
        payload = response.json()
        status_value = payload["status"]
        last_payload = payload

        if status_value == "READY":
            return payload
        if status_value == "FAILED":
            pytest.fail(f"Ingestion failed for {document_id}: {payload.get('error_message')}")

        await asyncio.sleep(poll_interval_seconds)

    pytest.fail(f"Document {document_id} did not reach READY within {timeout_seconds}s. {last_payload=}")


@pytest_asyncio.fixture
async def smoke_context(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    postgres_database_url: str,
    migrated_database: None,
) -> AsyncGenerator[SmokeContext]:
    monkeypatch.setenv("UPLOAD_ROOT_DIR", str(tmp_path))
    monkeypatch.setenv("INGEST_WORKERS", "1")
    monkeypatch.setenv("CHUNK_SIZE_CHARS", "80")
    monkeypatch.setenv("CHUNK_OVERLAP_CHARS", "0")
    monkeypatch.setenv("RETRIEVAL_MAX_COSINE_DISTANCE", "2.0")
    get_settings.cache_clear()

    db_session_module._engine = None
    db_session_module._session_maker = None

    await _truncate_all_tables(postgres_database_url)

    llm_capture: dict[str, str] = {}

    async def fake_embed_documents(texts: list[str]) -> list[list[float]]:
        dim = get_settings().embedding_dim
        return [_deterministic_embedding(chunk_text, dim=dim) for chunk_text in texts]

    async def fake_embed_question(
        question_text: str,
        *,
        settings: object | None,
    ) -> list[float]:
        dim = int(getattr(settings, "embedding_dim", get_settings().embedding_dim))
        return _deterministic_embedding(question_text, dim=dim)

    async def fake_generate_answer(
        context_chunks_text: str,
        question: str,
        *,
        settings: object | None = None,
    ) -> tuple[str, str]:
        llm_capture["context"] = context_chunks_text
        llm_capture["question"] = question
        return "Mocked answer from integration smoke test.", "mock-smoke-model"

    monkeypatch.setattr(ingestion_worker, "embed_documents", fake_embed_documents)
    monkeypatch.setattr(question_answering_service, "_embed_question", fake_embed_question)
    monkeypatch.setattr(question_answering_service, "generate_answer", fake_generate_answer)

    original_overrides = app.dependency_overrides.copy()
    app.dependency_overrides.clear()

    try:
        async with app.router.lifespan_context(app):
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(
                transport=transport,
                base_url="http://testserver",
            ) as client:
                yield SmokeContext(client=client, llm_context_capture=llm_capture)
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(original_overrides)
        await _truncate_all_tables(postgres_database_url)
        db_session_module._engine = None
        db_session_module._session_maker = None
        get_settings.cache_clear()


@pytest.mark.asyncio
async def test_upload_ingest_ask_and_history_smoke(
    smoke_context: SmokeContext,
    postgres_database_url: str,
) -> None:
    upload_text = (
        "ALPHA123 sentence: The office opens at 08:00 every weekday.\n"
        "ORBIT778 sentence: The deployment key is ORBIT778 for the blue release.\n"
        "GAMMA456 sentence: The support desk closes at 18:00.\n"
    )

    upload_response = await smoke_context.client.post(
        "/api/documents/upload",
        files={"file": ("smoke.txt", upload_text.encode("utf-8"), "text/plain")},
    )

    assert upload_response.status_code == 200
    upload_payload = upload_response.json()
    document_id = UUID(upload_payload["document_id"])

    document_payload = await _wait_until_ready(smoke_context.client, document_id=document_id)
    assert document_payload["status"] == "READY"
    assert document_payload["error_message"] is None

    assert await _count_document_chunks(postgres_database_url, document_id=document_id) >= 1

    ask_response = await smoke_context.client.post(
        "/api/questions/ask",
        json={
            "question": "ORBIT778",
        },
    )

    assert ask_response.status_code == 200
    ask_payload = ask_response.json()
    assert ask_payload["answer"] == "Mocked answer from integration smoke test."
    assert len(ask_payload["sources"]) >= 1
    assert ask_payload["sources"][0]["document_id"] == str(document_id)
    assert "ORBIT778 sentence" in smoke_context.llm_context_capture["context"]

    history_response = await smoke_context.client.get("/api/questions/history")
    assert history_response.status_code == 200
    history_payload = history_response.json()
    assert any(
        item["question_id"] == ask_payload["question_id"] for item in history_payload["items"]
    )
