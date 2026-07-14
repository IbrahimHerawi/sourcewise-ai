"""Service layer package."""

from app.services.embeddings import (
    EmbeddingCardinalityMismatchError,
    EmbeddingDimensionMismatchError,
    OllamaEmbeddingClient,
    OllamaEmbeddingError,
    OllamaMalformedResponseError,
    OllamaTransientEmbeddingError,
    close_embeddings_client,
    embed_documents,
    embed_query,
    get_embeddings_client,
)
from app.services.llm import (
    LLMInvalidResponseError,
    LLMRejectedError,
    LLMTransientError,
    build_openai_client,
    generate_answer,
)
from app.services.question_answering import (
    QuestionAnsweringError,
    answer_question,
)

__all__ = [
    "EmbeddingCardinalityMismatchError",
    "EmbeddingDimensionMismatchError",
    "LLMInvalidResponseError",
    "LLMRejectedError",
    "LLMTransientError",
    "OllamaEmbeddingClient",
    "OllamaEmbeddingError",
    "OllamaMalformedResponseError",
    "OllamaTransientEmbeddingError",
    "build_openai_client",
    "close_embeddings_client",
    "embed_documents",
    "embed_query",
    "generate_answer",
    "get_embeddings_client",
    "QuestionAnsweringError",
    "answer_question",
]
