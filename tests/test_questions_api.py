from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator
from datetime import UTC, datetime

import httpx
import pytest
import pytest_asyncio
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

import app.services.question_answering as question_answering_service
from app.api.schemas.questions import QuestionAnswerResponse, QuestionSourceResponse
from app.core.settings import get_settings
from app.db.models.documents import DocumentStatus
from app.db.models.questions import Question
from app.db.session import get_db_session
from app.main import app
from app.repositories.chunk_repository import ChunkRepository
from app.repositories.document_repository import DocumentRepository
from app.repositories.question_context_repository import QuestionContextRepository
from app.repositories.question_repository import QuestionRepository
from app.repositories.types import ChunkWithEmbedding, QuestionContextRow


@pytest_asyncio.fixture
async def api_client(db_session: AsyncSession) -> AsyncGenerator[httpx.AsyncClient]:
    async def _override_get_db_session() -> AsyncGenerator[AsyncSession]:
        yield db_session

    original_overrides = app.dependency_overrides.copy()
    app.dependency_overrides[get_db_session] = _override_get_db_session

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client

    app.dependency_overrides.clear()
    app.dependency_overrides.update(original_overrides)


async def _create_document(
    session: AsyncSession,
    *,
    filename: str,
    status: DocumentStatus = DocumentStatus.READY,
) -> uuid.UUID:
    document = await DocumentRepository(session).create_document(
        filename=filename,
        original_extension=".txt",
        content_type="text/plain",
        size_bytes=42,
        storage_path=f"/tmp/{filename}",
        extracted_text="sample extracted text",
        status=status,
    )
    return document.id


def _embedding(first_dim: float, second_dim: float, dim: int) -> list[float]:
    if dim < 2:
        raise ValueError("embedding_dim must be at least 2 for API tests")
    return [first_dim, second_dim] + [0.0] * (dim - 2)


async def _set_question_created_at(
    session: AsyncSession,
    question_id: uuid.UUID,
    created_at: datetime,
) -> None:
    await session.execute(
        update(Question).where(Question.id == question_id).values(created_at=created_at)
    )
    await session.flush()


async def _seed_question_history_data(
    session: AsyncSession,
) -> dict[str, uuid.UUID]:
    settings = get_settings()

    first_document_id = await _create_document(session, filename="history-first.txt")
    second_document_id = await _create_document(session, filename="history-second.txt")

    first_chunks = await ChunkRepository(session).bulk_insert_chunks(
        first_document_id,
        [
            ChunkWithEmbedding(
                chunk_index=0,
                content="first history chunk zero",
                embedding=_embedding(1.0, 0.0, settings.embedding_dim),
            ),
            ChunkWithEmbedding(
                chunk_index=1,
                content="first history chunk one",
                embedding=_embedding(0.8, 0.2, settings.embedding_dim),
            ),
        ],
    )
    second_chunks = await ChunkRepository(session).bulk_insert_chunks(
        second_document_id,
        [
            ChunkWithEmbedding(
                chunk_index=0,
                content="second history chunk zero",
                embedding=_embedding(0.0, 1.0, settings.embedding_dim),
            )
        ],
    )

    question_repo = QuestionRepository(session)
    context_repo = QuestionContextRepository(session)

    oldest_question = await question_repo.create_question(
        question_text="What is in the oldest question?",
        embedding=_embedding(1.0, 0.0, settings.embedding_dim),
        answer_text="Oldest answer",
        ai_provider="ollama",
        model_used="history-model-old",
    )
    middle_question = await question_repo.create_question(
        question_text="What is in the middle question?",
        embedding=_embedding(0.7, 0.3, settings.embedding_dim),
        answer_text="Middle answer",
        ai_provider="ollama",
        model_used="history-model-middle",
    )
    newest_question = await question_repo.create_question(
        question_text="What is in the newest question?",
        embedding=_embedding(0.0, 1.0, settings.embedding_dim),
        answer_text="Newest answer",
        ai_provider="ollama",
        model_used="history-model-new",
    )

    await context_repo.bulk_insert_question_context(
        oldest_question.id,
        [
            QuestionContextRow(
                chunk_id=first_chunks[0].id,
                similarity_score=0.11,
                rank=1,
            )
        ],
    )
    await context_repo.bulk_insert_question_context(
        middle_question.id,
        [
            QuestionContextRow(
                chunk_id=second_chunks[0].id,
                similarity_score=0.22,
                rank=1,
            )
        ],
    )
    await context_repo.bulk_insert_question_context(
        newest_question.id,
        [
            QuestionContextRow(
                chunk_id=first_chunks[0].id,
                similarity_score=0.31,
                rank=1,
            ),
            QuestionContextRow(
                chunk_id=first_chunks[1].id,
                similarity_score=0.32,
                rank=2,
            ),
            QuestionContextRow(
                chunk_id=second_chunks[0].id,
                similarity_score=0.33,
                rank=3,
            ),
        ],
    )

    await _set_question_created_at(
        session,
        oldest_question.id,
        datetime(2026, 1, 1, 12, 0, tzinfo=UTC),
    )
    await _set_question_created_at(
        session,
        middle_question.id,
        datetime(2026, 1, 2, 12, 0, tzinfo=UTC),
    )
    await _set_question_created_at(
        session,
        newest_question.id,
        datetime(2026, 1, 3, 12, 0, tzinfo=UTC),
    )

    return {
        "first_document_id": first_document_id,
        "second_document_id": second_document_id,
        "oldest_question_id": oldest_question.id,
        "middle_question_id": middle_question.id,
        "newest_question_id": newest_question.id,
    }


@pytest.mark.asyncio
async def test_ask_question_returns_answer_payload(
    api_client: httpx.AsyncClient,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first_document_id = await _create_document(db_session, filename="first.txt")
    second_document_id = await _create_document(db_session, filename="second.txt")
    response_payload = QuestionAnswerResponse(
        question_id=uuid.uuid4(),
        answer="Answer from the QA service.",
        sources=[
            QuestionSourceResponse(
                document_id=second_document_id,
                chunk_id=uuid.uuid4(),
                chunk_index=3,
                distance=0.12,
            )
        ],
        provider="ollama",
        model="test-model",
    )
    captured: dict[str, object] = {}

    async def fake_answer_question(
        session: AsyncSession,
        *,
        question_text: str,
        document_ids: tuple[uuid.UUID, ...] | None = None,
        **_: object,
    ) -> QuestionAnswerResponse:
        captured["session"] = session
        captured["question_text"] = question_text
        captured["document_ids"] = document_ids
        return response_payload

    monkeypatch.setattr(question_answering_service, "answer_question", fake_answer_question)

    response = await api_client.post(
        "/api/v1/questions/ask",
        json={
            "question": "  What does the second document say?  ",
            "document_ids": [
                str(first_document_id),
                str(second_document_id),
                str(first_document_id),
            ],
        },
    )

    assert response.status_code == 200
    assert response.json() == response_payload.model_dump(mode="json")
    assert captured["session"] is db_session
    assert captured["question_text"] == "What does the second document say?"
    assert captured["document_ids"] == (first_document_id, second_document_id)


@pytest.mark.asyncio
async def test_ask_question_returns_404_when_any_document_id_is_missing(
    api_client: httpx.AsyncClient,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    existing_document_id = await _create_document(db_session, filename="existing.txt")
    missing_document_id = uuid.uuid4()
    called = False

    async def fail_if_called(*args: object, **kwargs: object) -> QuestionAnswerResponse:
        nonlocal called
        called = True
        raise AssertionError("answer_question should not run when document ids are missing")

    monkeypatch.setattr(question_answering_service, "answer_question", fail_if_called)

    response = await api_client.post(
        "/api/v1/questions/ask",
        json={
            "question": "Which documents exist?",
            "document_ids": [
                str(existing_document_id),
                str(missing_document_id),
                str(missing_document_id),
            ],
        },
    )

    assert response.status_code == 404
    assert response.json() == {
        "detail": {
            "message": "One or more documents were not found.",
            "missing_document_ids": [str(missing_document_id)],
        }
    }
    assert called is False


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("question", "expected_message"),
    [
        ("   ", "String should have at least 1 character"),
        ("a" * 4_001, "String should have at most 4000 characters"),
    ],
)
async def test_ask_question_validates_question_length(
    api_client: httpx.AsyncClient,
    question: str,
    expected_message: str,
) -> None:
    response = await api_client.post(
        "/api/v1/questions/ask",
        json={"question": question},
    )

    assert response.status_code == 422
    detail = response.json()["detail"]
    assert detail[0]["loc"] == ["body", "question"]
    assert expected_message in detail[0]["msg"]


@pytest.mark.asyncio
async def test_question_history_returns_paginated_items(
    api_client: httpx.AsyncClient,
    db_session: AsyncSession,
) -> None:
    seeded = await _seed_question_history_data(db_session)

    response = await api_client.get(
        "/api/questions/history",
        params={"limit": 2, "offset": 1},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["limit"] == 2
    assert payload["offset"] == 1
    assert payload["total"] == 3
    assert [item["question_id"] for item in payload["items"]] == [
        str(seeded["middle_question_id"]),
        str(seeded["oldest_question_id"]),
    ]
    assert payload["items"][0]["question"] == "What is in the middle question?"
    assert payload["items"][0]["answer"] == "Middle answer"
    assert payload["items"][0]["provider"] == "ollama"
    assert payload["items"][0]["model"] == "history-model-middle"
    assert set(payload["items"][0]["sources"][0]) == {
        "document_id",
        "chunk_id",
        "chunk_index",
        "distance",
    }
    assert "question_embedding" not in payload["items"][0]


@pytest.mark.asyncio
async def test_question_history_filters_by_document_id_without_duplicate_items(
    api_client: httpx.AsyncClient,
    db_session: AsyncSession,
) -> None:
    seeded = await _seed_question_history_data(db_session)

    response = await api_client.get(
        "/api/questions/history",
        params={"document_id": str(seeded["first_document_id"])},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["limit"] == 20
    assert payload["offset"] == 0
    assert payload["total"] == 2
    assert [item["question_id"] for item in payload["items"]] == [
        str(seeded["newest_question_id"]),
        str(seeded["oldest_question_id"]),
    ]
    assert payload["items"][0]["sources"][0]["document_id"] == str(seeded["first_document_id"])
