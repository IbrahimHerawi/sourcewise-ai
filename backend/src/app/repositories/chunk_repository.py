"""Repository for document chunk persistence and similarity search."""

from __future__ import annotations

import uuid
from collections.abc import Sequence

from sqlalchemy import insert, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.document_chunks import DocumentChunk
from app.db.models.documents import Document, DocumentStatus
from app.repositories.types import ChunkWithEmbedding, SimilaritySearchResult


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
        user_id: uuid.UUID,
        query_embedding: list[float],
        top_k: int,
        collection_id: uuid.UUID | None = None,
        document_ids: Sequence[uuid.UUID] | None = None,
        max_distance: float | None = None,
    ) -> list[SimilaritySearchResult]:
        """Search one owner's READY document chunks by cosine distance."""
        if top_k <= 0:
            raise ValueError("top_k must be greater than 0")
        if max_distance is not None and not max_distance >= 0:
            raise ValueError("max_distance must be greater than or equal to 0")

        distance_expr = DocumentChunk.embedding.cosine_distance(query_embedding)
        stmt = (
            select(
                DocumentChunk.id,
                Document.id,
                Document.filename,
                DocumentChunk.chunk_index,
                DocumentChunk.content,
                distance_expr.label("distance"),
            )
            .join(Document, Document.id == DocumentChunk.document_id)
            .where(
                Document.user_id == user_id,
                Document.status == DocumentStatus.READY,
            )
        )
        if collection_id is not None:
            stmt = stmt.where(Document.collection_id == collection_id)
        if document_ids is not None:
            unique_document_ids = tuple(dict.fromkeys(document_ids))
            if not unique_document_ids:
                return []
            stmt = stmt.where(Document.id.in_(unique_document_ids))
        if max_distance is not None:
            stmt = stmt.where(distance_expr <= max_distance)

        stmt = stmt.order_by(distance_expr.asc(), DocumentChunk.id.asc()).limit(top_k)
        result = await self._session.execute(stmt)
        return [
            SimilaritySearchResult(
                chunk_id=chunk_id,
                document_id=document_id,
                document_filename=document_filename,
                chunk_index=chunk_index,
                content=content,
                distance=float(distance),
            )
            for (
                chunk_id,
                document_id,
                document_filename,
                chunk_index,
                content,
                distance,
            ) in result.all()
        ]


__all__ = ["ChunkRepository"]
