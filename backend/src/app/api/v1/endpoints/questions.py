"""V1 question-answering endpoints."""

from __future__ import annotations

import logging
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
from app.core.errors import AppError, NotFoundError, ValidationError
from app.db.models.auth import User
from app.db.session import get_db_session
from app.repositories.collection_repository import CollectionRepository
from app.repositories.document_repository import DocumentRepository
from app.repositories.question_repository import QuestionRepository

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/ask", response_model=QuestionAnswerResponse)
async def ask_question(
    payload: QuestionAnswerRequest,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_verified_user)],
) -> QuestionAnswerResponse:
    """Answer a grounded question using a user-owned collection and/or document selection."""
    if payload.collection_id is not None:
        collection = await CollectionRepository(session).get_collection(
            current_user.id,
            payload.collection_id,
        )
        if collection is None:
            raise NotFoundError("Collection not found.")

    document_ids = tuple(payload.document_ids or ())
    if document_ids:
        documents = await DocumentRepository(session).list_documents_by_ids(
            current_user.id,
            document_ids,
            collection_id=payload.collection_id,
        )
        found_document_ids = {document.id for document in documents}
        missing_document_ids = [
            document_id for document_id in document_ids if document_id not in found_document_ids
        ]
        if missing_document_ids:
            raise NotFoundError(
                "One or more selected documents were not found.",
                code="documents_not_found",
                details={"document_ids": [str(document_id) for document_id in missing_document_ids]},
            )

        not_ready_documents = [
            document for document in documents if document.status.value != "READY"
        ]
        if not_ready_documents:
            raise ValidationError(
                "Selected documents must finish processing before they can be searched.",
                code="documents_not_ready",
                details={
                    "document_ids": [str(document.id) for document in not_ready_documents],
                    "statuses": {str(document.id): document.status.value for document in not_ready_documents},
                },
                status_code=status.HTTP_409_CONFLICT,
            )

    try:
        answer = await question_answering_service.answer_question(
            session,
            user_id=current_user.id,
            question_text=payload.question,
            collection_id=payload.collection_id,
            document_ids=document_ids or None,
        )
        # Authentication and scope checks issue reads that start SQLAlchemy's implicit
        # transaction. Persist the successful question/citation write before this
        # request-scoped session closes and rolls that transaction back.
        await session.commit()
        return answer
    except question_answering_service.QuestionAnsweringError as exc:
        await session.rollback()
        logger.info(
            "Question answer request rejected user_id=%s code=%s",
            current_user.id,
            exc.code,
        )
        raise AppError(
            str(exc),
            code=exc.code,
            status_code=exc.status_code,
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
