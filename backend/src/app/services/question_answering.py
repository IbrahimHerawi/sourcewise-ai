"""Core retrieval-augmented question answering flow."""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import app.services.embeddings as embeddings_service
from app.api.schemas.questions import CitationResponse, QuestionAnswerResponse
from app.core.settings import get_settings
from app.db.models.collections import Collection
from app.repositories.chunk_repository import ChunkRepository
from app.repositories.collection_repository import CollectionRepository
from app.repositories.question_context_repository import QuestionContextRepository
from app.repositories.question_repository import QuestionRepository
from app.repositories.types import QuestionContextRow, SimilaritySearchResult
from app.services.llm import FALLBACK_ANSWER, GeneratedAnswer, generate_answer

DEFAULT_TOP_K: Final[int] = 5
DEFAULT_MAX_CONTEXT_CHARS: Final[int] = 12_000
_CHUNK_SEPARATOR: Final[str] = "\n\n---\n\n"
_TRUNCATION_MARKER: Final[str] = "\n[content truncated]"


class QuestionAnsweringError(ValueError):
    """Raised when a question cannot be answered from the available document set."""


class CollectionNotFoundError(LookupError):
    """Raised when a requested collection is not owned by the requesting user."""

    def __init__(self, collection_id: uuid.UUID) -> None:
        super().__init__("Collection not found.")
        self.collection_id = collection_id


@dataclass(frozen=True, slots=True)
class RetrievedContextChunk:
    """An immutable snapshot of one chunk included in an LLM context."""

    rank: int
    document_id: uuid.UUID
    document_filename: str
    chunk_id: uuid.UUID
    chunk_index: int
    content: str
    distance: float


@dataclass(frozen=True, slots=True)
class QuestionRetrievalResult:
    """The complete immutable output of owner-scoped question retrieval."""

    normalized_question: str
    query_embedding: tuple[float, ...]
    collection_id: uuid.UUID | None
    context_text: str
    chunks: tuple[RetrievedContextChunk, ...]


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


def _retrieval_section_header(
    chunk: SimilaritySearchResult,
    *,
    rank: int,
) -> str:
    return (
        f"[{rank}]\n"
        f"document_filename: {chunk.document_filename}\n"
        f"document_id: {chunk.document_id}\n"
        f"chunk_id: {chunk.chunk_id}\n"
        f"chunk_index: {chunk.chunk_index}\n"
        "content:\n"
    )


def _truncate_retrieval_content(
    content: str,
    *,
    max_chars: int,
) -> tuple[str, bool]:
    normalized_content = content.strip()
    if not normalized_content:
        return "", False
    if len(normalized_content) <= max_chars:
        return normalized_content, False
    return _truncate_text(normalized_content, max_chars=max_chars), True


def _build_retrieval_context(
    search_results: Sequence[SimilaritySearchResult],
    *,
    max_chars: int,
) -> tuple[str, tuple[RetrievedContextChunk, ...]]:
    """Format ranked retrieval snapshots within the complete context budget."""
    sections: list[str] = []
    chunks: list[RetrievedContextChunk] = []
    used_chars = 0

    for search_result in search_results:
        rank = len(chunks) + 1
        separator = _CHUNK_SEPARATOR if sections else ""
        header = _retrieval_section_header(search_result, rank=rank)
        content_budget = max_chars - used_chars - len(separator) - len(header)
        if content_budget <= 0:
            break

        content, was_truncated = _truncate_retrieval_content(
            search_result.content,
            max_chars=content_budget,
        )
        if not content:
            continue

        section = f"{header}{content}"
        sections.append(f"{separator}{section}")
        chunks.append(
            RetrievedContextChunk(
                rank=rank,
                document_id=search_result.document_id,
                document_filename=search_result.document_filename,
                chunk_id=search_result.chunk_id,
                chunk_index=search_result.chunk_index,
                content=content,
                distance=search_result.distance,
            )
        )
        used_chars += len(separator) + len(section)

        if was_truncated:
            break

    return "".join(sections), tuple(chunks)


async def retrieve_question_context(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    question_text: str,
    collection_id: uuid.UUID | None = None,
    top_k: int | None = None,
    max_context_chars: int | None = None,
) -> QuestionRetrievalResult:
    """Embed and retrieve owner-scoped context without calling an LLM or writing history."""
    normalized_question = question_text.strip()
    if not normalized_question:
        raise ValueError("question_text must not be blank.")

    resolved_settings = get_settings()
    effective_top_k = top_k if top_k is not None else resolved_settings.top_k
    effective_max_context_chars = (
        max_context_chars
        if max_context_chars is not None
        else DEFAULT_MAX_CONTEXT_CHARS
    )
    if effective_top_k <= 0:
        raise ValueError("top_k must be greater than 0.")
    if effective_max_context_chars <= 0:
        raise ValueError("max_context_chars must be greater than 0.")
    if session.in_transaction():
        raise RuntimeError("Question retrieval requires a session without an active transaction.")

    query_embedding = await embeddings_service.embed_query(normalized_question)

    async with session.begin():
        if collection_id is not None:
            collection = await CollectionRepository(session).get_collection(
                user_id,
                collection_id,
            )
            if collection is None:
                raise CollectionNotFoundError(collection_id)

        search_results = await ChunkRepository(session).similarity_search(
            user_id,
            query_embedding,
            top_k=effective_top_k,
            collection_id=collection_id,
            max_distance=resolved_settings.retrieval_max_cosine_distance,
        )

    context_text, chunks = _build_retrieval_context(
        search_results,
        max_chars=effective_max_context_chars,
    )
    return QuestionRetrievalResult(
        normalized_question=normalized_question,
        query_embedding=tuple(query_embedding),
        collection_id=collection_id,
        context_text=context_text,
        chunks=chunks,
    )


async def answer_question(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    question_text: str,
    collection_id: uuid.UUID | None = None,
    top_k: int | None = None,
    max_context_chars: int | None = None,
) -> QuestionAnswerResponse:
    """Generate and atomically persist one owner-scoped question and its citations."""
    retrieval = await retrieve_question_context(
        session,
        user_id=user_id,
        question_text=question_text,
        collection_id=collection_id,
        top_k=top_k,
        max_context_chars=max_context_chars,
    )

    answer_text = FALLBACK_ANSWER
    ai_provider: str | None = None
    model_used: str | None = None
    cited_chunks: tuple[RetrievedContextChunk, ...] = ()

    if retrieval.chunks:
        settings = get_settings()
        generated_answer = await generate_answer(
            retrieval.context_text,
            retrieval.normalized_question,
            len(retrieval.chunks),
            settings=settings,
        )
        ai_provider = settings.ai_provider
        model_used = generated_answer.model_used
        answer_text, cited_chunks = _ground_generated_answer(
            generated_answer,
            chunks=retrieval.chunks,
        )

    async with session.begin():
        if retrieval.collection_id is not None:
            await _lock_owned_collection(
                session,
                user_id=user_id,
                collection_id=retrieval.collection_id,
            )

        question = await QuestionRepository(session).create_question(
            user_id,
            collection_id=retrieval.collection_id,
            question_text=retrieval.normalized_question,
            embedding=list(retrieval.query_embedding),
            answer_text=answer_text,
            ai_provider=ai_provider,
            model_used=model_used,
        )
        snapshots = await QuestionContextRepository(session).bulk_insert_question_context(
            question.id,
            [_context_row(chunk) for chunk in cited_chunks],
        )

    return QuestionAnswerResponse(
        question_id=question.id,
        collection_id=question.collection_id,
        answer=question.answer_text,
        citations=[CitationResponse.model_validate(snapshot) for snapshot in snapshots],
        created_at=question.created_at,
        provider=question.ai_provider,
        model=question.model_used,
    )


def _ground_generated_answer(
    generated_answer: GeneratedAnswer,
    *,
    chunks: Sequence[RetrievedContextChunk],
) -> tuple[str, tuple[RetrievedContextChunk, ...]]:
    """Resolve validated model citation ranks to unique retrieval snapshots."""
    if generated_answer.answer_text == FALLBACK_ANSWER:
        return FALLBACK_ANSWER, ()

    chunks_by_rank = {chunk.rank: chunk for chunk in chunks}
    cited_chunks: list[RetrievedContextChunk] = []
    seen_ranks: set[int] = set()
    for rank in generated_answer.citation_ranks:
        if rank in seen_ranks:
            continue
        chunk = chunks_by_rank.get(rank)
        if chunk is None:
            return FALLBACK_ANSWER, ()
        seen_ranks.add(rank)
        cited_chunks.append(chunk)

    if not cited_chunks:
        return FALLBACK_ANSWER, ()
    cited_chunks.sort(key=lambda chunk: chunk.rank)
    return generated_answer.answer_text, tuple(cited_chunks)


async def _lock_owned_collection(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    collection_id: uuid.UUID,
) -> None:
    """Protect an owned collection's FK key for the duration of the write."""
    stmt = (
        select(Collection.id)
        .where(
            Collection.id == collection_id,
            Collection.user_id == user_id,
        )
        .with_for_update(read=True, key_share=True)
    )
    if await session.scalar(stmt) is None:
        raise CollectionNotFoundError(collection_id)


def _context_row(chunk: RetrievedContextChunk) -> QuestionContextRow:
    return QuestionContextRow(
        rank=chunk.rank,
        document_id=chunk.document_id,
        document_filename=chunk.document_filename,
        chunk_id=chunk.chunk_id,
        chunk_index=chunk.chunk_index,
        chunk_content=chunk.content,
        similarity_score=chunk.distance,
    )


__all__ = [
    "CollectionNotFoundError",
    "DEFAULT_MAX_CONTEXT_CHARS",
    "DEFAULT_TOP_K",
    "QuestionAnsweringError",
    "QuestionRetrievalResult",
    "RetrievedContextChunk",
    "answer_question",
    "retrieve_question_context",
]
