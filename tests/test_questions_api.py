from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator

import httpx
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

import app.services.question_answering as question_answering_service
from app.api.schemas.questions import QuestionAnswerResponse, QuestionSourceResponse
from app.db.models.documents import DocumentStatus
from app.db.session import get_db_session
from app.main import app
from app.repositories.document_repository import DocumentRepository


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
