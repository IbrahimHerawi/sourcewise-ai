"""V1 question-answering endpoints."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

import app.services.question_answering as question_answering_service
from app.api.dependencies import get_current_verified_user
from app.api.schemas.questions import (
    CitationResponse,
    PaginatedQuestionHistoryResponse,
    QuestionAnswerRequest,
    QuestionAnswerResponse,
    QuestionHistoryItemResponse,
)
from app.core.errors import NotFoundError, ValidationError
from app.db.models.auth import User
from app.db.session import get_db_session
from app.repositories.collection_repository import CollectionRepository
from app.repositories.question_repository import QuestionRepository

router = APIRouter()


@router.post("/ask", response_model=QuestionAnswerResponse)
async def ask_question(
    payload: QuestionAnswerRequest,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_verified_user)],
) -> QuestionAnswerResponse:
    """Answer a question using all owner documents or one owner collection."""
    if payload.collection_id is not None:
        collection = await CollectionRepository(session).get_collection(
            current_user.id,
            payload.collection_id,
        )
        if collection is None:
            raise NotFoundError("Collection not found.")

    try:
        return await question_answering_service.answer_question(
            session,
            user_id=current_user.id,
            question_text=payload.question,
            collection_id=payload.collection_id,
        )
    except question_answering_service.QuestionAnsweringError as exc:
        raise ValidationError(
            str(exc),
            status_code=status.HTTP_400_BAD_REQUEST,
        ) from exc


@router.get("/history", response_model=PaginatedQuestionHistoryResponse)
async def list_question_history(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_verified_user)],
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
    document_id: uuid.UUID | None = None,
) -> PaginatedQuestionHistoryResponse:
    """Return paginated question history, optionally filtered by source document id."""
    question_repo = QuestionRepository(session)
    items = await question_repo.list_questions(
        current_user.id,
        limit=limit,
        offset=offset,
        document_id=document_id,
    )
    total = await question_repo.count_questions(current_user.id, document_id=document_id)

    return PaginatedQuestionHistoryResponse(
        items=[
            QuestionHistoryItemResponse(
                question_id=question.id,
                collection_id=question.collection_id,
                question=question.question_text,
                answer=question.answer_text,
                provider=question.ai_provider,
                model=question.model_used,
                created_at=question.created_at,
                citations=[
                    CitationResponse(
                        rank=context_chunk.rank,
                        document_id=context_chunk.document_id,
                        document_filename=context_chunk.document_filename,
                        chunk_id=context_chunk.chunk_id,
                        chunk_index=context_chunk.chunk_index,
                        excerpt=context_chunk.chunk_content,
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
