"""Core retrieval-augmented question answering flow."""

from __future__ import annotations

import logging
import re
import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas.questions import CitationResponse, QuestionAnswerResponse
from app.core.settings import Settings, get_settings
from app.db.models.documents import Document, DocumentStatus
from app.repositories.chunk_repository import ChunkRepository
from app.repositories.question_context_repository import QuestionContextRepository
from app.repositories.question_repository import QuestionRepository
from app.repositories.types import QuestionContextRow, SimilaritySearchResult
from app.services.embeddings import OllamaEmbeddingError, embed_query
from app.services.llm import (
    GROUNDED_NOT_FOUND_ANSWER,
    AnswerProviderError,
    generate_answer,
)
from app.services.llm import (
    AnswerProviderUnavailableError as LLMProviderUnavailableError,
)

logger = logging.getLogger(__name__)

DEFAULT_TOP_K: Final[int] = 5
DEFAULT_MAX_CONTEXT_CHARS: Final[int] = 12_000
_CHUNK_SEPARATOR: Final[str] = "\n\n---\n\n"
_TRUNCATION_MARKER: Final[str] = "\n[content truncated]"
_EMAIL_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"(?<![\w.+-])[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}(?![\w.-])",
    re.IGNORECASE,
)


class QuestionAnsweringError(ValueError):
    """A safe domain failure exposed by the question-answering endpoint."""

    code = "question_answering_error"
    status_code = 400


class NoReadyDocumentsError(QuestionAnsweringError):
    code = "no_ready_documents"
    status_code = 409


class QueryEmbeddingUnavailableError(QuestionAnsweringError):
    code = "query_embedding_unavailable"
    status_code = 503


class AnswerProviderUnavailableError(QuestionAnsweringError):
    code = "answer_provider_unavailable"
    status_code = 503


class AnswerProviderRejectedError(QuestionAnsweringError):
    code = "answer_provider_rejected"
    status_code = 502


@dataclass(frozen=True, slots=True)
class _RetrievedChunk:
    chunk_id: uuid.UUID
    document_id: uuid.UUID
    document_filename: str
    chunk_index: int
    content: str
    distance: float


async def _embed_question(
    question_text: str,
    *,
    settings: Settings | None,
) -> list[float]:
    return await embed_query(question_text)


async def _count_documents_by_status(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    collection_id: uuid.UUID | None,
    document_ids: Sequence[uuid.UUID] | None,
) -> dict[DocumentStatus, int]:
    stmt = select(Document.status, func.count()).where(Document.user_id == user_id)
    if collection_id is not None:
        stmt = stmt.where(Document.collection_id == collection_id)
    if document_ids is not None:
        unique_document_ids = tuple(dict.fromkeys(document_ids))
        if not unique_document_ids:
            return {}
        stmt = stmt.where(Document.id.in_(unique_document_ids))
    result = await session.execute(stmt.group_by(Document.status))
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


def _message_for_missing_ready_documents(status_counts: dict[DocumentStatus, int]) -> str:
    ready_count = status_counts.get(DocumentStatus.READY, 0)
    pending_or_processing_count = status_counts.get(DocumentStatus.PENDING, 0) + status_counts.get(
        DocumentStatus.PROCESSING, 0
    )

    if ready_count == 0 and pending_or_processing_count > 0:
        return (
            "No ready documents are available yet. "
            "Documents that are still processing are not searchable."
        )
    if ready_count == 0:
        return "No ready documents are available for question answering."
    return GROUNDED_NOT_FOUND_ANSWER


async def _persist_not_found_answer(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    collection_id: uuid.UUID | None,
    question: str,
    query_embedding: list[float],
) -> QuestionAnswerResponse:
    question_row = await QuestionRepository(session).create_question(
        user_id,
        collection_id=collection_id,
        question_text=question,
        embedding=query_embedding,
        answer_text=GROUNDED_NOT_FOUND_ANSWER,
        ai_provider=None,
        model_used=None,
    )
    return QuestionAnswerResponse(
        question_id=question_row.id,
        collection_id=collection_id,
        answer=GROUNDED_NOT_FOUND_ANSWER,
        citations=[],
        created_at=question_row.created_at,
        provider=None,
        model=None,
    )


def _recover_grounded_literal_answer(
    *,
    question: str,
    answer: str,
    context_chunks: Sequence[_RetrievedChunk],
) -> str:
    """Recover a single cited email when a small provider gives a false no-match answer."""
    if answer.strip().casefold() != GROUNDED_NOT_FOUND_ANSWER.casefold():
        return answer
    if "email" not in question.casefold():
        return answer

    matches: dict[str, str] = {}
    for chunk in context_chunks:
        for match in _EMAIL_PATTERN.findall(chunk.content):
            matches.setdefault(match.casefold(), match)

    if len(matches) != 1:
        return answer

    email = next(iter(matches.values()))
    return f"The email address in the selected documents is {email}."


async def answer_question(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    question_text: str,
    collection_id: uuid.UUID | None = None,
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

    normalized_document_ids = (
        tuple(dict.fromkeys(document_ids)) if document_ids is not None else None
    )
    try:
        query_embedding = await _embed_question(
            question,
            settings=resolved_settings if settings is not None else None,
        )
    except OllamaEmbeddingError as exc:
        logger.exception("Question embedding failed user_id=%s", user_id)
        raise QueryEmbeddingUnavailableError(
            "The document search service is temporarily unavailable. Please try again."
        ) from exc

    if session.in_transaction():
        return await _answer_question_in_transaction(
            session,
            user_id=user_id,
            question=question,
            query_embedding=query_embedding,
            collection_id=collection_id,
            document_ids=normalized_document_ids,
            top_k=effective_top_k,
            max_context_chars=max_context_chars,
            settings=resolved_settings,
        )

    async with session.begin():
        return await _answer_question_in_transaction(
            session,
            user_id=user_id,
            question=question,
            query_embedding=query_embedding,
            collection_id=collection_id,
            document_ids=normalized_document_ids,
            top_k=effective_top_k,
            max_context_chars=max_context_chars,
            settings=resolved_settings,
        )


async def _answer_question_in_transaction(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    question: str,
    query_embedding: list[float],
    collection_id: uuid.UUID | None,
    document_ids: Sequence[uuid.UUID] | None,
    top_k: int,
    max_context_chars: int,
    settings: Settings,
) -> QuestionAnswerResponse:
    search_results: list[SimilaritySearchResult] = await ChunkRepository(session).similarity_search(
        user_id,
        query_embedding,
        top_k,
        collection_id=collection_id,
        document_ids=document_ids,
        max_distance=settings.retrieval_max_cosine_distance,
    )

    if not search_results:
        status_counts = await _count_documents_by_status(
            session,
            user_id=user_id,
            collection_id=collection_id,
            document_ids=document_ids,
        )
        if status_counts.get(DocumentStatus.READY, 0) == 0:
            raise NoReadyDocumentsError(_message_for_missing_ready_documents(status_counts))
        return await _persist_not_found_answer(
            session,
            user_id=user_id,
            collection_id=collection_id,
            question=question,
            query_embedding=query_embedding,
        )

    retrieved_chunks = [
        _RetrievedChunk(
            chunk_id=result.chunk_id,
            document_id=result.document_id,
            document_filename=result.document_filename,
            chunk_index=result.chunk_index,
            content=result.content,
            distance=result.distance,
        )
        for result in search_results
    ]
    context_text, context_chunks = _build_context(
        retrieved_chunks,
        max_chars=max_context_chars,
    )
    if not context_chunks:
        raise RuntimeError("Failed to construct question context from retrieved chunks.")

    try:
        answer_text, model_used = await generate_answer(
            context_text,
            question,
            settings=settings,
        )
    except LLMProviderUnavailableError as exc:
        logger.exception("Answer provider unavailable user_id=%s", user_id)
        raise AnswerProviderUnavailableError(
            "The answer-generation service is temporarily unavailable. Please try again."
        ) from exc
    except AnswerProviderError as exc:
        logger.exception("Answer provider rejected request user_id=%s", user_id)
        raise AnswerProviderRejectedError(
            "The answer-generation service could not process this request."
        ) from exc

    answer_text = _recover_grounded_literal_answer(
        question=question,
        answer=answer_text,
        context_chunks=context_chunks,
    )

    question_row = await QuestionRepository(session).create_question(
        user_id,
        collection_id=collection_id,
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
                document_id=chunk.document_id,
                document_filename=chunk.document_filename,
                chunk_content=chunk.content,
                chunk_index=chunk.chunk_index,
                similarity_score=chunk.distance,
                rank=rank,
            )
            for rank, chunk in enumerate(context_chunks, start=1)
        ],
    )

    return QuestionAnswerResponse(
        question_id=question_row.id,
        collection_id=collection_id,
        answer=answer_text,
        citations=[
            CitationResponse(
                rank=rank,
                document_id=chunk.document_id,
                document_filename=chunk.document_filename,
                chunk_id=chunk.chunk_id,
                chunk_index=chunk.chunk_index,
                excerpt=chunk.content,
                distance=chunk.distance,
            )
            for rank, chunk in enumerate(context_chunks, start=1)
        ],
        created_at=question_row.created_at,
        provider=settings.ai_provider,
        model=model_used,
    )


__all__ = [
    "DEFAULT_MAX_CONTEXT_CHARS",
    "DEFAULT_TOP_K",
    "NoReadyDocumentsError",
    "QueryEmbeddingUnavailableError",
    "AnswerProviderUnavailableError",
    "AnswerProviderRejectedError",
    "QuestionAnsweringError",
    "answer_question",
]
