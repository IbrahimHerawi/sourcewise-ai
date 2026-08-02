from __future__ import annotations

import uuid
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.settings import get_settings
from app.db.models import DocumentStatus, User
from app.repositories import (
    CollectionRepository,
    DocumentRepository,
    OverviewCounts,
    OverviewRepository,
    QuestionRepository,
)


async def _create_user(session: AsyncSession, label: str) -> User:
    user = User(
        email=f"{label}-{uuid.uuid4()}@example.com",
        password_hash="test-password-hash",
        first_name="Overview",
        last_name="Tester",
    )
    session.add(user)
    await session.flush()
    return user


async def _create_document(
    session: AsyncSession,
    user: User,
    *,
    filename: str,
    status: DocumentStatus,
    collection_id: uuid.UUID | None = None,
):
    return await DocumentRepository(session).create_document(
        user.id,
        collection_id=collection_id,
        filename=filename,
        original_extension=".txt",
        content_type="text/plain",
        size_bytes=42,
        storage_path=f"/tmp/{filename}",
        status=status,
    )


async def _create_question(
    session: AsyncSession,
    user: User,
    *,
    question_text: str,
    collection_id: uuid.UUID | None = None,
    grounded: bool = False,
):
    return await QuestionRepository(session).create_question(
        user.id,
        collection_id=collection_id,
        question_text=question_text,
        embedding=[0.0] * get_settings().embedding_dim,
        answer_text="Grounded answer." if grounded else "Deterministic fallback.",
        ai_provider="ollama" if grounded else None,
        model_used="test-model" if grounded else None,
    )


@pytest.mark.asyncio
async def test_overview_repository_returns_zeroes_for_user_without_resources(
    db_session: AsyncSession,
) -> None:
    user = await _create_user(db_session, "overview-empty")

    counts = await OverviewRepository(db_session).get_counts(user.id)

    assert counts == OverviewCounts(0, 0, 0)


@pytest.mark.asyncio
async def test_overview_repository_counts_all_variants_and_excludes_other_users(
    db_session: AsyncSession,
) -> None:
    owner = await _create_user(db_session, "overview-owner")
    other_user = await _create_user(db_session, "overview-other")
    collection_repository = CollectionRepository(db_session)
    owner_collection = await collection_repository.create_collection(
        owner.id,
        "Collected resources",
    )
    await collection_repository.create_collection(owner.id, "Second collection")
    other_collection = await collection_repository.create_collection(
        other_user.id,
        "Other resources",
    )

    statuses = list(DocumentStatus)
    for index, document_status in enumerate(statuses):
        await _create_document(
            db_session,
            owner,
            filename=f"owner-{document_status.value.lower()}.txt",
            status=document_status,
            collection_id=owner_collection.id if index % 2 == 0 else None,
        )
    await _create_document(
        db_session,
        other_user,
        filename="other.txt",
        status=DocumentStatus.READY,
        collection_id=other_collection.id,
    )

    await _create_question(
        db_session,
        owner,
        question_text="Grounded and collected?",
        collection_id=owner_collection.id,
        grounded=True,
    )
    await _create_question(
        db_session,
        owner,
        question_text="Fallback and uncollected?",
    )
    await _create_question(
        db_session,
        other_user,
        question_text="Other user's fallback?",
    )

    assert await OverviewRepository(db_session).get_counts(owner.id) == OverviewCounts(
        total_documents=4,
        total_questions=2,
        total_collections=2,
    )
    assert await OverviewRepository(db_session).get_counts(
        other_user.id
    ) == OverviewCounts(
        total_documents=1,
        total_questions=1,
        total_collections=1,
    )


@pytest.mark.asyncio
async def test_overview_repository_deletions_update_only_defined_totals(
    db_session: AsyncSession,
) -> None:
    owner = await _create_user(db_session, "overview-deletions")
    collection_repository = CollectionRepository(db_session)
    document_repository = DocumentRepository(db_session)
    question_repository = QuestionRepository(db_session)
    overview_repository = OverviewRepository(db_session)
    collection = await collection_repository.create_collection(owner.id, "Deletions")
    document = await _create_document(
        db_session,
        owner,
        filename="deletable.txt",
        status=DocumentStatus.READY,
        collection_id=collection.id,
    )
    collected_question = await _create_question(
        db_session,
        owner,
        question_text="Will collection deletion retain me?",
        collection_id=collection.id,
        grounded=True,
    )
    retained_question = await _create_question(
        db_session,
        owner,
        question_text="Will source deletion retain history?",
    )
    assert await overview_repository.get_counts(owner.id) == OverviewCounts(1, 2, 1)

    assert await collection_repository.delete_collection(owner.id, collection.id)
    assert await overview_repository.get_counts(owner.id) == OverviewCounts(1, 2, 0)

    assert await document_repository.delete_document(owner.id, document.id) is not None
    assert await overview_repository.get_counts(owner.id) == OverviewCounts(0, 2, 0)

    assert await question_repository.delete_question(owner.id, collected_question.id)
    assert await overview_repository.get_counts(owner.id) == OverviewCounts(0, 1, 0)
    assert await question_repository.get_question(owner.id, retained_question.id) is not None


@pytest.mark.asyncio
async def test_overview_repository_requires_user_id_before_sql() -> None:
    session = AsyncMock(spec=AsyncSession)

    with pytest.raises(ValueError, match="user_id is required"):
        await OverviewRepository(session).get_counts(None)  # type: ignore[arg-type]

    session.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_overview_repository_executes_exactly_one_sql_statement(
    db_session: AsyncSession,
) -> None:
    user = await _create_user(db_session, "overview-one-statement")
    connection = await db_session.connection()
    statements: list[str] = []

    def record_statement(
        _connection,
        _cursor,
        statement: str,
        _parameters,
        _context,
        _executemany: bool,
    ) -> None:
        statements.append(statement)

    event.listen(connection.sync_connection, "before_cursor_execute", record_statement)
    try:
        await OverviewRepository(db_session).get_counts(user.id)
    finally:
        event.remove(connection.sync_connection, "before_cursor_execute", record_statement)

    assert len(statements) == 1
    normalized_statement = " ".join(statements[0].lower().split())
    assert normalized_statement.startswith("select")
    assert normalized_statement.count("select count(*)") == 3
    assert "from documents" in normalized_statement
    assert "from questions" in normalized_statement
    assert "from collections" in normalized_statement
    assert " join " not in normalized_statement
