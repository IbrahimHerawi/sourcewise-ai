from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.settings import get_settings
from app.db.models.auth import User
from app.db.models.collections import Collection
from app.db.models.documents import Document, DocumentStatus
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

    query_embedding = _embedding(0.9, 0.1, settings.embedding_dim)
    results = await repository.similarity_search(
        query_embedding=query_embedding,
        top_k=3,
        document_ids=[document.id],
    )

    assert [chunk.chunk_index for chunk, _ in results] == [0, 2, 1]
    assert results[0][1] < results[1][1] < results[2][1]


@pytest.mark.asyncio
async def test_question_repository_lists_and_counts_history_with_optional_document_filter(
    db_session: AsyncSession,
) -> None:
    settings = get_settings()
    question_repo = QuestionRepository(db_session)
    context_repo = QuestionContextRepository(db_session)
    user = await _create_user(db_session, "question-history-owner")

    first_document = await _create_document(
        db_session,
        user_id=user.id,
        filename="first-history.txt",
    )
    second_document = await _create_document(
        db_session,
        user_id=user.id,
        filename="second-history.txt",
    )
    first_document.status = DocumentStatus.READY
    second_document.status = DocumentStatus.READY
    await db_session.flush()

    first_chunks = await ChunkRepository(db_session).bulk_insert_chunks(
        first_document.id,
        [
            ChunkWithEmbedding(
                chunk_index=0,
                content="first chunk zero",
                embedding=_embedding(1.0, 0.0, settings.embedding_dim),
            ),
            ChunkWithEmbedding(
                chunk_index=1,
                content="first chunk one",
                embedding=_embedding(0.9, 0.1, settings.embedding_dim),
            ),
        ],
    )
    second_chunks = await ChunkRepository(db_session).bulk_insert_chunks(
        second_document.id,
        [
            ChunkWithEmbedding(
                chunk_index=0,
                content="second chunk zero",
                embedding=_embedding(0.0, 1.0, settings.embedding_dim),
            )
        ],
    )

    oldest_question = await question_repo.create_question(
        question_text="Oldest question?",
        embedding=_embedding(1.0, 0.0, settings.embedding_dim),
        answer_text="Oldest answer.",
        ai_provider="ollama",
        model_used="model-a",
    )
    middle_question = await question_repo.create_question(
        question_text="Middle question?",
        embedding=_embedding(0.8, 0.2, settings.embedding_dim),
        answer_text="Middle answer.",
        ai_provider="ollama",
        model_used="model-b",
    )
    newest_question = await question_repo.create_question(
        question_text="Newest question?",
        embedding=_embedding(0.0, 1.0, settings.embedding_dim),
        answer_text="Newest answer.",
        ai_provider="ollama",
        model_used="model-c",
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
        db_session,
        oldest_question,
        datetime(2026, 1, 1, 12, 0, tzinfo=UTC),
    )
    await _set_question_created_at(
        db_session,
        middle_question,
        datetime(2026, 1, 2, 12, 0, tzinfo=UTC),
    )
    await _set_question_created_at(
        db_session,
        newest_question,
        datetime(2026, 1, 3, 12, 0, tzinfo=UTC),
    )

    listed = await question_repo.list_questions(limit=2, offset=1)
    filtered = await question_repo.list_questions(
        limit=20,
        offset=0,
        document_id=first_document.id,
    )
    total = await question_repo.count_questions()
    filtered_total = await question_repo.count_questions(document_id=first_document.id)

    assert [question.id for question in listed] == [middle_question.id, oldest_question.id]
    assert [question.id for question in filtered] == [newest_question.id, oldest_question.id]
    assert total == 3
    assert filtered_total == 2
