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
    FALLBACK_ANSWER,
    GeneratedAnswer,
    LLMInvalidResponseError,
    LLMRejectedError,
    LLMTransientError,
    build_openai_client,
    generate_answer,
)
from app.services.question_answering import (
    CollectionNotFoundError,
    QuestionAnsweringError,
    QuestionRetrievalResult,
    RetrievedContextChunk,
    answer_question,
    retrieve_question_context,
)

__all__ = [
    "EmbeddingCardinalityMismatchError",
    "EmbeddingDimensionMismatchError",
    "FALLBACK_ANSWER",
    "GeneratedAnswer",
    "LLMInvalidResponseError",
    "LLMRejectedError",
    "LLMTransientError",
    "OllamaEmbeddingClient",
    "OllamaEmbeddingError",
    "OllamaMalformedResponseError",
    "OllamaTransientEmbeddingError",
    "build_openai_client",
    "close_embeddings_client",
    "CollectionNotFoundError",
    "embed_documents",
    "embed_query",
    "generate_answer",
    "get_embeddings_client",
    "QuestionAnsweringError",
    "QuestionRetrievalResult",
    "RetrievedContextChunk",
    "answer_question",
    "retrieve_question_context",
]
