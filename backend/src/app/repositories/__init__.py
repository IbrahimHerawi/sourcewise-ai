"""Data access repositories package."""

from app.repositories.chunk_repository import ChunkRepository
from app.repositories.collection_repository import (
    CollectionRepository,
    DuplicateCollectionNameError,
)
from app.repositories.document_repository import DocumentRepository
from app.repositories.ingestion_job_repository import IngestionJobRepository
from app.repositories.question_context_repository import QuestionContextRepository
from app.repositories.question_repository import QuestionRepository
from app.repositories.types import (
    ChunkWithEmbedding,
    QuestionContextRow,
    SimilaritySearchResult,
)
from app.repositories.user_repository import DuplicateUserEmailError, UserRepository

__all__ = [
    "ChunkRepository",
    "ChunkWithEmbedding",
    "CollectionRepository",
    "DocumentRepository",
    "DuplicateCollectionNameError",
    "DuplicateUserEmailError",
    "IngestionJobRepository",
    "QuestionContextRepository",
    "QuestionContextRow",
    "QuestionRepository",
    "SimilaritySearchResult",
    "UserRepository",
]
