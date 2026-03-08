"""V1 question-answering endpoints."""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import app.services.question_answering as question_answering_service
from app.api.schemas.questions import QuestionAnswerRequest, QuestionAnswerResponse
from app.db.models.documents import Document
from app.db.session import get_db_session

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
