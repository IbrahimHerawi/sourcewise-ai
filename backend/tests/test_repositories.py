from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.settings import get_settings
from app.db.models.auth import User
from app.db.models.collections import Collection
from app.db.models.documents import Document, DocumentStatus
from app.db.models.question_context_chunks import QuestionContextChunk
from app.db.models.questions import Question
from app.repositories.chunk_repository import ChunkRepository
from app.repositories.document_repository import DocumentRepository
from app.repositories.question_context_repository import QuestionContextRepository
from app.repositories.question_repository import QuestionRepository
from app.repositories.types import ChunkWithEmbedding, QuestionContextRow


def _embedding(first_dim: float, second_dim: float, dim: int) -> list[float]:
    if dim < 2:
        raise ValueError("embedding_dim must be at least 2 for repository tests")
    return [first_dim, second_dim] + [0.0] * (dim - 2)


async def _create_document(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    filename: str,
    collection_id: uuid.UUID | None = None,
    extracted_text: str = "sample extracted text",
) -> Document:
    repository = DocumentRepository(session)
    return await repository.create_document(
        user_id,
        collection_id=collection_id,
        filename=filename,
        original_extension=".txt",
        content_type="text/plain",
        size_bytes=42,
        storage_path=f"/tmp/{filename}",
        extracted_text=extracted_text,
    )


async def _create_user(session: AsyncSession, label: str) -> User:
    user = User(
        email=f"{label}-{uuid.uuid4()}@example.com",
        password_hash="test-password-hash",
        first_name="Document",
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


async def _set_created_at(
    session: AsyncSession,
    document: Document,
    created_at: datetime,
) -> None:
    await session.execute(
        update(Document).where(Document.id == document.id).values(created_at=created_at)
    )
    await session.flush()
    await session.refresh(document)


async def _set_question_created_at(
    session: AsyncSession,
    question: Question,
    created_at: datetime,
) -> None:
    await session.execute(
        update(Question).where(Question.id == question.id).values(created_at=created_at)
    )
    await session.flush()
    await session.refresh(question)


@pytest.mark.asyncio
async def test_document_repository_crud_create_get_update_status(db_session: AsyncSession) -> None:
    repository = DocumentRepository(db_session)
    owner = await _create_user(db_session, "document-owner")
    other_user = await _create_user(db_session, "document-other")
    collection = await _create_collection(
        db_session,
        user_id=owner.id,
        name="Owner collection",
    )

    created = await repository.create_document(
        owner.id,
        collection_id=collection.id,
        filename="doc-a.txt",
        original_extension=".txt",
        content_type="text/plain",
        size_bytes=111,
        storage_path="/tmp/doc-a.txt",
        extracted_text="hello world",
    )
    other_document = await _create_document(
        db_session,
        user_id=other_user.id,
        filename="other.txt",
    )
    fetched = await repository.get_document(owner.id, created.id)
    assert fetched is not None
    assert fetched.id == created.id
    assert fetched.user_id == owner.id
    assert fetched.collection_id == collection.id
    assert fetched.status == DocumentStatus.PENDING
    assert await repository.get_document(other_user.id, created.id) is None
    assert await repository.get_document(owner.id, other_document.id) is None
    assert (
        await repository.update_status(
            other_user.id,
            created.id,
            DocumentStatus.FAILED,
            "must remain hidden",
        )
        is None
    )
    assert await repository.delete_document(other_user.id, created.id) is None

    updated = await repository.update_status(owner.id, created.id, DocumentStatus.READY)
    fetched_after_update = await repository.get_document(owner.id, created.id)

    assert updated is not None
    assert updated.status == DocumentStatus.READY
    assert fetched_after_update is not None
    assert fetched_after_update.status == DocumentStatus.READY

    deleted = await repository.delete_document(owner.id, created.id)
    assert deleted is not None
    assert deleted.id == created.id
    assert await repository.get_document(owner.id, created.id) is None
    assert await repository.get_document(other_user.id, other_document.id) is not None


@pytest.mark.asyncio
async def test_document_repository_creates_pending_document_without_extracted_text(
    db_session: AsyncSession,
) -> None:
    repository = DocumentRepository(db_session)
    owner = await _create_user(db_session, "pending-document-owner")

    created = await repository.create_document(
        owner.id,
        filename="pending.txt",
        original_extension=".txt",
        content_type="text/plain",
        size_bytes=42,
        storage_path="/tmp/pending.txt",
    )

    assert created.status == DocumentStatus.PENDING
    assert created.extracted_text is None


@pytest.mark.asyncio
async def test_document_repository_list_documents_orders_newest_first_and_counts_total(
    db_session: AsyncSession,
) -> None:
    repository = DocumentRepository(db_session)
    owner = await _create_user(db_session, "document-list-owner")
    other_user = await _create_user(db_session, "document-list-other")
    first_collection = await _create_collection(
        db_session,
        user_id=owner.id,
        name="First collection",
    )
    second_collection = await _create_collection(
        db_session,
        user_id=owner.id,
        name="Second collection",
    )

    oldest = await _create_document(
        db_session,
        user_id=owner.id,
        collection_id=first_collection.id,
        filename="oldest.txt",
    )
    middle = await _create_document(
        db_session,
        user_id=owner.id,
        collection_id=first_collection.id,
        filename="middle.txt",
    )
    newest = await _create_document(
        db_session,
        user_id=owner.id,
        collection_id=second_collection.id,
        filename="newest.txt",
    )
    other_document = await _create_document(
        db_session,
        user_id=other_user.id,
        collection_id=first_collection.id,
        filename="foreign-owned.txt",
    )

    await _set_created_at(db_session, oldest, datetime(2026, 1, 1, 12, 0, tzinfo=UTC))
    await _set_created_at(db_session, middle, datetime(2026, 1, 2, 12, 0, tzinfo=UTC))
    await _set_created_at(db_session, newest, datetime(2026, 1, 2, 12, 0, tzinfo=UTC))
    await _set_created_at(
        db_session,
        other_document,
        datetime(2026, 1, 3, 12, 0, tzinfo=UTC),
    )

    listed = await repository.list_documents(owner.id, limit=2, offset=0)
    expected_tied_ids = sorted((middle.id, newest.id), reverse=True)
    filtered = await repository.list_documents(
        owner.id,
        limit=20,
        offset=0,
        collection_id=first_collection.id,
    )

    assert [document.id for document in listed] == expected_tied_ids
    assert [document.id for document in filtered] == [middle.id, oldest.id]
    assert other_document.id not in {document.id for document in filtered}
    assert await repository.count_documents(owner.id) == 3
    assert await repository.count_documents(other_user.id) == 1
    assert await repository.count_documents(owner.id, first_collection.id) == 2
    assert (
        await repository.list_documents(
            other_user.id,
            limit=20,
            offset=0,
            collection_id=first_collection.id,
        )
        == []
    )
    assert await repository.count_documents(other_user.id, first_collection.id) == 0


@pytest.mark.asyncio
async def test_chunk_repository_bulk_insert_chunks_enforces_document_chunk_index_uniqueness(
    db_session: AsyncSession,
) -> None:
    settings = get_settings()
    repository = ChunkRepository(db_session)
    user = await _create_user(db_session, "chunk-unique-owner")

    first_document = await _create_document(
        db_session,
        user_id=user.id,
        filename="first.txt",
    )
    second_document = await _create_document(
        db_session,
        user_id=user.id,
        filename="second.txt",
    )

    inserted_rows = await repository.bulk_insert_chunks(
        first_document.id,
        [
            ChunkWithEmbedding(
                chunk_index=0,
                content="first chunk",
                embedding=_embedding(1.0, 0.0, settings.embedding_dim),
            ),
            ChunkWithEmbedding(
                chunk_index=1,
                content="second chunk",
                embedding=_embedding(0.0, 1.0, settings.embedding_dim),
            ),
        ],
    )
    inserted_second_doc = await repository.bulk_insert_chunks(
        second_document.id,
        [
            ChunkWithEmbedding(
                chunk_index=0,
                content="same index, different document",
                embedding=_embedding(1.0, 1.0, settings.embedding_dim),
            )
        ],
    )

    assert [(chunk.document_id, chunk.chunk_index) for chunk in inserted_rows] == [
        (first_document.id, 0),
        (first_document.id, 1),
    ]
    assert len(inserted_second_doc) == 1
    assert inserted_second_doc[0].document_id == second_document.id
    assert inserted_second_doc[0].chunk_index == 0

    with pytest.raises(IntegrityError):
        await repository.bulk_insert_chunks(
            first_document.id,
            [
                ChunkWithEmbedding(
                    chunk_index=0,
                    content="duplicate index",
                    embedding=_embedding(0.9, 0.1, settings.embedding_dim),
                )
            ],
        )


@pytest.mark.asyncio
async def test_chunk_repository_similarity_search_orders_by_cosine_distance(
    db_session: AsyncSession,
) -> None:
    settings = get_settings()
    repository = ChunkRepository(db_session)
    user = await _create_user(db_session, "chunk-similarity-owner")
    document = await _create_document(
        db_session,
        user_id=user.id,
        filename="similarity.txt",
    )

    await repository.bulk_insert_chunks(
        document.id,
        [
            ChunkWithEmbedding(
                chunk_index=0,
                content="vector [1, 0]",
                embedding=_embedding(1.0, 0.0, settings.embedding_dim),
            ),
            ChunkWithEmbedding(
                chunk_index=1,
                content="vector [0, 1]",
                embedding=_embedding(0.0, 1.0, settings.embedding_dim),
            ),
            ChunkWithEmbedding(
                chunk_index=2,
                content="vector [1, 1]",
                embedding=_embedding(1.0, 1.0, settings.embedding_dim),
            ),
        ],
    )
    await DocumentRepository(db_session).update_status(
        user.id,
        document.id,
        DocumentStatus.READY,
    )

    query_embedding = _embedding(0.9, 0.1, settings.embedding_dim)
    results = await repository.similarity_search(
        user_id=user.id,
        query_embedding=query_embedding,
        top_k=3,
    )

    assert [result.chunk_index for result in results] == [0, 2, 1]
    assert results[0].distance < results[1].distance < results[2].distance


@pytest.mark.asyncio
async def test_question_repository_creates_grounded_and_fallback_records_without_commit(
    db_session: AsyncSession,
) -> None:
    settings = get_settings()
    repository = QuestionRepository(db_session)
    user = await _create_user(db_session, "question-create-owner")
    collection = await _create_collection(
        db_session,
        user_id=user.id,
        name="Question creation",
    )
    transaction = await db_session.begin_nested()

    grounded = await repository.create_question(
        user.id,
        collection_id=collection.id,
        question_text="What supports the grounded answer?",
        embedding=_embedding(1.0, 0.0, settings.embedding_dim),
        answer_text="A citation snapshot.",
        ai_provider="ollama",
        model_used="grounded-model",
    )
    fallback = await repository.create_question(
        user.id,
        question_text="What happens without enough context?",
        embedding=_embedding(0.0, 1.0, settings.embedding_dim),
        answer_text="A deterministic fallback is returned.",
        ai_provider=None,
        model_used=None,
    )

    assert grounded.user_id == user.id
    assert grounded.collection_id == collection.id
    assert grounded.ai_provider == "ollama"
    assert grounded.model_used == "grounded-model"
    assert fallback.user_id == user.id
    assert fallback.collection_id is None
    assert fallback.ai_provider is None
    assert fallback.model_used is None

    grounded_id = grounded.id
    fallback_id = fallback.id
    await transaction.rollback()
    persisted = await db_session.scalar(
        select(func.count())
        .select_from(Question)
        .where(Question.id.in_([grounded_id, fallback_id]))
    )
    assert persisted == 0


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("ai_provider", "model_used"),
    [("ollama", None), (None, "model-without-provider")],
)
async def test_question_repository_rejects_partial_llm_metadata_without_sql(
    ai_provider: str | None,
    model_used: str | None,
) -> None:
    session = AsyncMock(spec=AsyncSession)
    repository = QuestionRepository(session)

    with pytest.raises(
        ValueError,
        match="ai_provider and model_used must both be null or both be non-null",
    ):
        await repository.create_question(
            uuid.uuid4(),
            question_text="Invalid metadata pair?",
            embedding=[0.0] * get_settings().embedding_dim,
            answer_text="This must not be persisted.",
            ai_provider=ai_provider,
            model_used=model_used,
        )

    session.add.assert_not_called()
    session.flush.assert_not_awaited()
    session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_question_repository_lists_counts_paginates_and_filters_per_owner(
    db_session: AsyncSession,
) -> None:
    settings = get_settings()
    repository = QuestionRepository(db_session)
    owner = await _create_user(db_session, "question-history-owner")
    other_user = await _create_user(db_session, "question-history-other")
    first_collection = await _create_collection(
        db_session,
        user_id=owner.id,
        name="First question collection",
    )
    second_collection = await _create_collection(
        db_session,
        user_id=owner.id,
        name="Second question collection",
    )

    oldest = await repository.create_question(
        owner.id,
        collection_id=first_collection.id,
        question_text="Oldest question?",
        embedding=_embedding(1.0, 0.0, settings.embedding_dim),
        answer_text="Oldest answer.",
        ai_provider="ollama",
        model_used="model-a",
    )
    middle = await repository.create_question(
        owner.id,
        collection_id=first_collection.id,
        question_text="Middle question?",
        embedding=_embedding(0.8, 0.2, settings.embedding_dim),
        answer_text="Middle answer.",
        ai_provider=None,
        model_used=None,
    )
    newest = await repository.create_question(
        owner.id,
        collection_id=second_collection.id,
        question_text="Newest question?",
        embedding=_embedding(0.0, 1.0, settings.embedding_dim),
        answer_text="Newest answer.",
        ai_provider="openai",
        model_used="model-c",
    )
    foreign_question = await repository.create_question(
        other_user.id,
        question_text="Foreign question?",
        embedding=_embedding(0.5, 0.5, settings.embedding_dim),
        answer_text="This belongs to another user.",
        ai_provider=None,
        model_used=None,
    )
    await _set_question_created_at(
        db_session,
        oldest,
        datetime(2026, 1, 1, 12, 0, tzinfo=UTC),
    )
    await _set_question_created_at(
        db_session,
        middle,
        datetime(2026, 1, 2, 12, 0, tzinfo=UTC),
    )
    await _set_question_created_at(
        db_session,
        newest,
        datetime(2026, 1, 3, 12, 0, tzinfo=UTC),
    )
    await _set_question_created_at(
        db_session,
        foreign_question,
        datetime(2026, 1, 4, 12, 0, tzinfo=UTC),
    )

    page = await repository.list_questions(owner.id, limit=2, offset=1)
    filtered = await repository.list_questions(
        owner.id,
        limit=20,
        offset=0,
        collection_id=first_collection.id,
    )

    assert [question.id for question in page] == [middle.id, oldest.id]
    assert [question.id for question in filtered] == [middle.id, oldest.id]
    assert await repository.count_questions(owner.id) == 3
    assert await repository.count_questions(owner.id, first_collection.id) == 2
    assert await repository.count_questions(other_user.id) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("limit", "offset", "message"),
    [
        (0, 0, "limit must be greater than 0"),
        (-1, 0, "limit must be greater than 0"),
        (1, -1, "offset must be greater than or equal to 0"),
    ],
)
async def test_question_repository_validates_pagination(
    limit: int,
    offset: int,
    message: str,
) -> None:
    session = AsyncMock(spec=AsyncSession)
    repository = QuestionRepository(session)

    with pytest.raises(ValueError, match=message):
        await repository.list_questions(uuid.uuid4(), limit=limit, offset=offset)

    session.scalars.assert_not_awaited()


@pytest.mark.asyncio
async def test_question_repository_detail_delete_citations_and_document_independence(
    db_session: AsyncSession,
) -> None:
    settings = get_settings()
    question_repository = QuestionRepository(db_session)
    context_repository = QuestionContextRepository(db_session)
    document_repository = DocumentRepository(db_session)
    owner = await _create_user(db_session, "question-detail-owner")
    other_user = await _create_user(db_session, "question-detail-other")

    deleted_document = await _create_document(
        db_session,
        user_id=owner.id,
        filename="deleted-source.txt",
    )
    deleted_chunk = (
        await ChunkRepository(db_session).bulk_insert_chunks(
            deleted_document.id,
            [
                ChunkWithEmbedding(
                    chunk_index=4,
                    content="Original live content that will be deleted.",
                    embedding=_embedding(1.0, 0.0, settings.embedding_dim),
                )
            ],
        )
    )[0]
    historical_question = await question_repository.create_question(
        owner.id,
        question_text="Will citation history survive source deletion?",
        embedding=_embedding(1.0, 0.0, settings.embedding_dim),
        answer_text="Yes, because citations are snapshots.",
        ai_provider="ollama",
        model_used="history-model",
    )
    await context_repository.bulk_insert_question_context(
        historical_question.id,
        [
            QuestionContextRow(
                rank=2,
                document_id=deleted_document.id,
                document_filename="deleted-source.txt",
                chunk_id=uuid.uuid4(),
                chunk_index=8,
                chunk_content="Second-ranked immutable snapshot.",
                similarity_score=0.22,
            ),
            QuestionContextRow(
                rank=1,
                document_id=deleted_document.id,
                document_filename="deleted-source.txt",
                chunk_id=deleted_chunk.id,
                chunk_index=deleted_chunk.chunk_index,
                chunk_content="First-ranked immutable snapshot.",
                similarity_score=0.11,
            ),
        ],
    )
    assert await document_repository.delete_document(owner.id, deleted_document.id) is not None

    live_document = await _create_document(
        db_session,
        user_id=owner.id,
        filename="live-source.txt",
    )
    deletable_question = await question_repository.create_question(
        owner.id,
        question_text="Can this history item be deleted?",
        embedding=_embedding(0.0, 1.0, settings.embedding_dim),
        answer_text="Yes.",
        ai_provider=None,
        model_used=None,
    )
    await context_repository.bulk_insert_question_context(
        deletable_question.id,
        [
            QuestionContextRow(
                rank=1,
                document_id=live_document.id,
                document_filename=live_document.filename,
                chunk_id=uuid.uuid4(),
                chunk_index=0,
                chunk_content="Citation removed only with its question.",
                similarity_score=0.33,
            )
        ],
    )
    foreign_question = await question_repository.create_question(
        other_user.id,
        question_text="Who owns this question?",
        embedding=_embedding(0.5, 0.5, settings.embedding_dim),
        answer_text="Another user.",
        ai_provider=None,
        model_used=None,
    )
    historical_question_id = historical_question.id
    deletable_question_id = deletable_question.id
    foreign_question_id = foreign_question.id
    live_document_id = live_document.id
    db_session.expunge_all()

    detail = await question_repository.get_question(owner.id, historical_question_id)
    assert detail is not None
    assert [citation.rank for citation in detail.context_chunks] == [1, 2]
    assert [citation.chunk_content for citation in detail.context_chunks] == [
        "First-ranked immutable snapshot.",
        "Second-ranked immutable snapshot.",
    ]
    history = await question_repository.list_questions(owner.id, limit=20, offset=0)
    assert historical_question_id in {question.id for question in history}
    assert await question_repository.get_question(owner.id, foreign_question_id) is None
    assert not await question_repository.delete_question(owner.id, foreign_question_id)

    assert await question_repository.delete_question(owner.id, deletable_question_id)
    citation_count = await db_session.scalar(
        select(func.count())
        .select_from(QuestionContextChunk)
        .where(QuestionContextChunk.question_id == deletable_question_id)
    )
    assert citation_count == 0
    assert await document_repository.get_document(owner.id, live_document_id) is not None
    assert await question_repository.get_question(owner.id, deletable_question_id) is None
