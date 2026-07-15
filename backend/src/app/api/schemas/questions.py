"""Schemas for question-answering requests and responses."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import (
    AliasChoices,
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
)

QuestionText = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=4_000),
]
Provider = Literal["openai", "ollama"]
PositiveInteger = Annotated[int, Field(strict=True, gt=0)]
NonNegativeInteger = Annotated[int, Field(strict=True, ge=0)]
FiniteDistance = Annotated[float, Field(strict=True, allow_inf_nan=False)]


class QuestionAnswerRequest(BaseModel):
    """One independent question, optionally narrowed to a collection or documents."""

    model_config = ConfigDict(extra="forbid")

    question: QuestionText
    collection_id: UUID | None = None
    document_ids: list[UUID] | None = Field(default=None, max_length=100)

    @field_validator("document_ids")
    @classmethod
    def normalize_document_ids(cls, value: list[UUID] | None) -> list[UUID] | None:
        """Deduplicate a document selection while preserving the submitted order."""
        if not value:
            return None
        return list(dict.fromkeys(value))


class CitationResponse(BaseModel):
    """An API-safe citation derived from a persisted chunk snapshot."""

    model_config = ConfigDict(extra="forbid", from_attributes=True)

    rank: PositiveInteger
    document_id: UUID
    document_filename: str
    chunk_id: UUID
    chunk_index: NonNegativeInteger
    excerpt: str = Field(
        validation_alias=AliasChoices("excerpt", "chunk_content"),
    )
    distance: FiniteDistance = Field(
        validation_alias=AliasChoices("distance", "similarity_score"),
    )

    @field_validator("excerpt")
    @classmethod
    def build_excerpt(cls, value: str) -> str:
        """Trim a snapshot and cap it at 500 characters plus an ellipsis."""
        content = value.strip()
        if len(content) <= 500:
            return content
        return f"{content[:500]}…"


class QuestionAnswerResponse(BaseModel):
    """Answer payload with collection scope, citations, and model metadata."""

    model_config = ConfigDict(extra="forbid", from_attributes=True)

    question_id: UUID = Field(validation_alias=AliasChoices("question_id", "id"))
    collection_id: UUID | None = None
    answer: str = Field(validation_alias=AliasChoices("answer", "answer_text"))
    citations: list[CitationResponse] = Field(
        validation_alias=AliasChoices("citations", "context_chunks"),
    )
    created_at: datetime
    provider: Provider | None = Field(
        default=None,
        validation_alias=AliasChoices("provider", "ai_provider"),
    )
    model: str | None = Field(
        default=None,
        validation_alias=AliasChoices("model", "model_used"),
    )


class QuestionHistoryItemResponse(BaseModel):
    """One persisted question-and-answer history item."""

    model_config = ConfigDict(extra="forbid", from_attributes=True)

    question_id: UUID = Field(validation_alias=AliasChoices("question_id", "id"))
    collection_id: UUID | None = None
    question: str = Field(validation_alias=AliasChoices("question", "question_text"))
    answer: str = Field(validation_alias=AliasChoices("answer", "answer_text"))
    citations: list[CitationResponse] = Field(
        validation_alias=AliasChoices("citations", "context_chunks"),
    )
    created_at: datetime
    provider: Provider | None = Field(
        default=None,
        validation_alias=AliasChoices("provider", "ai_provider"),
    )
    model: str | None = Field(
        default=None,
        validation_alias=AliasChoices("model", "model_used"),
    )


class PaginatedQuestionHistoryResponse(BaseModel):
    """Paginated question history response payload."""

    model_config = ConfigDict(extra="forbid")

    items: list[QuestionHistoryItemResponse]
    limit: int
    offset: int
    total: int


class QuestionSourceResponse(BaseModel):
    """Legacy internal source type retained until Q&A orchestration is migrated."""

    document_id: UUID
    chunk_id: UUID
    chunk_index: int
    distance: float


QuestionAskRequest = QuestionAnswerRequest
QuestionAskResponse = QuestionAnswerResponse


__all__ = [
    "CitationResponse",
    "PaginatedQuestionHistoryResponse",
    "QuestionAnswerRequest",
    "QuestionAnswerResponse",
    "QuestionAskRequest",
    "QuestionAskResponse",
    "QuestionHistoryItemResponse",
    "QuestionSourceResponse",
]
