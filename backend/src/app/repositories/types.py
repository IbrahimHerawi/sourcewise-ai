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
    """A complete citation snapshot captured for a question."""

    rank: int
    document_id: uuid.UUID
    document_filename: str
    chunk_id: uuid.UUID
    chunk_index: int
    chunk_content: str
    similarity_score: float


__all__ = ["ChunkWithEmbedding", "QuestionContextRow"]
