from __future__ import annotations

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.settings import get_settings
from app.db.models.documents import Document, DocumentStatus
from app.repositories.chunk_repository import ChunkRepository
from app.repositories.document_repository import DocumentRepository
from app.repositories.types import ChunkWithEmbedding


def _embedding(first_dim: float, second_dim: float, dim: int) -> list[float]:
    if dim < 2:
        raise ValueError("embedding_dim must be at least 2 for repository tests")
    return [first_dim, second_dim] + [0.0] * (dim - 2)


async def _create_document(
    session: AsyncSession,
    *,
    filename: str,
    extracted_text: str = "sample extracted text",
) -> Document:
    repository = DocumentRepository(session)
    return await repository.create_document(
        filename=filename,
        original_extension=".txt",
        content_type="text/plain",
        size_bytes=42,
        storage_path=f"/tmp/{filename}",
        extracted_text=extracted_text,
    )


@pytest.mark.asyncio
async def test_document_repository_crud_create_get_update_status(db_session: AsyncSession) -> None:
    repository = DocumentRepository(db_session)

    created = await repository.create_document(
        filename="doc-a.txt",
        original_extension=".txt",
        content_type="text/plain",
        size_bytes=111,
        storage_path="/tmp/doc-a.txt",
        extracted_text="hello world",
    )
    fetched = await repository.get_document(created.id)
    assert fetched is not None
    assert fetched.id == created.id
    assert fetched.status == DocumentStatus.PENDING

    updated = await repository.update_status(created.id, DocumentStatus.READY)
    fetched_after_update = await repository.get_document(created.id)

    assert updated is not None
    assert updated.status == DocumentStatus.READY
    assert fetched_after_update is not None
    assert fetched_after_update.status == DocumentStatus.READY


@pytest.mark.asyncio
async def test_chunk_repository_bulk_insert_chunks_enforces_document_chunk_index_uniqueness(
    db_session: AsyncSession,
) -> None:
    settings = get_settings()
    repository = ChunkRepository(db_session)

    first_document = await _create_document(db_session, filename="first.txt")
    second_document = await _create_document(db_session, filename="second.txt")

    inserted_rows = await repository.bulk_insert_chunks(
        first_document.id,
        [
            ChunkWithEmbedding(
                chunk_index=0,
                content="first chunk",
                embedding=_embedding(1.0, 0.0, settings.embedding_dim),
            ),
            ChunkWithEmbedding(
                chunk_index=1,
                content="second chunk",
                embedding=_embedding(0.0, 1.0, settings.embedding_dim),
            ),
        ],
    )
    inserted_second_doc = await repository.bulk_insert_chunks(
        second_document.id,
        [
            ChunkWithEmbedding(
                chunk_index=0,
                content="same index, different document",
                embedding=_embedding(1.0, 1.0, settings.embedding_dim),
            )
        ],
    )

    assert [(chunk.document_id, chunk.chunk_index) for chunk in inserted_rows] == [
        (first_document.id, 0),
        (first_document.id, 1),
    ]
    assert len(inserted_second_doc) == 1
    assert inserted_second_doc[0].document_id == second_document.id
    assert inserted_second_doc[0].chunk_index == 0

    with pytest.raises(IntegrityError):
        await repository.bulk_insert_chunks(
            first_document.id,
            [
                ChunkWithEmbedding(
                    chunk_index=0,
                    content="duplicate index",
                    embedding=_embedding(0.9, 0.1, settings.embedding_dim),
                )
            ],
        )


@pytest.mark.asyncio
async def test_chunk_repository_similarity_search_orders_by_cosine_distance(
    db_session: AsyncSession,
) -> None:
    settings = get_settings()
    repository = ChunkRepository(db_session)
    document = await _create_document(db_session, filename="similarity.txt")

    await repository.bulk_insert_chunks(
        document.id,
        [
            ChunkWithEmbedding(
                chunk_index=0,
                content="vector [1, 0]",
                embedding=_embedding(1.0, 0.0, settings.embedding_dim),
            ),
            ChunkWithEmbedding(
                chunk_index=1,
                content="vector [0, 1]",
                embedding=_embedding(0.0, 1.0, settings.embedding_dim),
            ),
            ChunkWithEmbedding(
                chunk_index=2,
                content="vector [1, 1]",
                embedding=_embedding(1.0, 1.0, settings.embedding_dim),
            ),
        ],
    )

    query_embedding = _embedding(0.9, 0.1, settings.embedding_dim)
    results = await repository.similarity_search(
        query_embedding=query_embedding,
        top_k=3,
        document_ids=[document.id],
    )

    assert [chunk.chunk_index for chunk, _ in results] == [0, 2, 1]
    assert results[0][1] < results[1][1] < results[2][1]
