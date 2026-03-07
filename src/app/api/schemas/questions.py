"""Schemas for question-answering requests and responses."""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class QuestionAnswerRequest(BaseModel):
    """Request payload for asking a question over indexed documents."""

    question_text: str = Field(min_length=1)
    document_ids: list[UUID] | None = None


class QuestionSourceResponse(BaseModel):
    """One supporting chunk returned with an answer."""

    document_id: UUID
    chunk_id: UUID
    chunk_index: int
    distance: float


class QuestionAnswerResponse(BaseModel):
    """Answer payload with supporting sources and model metadata."""

    question_id: UUID
    answer: str
    sources: list[QuestionSourceResponse]
    provider: Literal["openai", "ollama"]
    model: str

