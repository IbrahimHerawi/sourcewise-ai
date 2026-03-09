"""Shared repository input data structures."""

from __future__ import annotations

import uuid
from dataclasses import dataclass


@dataclass(slots=True, frozen=True)
class ChunkWithEmbedding:
    """A prepared document chunk with its embedding vector."""

    chunk_index: int
    content: str
    embedding: list[float]


@dataclass(slots=True, frozen=True)
class QuestionContextRow:
    """A single question-to-context chunk link row."""

    chunk_id: uuid.UUID
    similarity_score: float
    rank: int


__all__ = ["ChunkWithEmbedding", "QuestionContextRow"]
