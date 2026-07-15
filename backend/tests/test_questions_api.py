from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator, Generator
from datetime import UTC, datetime

import httpx
import pytest
import pytest_asyncio
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

import app.services.question_answering as question_answering_service
from app.api.schemas.questions import QuestionAnswerResponse
from app.core.security import create_access_token
from app.core.settings import get_settings
from app.db.models.auth import User
from app.db.models.collections import Collection
from app.db.models.document_chunks import DocumentChunk
from app.db.models.documents import Document, DocumentStatus
from app.db.models.question_context_chunks import QuestionContextChunk
from app.db.models.questions import Question
from app.db.session import get_db_session
from app.main import app
from app.repositories.chunk_repository import ChunkRepository
from app.repositories.collection_repository import CollectionRepository
from app.repositories.document_repository import DocumentRepository
from app.repositories.question_context_repository import QuestionContextRepository
from app.repositories.question_repository import QuestionRepository
from app.repositories.types import ChunkWithEmbedding, QuestionContextRow
from app.repositories.user_repository import UserRepository
from app.services.llm import (
    FALLBACK_ANSWER,
    GeneratedAnswer,
    LLMInvalidResponseError,
    LLMRejectedError,
    LLMTransientError,
)

ASK_PATH = "/api/v1/questions/ask"
HISTORY_PATH = "/api/v1/questions/history"
COLLECTION_NOT_FOUND = {
    "error": {"code": "not_found", "message": "Collection not found."}
}
QUESTION_NOT_FOUND = {
    "error": {"code": "not_found", "message": "Question not found."}
}


@pytest.fixture
def question_api_settings(monkeypatch: pytest.MonkeyPatch) -> Generator[None]:
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("SECRET_KEY", "test-secret-key-with-enough-length")
    monkeypatch.setenv("JWT_ALGORITHM", "HS256")
    monkeypatch.setenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest_asyncio.fixture
async def api_client(
    question_api_settings: None,
    db_session: AsyncSession,
) -> AsyncGenerator[httpx.AsyncClient]:
    async def _override_get_db_session() -> AsyncGenerator[AsyncSession]:
        yield db_session

    original_overrides = app.dependency_overrides.copy()
    app.dependency_overrides[get_db_session] = _override_get_db_session

    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client

    app.dependency_overrides.clear()
    app.dependency_overrides.update(original_overrides)


async def _create_user(
    session: AsyncSession,
    label: str,
    *,
    is_active: bool = True,
    is_email_verified: bool = True,
) -> User:
    return await UserRepository(session).create_user(
        email=f"questions-{label}-{uuid.uuid4()}@example.com",
        password_hash="test-password-hash",
        first_name="Question",
        last_name="Tester",
        is_active=is_active,
        is_email_verified=is_email_verified,
    )


def _auth_headers(user: User) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(user.id)}"}


def _embedding(first_dim: float = 1.0, second_dim: float = 0.0) -> list[float]:
    dim = get_settings().embedding_dim
    if dim < 2:
        raise ValueError("embedding_dim must be at least 2 for question API tests")
    return [first_dim, second_dim] + [0.0] * (dim - 2)


async def _create_collection(
    session: AsyncSession,
    user: User,
    name: str,
) -> Collection:
    return await CollectionRepository(session).create_collection(user.id, name)


async def _create_document(
    session: AsyncSession,
    user: User,
    *,
    filename: str,
    collection_id: uuid.UUID | None = None,
) -> Document:
    return await DocumentRepository(session).create_document(
        user.id,
        collection_id=collection_id,
        filename=filename,
        original_extension=".txt",
        content_type="text/plain",
        size_bytes=42,
        storage_path=f"/private/{filename}",
        extracted_text="private full extracted text",
        status=DocumentStatus.READY,
    )


async def _create_question(
    session: AsyncSession,
    user: User,
    *,
    question: str,
    answer: str,
    collection_id: uuid.UUID | None = None,
    provider: str | None = None,
    model: str | None = None,
    created_at: datetime | None = None,
) -> Question:
    record = await QuestionRepository(session).create_question(
        user.id,
        collection_id=collection_id,
        question_text=question,
        embedding=_embedding(),
        answer_text=answer,
        ai_provider=provider,
        model_used=model,
    )
    if created_at is not None:
        await session.execute(
            update(Question).where(Question.id == record.id).values(created_at=created_at)
        )
        record.created_at = created_at
    return record


def _snapshot(rank: int, *, excerpt: str | None = None) -> QuestionContextRow:
    return QuestionContextRow(
        rank=rank,
        document_id=uuid.uuid4(),
        document_filename=f"snapshot-{rank}.txt",
        chunk_id=uuid.uuid4(),
        chunk_index=rank - 1,
        chunk_content=excerpt or f"Exact citation snapshot {rank}.",
        similarity_score=rank / 10,
    )


async def _seed_history(
    session: AsyncSession,
    owner: User,
    foreign_user: User,
) -> dict[str, Question | Collection]:
    first_collection = await _create_collection(session, owner, "First history collection")
    second_collection = await _create_collection(session, owner, "Second history collection")
    oldest = await _create_question(
        session,
        owner,
        collection_id=first_collection.id,
        question="Oldest question?",
        answer="Oldest answer.",
        provider="ollama",
        model="old-model",
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    middle = await _create_question(
        session,
        owner,
        collection_id=first_collection.id,
        question="Middle question?",
        answer=FALLBACK_ANSWER,
        created_at=datetime(2026, 1, 2, tzinfo=UTC),
    )
    newest = await _create_question(
        session,
        owner,
        collection_id=second_collection.id,
        question="Newest question?",
        answer="Newest grounded answer [1] [2].",
        provider="openai",
        model="new-model",
        created_at=datetime(2026, 1, 3, tzinfo=UTC),
    )
    await QuestionContextRepository(session).bulk_insert_question_context(
        newest.id,
        [
            _snapshot(2, excerpt="Second-ranked snapshot."),
            _snapshot(1, excerpt=f"  {'x' * 510} private-tail  "),
        ],
    )
    foreign = await _create_question(
        session,
        foreign_user,
        question="Foreign question?",
        answer="Foreign answer.",
        created_at=datetime(2026, 1, 4, tzinfo=UTC),
    )
    return {
        "first_collection": first_collection,
        "second_collection": second_collection,
        "oldest": oldest,
        "middle": middle,
        "newest": newest,
        "foreign": foreign,
    }


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("method", "path", "json_body"),
    [
        ("POST", ASK_PATH, {"question": "What is protected?"}),
        ("GET", HISTORY_PATH, None),
        ("GET", f"{HISTORY_PATH}/{uuid.uuid4()}", None),
        ("DELETE", f"{HISTORY_PATH}/{uuid.uuid4()}", None),
    ],
)
async def test_question_endpoints_require_authentication(
    api_client: httpx.AsyncClient,
    method: str,
    path: str,
    json_body: dict[str, str] | None,
) -> None:
    kwargs = {"json": json_body} if json_body is not None else {}

    response = await api_client.request(method, path, **kwargs)

    assert response.status_code == 401
    assert response.json() == {
        "error": {
            "code": "unauthorized",
            "message": "Authentication credentials could not be validated.",
        }
    }


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("method", "path", "json_body"),
    [
        ("POST", ASK_PATH, {"question": "What is protected?"}),
        ("GET", HISTORY_PATH, None),
        ("GET", f"{HISTORY_PATH}/{uuid.uuid4()}", None),
        ("DELETE", f"{HISTORY_PATH}/{uuid.uuid4()}", None),
    ],
)
@pytest.mark.parametrize(
    ("is_active", "is_email_verified", "expected_message"),
    [
        (False, True, "User account is inactive."),
        (True, False, "User email is not verified."),
    ],
)
async def test_question_endpoints_require_active_verified_users(
    api_client: httpx.AsyncClient,
    db_session: AsyncSession,
    method: str,
    path: str,
    json_body: dict[str, str] | None,
    is_active: bool,
    is_email_verified: bool,
    expected_message: str,
) -> None:
    user = await _create_user(
        db_session,
        "ineligible",
        is_active=is_active,
        is_email_verified=is_email_verified,
    )
    kwargs = {"json": json_body} if json_body is not None else {}

    response = await api_client.request(
        method,
        path,
        headers=_auth_headers(user),
        **kwargs,
    )

    assert response.status_code == 403
    assert response.json() == {
        "error": {"code": "forbidden", "message": expected_message}
    }


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "payload",
    [
        {"question": "   "},
        {"question": "q" * 4_001},
        {"question": "Single question", "messages": []},
        {"question": "Single question", "conversation_id": str(uuid.uuid4())},
        {"question": "Single question", "prompt": "private"},
    ],
)
async def test_ask_rejects_invalid_or_conversation_state_requests(
    api_client: httpx.AsyncClient,
    db_session: AsyncSession,
    payload: dict[str, object],
) -> None:
    user = await _create_user(db_session, "invalid-ask")

    response = await api_client.post(ASK_PATH, headers=_auth_headers(user), json=payload)

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "params",
    [
        {"limit": 0},
        {"limit": 101},
        {"offset": -1},
        {"collection_id": "not-a-uuid"},
    ],
)
async def test_history_validates_pagination_and_filter(
    api_client: httpx.AsyncClient,
    db_session: AsyncSession,
    params: dict[str, object],
) -> None:
    user = await _create_user(db_session, "invalid-history")

    response = await api_client.get(
        HISTORY_PATH,
        headers=_auth_headers(user),
        params=params,
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


@pytest.mark.asyncio
async def test_ask_passes_normalized_question_collection_and_current_user_to_service(
    api_client: httpx.AsyncClient,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user = await _create_user(db_session, "service-arguments")
    collection = await _create_collection(db_session, user, "Service arguments")
    response_payload = QuestionAnswerResponse(
        question_id=uuid.uuid4(),
        collection_id=collection.id,
        answer="Grounded answer [1].",
        citations=[],
        created_at=datetime.now(UTC),
        provider=None,
        model=None,
    )
    captured: dict[str, object] = {}

    async def fake_answer_question(
        session: AsyncSession,
        **kwargs: object,
    ) -> QuestionAnswerResponse:
        captured["session"] = session
        captured.update(kwargs)
        return response_payload

    monkeypatch.setattr(question_answering_service, "answer_question", fake_answer_question)

    response = await api_client.post(
        ASK_PATH,
        headers=_auth_headers(user),
        json={"question": "  What is scoped?  ", "collection_id": str(collection.id)},
    )

    assert response.status_code == 200
    assert response.json() == response_payload.model_dump(mode="json")
    assert captured == {
        "session": db_session,
        "user_id": user.id,
        "question_text": "What is scoped?",
        "collection_id": collection.id,
        "document_ids": None,
    }


@pytest.mark.asyncio
async def test_ask_returns_and_persists_exact_no_document_fallback(
    api_client: httpx.AsyncClient,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user = await _create_user(db_session, "fallback")

    async def fake_embed_query(question: str) -> list[float]:
        assert question == "What is missing?"
        return _embedding()

    async def fail_generate(*args: object, **kwargs: object) -> GeneratedAnswer:
        raise AssertionError("the provider must not run without matching chunks")

    monkeypatch.setattr(
        question_answering_service.embeddings_service,
        "embed_query",
        fake_embed_query,
    )
    monkeypatch.setattr(question_answering_service, "generate_answer", fail_generate)

    response = await api_client.post(
        ASK_PATH,
        headers=_auth_headers(user),
        json={"question": "What is missing?"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["answer"] == FALLBACK_ANSWER
    assert payload["citations"] == []
    assert payload["provider"] is None
    assert payload["model"] is None
    persisted = await QuestionRepository(db_session).get_question(
        user.id,
        uuid.UUID(payload["question_id"]),
    )
    assert persisted is not None
    assert persisted.answer_text == FALLBACK_ANSWER
    assert persisted.context_chunks == []


@pytest.mark.asyncio
async def test_ask_returns_grounded_snapshot_citations_without_private_fields(
    api_client: httpx.AsyncClient,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user = await _create_user(db_session, "grounded")
    collection = await _create_collection(db_session, user, "Grounded")
    document = await _create_document(
        db_session,
        user,
        filename="grounded.txt",
        collection_id=collection.id,
    )
    original_content = "Exact supporting snapshot from the document."
    chunk = (
        await ChunkRepository(db_session).bulk_insert_chunks(
            document.id,
            [
                ChunkWithEmbedding(
                    chunk_index=7,
                    content=original_content,
                    embedding=_embedding(),
                )
            ],
        )
    )[0]

    async def fake_embed_query(question: str) -> list[float]:
        assert question == "What is grounded?"
        return _embedding()

    async def fake_generate(
        context: str,
        question: str,
        available_context_entries: int,
        **_: object,
    ) -> GeneratedAnswer:
        assert original_content in context
        assert question == "What is grounded?"
        assert available_context_entries == 1
        return GeneratedAnswer(
            answer_text="The snapshot grounds this answer [1].",
            model_used="grounded-model",
            citation_ranks=(1,),
        )

    monkeypatch.setattr(
        question_answering_service.embeddings_service,
        "embed_query",
        fake_embed_query,
    )
    monkeypatch.setattr(question_answering_service, "generate_answer", fake_generate)

    response = await api_client.post(
        ASK_PATH,
        headers=_auth_headers(user),
        json={"question": "What is grounded?", "collection_id": str(collection.id)},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["answer"] == "The snapshot grounds this answer [1]."
    assert payload["collection_id"] == str(collection.id)
    assert payload["provider"] == get_settings().ai_provider
    assert payload["model"] == "grounded-model"
    assert payload["citations"] == [
        {
            "rank": 1,
            "document_id": str(document.id),
            "document_filename": document.filename,
            "chunk_id": str(chunk.id),
            "chunk_index": 7,
            "excerpt": original_content,
            "distance": pytest.approx(0.0, abs=1e-6),
        }
    ]
    assert not {
        "embedding",
        "prompt",
        "chunk_content",
        "storage_path",
        "question_embedding",
    } & payload.keys()
    assert not {"prompt", "chunk_content", "storage_path"} & payload["citations"][0].keys()

    await db_session.execute(
        update(DocumentChunk)
        .where(DocumentChunk.id == chunk.id)
        .values(content="Changed live chunk content.")
    )
    detail = await api_client.get(
        f"{HISTORY_PATH}/{payload['question_id']}",
        headers=_auth_headers(user),
    )
    assert detail.status_code == 200
    assert detail.json()["citations"][0]["excerpt"] == original_content


@pytest.mark.asyncio
@pytest.mark.parametrize("use_foreign_collection", [False, True])
async def test_missing_and_foreign_collections_are_indistinguishable_for_ask_and_list(
    api_client: httpx.AsyncClient,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
    use_foreign_collection: bool,
) -> None:
    owner = await _create_user(db_session, "collection-owner")
    foreign_user = await _create_user(db_session, "collection-foreign")
    foreign_collection = await _create_collection(db_session, foreign_user, "Foreign")
    missing_collection_id = uuid.uuid4()
    owner_headers = _auth_headers(owner)
    collection_id = foreign_collection.id if use_foreign_collection else missing_collection_id

    async def fake_embed_query(question: str) -> list[float]:
        return _embedding()

    monkeypatch.setattr(
        question_answering_service.embeddings_service,
        "embed_query",
        fake_embed_query,
    )

    list_response = await api_client.get(
        HISTORY_PATH,
        headers=owner_headers,
        params={"collection_id": str(collection_id)},
    )
    ask_response = await api_client.post(
        ASK_PATH,
        headers=owner_headers,
        json={"question": "Can I access it?", "collection_id": str(collection_id)},
    )

    assert ask_response.status_code == 404
    assert ask_response.json() == COLLECTION_NOT_FOUND
    assert list_response.status_code == 404
    assert list_response.json() == COLLECTION_NOT_FOUND


@pytest.mark.asyncio
async def test_history_lists_newest_first_with_pagination_filtering_and_ranked_excerpts(
    api_client: httpx.AsyncClient,
    db_session: AsyncSession,
) -> None:
    owner = await _create_user(db_session, "history-owner")
    foreign_user = await _create_user(db_session, "history-foreign")
    seeded = await _seed_history(db_session, owner, foreign_user)

    full_response = await api_client.get(HISTORY_PATH, headers=_auth_headers(owner))
    page_response = await api_client.get(
        HISTORY_PATH,
        headers=_auth_headers(owner),
        params={"limit": 2, "offset": 1},
    )
    filter_response = await api_client.get(
        HISTORY_PATH,
        headers=_auth_headers(owner),
        params={"collection_id": str(seeded["first_collection"].id)},
    )

    assert full_response.status_code == 200
    full = full_response.json()
    assert full["limit"] == 20
    assert full["offset"] == 0
    assert full["total"] == 3
    assert [item["question_id"] for item in full["items"]] == [
        str(seeded["newest"].id),
        str(seeded["middle"].id),
        str(seeded["oldest"].id),
    ]
    newest = full["items"][0]
    assert [citation["rank"] for citation in newest["citations"]] == [1, 2]
    assert newest["citations"][0]["excerpt"] == f"{'x' * 500}…"
    assert set(newest) == {
        "question_id",
        "collection_id",
        "question",
        "answer",
        "citations",
        "created_at",
        "provider",
        "model",
    }
    assert full["items"][1]["provider"] is None
    assert full["items"][1]["model"] is None

    page = page_response.json()
    assert page["total"] == 3
    assert [item["question_id"] for item in page["items"]] == [
        str(seeded["middle"].id),
        str(seeded["oldest"].id),
    ]
    filtered = filter_response.json()
    assert filtered["total"] == 2
    assert [item["question_id"] for item in filtered["items"]] == [
        str(seeded["middle"].id),
        str(seeded["oldest"].id),
    ]
    assert str(seeded["foreign"].id) not in full_response.text


@pytest.mark.asyncio
async def test_history_detail_and_delete_enforce_owner_and_cascade_only_citations(
    api_client: httpx.AsyncClient,
    db_session: AsyncSession,
) -> None:
    owner = await _create_user(db_session, "detail-owner")
    foreign_user = await _create_user(db_session, "detail-foreign")
    seeded = await _seed_history(db_session, owner, foreign_user)
    newest = seeded["newest"]
    foreign = seeded["foreign"]
    missing_id = uuid.uuid4()

    detail = await api_client.get(
        f"{HISTORY_PATH}/{newest.id}",
        headers=_auth_headers(owner),
    )
    foreign_detail = await api_client.get(
        f"{HISTORY_PATH}/{foreign.id}",
        headers=_auth_headers(owner),
    )
    missing_detail = await api_client.get(
        f"{HISTORY_PATH}/{missing_id}",
        headers=_auth_headers(owner),
    )
    foreign_delete = await api_client.delete(
        f"{HISTORY_PATH}/{foreign.id}",
        headers=_auth_headers(owner),
    )
    missing_delete = await api_client.delete(
        f"{HISTORY_PATH}/{missing_id}",
        headers=_auth_headers(owner),
    )

    assert detail.status_code == 200
    assert detail.json()["question_id"] == str(newest.id)
    assert [citation["rank"] for citation in detail.json()["citations"]] == [1, 2]
    for response in (foreign_detail, missing_detail, foreign_delete, missing_delete):
        assert response.status_code == 404
        assert response.json() == QUESTION_NOT_FOUND

    delete_response = await api_client.delete(
        f"{HISTORY_PATH}/{newest.id}",
        headers=_auth_headers(owner),
    )

    assert delete_response.status_code == 204
    assert delete_response.content == b""
    assert await db_session.get(Question, newest.id) is None
    citation_count = await db_session.scalar(
        select(func.count())
        .select_from(QuestionContextChunk)
        .where(QuestionContextChunk.question_id == newest.id)
    )
    assert citation_count == 0
    assert await db_session.get(User, owner.id) is not None
    assert await db_session.get(Collection, seeded["second_collection"].id) is not None
    assert await db_session.get(Question, seeded["middle"].id) is not None
    assert await db_session.get(Question, foreign.id) is not None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("provider_error", "expected_status", "expected_code", "expected_message"),
    [
        (
            LLMTransientError(category="timeout-with-sk-provider-secret"),
            503,
            "question_answering_unavailable",
            "Question answering service is temporarily unavailable.",
        ),
        (
            LLMInvalidResponseError(),
            502,
            "question_answering_provider_error",
            "Question answering service failed.",
        ),
        (
            LLMRejectedError(status_code=401),
            502,
            "question_answering_provider_error",
            "Question answering service failed.",
        ),
        (
            LLMRejectedError(status_code=400),
            502,
            "question_answering_provider_error",
            "Question answering service failed.",
        ),
    ],
)
async def test_ask_maps_provider_failures_without_fallback_or_raw_details(
    api_client: httpx.AsyncClient,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
    provider_error: Exception,
    expected_status: int,
    expected_code: str,
    expected_message: str,
) -> None:
    user = await _create_user(db_session, f"provider-{expected_status}")

    async def fail_answer(*args: object, **kwargs: object) -> QuestionAnswerResponse:
        raise provider_error

    monkeypatch.setattr(question_answering_service, "answer_question", fail_answer)

    response = await api_client.post(
        ASK_PATH,
        headers=_auth_headers(user),
        json={"question": "Will the provider fail?"},
    )

    assert response.status_code == expected_status
    assert response.json() == {
        "error": {"code": expected_code, "message": expected_message}
    }
    assert str(provider_error) not in response.text
    assert "sk-provider-secret" not in response.text
    assert FALLBACK_ANSWER not in response.text
    assert await QuestionRepository(db_session).count_questions(user.id) == 0


@pytest.mark.asyncio
async def test_ask_maps_unexpected_failure_to_secret_free_500(
    api_client: httpx.AsyncClient,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    user = await _create_user(db_session, "unexpected")
    raw_secret = "sk-live-secret prompt=/private/prompt storage=/private/chunk"

    async def fail_answer(*args: object, **kwargs: object) -> QuestionAnswerResponse:
        raise RuntimeError(raw_secret)

    monkeypatch.setattr(question_answering_service, "answer_question", fail_answer)

    response = await api_client.post(
        ASK_PATH,
        headers=_auth_headers(user),
        json={"question": "Will this fail safely?"},
    )

    assert response.status_code == 500
    assert response.json() == {
        "error": {
            "code": "internal_server_error",
            "message": "An unexpected error occurred.",
        }
    }
    assert raw_secret not in response.text
    assert raw_secret not in caplog.text
    assert FALLBACK_ANSWER not in response.text
