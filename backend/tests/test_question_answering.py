from __future__ import annotations

import uuid
from dataclasses import FrozenInstanceError

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

import app.services.question_answering as question_answering_service
from app.core.settings import get_settings
from app.db.models.auth import User
from app.db.models.collections import Collection
from app.db.models.documents import Document, DocumentStatus
from app.db.models.questions import Question
from app.repositories.chunk_repository import ChunkRepository
from app.repositories.document_repository import DocumentRepository
from app.repositories.types import ChunkWithEmbedding


def _embedding(first_dim: float, second_dim: float) -> list[float]:
    dim = get_settings().embedding_dim
    if dim < 2:
        raise ValueError("embedding_dim must be at least 2 for retrieval tests")
    return [first_dim, second_dim] + [0.0] * (dim - 2)


async def _create_user(session: AsyncSession, label: str) -> User:
    user = User(
        email=f"retrieval-{label}-{uuid.uuid4()}@example.com",
        password_hash="test-password-hash",
        first_name="Retrieval",
        last_name="Tester",
    )
    session.add(user)
    await session.flush()
    return user


async def _create_collection(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    name: str,
) -> Collection:
    collection = Collection(user_id=user_id, name=name)
    session.add(collection)
    await session.flush()
    return collection


async def _create_document(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    filename: str,
    status: DocumentStatus = DocumentStatus.READY,
    collection_id: uuid.UUID | None = None,
) -> Document:
    return await DocumentRepository(session).create_document(
        user_id,
        collection_id=collection_id,
        filename=filename,
        original_extension=".txt",
        content_type="text/plain",
        size_bytes=42,
        storage_path=f"/tmp/{filename}",
        extracted_text="retrieval fixture",
        status=status,
    )


async def _insert_chunk(
    session: AsyncSession,
    *,
    document: Document,
    content: str,
    embedding: list[float],
    chunk_index: int = 0,
) -> uuid.UUID:
    chunks = await ChunkRepository(session).bulk_insert_chunks(
        document.id,
        [
            ChunkWithEmbedding(
                chunk_index=chunk_index,
                content=content,
                embedding=embedding,
            )
        ],
    )
    return chunks[0].id


@pytest.mark.asyncio
async def test_retrieve_question_context_uses_shared_embedding_outside_transaction_and_formats(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    owner = await _create_user(db_session, "owner")
    foreign_user = await _create_user(db_session, "foreign")
    first_document = await _create_document(
        db_session,
        user_id=owner.id,
        filename="first.txt",
    )
    second_document = await _create_document(
        db_session,
        user_id=owner.id,
        filename="second.txt",
    )
    pending_document = await _create_document(
        db_session,
        user_id=owner.id,
        filename="pending.txt",
        status=DocumentStatus.PENDING,
    )
    foreign_document = await _create_document(
        db_session,
        user_id=foreign_user.id,
        filename="foreign.txt",
    )

    first_chunk_id = await _insert_chunk(
        db_session,
        document=first_document,
        content="First owner content.",
        embedding=_embedding(1.0, 0.0),
        chunk_index=2,
    )
    second_chunk_id = await _insert_chunk(
        db_session,
        document=second_document,
        content="Second owner content.",
        embedding=_embedding(0.9, 0.1),
        chunk_index=4,
    )
    await _insert_chunk(
        db_session,
        document=pending_document,
        content="Pending content must be excluded.",
        embedding=_embedding(1.0, 0.0),
    )
    await _insert_chunk(
        db_session,
        document=foreign_document,
        content="Foreign content must be excluded.",
        embedding=_embedding(1.0, 0.0),
    )
    await db_session.commit()

    query_embedding = _embedding(1.0, 0.0)
    embedding_calls: list[str] = []

    async def fake_embed_query(text: str) -> list[float]:
        assert not db_session.in_transaction()
        embedding_calls.append(text)
        return query_embedding

    async def fail_generate_answer(*args: object, **kwargs: object) -> object:
        raise AssertionError("retrieval must not call the chat LLM")

    monkeypatch.setattr(
        question_answering_service.embeddings_service,
        "embed_query",
        fake_embed_query,
    )
    monkeypatch.setattr(question_answering_service, "generate_answer", fail_generate_answer)

    result = await question_answering_service.retrieve_question_context(
        db_session,
        user_id=owner.id,
        question_text="  What is included?  ",
        top_k=10,
    )

    expected_context = (
        f"[1]\n"
        f"document_filename: first.txt\n"
        f"document_id: {first_document.id}\n"
        f"chunk_id: {first_chunk_id}\n"
        f"chunk_index: 2\n"
        f"content:\n"
        f"First owner content.\n\n---\n\n"
        f"[2]\n"
        f"document_filename: second.txt\n"
        f"document_id: {second_document.id}\n"
        f"chunk_id: {second_chunk_id}\n"
        f"chunk_index: 4\n"
        f"content:\n"
        f"Second owner content."
    )
    assert embedding_calls == ["What is included?"]
    assert not db_session.in_transaction()
    assert result.normalized_question == "What is included?"
    assert result.query_embedding == tuple(query_embedding)
    assert result.collection_id is None
    assert result.context_text == expected_context
    assert [chunk.rank for chunk in result.chunks] == [1, 2]
    assert [chunk.chunk_id for chunk in result.chunks] == [first_chunk_id, second_chunk_id]
    assert [chunk.document_filename for chunk in result.chunks] == ["first.txt", "second.txt"]
    assert isinstance(result.chunks, tuple)
    with pytest.raises(FrozenInstanceError):
        result.chunks[0].content = "mutated"  # type: ignore[misc]

    question_count = await db_session.scalar(select(func.count()).select_from(Question))
    assert question_count == 0


@pytest.mark.asyncio
async def test_retrieve_question_context_validates_owned_collection_and_scopes_search(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    owner = await _create_user(db_session, "collection-owner")
    selected_collection = await _create_collection(
        db_session,
        user_id=owner.id,
        name="Selected",
    )
    other_collection = await _create_collection(
        db_session,
        user_id=owner.id,
        name="Other",
    )
    selected_document = await _create_document(
        db_session,
        user_id=owner.id,
        collection_id=selected_collection.id,
        filename="selected.txt",
    )
    other_document = await _create_document(
        db_session,
        user_id=owner.id,
        collection_id=other_collection.id,
        filename="other.txt",
    )
    selected_chunk_id = await _insert_chunk(
        db_session,
        document=selected_document,
        content="Selected collection content.",
        embedding=_embedding(0.9, 0.1),
    )
    await _insert_chunk(
        db_session,
        document=other_document,
        content="Closer but outside the selected collection.",
        embedding=_embedding(1.0, 0.0),
    )
    await db_session.commit()

    async def fake_embed_query(text: str) -> list[float]:
        return _embedding(1.0, 0.0)

    monkeypatch.setattr(
        question_answering_service.embeddings_service,
        "embed_query",
        fake_embed_query,
    )

    result = await question_answering_service.retrieve_question_context(
        db_session,
        user_id=owner.id,
        question_text="Search one collection",
        collection_id=selected_collection.id,
        top_k=10,
    )

    assert result.collection_id == selected_collection.id
    assert [chunk.chunk_id for chunk in result.chunks] == [selected_chunk_id]
    assert "Selected collection content." in result.context_text
    assert "outside the selected collection" not in result.context_text


@pytest.mark.asyncio
async def test_retrieve_question_context_hides_missing_and_foreign_collections(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    owner = await _create_user(db_session, "not-found-owner")
    foreign_user = await _create_user(db_session, "not-found-foreign")
    foreign_collection = await _create_collection(
        db_session,
        user_id=foreign_user.id,
        name="Foreign",
    )
    owner_id = owner.id
    foreign_collection_id = foreign_collection.id
    await db_session.commit()

    embedding_calls = 0

    async def fake_embed_query(text: str) -> list[float]:
        nonlocal embedding_calls
        embedding_calls += 1
        assert not db_session.in_transaction()
        return _embedding(1.0, 0.0)

    monkeypatch.setattr(
        question_answering_service.embeddings_service,
        "embed_query",
        fake_embed_query,
    )

    errors: list[question_answering_service.CollectionNotFoundError] = []
    for collection_id in (foreign_collection_id, uuid.uuid4()):
        with pytest.raises(question_answering_service.CollectionNotFoundError) as exc_info:
            await question_answering_service.retrieve_question_context(
                db_session,
                user_id=owner_id,
                question_text="Search safely",
                collection_id=collection_id,
            )
        errors.append(exc_info.value)
        assert not db_session.in_transaction()

    assert embedding_calls == 2
    assert [str(error) for error in errors] == ["Collection not found.", "Collection not found."]


@pytest.mark.asyncio
async def test_retrieve_question_context_returns_empty_result_without_ready_matches(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    owner = await _create_user(db_session, "empty-owner")
    pending_document = await _create_document(
        db_session,
        user_id=owner.id,
        filename="not-ready.txt",
        status=DocumentStatus.PROCESSING,
    )
    await _insert_chunk(
        db_session,
        document=pending_document,
        content="Not ready.",
        embedding=_embedding(1.0, 0.0),
    )
    await db_session.commit()

    async def fake_embed_query(text: str) -> list[float]:
        return _embedding(1.0, 0.0)

    monkeypatch.setattr(
        question_answering_service.embeddings_service,
        "embed_query",
        fake_embed_query,
    )

    result = await question_answering_service.retrieve_question_context(
        db_session,
        user_id=owner.id,
        question_text="Nothing ready",
    )

    assert result.context_text == ""
    assert result.chunks == ()


@pytest.mark.asyncio
async def test_retrieve_question_context_caps_and_snapshots_exact_truncated_content(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    owner = await _create_user(db_session, "truncation-owner")
    document = await _create_document(
        db_session,
        user_id=owner.id,
        filename="long.txt",
    )
    chunk_id = await _insert_chunk(
        db_session,
        document=document,
        content="alpha beta gamma delta epsilon zeta eta theta",
        embedding=_embedding(1.0, 0.0),
        chunk_index=7,
    )
    await db_session.commit()

    async def fake_embed_query(text: str) -> list[float]:
        return _embedding(1.0, 0.0)

    monkeypatch.setattr(
        question_answering_service.embeddings_service,
        "embed_query",
        fake_embed_query,
    )

    header = (
        f"[1]\n"
        f"document_filename: long.txt\n"
        f"document_id: {document.id}\n"
        f"chunk_id: {chunk_id}\n"
        f"chunk_index: 7\n"
        f"content:\n"
    )
    max_context_chars = len(header) + 35
    result = await question_answering_service.retrieve_question_context(
        db_session,
        user_id=owner.id,
        question_text="Truncate this",
        top_k=1,
        max_context_chars=max_context_chars,
    )

    expected_content = "alpha beta\n[content truncated]"
    assert len(result.context_text) <= max_context_chars
    assert result.context_text == f"{header}{expected_content}"
    assert result.chunks[0].content == expected_content
    assert result.context_text.split("content:\n", maxsplit=1)[1] == result.chunks[0].content


@pytest.mark.asyncio
async def test_retrieve_question_context_never_emits_empty_sections_and_reranks(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    owner = await _create_user(db_session, "rerank-owner")
    document = await _create_document(
        db_session,
        user_id=owner.id,
        filename="rerank.txt",
    )
    await _insert_chunk(
        db_session,
        document=document,
        content="   \n  ",
        embedding=_embedding(1.0, 0.0),
        chunk_index=0,
    )
    included_chunk_id = await _insert_chunk(
        db_session,
        document=document,
        content="Included after blank content.",
        embedding=_embedding(0.9, 0.1),
        chunk_index=1,
    )
    await db_session.commit()

    async def fake_embed_query(text: str) -> list[float]:
        return _embedding(1.0, 0.0)

    monkeypatch.setattr(
        question_answering_service.embeddings_service,
        "embed_query",
        fake_embed_query,
    )

    result = await question_answering_service.retrieve_question_context(
        db_session,
        user_id=owner.id,
        question_text="Re-rank",
        top_k=10,
    )

    assert len(result.chunks) == 1
    assert result.chunks[0].rank == 1
    assert result.chunks[0].chunk_id == included_chunk_id
    assert result.context_text.startswith("[1]\n")
    assert "[2]\n" not in result.context_text


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("question_text", "top_k", "max_context_chars", "message"),
    [
        ("   ", None, 100, "question_text must not be blank"),
        ("valid", 0, 100, "top_k must be greater than 0"),
        ("valid", -1, 100, "top_k must be greater than 0"),
        ("valid", 1, 0, "max_context_chars must be greater than 0"),
        ("valid", 1, -1, "max_context_chars must be greater than 0"),
    ],
)
async def test_retrieve_question_context_validates_before_embedding(
    question_text: str,
    top_k: int | None,
    max_context_chars: int,
    message: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = AsyncSession()

    async def fail_embed_query(text: str) -> list[float]:
        raise AssertionError("invalid input must not be embedded")

    monkeypatch.setattr(
        question_answering_service.embeddings_service,
        "embed_query",
        fail_embed_query,
    )

    with pytest.raises(ValueError, match=message):
        await question_answering_service.retrieve_question_context(
            session,
            user_id=uuid.uuid4(),
            question_text=question_text,
            top_k=top_k,
            max_context_chars=max_context_chars,
        )

    assert not session.in_transaction()
    await session.close()


@pytest.mark.asyncio
async def test_retrieve_question_context_rejects_an_existing_transaction_before_embedding(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = AsyncSession()
    await session.begin()

    async def fail_embed_query(text: str) -> list[float]:
        raise AssertionError("embedding must not run inside a transaction")

    monkeypatch.setattr(
        question_answering_service.embeddings_service,
        "embed_query",
        fail_embed_query,
    )

    with pytest.raises(RuntimeError, match="without an active transaction"):
        await question_answering_service.retrieve_question_context(
            session,
            user_id=uuid.uuid4(),
            question_text="valid",
        )

    await session.rollback()
    await session.close()
