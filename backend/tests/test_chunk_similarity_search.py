from __future__ import annotations

import uuid
from dataclasses import FrozenInstanceError

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.settings import get_settings
from app.db.models.auth import User
from app.db.models.collections import Collection
from app.db.models.documents import Document, DocumentStatus
from app.db.models.ingestion_jobs import IngestionJobStatus
from app.repositories.chunk_repository import ChunkRepository
from app.repositories.document_repository import DocumentRepository
from app.repositories.ingestion_job_repository import IngestionJobRepository
from app.repositories.types import ChunkWithEmbedding, SimilaritySearchResult


def _embedding(first_dim: float, second_dim: float) -> list[float]:
    dim = get_settings().embedding_dim
    if dim < 2:
        raise ValueError("embedding_dim must be at least 2 for repository tests")
    return [first_dim, second_dim] + [0.0] * (dim - 2)


async def _create_user(session: AsyncSession, label: str) -> User:
    user = User(
        email=f"similarity-{label}-{uuid.uuid4()}@example.com",
        password_hash="test-password-hash",
        first_name="Similarity",
        last_name="Tester",
    )
    session.add(user)
    await session.flush()
    return user


async def _create_collection(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    name: str,
) -> Collection:
    collection = Collection(user_id=user_id, name=name)
    session.add(collection)
    await session.flush()
    return collection


async def _create_document(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    filename: str,
    status: DocumentStatus = DocumentStatus.READY,
    collection_id: uuid.UUID | None = None,
) -> Document:
    return await DocumentRepository(session).create_document(
        user_id,
        collection_id=collection_id,
        filename=filename,
        original_extension=".txt",
        content_type="text/plain",
        size_bytes=42,
        storage_path=f"/tmp/{filename}",
        extracted_text="retrieval fixture",
        status=status,
    )


async def _insert_chunk(
    session: AsyncSession,
    *,
    document: Document,
    content: str,
    embedding: list[float],
    chunk_index: int = 0,
) -> uuid.UUID:
    inserted = await ChunkRepository(session).bulk_insert_chunks(
        document.id,
        [
            ChunkWithEmbedding(
                chunk_index=chunk_index,
                content=content,
                embedding=embedding,
            )
        ],
    )
    return inserted[0].id


@pytest.mark.asyncio
async def test_similarity_search_enforces_owner_collection_and_ready_status_before_limit(
    db_session: AsyncSession,
) -> None:
    repository = ChunkRepository(db_session)
    owner = await _create_user(db_session, "owner")
    foreign_user = await _create_user(db_session, "foreign")
    first_collection = await _create_collection(
        db_session,
        user_id=owner.id,
        name="First collection",
    )
    second_collection = await _create_collection(
        db_session,
        user_id=owner.id,
        name="Second collection",
    )
    foreign_collection = await _create_collection(
        db_session,
        user_id=foreign_user.id,
        name="Foreign collection",
    )

    ready_documents = [
        await _create_document(
            db_session,
            user_id=owner.id,
            collection_id=first_collection.id,
            filename="first-ready.txt",
        ),
        await _create_document(
            db_session,
            user_id=owner.id,
            collection_id=second_collection.id,
            filename="second-ready.txt",
        ),
        await _create_document(
            db_session,
            user_id=owner.id,
            filename="uncollected-ready.txt",
        ),
    ]
    for document, content, embedding in zip(
        ready_documents,
        ("first ready", "second ready", "uncollected ready"),
        (_embedding(0.9, 0.1), _embedding(0.8, 0.2), _embedding(0.7, 0.3)),
        strict=True,
    ):
        await _insert_chunk(
            db_session,
            document=document,
            content=content,
            embedding=embedding,
        )

    foreign_document = await _create_document(
        db_session,
        user_id=foreign_user.id,
        collection_id=foreign_collection.id,
        filename="globally-closest-foreign.txt",
    )
    await _insert_chunk(
        db_session,
        document=foreign_document,
        content="globally closest foreign",
        embedding=_embedding(1.0, 0.0),
    )

    for status in (
        DocumentStatus.PENDING,
        DocumentStatus.PROCESSING,
        DocumentStatus.FAILED,
    ):
        document = await _create_document(
            db_session,
            user_id=owner.id,
            collection_id=first_collection.id,
            filename=f"{status.value.lower()}.txt",
            status=status,
        )
        await _insert_chunk(
            db_session,
            document=document,
            content=f"excluded {status.value}",
            embedding=_embedding(1.0, 0.0),
        )

    all_owner_results = await repository.similarity_search(
        owner.id,
        _embedding(1.0, 0.0),
        top_k=10,
    )
    top_owner_results = await repository.similarity_search(
        owner.id,
        _embedding(1.0, 0.0),
        top_k=1,
    )
    first_collection_results = await repository.similarity_search(
        owner.id,
        _embedding(1.0, 0.0),
        top_k=1,
        collection_id=first_collection.id,
    )
    foreign_collection_results = await repository.similarity_search(
        owner.id,
        _embedding(1.0, 0.0),
        top_k=10,
        collection_id=foreign_collection.id,
    )

    assert [result.content for result in all_owner_results] == [
        "first ready",
        "second ready",
        "uncollected ready",
    ]
    assert [result.content for result in top_owner_results] == ["first ready"]
    assert [result.content for result in first_collection_results] == ["first ready"]
    assert foreign_collection_results == []


@pytest.mark.asyncio
async def test_similarity_search_applies_maximum_distance_and_returns_empty_results(
    db_session: AsyncSession,
) -> None:
    repository = ChunkRepository(db_session)
    owner = await _create_user(db_session, "distance-owner")
    document = await _create_document(
        db_session,
        user_id=owner.id,
        filename="distance.txt",
    )
    await _insert_chunk(
        db_session,
        document=document,
        content="exact match",
        embedding=_embedding(1.0, 0.0),
        chunk_index=0,
    )
    await _insert_chunk(
        db_session,
        document=document,
        content="orthogonal match",
        embedding=_embedding(0.0, 1.0),
        chunk_index=1,
    )

    results = await repository.similarity_search(
        owner.id,
        _embedding(1.0, 0.0),
        top_k=10,
        max_distance=0.5,
    )
    no_results = await repository.similarity_search(
        owner.id,
        _embedding(0.0, 1.0),
        top_k=10,
        max_distance=0.5,
        collection_id=uuid.uuid4(),
    )

    assert [result.content for result in results] == ["exact match"]
    assert results[0].distance == pytest.approx(0.0)
    assert no_results == []


@pytest.mark.asyncio
async def test_similarity_search_orders_ties_by_chunk_id_limits_and_returns_snapshots(
    db_session: AsyncSession,
) -> None:
    repository = ChunkRepository(db_session)
    owner = await _create_user(db_session, "tie-owner")
    document = await _create_document(
        db_session,
        user_id=owner.id,
        filename="tie-source.txt",
    )
    chunk_ids = [
        await _insert_chunk(
            db_session,
            document=document,
            content=f"tie {chunk_index}",
            embedding=_embedding(1.0, 0.0),
            chunk_index=chunk_index,
        )
        for chunk_index in range(3)
    ]

    results = await repository.similarity_search(
        owner.id,
        _embedding(1.0, 0.0),
        top_k=2,
    )

    assert all(isinstance(result, SimilaritySearchResult) for result in results)
    assert [result.chunk_id for result in results] == sorted(chunk_ids)[:2]
    assert [result.distance for result in results] == pytest.approx([0.0, 0.0])
    assert {result.document_filename for result in results} == {"tie-source.txt"}
    with pytest.raises(FrozenInstanceError):
        results[0].content = "mutated"  # type: ignore[misc]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("top_k", "max_distance", "message"),
    [
        (0, None, "top_k must be greater than 0"),
        (-1, None, "top_k must be greater than 0"),
        (1, -0.001, "max_distance must be greater than or equal to 0"),
        (1, float("nan"), "max_distance must be greater than or equal to 0"),
    ],
)
async def test_similarity_search_rejects_invalid_arguments_before_querying(
    top_k: int,
    max_distance: float | None,
    message: str,
) -> None:
    session = AsyncSession()
    repository = ChunkRepository(session)

    with pytest.raises(ValueError, match=message):
        await repository.similarity_search(
            uuid.uuid4(),
            _embedding(1.0, 0.0),
            top_k=top_k,
            max_distance=max_distance,
        )

    assert not session.in_transaction()
    await session.close()


@pytest.mark.asyncio
async def test_similarity_search_supports_legacy_and_batched_ready_documents(
    db_session: AsyncSession,
) -> None:
    repository = ChunkRepository(db_session)
    owner = await _create_user(db_session, "compatibility-owner")

    legacy_document = Document(
        user_id=owner.id,
        filename="legacy-ready.txt",
        original_extension=".txt",
        content_type="text/plain",
        size_bytes=42,
        storage_path="/tmp/legacy-ready.txt",
        extracted_text="created before batched ingestion",
        status=DocumentStatus.READY,
    )
    db_session.add(legacy_document)
    await db_session.flush()
    batched_document = await _create_document(
        db_session,
        user_id=owner.id,
        filename="batched-ready.txt",
    )
    await IngestionJobRepository(db_session).create_job(
        document_id=batched_document.id,
        status=IngestionJobStatus.DONE,
    )

    await _insert_chunk(
        db_session,
        document=legacy_document,
        content="legacy retrieval data",
        embedding=_embedding(1.0, 0.0),
    )
    await _insert_chunk(
        db_session,
        document=batched_document,
        content="batched retrieval data",
        embedding=_embedding(0.9, 0.1),
    )

    results = await repository.similarity_search(
        owner.id,
        _embedding(1.0, 0.0),
        top_k=10,
    )

    assert [result.content for result in results] == [
        "legacy retrieval data",
        "batched retrieval data",
    ]
