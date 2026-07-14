"""Core retrieval-augmented question answering flow."""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas.questions import QuestionAnswerResponse, QuestionSourceResponse
from app.core.settings import Settings, get_settings
from app.db.models.document_chunks import DocumentChunk
from app.db.models.documents import Document, DocumentStatus
from app.repositories.chunk_repository import ChunkRepository
from app.repositories.question_context_repository import QuestionContextRepository
from app.repositories.question_repository import QuestionRepository
from app.repositories.types import QuestionContextRow
from app.services.embeddings import embed_query
from app.services.llm import generate_answer

DEFAULT_TOP_K: Final[int] = 5
DEFAULT_MAX_CONTEXT_CHARS: Final[int] = 12_000
_CHUNK_SEPARATOR: Final[str] = "\n\n---\n\n"
_TRUNCATION_MARKER: Final[str] = "\n[content truncated]"


class QuestionAnsweringError(ValueError):
    """Raised when a question cannot be answered from the available document set."""


@dataclass(frozen=True, slots=True)
class _RetrievedChunk:
    chunk_id: uuid.UUID
    document_id: uuid.UUID
    chunk_index: int
    content: str
    distance: float


def _normalize_document_ids(
    document_ids: Sequence[uuid.UUID] | None,
) -> tuple[uuid.UUID, ...] | None:
    if document_ids is None:
        return None

    deduplicated = tuple(dict.fromkeys(document_ids))
    return deduplicated or None


async def _embed_question(
    question_text: str,
    *,
    settings: Settings | None,
) -> list[float]:
    return await embed_query(question_text)


async def _load_document_statuses(
    session: AsyncSession,
    *,
    document_ids: Sequence[uuid.UUID],
) -> dict[uuid.UUID, DocumentStatus]:
    if not document_ids:
        return {}

    result = await session.execute(
        select(Document.id, Document.status).where(Document.id.in_(document_ids))
    )
    return {document_id: status for document_id, status in result.all()}


async def _count_documents_by_status(session: AsyncSession) -> dict[DocumentStatus, int]:
    result = await session.execute(select(Document.status, func.count()).group_by(Document.status))
    return {status: int(count) for status, count in result.all()}


def _truncate_text(text: str, *, max_chars: int) -> str:
    if max_chars <= 0:
        return ""

    stripped = text.strip()
    if len(stripped) <= max_chars:
        return stripped

    if max_chars <= len(_TRUNCATION_MARKER):
        return stripped[:max_chars].rstrip()

    content_budget = max_chars - len(_TRUNCATION_MARKER)
    candidate = stripped[:content_budget]
    safe_cut = max(candidate.rfind("\n"), candidate.rfind(" "))
    if safe_cut >= content_budget // 2:
        candidate = candidate[:safe_cut]

    return candidate.rstrip() + _TRUNCATION_MARKER


def _render_context_section(
    chunk: _RetrievedChunk,
    *,
    rank: int,
    max_chars: int,
) -> str:
    header = (
        f"[Chunk {rank}]\n"
        f"document_id: {chunk.document_id}\n"
        f"chunk_id: {chunk.chunk_id}\n"
        f"chunk_index: {chunk.chunk_index}\n"
        f"distance: {chunk.distance:.6f}\n"
        "content:\n"
    )
    if len(header) >= max_chars:
        return _truncate_text(header, max_chars=max_chars)

    content = _truncate_text(chunk.content, max_chars=max_chars - len(header))
    return f"{header}{content}"


def _build_context(
    chunks: Sequence[_RetrievedChunk],
    *,
    max_chars: int,
) -> tuple[str, list[_RetrievedChunk]]:
    if max_chars <= 0:
        raise ValueError("max_context_chars must be greater than 0.")

    sections: list[str] = []
    included_chunks: list[_RetrievedChunk] = []
    used_chars = 0

    for rank, chunk in enumerate(chunks, start=1):
        separator = _CHUNK_SEPARATOR if sections else ""
        remaining_budget = max_chars - used_chars - len(separator)
        if remaining_budget <= 0:
            break

        section = _render_context_section(chunk, rank=rank, max_chars=remaining_budget)
        if not section:
            break

        sections.append(f"{separator}{section}")
        included_chunks.append(chunk)
        used_chars += len(separator) + len(section)

        if len(section) < len(_render_context_section(chunk, rank=rank, max_chars=max_chars)):
            break

    return "".join(sections), included_chunks


def _message_for_missing_requested_chunks(
    requested_statuses: dict[uuid.UUID, DocumentStatus],
    *,
    ready_document_ids: Sequence[uuid.UUID],
) -> str:
    if not requested_statuses:
        return "None of the requested documents were found."

    if not ready_document_ids:
        if any(
            status in (DocumentStatus.PENDING, DocumentStatus.PROCESSING)
            for status in requested_statuses.values()
        ):
            return (
                "None of the requested documents are READY yet. "
                "Documents in PENDING or PROCESSING are ignored for retrieval."
            )
        return "None of the requested documents are READY for retrieval."

    return "No related content was found in the requested READY documents."


def _message_for_missing_global_chunks(status_counts: dict[DocumentStatus, int]) -> str:
    ready_count = status_counts.get(DocumentStatus.READY, 0)
    pending_or_processing_count = (
        status_counts.get(DocumentStatus.PENDING, 0)
        + status_counts.get(DocumentStatus.PROCESSING, 0)
    )

    if ready_count == 0 and pending_or_processing_count > 0:
        return (
            "No READY documents are available yet. "
            "Documents in PENDING or PROCESSING are ignored for retrieval."
        )
    if ready_count == 0:
        return "No READY documents are available for question answering."
    return "No related content was found in READY documents."


async def answer_question(
    session: AsyncSession,
    *,
    question_text: str,
    document_ids: Sequence[uuid.UUID] | None = None,
    top_k: int | None = None,
    max_context_chars: int = DEFAULT_MAX_CONTEXT_CHARS,
    settings: Settings | None = None,
) -> QuestionAnswerResponse:
    """Embed a question, retrieve relevant context, generate an answer, and persist history."""
    question = question_text.strip()
    if not question:
        raise ValueError("question_text must not be blank.")
    if max_context_chars <= 0:
        raise ValueError("max_context_chars must be greater than 0.")

    resolved_settings = settings or get_settings()
    effective_top_k = top_k if top_k is not None else resolved_settings.top_k
    if effective_top_k <= 0:
        raise ValueError("top_k must be greater than 0.")

    normalized_document_ids = _normalize_document_ids(document_ids)
    query_embedding = await _embed_question(
        question,
        settings=resolved_settings if settings is not None else None,
    )

    if session.in_transaction():
        return await _answer_question_in_transaction(
            session,
            question=question,
            query_embedding=query_embedding,
            document_ids=normalized_document_ids,
            top_k=effective_top_k,
            max_context_chars=max_context_chars,
            settings=resolved_settings,
        )

    async with session.begin():
        return await _answer_question_in_transaction(
            session,
            question=question,
            query_embedding=query_embedding,
            document_ids=normalized_document_ids,
            top_k=effective_top_k,
            max_context_chars=max_context_chars,
            settings=resolved_settings,
        )


async def _answer_question_in_transaction(
    session: AsyncSession,
    *,
    question: str,
    query_embedding: list[float],
    document_ids: tuple[uuid.UUID, ...] | None,
    top_k: int,
    max_context_chars: int,
    settings: Settings,
) -> QuestionAnswerResponse:
    requested_statuses: dict[uuid.UUID, DocumentStatus] = {}
    ready_document_ids = document_ids
    if document_ids is not None:
        requested_statuses = await _load_document_statuses(
            session,
            document_ids=document_ids,
        )
        ready_document_ids = tuple(
            document_id
            for document_id in document_ids
            if requested_statuses.get(document_id) == DocumentStatus.READY
        )

    search_results: list[tuple[DocumentChunk, float]] = []
    if document_ids is None or ready_document_ids:
        search_results = await ChunkRepository(session).similarity_search(
            query_embedding=query_embedding,
            top_k=top_k,
            document_ids=ready_document_ids,
            ready_only=True,
            max_distance=settings.retrieval_max_cosine_distance,
        )

    if not search_results:
        if document_ids is not None:
            raise QuestionAnsweringError(
                _message_for_missing_requested_chunks(
                    requested_statuses,
                    ready_document_ids=ready_document_ids or (),
                )
            )

        raise QuestionAnsweringError(
            _message_for_missing_global_chunks(await _count_documents_by_status(session))
        )

    retrieved_chunks = [
        _RetrievedChunk(
            chunk_id=chunk.id,
            document_id=chunk.document_id,
            chunk_index=chunk.chunk_index,
            content=chunk.content,
            distance=distance,
        )
        for chunk, distance in search_results
    ]
    context_text, context_chunks = _build_context(
        retrieved_chunks,
        max_chars=max_context_chars,
    )
    if not context_chunks:
        raise RuntimeError("Failed to construct question context from retrieved chunks.")

    answer_text, model_used = await generate_answer(
        context_text,
        question,
        settings=settings,
    )

    question_row = await QuestionRepository(session).create_question(
        question_text=question,
        embedding=query_embedding,
        answer_text=answer_text,
        ai_provider=settings.ai_provider,
        model_used=model_used,
    )
    await QuestionContextRepository(session).bulk_insert_question_context(
        question_row.id,
        [
            QuestionContextRow(
                chunk_id=chunk.chunk_id,
                similarity_score=chunk.distance,
                rank=rank,
            )
            for rank, chunk in enumerate(context_chunks, start=1)
        ],
    )

    return QuestionAnswerResponse(
        question_id=question_row.id,
        answer=answer_text,
        sources=[
            QuestionSourceResponse(
                document_id=chunk.document_id,
                chunk_id=chunk.chunk_id,
                chunk_index=chunk.chunk_index,
                distance=chunk.distance,
            )
            for chunk in context_chunks
        ],
        provider=settings.ai_provider,
        model=model_used,
    )


__all__ = [
    "DEFAULT_MAX_CONTEXT_CHARS",
    "DEFAULT_TOP_K",
    "QuestionAnsweringError",
    "answer_question",
]
