from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator
from datetime import UTC, datetime

import httpx
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

import app.services.question_answering as question_answering_service
from app.api.dependencies import get_current_verified_user
from app.api.schemas.questions import CitationResponse, QuestionAnswerResponse
from app.db.models.auth import User
from app.db.models.documents import DocumentStatus
from app.db.session import get_db_session
from app.main import app
from app.repositories.document_repository import DocumentRepository


async def _api_user(session: AsyncSession) -> User:
    cached = session.info.get("questions_api_user")
    if isinstance(cached, User):
        return cached

    user = User(
        email=f"questions-api-{uuid.uuid4()}@example.com",
        password_hash="test-password-hash",
        first_name="Questions",
        last_name="Tester",
        is_email_verified=True,
    )
    session.add(user)
    await session.flush()
    session.info["questions_api_user"] = user
    return user


@pytest_asyncio.fixture
async def api_client(db_session: AsyncSession) -> AsyncGenerator[httpx.AsyncClient]:
    user = await _api_user(db_session)

    async def _override_get_db_session() -> AsyncGenerator[AsyncSession]:
        yield db_session

    async def _override_current_user() -> User:
        return user

    original_overrides = app.dependency_overrides.copy()
    app.dependency_overrides[get_db_session] = _override_get_db_session
    app.dependency_overrides[get_current_verified_user] = _override_current_user

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client

    app.dependency_overrides.clear()
    app.dependency_overrides.update(original_overrides)


async def _create_document(
    session: AsyncSession,
    *,
    filename: str,
    owner_id: uuid.UUID | None = None,
    status: DocumentStatus = DocumentStatus.READY,
) -> uuid.UUID:
    owner = owner_id or (await _api_user(session)).id
    document = await DocumentRepository(session).create_document(
        owner,
        filename=filename,
        original_extension=".txt",
        content_type="text/plain",
        size_bytes=42,
        storage_path=f"/tmp/{filename}",
        extracted_text="sample extracted text",
        status=status,
    )
    return document.id


def _answer_payload(document_id: uuid.UUID) -> QuestionAnswerResponse:
    return QuestionAnswerResponse(
        question_id=uuid.uuid4(),
        collection_id=None,
        answer="Answer from the QA service.",
        citations=[
            CitationResponse(
                rank=1,
                document_id=document_id,
                document_filename="second.txt",
                chunk_id=uuid.uuid4(),
                chunk_index=3,
                excerpt="Grounded citation text.",
                distance=0.12,
            )
        ],
        created_at=datetime.now(UTC),
        provider="ollama",
        model="test-model",
    )


@pytest.mark.asyncio
async def test_ask_question_forwards_owned_document_selection(
    api_client: httpx.AsyncClient,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first_document_id = await _create_document(db_session, filename="first.txt")
    second_document_id = await _create_document(db_session, filename="second.txt")
    response_payload = _answer_payload(second_document_id)
    captured: dict[str, object] = {}

    async def fake_answer_question(
        session: AsyncSession,
        *,
        user_id: uuid.UUID,
        question_text: str,
        document_ids: tuple[uuid.UUID, ...] | None = None,
        **_: object,
    ) -> QuestionAnswerResponse:
        captured.update(
            session=session,
            user_id=user_id,
            question_text=question_text,
            document_ids=document_ids,
        )
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
    assert captured["user_id"] == (await _api_user(db_session)).id
    assert captured["question_text"] == "What does the second document say?"
    assert captured["document_ids"] == (first_document_id, second_document_id)


@pytest.mark.asyncio
async def test_ask_question_rejects_missing_or_other_users_document_ids(
    api_client: httpx.AsyncClient,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    own_document_id = await _create_document(db_session, filename="owned.txt")
    other_user = User(
        email=f"other-user-{uuid.uuid4()}@example.com",
        password_hash="test-password-hash",
        first_name="Other",
        last_name="User",
        is_email_verified=True,
    )
    db_session.add(other_user)
    await db_session.flush()
    foreign_document_id = await _create_document(
        db_session,
        filename="foreign.txt",
        owner_id=other_user.id,
    )
    called = False

    async def fail_if_called(*args: object, **kwargs: object) -> QuestionAnswerResponse:
        nonlocal called
        called = True
        raise AssertionError("answer_question should not run for inaccessible documents")

    monkeypatch.setattr(question_answering_service, "answer_question", fail_if_called)
    response = await api_client.post(
        "/api/v1/questions/ask",
        json={
            "question": "Which documents exist?",
            "document_ids": [str(own_document_id), str(foreign_document_id)],
        },
    )

    assert response.status_code == 404
    assert response.json()["error"] == {
        "code": "documents_not_found",
        "message": "One or more selected documents were not found.",
        "details": {"document_ids": [str(foreign_document_id)]},
    }
    assert called is False


@pytest.mark.asyncio
async def test_ask_question_rejects_selected_documents_still_processing(
    api_client: httpx.AsyncClient,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    processing_document_id = await _create_document(
        db_session,
        filename="processing.txt",
        status=DocumentStatus.PROCESSING,
    )

    async def fail_if_called(*args: object, **kwargs: object) -> QuestionAnswerResponse:
        raise AssertionError("answer_question should not run for processing documents")

    monkeypatch.setattr(question_answering_service, "answer_question", fail_if_called)
    response = await api_client.post(
        "/api/v1/questions/ask",
        json={
            "question": "Can I search this document?",
            "document_ids": [str(processing_document_id)],
        },
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "documents_not_ready"
    assert response.json()["error"]["details"]["document_ids"] == [str(processing_document_id)]


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
    response = await api_client.post("/api/v1/questions/ask", json={"question": question})

    assert response.status_code == 422
    errors = response.json()["error"]["details"]["errors"]
    assert errors[0]["loc"] == ["body", "question"]
    assert expected_message in errors[0]["msg"]
