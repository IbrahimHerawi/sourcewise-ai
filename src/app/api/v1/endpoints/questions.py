"""V1 question-answering endpoints."""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import app.services.question_answering as question_answering_service
from app.api.schemas.questions import (
    PaginatedQuestionHistoryResponse,
    QuestionAnswerRequest,
    QuestionAnswerResponse,
    QuestionHistoryItemResponse,
    QuestionSourceResponse,
)
from app.db.models.documents import Document
from app.db.session import get_db_session
from app.repositories.question_repository import QuestionRepository

router = APIRouter()


def _normalize_document_ids(document_ids: Sequence[uuid.UUID] | None) -> tuple[uuid.UUID, ...]:
    if not document_ids:
        return ()
    return tuple(dict.fromkeys(document_ids))


async def _find_missing_document_ids(
    session: AsyncSession,
    *,
    document_ids: Sequence[uuid.UUID],
) -> list[str]:
    if not document_ids:
        return []

    existing_document_ids = set(
        (
            await session.scalars(select(Document.id).where(Document.id.in_(document_ids)))
        ).all()
    )
    return [str(document_id) for document_id in document_ids if document_id not in existing_document_ids]


@router.post("/ask", response_model=QuestionAnswerResponse)
async def ask_question(
    payload: QuestionAnswerRequest,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> QuestionAnswerResponse:
    """Answer a question using all ready documents or a caller-provided subset."""
    document_ids = _normalize_document_ids(payload.document_ids)
    missing_document_ids = await _find_missing_document_ids(
        session,
        document_ids=document_ids,
    )
    if missing_document_ids:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "message": "One or more documents were not found.",
                "missing_document_ids": missing_document_ids,
            },
        )

    try:
        return await question_answering_service.answer_question(
            session,
            question_text=payload.question,
            document_ids=document_ids or None,
        )
    except question_answering_service.QuestionAnsweringError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@router.get("/history", response_model=PaginatedQuestionHistoryResponse)
async def list_question_history(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
    document_id: uuid.UUID | None = None,
) -> PaginatedQuestionHistoryResponse:
    """Return paginated question history, optionally filtered by source document id."""
    question_repo = QuestionRepository(session)
    items = await question_repo.list_questions(
        limit=limit,
        offset=offset,
        document_id=document_id,
    )
    total = await question_repo.count_questions(document_id=document_id)

    return PaginatedQuestionHistoryResponse(
        items=[
            QuestionHistoryItemResponse(
                question_id=question.id,
                question=question.question_text,
                answer=question.answer_text,
                provider=question.ai_provider,
                model=question.model_used,
                created_at=question.created_at,
                sources=[
                    QuestionSourceResponse(
                        document_id=context_chunk.chunk.document_id,
                        chunk_id=context_chunk.chunk_id,
                        chunk_index=context_chunk.chunk.chunk_index,
                        distance=context_chunk.similarity_score,
                    )
                    for context_chunk in sorted(
                        question.context_chunks,
                        key=lambda context_chunk: context_chunk.rank,
                    )
                ],
            )
            for question in items
        ],
        limit=limit,
        offset=offset,
        total=total,
    )
