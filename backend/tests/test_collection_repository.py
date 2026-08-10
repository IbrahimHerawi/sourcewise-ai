from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.settings import get_settings
from app.db.models import Collection, Document, DocumentStatus, Question, User
from app.repositories import CollectionRepository, DuplicateCollectionNameError


async def _create_user(session: AsyncSession, label: str) -> User:
    user = User(
        email=f"{label}-{uuid.uuid4()}@example.com",
        password_hash="test-password-hash",
        first_name="Collection",
        last_name="Tester",
    )
    session.add(user)
    await session.flush()
    return user


@pytest.mark.asyncio
async def test_collection_repository_crud_and_normalization(
    db_session: AsyncSession,
) -> None:
    user = await _create_user(db_session, "collection-crud")
    repository = CollectionRepository(db_session)

    created = await repository.create_collection(
        user.id,
        "  Research Sources  ",
        "  Primary material  ",
    )
    fetched = await repository.get_collection(user.id, created.id)

    assert fetched is not None
    assert fetched.name == "Research Sources"
    assert fetched.description == "Primary material"

    updated = await repository.update_collection(
        user.id,
        created.id,
        name="  My RESEARCH  ",
        description="   ",
    )

    assert updated is not None
    assert updated.name == "My RESEARCH"
    assert updated.description is None
    assert await repository.delete_collection(user.id, created.id) is True
    assert await repository.get_collection(user.id, created.id) is None
    assert await repository.delete_collection(user.id, created.id) is False


@pytest.mark.asyncio
async def test_collection_repository_applies_schema_validation_before_writes(
    db_session: AsyncSession,
) -> None:
    user = await _create_user(db_session, "collection-validation")
    repository = CollectionRepository(db_session)

    with pytest.raises(ValidationError):
        await repository.create_collection(user.id, "   ", None)

    collection = await repository.create_collection(user.id, "Valid", None)
    with pytest.raises(ValidationError):
        await repository.update_collection(user.id, collection.id)
    with pytest.raises(ValidationError):
        await repository.update_collection(user.id, collection.id, unknown=True)

    unchanged = await repository.get_collection(user.id, collection.id)
    assert unchanged is not None
    assert unchanged.name == "Valid"


@pytest.mark.asyncio
async def test_collection_repository_paginates_in_stable_newest_first_order(
    db_session: AsyncSession,
) -> None:
    user = await _create_user(db_session, "collection-pagination")
    other_user = await _create_user(db_session, "collection-pagination-other")
    repository = CollectionRepository(db_session)

    collections = [
        await repository.create_collection(user.id, name, None)
        for name in ("First", "Second", "Third")
    ]
    await repository.create_collection(other_user.id, "Other owner's collection", None)
    common_timestamp = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
    await db_session.execute(
        update(Collection)
        .where(Collection.user_id == user.id)
        .values(created_at=common_timestamp)
    )

    listed = await repository.list_collections(user.id, limit=2, offset=1)

    expected_ids = sorted(
        (collection.id for collection in collections),
        reverse=True,
    )[1:]
    assert [collection.id for collection in listed] == expected_ids
    assert await repository.count_collections(user.id) == 3
    assert await repository.count_collections(other_user.id) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("limit", "offset"),
    [(0, 0), (-1, 0), (1, -1)],
)
async def test_collection_repository_rejects_invalid_pagination(
    db_session: AsyncSession,
    limit: int,
    offset: int,
) -> None:
    repository = CollectionRepository(db_session)

    with pytest.raises(ValueError):
        await repository.list_collections(uuid.uuid4(), limit=limit, offset=offset)


@pytest.mark.asyncio
async def test_collection_repository_enforces_owner_isolation(
    db_session: AsyncSession,
) -> None:
    owner = await _create_user(db_session, "collection-owner")
    other_user = await _create_user(db_session, "collection-other-user")
    repository = CollectionRepository(db_session)

    owners_collection = await repository.create_collection(
        owner.id,
        "  Shared Name  ",
        "Owner's description",
    )
    others_collection = await repository.create_collection(
        other_user.id,
        "shared name",
        "Other user's description",
    )

    assert await repository.get_collection(other_user.id, owners_collection.id) is None
    assert (
        await repository.update_collection(
            other_user.id,
            owners_collection.id,
            name="Hijacked",
        )
        is None
    )
    assert (
        await repository.delete_collection(other_user.id, owners_collection.id) is False
    )

    owner_result = await repository.get_collection(owner.id, owners_collection.id)
    other_result = await repository.get_collection(other_user.id, others_collection.id)
    assert owner_result is not None
    assert owner_result.name == "Shared Name"
    assert other_result is not None
    assert other_result.name == "shared name"
    assert [item.id for item in await repository.list_collections(owner.id, 10, 0)] == [
        owners_collection.id
    ]


@pytest.mark.asyncio
async def test_collection_repository_translates_case_insensitive_duplicates(
    db_session: AsyncSession,
) -> None:
    user = await _create_user(db_session, "collection-duplicate")
    repository = CollectionRepository(db_session)
    original = await repository.create_collection(user.id, "Research", None)

    with pytest.raises(DuplicateCollectionNameError) as create_error:
        await repository.create_collection(user.id, "  RESEARCH  ", None)

    second = await repository.create_collection(user.id, "Second", None)
    with pytest.raises(DuplicateCollectionNameError) as update_error:
        await repository.update_collection(user.id, second.id, name="research")

    assert create_error.value.user_id == user.id
    assert create_error.value.name == "RESEARCH"
    assert update_error.value.user_id == user.id
    assert update_error.value.name == "research"
    assert await repository.count_collections(user.id) == 2
    assert (await repository.get_collection(user.id, original.id)) is not None
    unchanged_second = await repository.get_collection(user.id, second.id)
    assert unchanged_second is not None
    assert unchanged_second.name == "Second"


@pytest.mark.asyncio
async def test_collection_repository_concurrent_duplicate_protection(
    postgres_database_url: str,
    migrated_database: None,
) -> None:
    del migrated_database
    engine = create_async_engine(postgres_database_url, pool_pre_ping=True)
    session_maker = async_sessionmaker(engine, expire_on_commit=False, autoflush=False)
    user_id = uuid.uuid4()
    email = f"concurrent-collection-{user_id}@example.com"

    async with session_maker() as setup_session:
        setup_session.add(
            User(
                id=user_id,
                email=email,
                password_hash="test-password-hash",
                first_name="Concurrent",
                last_name="Tester",
            )
        )
        await setup_session.commit()

    async def create(name: str) -> Collection | DuplicateCollectionNameError:
        async with session_maker() as session:
            try:
                collection = await CollectionRepository(session).create_collection(
                    user_id,
                    name,
                    None,
                )
                await session.commit()
                return collection
            except DuplicateCollectionNameError as exc:
                await session.rollback()
                return exc

    try:
        results = await asyncio.gather(create("Research"), create("RESEARCH"))

        assert sum(isinstance(item, Collection) for item in results) == 1
        assert sum(isinstance(item, DuplicateCollectionNameError) for item in results) == 1

        async with session_maker() as verification_session:
            names = list(
                await verification_session.scalars(
                    select(Collection.name).where(Collection.user_id == user_id)
                )
            )
        assert len(names) == 1
        assert names[0].lower() == "research"
    finally:
        async with session_maker() as cleanup_session:
            cleanup_user = await cleanup_session.get(User, user_id)
            if cleanup_user is not None:
                await cleanup_session.delete(cleanup_user)
                await cleanup_session.commit()
        await engine.dispose()


@pytest.mark.asyncio
async def test_collection_delete_sets_associated_content_collection_to_null(
    db_session: AsyncSession,
) -> None:
    settings = get_settings()
    user = await _create_user(db_session, "collection-set-null")
    repository = CollectionRepository(db_session)
    collection = await repository.create_collection(user.id, "Sources", None)
    document = Document(
        user_id=user.id,
        collection_id=collection.id,
        filename="source.txt",
        original_extension=".txt",
        content_type="text/plain",
        size_bytes=12,
        storage_path="/tmp/source.txt",
        extracted_text="source text",
        status=DocumentStatus.READY,
    )
    question = Question(
        user_id=user.id,
        collection_id=collection.id,
        question_text="What is the source?",
        question_embedding=[0.0] * settings.embedding_dim,
        answer_text="A test source.",
        ai_provider="ollama",
        model_used="test-model",
    )
    db_session.add_all([document, question])
    await db_session.flush()

    assert await repository.delete_collection(user.id, collection.id) is True
    await db_session.refresh(document)
    await db_session.refresh(question)

    assert document.collection_id is None
    assert question.collection_id is None
    assert await db_session.get(Document, document.id) is not None
    assert await db_session.get(Question, question.id) is not None
