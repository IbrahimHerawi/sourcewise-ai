from __future__ import annotations

import uuid

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

import app.services.question_answering as question_answering_service
from app.core.settings import get_settings
from app.db.models.documents import DocumentStatus
from app.db.models.question_context_chunks import QuestionContextChunk
from app.db.models.questions import Question
from app.repositories.chunk_repository import ChunkRepository
from app.repositories.document_repository import DocumentRepository
from app.repositories.types import ChunkWithEmbedding


def _embedding(first_dim: float, second_dim: float, dim: int) -> list[float]:
    if dim < 2:
        raise ValueError("embedding_dim must be at least 2 for question-answering tests")
    return [first_dim, second_dim] + [0.0] * (dim - 2)


async def _create_document(
    session: AsyncSession,
    *,
    filename: str,
    status: DocumentStatus,
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
async def test_answer_question_retrieves_ready_chunks_generates_answer_and_persists_history(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = get_settings()
    query_embedding = _embedding(0.9, 0.1, settings.embedding_dim)
    ready_document_id = await _create_document(
        db_session,
        filename="ready.txt",
        status=DocumentStatus.READY,
    )
    pending_document_id = await _create_document(
        db_session,
        filename="pending.txt",
        status=DocumentStatus.PENDING,
    )

    ready_chunks = await ChunkRepository(db_session).bulk_insert_chunks(
        ready_document_id,
        [
            ChunkWithEmbedding(
                chunk_index=0,
                content="Ready chunk zero contains the answer.",
                embedding=_embedding(1.0, 0.0, settings.embedding_dim),
            ),
            ChunkWithEmbedding(
                chunk_index=1,
                content="Ready chunk one provides extra support.",
                embedding=_embedding(1.0, 1.0, settings.embedding_dim),
            ),
        ],
    )
    await ChunkRepository(db_session).bulk_insert_chunks(
        pending_document_id,
        [
            ChunkWithEmbedding(
                chunk_index=0,
                content="Pending chunk should never be used.",
                embedding=_embedding(0.9, 0.1, settings.embedding_dim),
            )
        ],
    )

    captured: dict[str, str] = {}

    async def fake_embed_question(question_text: str, *, settings: object) -> list[float]:
        captured["embedded_question"] = question_text
        return query_embedding

    async def fake_generate_answer(
        context_chunks_text: str,
        question: str,
        *,
        settings: object | None = None,
    ) -> tuple[str, str]:
        captured["context"] = context_chunks_text
        captured["question"] = question
        return "Answer from retrieved context.", "unit-test-model"

    monkeypatch.setattr(question_answering_service, "_embed_question", fake_embed_question)
    monkeypatch.setattr(question_answering_service, "generate_answer", fake_generate_answer)

    response = await question_answering_service.answer_question(
        db_session,
        question_text="What do the READY chunks say?",
        document_ids=[pending_document_id, ready_document_id],
        top_k=3,
    )

    assert response.answer == "Answer from retrieved context."
    assert response.provider == settings.ai_provider
    assert response.model == "unit-test-model"
    assert [source.document_id for source in response.sources] == [ready_document_id, ready_document_id]
    assert [source.chunk_id for source in response.sources] == [ready_chunks[0].id, ready_chunks[1].id]
    assert [source.chunk_index for source in response.sources] == [0, 1]

    assert captured["embedded_question"] == "What do the READY chunks say?"
    assert captured["question"] == "What do the READY chunks say?"
    assert f"document_id: {ready_document_id}" in captured["context"]
    assert "chunk_index: 0" in captured["context"]
    assert "chunk_index: 1" in captured["context"]
    assert "\n\n---\n\n" in captured["context"]
    assert "Pending chunk should never be used." not in captured["context"]

    question = await db_session.get(Question, response.question_id)
    assert question is not None
    assert question.question_text == "What do the READY chunks say?"
    assert list(question.question_embedding) == pytest.approx(query_embedding)
    assert question.answer_text == "Answer from retrieved context."
    assert question.ai_provider == settings.ai_provider
    assert question.model_used == "unit-test-model"

    context_rows = list(
        (
            await db_session.scalars(
                select(QuestionContextChunk)
                .where(QuestionContextChunk.question_id == response.question_id)
                .order_by(QuestionContextChunk.rank.asc())
            )
        ).all()
    )
    assert [row.chunk_id for row in context_rows] == [ready_chunks[0].id, ready_chunks[1].id]
    assert [row.rank for row in context_rows] == [1, 2]
    assert [row.similarity_score for row in context_rows] == [
        response.sources[0].distance,
        response.sources[1].distance,
    ]


@pytest.mark.asyncio
async def test_answer_question_raises_when_requested_documents_are_not_ready(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = get_settings()
    pending_document_id = await _create_document(
        db_session,
        filename="pending-only.txt",
        status=DocumentStatus.PROCESSING,
    )
    await ChunkRepository(db_session).bulk_insert_chunks(
        pending_document_id,
        [
            ChunkWithEmbedding(
                chunk_index=0,
                content="Processing chunk should be ignored.",
                embedding=_embedding(1.0, 0.0, settings.embedding_dim),
            )
        ],
    )

    async def fake_embed_question(question_text: str, *, settings: object) -> list[float]:
        return _embedding(1.0, 0.0, get_settings().embedding_dim)

    async def fail_generate_answer(*args: object, **kwargs: object) -> tuple[str, str]:
        raise AssertionError("generate_answer should not be called when no READY chunks exist")

    monkeypatch.setattr(question_answering_service, "_embed_question", fake_embed_question)
    monkeypatch.setattr(question_answering_service, "generate_answer", fail_generate_answer)

    with pytest.raises(question_answering_service.QuestionAnsweringError) as exc_info:
        await question_answering_service.answer_question(
            db_session,
            question_text="Can you answer from processing docs?",
            document_ids=[pending_document_id],
        )

    assert "READY yet" in str(exc_info.value)
    assert "ignored for retrieval" in str(exc_info.value)

    question_count = await db_session.scalar(select(func.count()).select_from(Question))
    assert question_count == 0


@pytest.mark.asyncio
async def test_answer_question_caps_context_size_and_truncates_safely(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = get_settings()
    ready_document_id = await _create_document(
        db_session,
        filename="long.txt",
        status=DocumentStatus.READY,
    )
    await ChunkRepository(db_session).bulk_insert_chunks(
        ready_document_id,
        [
            ChunkWithEmbedding(
                chunk_index=0,
                content="Long context " * 2000,
                embedding=_embedding(1.0, 0.0, settings.embedding_dim),
            )
        ],
    )

    captured: dict[str, str] = {}

    async def fake_embed_question(question_text: str, *, settings: object) -> list[float]:
        return _embedding(1.0, 0.0, get_settings().embedding_dim)

    async def fake_generate_answer(
        context_chunks_text: str,
        question: str,
        *,
        settings: object | None = None,
    ) -> tuple[str, str]:
        captured["context"] = context_chunks_text
        return "Trimmed answer.", "trim-test-model"

    monkeypatch.setattr(question_answering_service, "_embed_question", fake_embed_question)
    monkeypatch.setattr(question_answering_service, "generate_answer", fake_generate_answer)

    response = await question_answering_service.answer_question(
        db_session,
        question_text="Use a small context budget.",
        top_k=1,
        max_context_chars=500,
    )

    assert response.answer == "Trimmed answer."
    assert len(captured["context"]) <= 500
    assert "[content truncated]" in captured["context"]
