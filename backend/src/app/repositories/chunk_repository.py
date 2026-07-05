"""Repository for document chunk persistence and similarity search."""

from __future__ import annotations

import uuid
from collections.abc import Sequence

from sqlalchemy import insert, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.document_chunks import DocumentChunk
from app.db.models.documents import Document, DocumentStatus
from app.repositories.types import ChunkWithEmbedding


class ChunkRepository:
    """Data access methods for document chunks."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def bulk_insert_chunks(
        self,
        document_id: uuid.UUID,
        chunks_with_embeddings: Sequence[ChunkWithEmbedding],
    ) -> list[DocumentChunk]:
        """Bulk insert chunks for a document and return inserted ORM rows."""
        if not chunks_with_embeddings:
            return []

        payload = [
            {
                "document_id": document_id,
                "chunk_index": chunk.chunk_index,
                "content": chunk.content,
                "embedding": chunk.embedding,
            }
            for chunk in chunks_with_embeddings
        ]
        stmt = insert(DocumentChunk).values(payload).returning(DocumentChunk)
        result = await self._session.scalars(stmt)
        return list(result.all())

    async def similarity_search(
        self,
        query_embedding: list[float],
        top_k: int,
        document_ids: Sequence[uuid.UUID] | None = None,
        *,
        ready_only: bool = False,
        max_distance: float | None = None,
    ) -> list[tuple[DocumentChunk, float]]:
        """Search chunks by vector distance using pgvector `<=>` ordering."""
        if top_k <= 0:
            raise ValueError("top_k must be greater than 0")
        if document_ids is not None and not document_ids:
            return []
        if max_distance is not None and max_distance < 0:
            raise ValueError("max_distance must be greater than or equal to 0")

        distance_expr = DocumentChunk.embedding.cosine_distance(query_embedding)
        stmt = select(DocumentChunk, distance_expr.label("distance"))
        if ready_only:
            stmt = stmt.join(Document, Document.id == DocumentChunk.document_id).where(
                Document.status == DocumentStatus.READY
            )
        if document_ids is not None:
            stmt = stmt.where(DocumentChunk.document_id.in_(document_ids))
        if max_distance is not None:
            stmt = stmt.where(distance_expr <= max_distance)

        stmt = stmt.order_by(distance_expr).limit(top_k)
        result = await self._session.execute(stmt)
        return [(chunk, float(distance_value)) for chunk, distance_value in result.all()]


__all__ = ["ChunkRepository"]
