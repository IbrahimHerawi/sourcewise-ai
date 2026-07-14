from __future__ import annotations

import uuid
from dataclasses import replace
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.settings import get_settings
from app.db.models import Document, DocumentChunk, Question, QuestionContextChunk, User
from app.repositories.question_context_repository import QuestionContextRepository
from app.repositories.question_repository import QuestionRepository
from app.repositories.types import QuestionContextRow


def _snapshot(
    *,
    rank: int = 1,
    document_id: uuid.UUID | None = None,
    document_filename: str = "source.txt",
    chunk_id: uuid.UUID | None = None,
    chunk_index: int = 0,
    chunk_content: str = "Exact context supplied to the LLM.",
    similarity_score: float = 0.25,
) -> QuestionContextRow:
    return QuestionContextRow(
        rank=rank,
        document_id=document_id or uuid.uuid4(),
        document_filename=document_filename,
        chunk_id=chunk_id or uuid.uuid4(),
        chunk_index=chunk_index,
        chunk_content=chunk_content,
        similarity_score=similarity_score,
    )


async def _create_user(session: AsyncSession, label: str) -> User:
    user = User(
        email=f"{label}-{uuid.uuid4()}@example.com",
        password_hash="test-password-hash",
        first_name="Citation",
        last_name="Repository",
    )
    session.add(user)
    await session.flush()
    return user


async def _create_question(session: AsyncSession, user: User) -> Question:
    question = Question(
        user=user,
        question_text="Which context supports this answer?",
        question_embedding=[0.0] * get_settings().embedding_dim,
        answer_text="The persisted citation snapshots do.",
        ai_provider="ollama",
        model_used="citation-repository-test",
    )
    session.add(question)
    await session.flush()
    return question


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"rank": 0}, "rank must be greater than or equal to 1"),
        ({"document_filename": " \t\n"}, "document_filename must not be blank"),
        ({"chunk_content": " \t\n"}, "chunk_content must not be blank"),
        ({"similarity_score": float("nan")}, "similarity_score must be finite"),
        ({"similarity_score": float("inf")}, "similarity_score must be finite"),
        ({"similarity_score": float("-inf")}, "similarity_score must be finite"),
    ],
    ids=["invalid-rank", "blank-filename", "blank-content", "nan", "inf", "negative-inf"],
)
async def test_validation_failure_issues_no_sql(
    changes: dict[str, object],
    message: str,
) -> None:
    session = AsyncMock(spec=AsyncSession)
    repository = QuestionContextRepository(session)
    row = replace(_snapshot(), **changes)

    with pytest.raises(ValueError, match=message):
        await repository.bulk_insert_question_context(uuid.uuid4(), [row])

    session.scalars.assert_not_awaited()


@pytest.mark.asyncio
async def test_duplicate_rank_validation_issues_no_sql() -> None:
    session = AsyncMock(spec=AsyncSession)
    repository = QuestionContextRepository(session)

    with pytest.raises(ValueError, match="duplicate rank: 1"):
        await repository.bulk_insert_question_context(
            uuid.uuid4(),
            [_snapshot(rank=1), _snapshot(rank=1)],
        )

    session.scalars.assert_not_awaited()


@pytest.mark.asyncio
async def test_bulk_insert_persists_complete_snapshots_without_truncation_in_rank_order(
    db_session: AsyncSession,
) -> None:
    user = await _create_user(db_session, "complete-snapshot")
    question = await _create_question(db_session, user)
    exact_long_content = "  exact prefix\n" + ("context " * 3_000) + "\nexact suffix  "
    second = _snapshot(
        rank=2,
        document_filename="second.txt",
        chunk_index=8,
        chunk_content=exact_long_content,
        similarity_score=0.22,
    )
    first = _snapshot(
        rank=1,
        document_filename="  first.txt  ",
        chunk_index=4,
        chunk_content="  Exact first LLM context.  ",
        similarity_score=0.11,
    )

    inserted = await QuestionContextRepository(db_session).bulk_insert_question_context(
        question.id,
        [second, first],
    )

    assert [row.rank for row in inserted] == [1, 2]
    persisted = list(
        (
            await db_session.scalars(
                select(QuestionContextChunk)
                .where(QuestionContextChunk.question_id == question.id)
                .order_by(QuestionContextChunk.rank)
            )
        ).all()
    )
    assert [
        (
            row.rank,
            row.document_id,
            row.document_filename,
            row.chunk_id,
            row.chunk_index,
            row.chunk_content,
            row.similarity_score,
        )
        for row in persisted
    ] == [
        (
            first.rank,
            first.document_id,
            first.document_filename,
            first.chunk_id,
            first.chunk_index,
            first.chunk_content,
            first.similarity_score,
        ),
        (
            second.rank,
            second.document_id,
            second.document_filename,
            second.chunk_id,
            second.chunk_index,
            second.chunk_content,
            second.similarity_score,
        ),
    ]


@pytest.mark.asyncio
async def test_question_deletion_cascades_repository_snapshots(
    db_session: AsyncSession,
) -> None:
    user = await _create_user(db_session, "question-cascade")
    question = await _create_question(db_session, user)
    question_id = question.id
    await QuestionContextRepository(db_session).bulk_insert_question_context(
        question_id,
        [_snapshot()],
    )

    await db_session.delete(question)
    await db_session.flush()

    count = await db_session.scalar(
        select(func.count())
        .select_from(QuestionContextChunk)
        .where(QuestionContextChunk.question_id == question_id)
    )
    assert count == 0


@pytest.mark.asyncio
async def test_document_deletion_preserves_snapshots_and_history_uses_them(
    db_session: AsyncSession,
) -> None:
    user = await _create_user(db_session, "document-survival")
    question = await _create_question(db_session, user)
    document = Document(
        user=user,
        filename="live-name.txt",
        original_extension=".txt",
        content_type="text/plain",
        size_bytes=42,
        storage_path="/tmp/live-name.txt",
        extracted_text="Live extracted text.",
    )
    chunk = DocumentChunk(
        document=document,
        chunk_index=9,
        content="Live chunk content.",
        embedding=[0.0] * get_settings().embedding_dim,
    )
    db_session.add_all([document, chunk])
    await db_session.flush()
    snapshot = _snapshot(
        document_id=document.id,
        document_filename="snapshot-name.txt",
        chunk_id=chunk.id,
        chunk_index=3,
        chunk_content="Snapshot content supplied to the LLM.",
        similarity_score=0.33,
    )
    await QuestionContextRepository(db_session).bulk_insert_question_context(
        question.id,
        [snapshot],
    )

    await db_session.delete(document)
    await db_session.flush()
    db_session.expunge_all()

    history = await QuestionRepository(db_session).list_questions(
        user.id,
        limit=20,
        offset=0,
    )
    assert await QuestionRepository(db_session).count_questions(user.id) == 1
    assert len(history) == 1
    assert len(history[0].context_chunks) == 1
    citation = history[0].context_chunks[0]
    assert citation.document_id == snapshot.document_id
    assert citation.document_filename == snapshot.document_filename
    assert citation.chunk_id == snapshot.chunk_id
    assert citation.chunk_index == snapshot.chunk_index
    assert citation.chunk_content == snapshot.chunk_content
    assert citation.similarity_score == snapshot.similarity_score


@pytest.mark.asyncio
async def test_snapshot_insert_rolls_back_with_surrounding_question_transaction(
    db_session: AsyncSession,
) -> None:
    user = await _create_user(db_session, "transaction-rollback")
    transaction = await db_session.begin_nested()
    question = await _create_question(db_session, user)
    question_id = question.id
    await QuestionContextRepository(db_session).bulk_insert_question_context(
        question_id,
        [_snapshot()],
    )

    await transaction.rollback()

    question_count = await db_session.scalar(
        select(func.count()).select_from(Question).where(Question.id == question_id)
    )
    snapshot_count = await db_session.scalar(
        select(func.count())
        .select_from(QuestionContextChunk)
        .where(QuestionContextChunk.question_id == question_id)
    )
    assert question_count == 0
    assert snapshot_count == 0
