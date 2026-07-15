"""Protected V1 question-answering and history endpoints."""

from __future__ import annotations

import logging
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status
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
from app.core.errors import AppError, ExternalServiceError, NotFoundError
from app.db.models.auth import User
from app.db.models.questions import Question
from app.db.session import get_db_session
from app.repositories.collection_repository import CollectionRepository
from app.repositories.question_repository import QuestionRepository
from app.services.llm import (
    LLMInvalidResponseError,
    LLMRejectedError,
    LLMTransientError,
)

logger = logging.getLogger(__name__)

router = APIRouter()


def _collection_not_found_error() -> NotFoundError:
    return NotFoundError("Collection not found.")


def _question_not_found_error() -> NotFoundError:
    return NotFoundError("Question not found.")


def _provider_error(*, status_code: int) -> ExternalServiceError:
    if status_code == status.HTTP_503_SERVICE_UNAVAILABLE:
        return ExternalServiceError(
            "Question answering service is temporarily unavailable.",
            code="question_answering_unavailable",
            status_code=status_code,
        )
    return ExternalServiceError(
        "Question answering service failed.",
        code="question_answering_provider_error",
        status_code=status_code,
    )


def _internal_error() -> AppError:
    return AppError(
        "An unexpected error occurred.",
        code="internal_server_error",
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
    )


def _history_item(question: Question) -> QuestionHistoryItemResponse:
    return QuestionHistoryItemResponse(
        question_id=question.id,
        collection_id=question.collection_id,
        question=question.question_text,
        answer=question.answer_text,
        citations=[
            CitationResponse.model_validate(citation)
            for citation in sorted(
                question.context_chunks,
                key=lambda citation: citation.rank,
            )
        ],
        created_at=question.created_at,
        provider=question.ai_provider,
        model=question.model_used,
    )


@router.post("/ask", response_model=QuestionAnswerResponse)
async def ask_question(
    payload: QuestionAnswerRequest,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_verified_user)],
) -> QuestionAnswerResponse:
    """Answer and persist one independent owner-scoped question."""
    try:
        # Authentication performs a read on this session. End that transaction before
        # the service starts its explicit retrieval and persistence transactions.
        await session.commit()
        return await question_answering_service.answer_question(
            session,
            user_id=current_user.id,
            question_text=payload.question,
            collection_id=payload.collection_id,
        )
    except question_answering_service.CollectionNotFoundError as exc:
        raise _collection_not_found_error() from exc
    except LLMTransientError as exc:
        raise _provider_error(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        ) from exc
    except (LLMInvalidResponseError, LLMRejectedError) as exc:
        raise _provider_error(status_code=status.HTTP_502_BAD_GATEWAY) from exc
    except AppError:
        raise
    except Exception as exc:
        logger.error("Unexpected failure while answering a question.")
        raise _internal_error() from exc


@router.get("/history", response_model=PaginatedQuestionHistoryResponse)
async def list_question_history(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_verified_user)],
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
    collection_id: Annotated[uuid.UUID | None, Query()] = None,
) -> PaginatedQuestionHistoryResponse:
    """Return the authenticated user's newest questions first."""
    if collection_id is not None:
        collection = await CollectionRepository(session).get_collection(
            current_user.id,
            collection_id,
        )
        if collection is None:
            raise _collection_not_found_error()

    repository = QuestionRepository(session)
    items = await repository.list_questions(
        current_user.id,
        limit=limit,
        offset=offset,
        collection_id=collection_id,
    )
    total = await repository.count_questions(
        current_user.id,
        collection_id=collection_id,
    )

    return PaginatedQuestionHistoryResponse(
        items=[_history_item(question) for question in items],
        limit=limit,
        offset=offset,
        total=total,
    )


@router.get("/history/{question_id:uuid}", response_model=QuestionHistoryItemResponse)
async def get_question_history_item(
    question_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_verified_user)],
) -> QuestionHistoryItemResponse:
    """Return one owner-scoped persisted question and its citation snapshots."""
    question = await QuestionRepository(session).get_question(
        current_user.id,
        question_id,
    )
    if question is None:
        raise _question_not_found_error()
    return _history_item(question)


@router.delete(
    "/history/{question_id:uuid}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_question_history_item(
    question_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_verified_user)],
) -> Response:
    """Delete one owner-scoped question and its citation snapshots."""
    deleted = await QuestionRepository(session).delete_question(
        current_user.id,
        question_id,
    )
    if not deleted:
        raise _question_not_found_error()

    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
