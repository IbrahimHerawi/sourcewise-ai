"""Service layer package."""

from app.services.embeddings import (
    OllamaEmbeddingClient,
    close_embeddings_client,
    embed_documents,
    embed_query,
    get_embeddings_client,
)

__all__ = [
    "OllamaEmbeddingClient",
    "close_embeddings_client",
    "embed_documents",
    "embed_query",
    "get_embeddings_client",
]
