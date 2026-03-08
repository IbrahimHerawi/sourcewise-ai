"""Schemas for question-answering requests and responses."""

from __future__ import annotations

from typing import Annotated, Literal
from uuid import UUID

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, StringConstraints

QuestionText = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=4_000),
]


class QuestionAnswerRequest(BaseModel):
    """Request payload for asking a question over indexed documents."""

    model_config = ConfigDict(extra="forbid")

    question: QuestionText = Field(
        validation_alias=AliasChoices("question", "question_text"),
        serialization_alias="question",
    )
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


QuestionAskRequest = QuestionAnswerRequest
QuestionAskResponse = QuestionAnswerResponse
