"""Service layer package."""

from app.services.embeddings import (
    OllamaEmbeddingClient,
    close_embeddings_client,
    embed_documents,
    embed_query,
    get_embeddings_client,
)
from app.services.llm import build_openai_client, generate_answer

__all__ = [
    "OllamaEmbeddingClient",
    "build_openai_client",
    "close_embeddings_client",
    "embed_documents",
    "embed_query",
    "generate_answer",
    "get_embeddings_client",
]
