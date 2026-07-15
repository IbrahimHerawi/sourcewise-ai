from __future__ import annotations

import asyncio
import uuid
from pathlib import Path
from typing import Any

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncSession, create_async_engine

from app.db.models import Collection, User

ALEMBIC_INI_PATH = Path(__file__).resolve().parents[1] / "alembic.ini"
CASE_INSENSITIVE_INDEX_NAME = "uq_collections_user_lower_name"
ORIGINAL_CONSTRAINT_NAME = "uq_collections_user_id"


async def _collection_schema(connection: AsyncConnection) -> dict[str, Any]:
    def inspect_schema(sync_connection: Any) -> dict[str, Any]:
        inspector = inspect(sync_connection)
        return {
            "tables": set(inspector.get_table_names()),
            "indexes": {
                index["name"]: index for index in inspector.get_indexes("collections")
            },
            "foreign_keys": inspector.get_foreign_keys("collections"),
            "unique_constraints": inspector.get_unique_constraints("collections"),
        }

    return await connection.run_sync(inspect_schema)


def _alembic_config() -> Config:
    return Config(str(ALEMBIC_INI_PATH))


def _assert_case_insensitive_index(schema: dict[str, Any]) -> None:
    index = schema["indexes"][CASE_INSENSITIVE_INDEX_NAME]
    assert index["unique"] is True
    assert index["column_names"] == ["user_id", None]
    assert index["expressions"][0] == "user_id"
    assert "lower" in index["expressions"][1].lower()
    assert "name" in index["expressions"][1].lower()


async def _insert_user(connection: AsyncConnection, user_id: uuid.UUID, email: str) -> None:
    await connection.execute(
        text(
            """
            INSERT INTO users (id, email, password_hash, first_name, last_name)
            VALUES (:id, :email, 'test-password-hash', 'Migration', 'Test')
            """
        ),
        {"id": user_id, "email": email},
    )


async def _insert_collection(
    connection: AsyncConnection,
    *,
    collection_id: uuid.UUID,
    user_id: uuid.UUID,
    name: str,
    description: str | None = None,
) -> None:
    await connection.execute(
        text(
            """
            INSERT INTO collections (id, user_id, name, description)
            VALUES (:id, :user_id, :name, :description)
            """
        ),
        {
            "id": collection_id,
            "user_id": user_id,
            "name": name,
            "description": description,
        },
    )


@pytest.mark.asyncio
async def test_collection_persists_and_belongs_to_user(db_session: AsyncSession) -> None:
    user = User(
        email="collection-owner@example.com",
        password_hash="hashed-password",
        first_name="Collection",
        last_name="Owner",
    )
    collection = Collection(name="Research", description="Primary research sources")
    user.collections.append(collection)

    db_session.add(user)
    await db_session.flush()

    assert collection.id is not None
    assert collection.user_id == user.id
    assert collection.user is user
    assert collection.created_at is not None
    assert collection.updated_at is not None


@pytest.mark.asyncio
async def test_collection_migration_creates_constraints_and_owner_list_index(
    db_session: AsyncSession,
) -> None:
    async_connection = await db_session.connection()
    schema = await _collection_schema(async_connection)

    assert "collections" in schema["tables"]
    assert "ix_collections_user_created_desc" in schema["indexes"]
    assert "ix_collections_user_id" not in schema["indexes"]
    assert CASE_INSENSITIVE_INDEX_NAME in schema["indexes"]
    _assert_case_insensitive_index(schema)
    assert ORIGINAL_CONSTRAINT_NAME not in {
        constraint["name"] for constraint in schema["unique_constraints"]
    }

    user_foreign_keys = [
        foreign_key
        for foreign_key in schema["foreign_keys"]
        if foreign_key["referred_table"] == "users"
    ]
    assert len(user_foreign_keys) == 1
    assert user_foreign_keys[0]["options"]["ondelete"] == "CASCADE"


@pytest.mark.asyncio
async def test_collection_migration_downgrades_and_reupgrades(
    postgres_database_url: str,
    migrated_database: None,
) -> None:
    del migrated_database
    alembic_config = _alembic_config()
    engine = create_async_engine(postgres_database_url, pool_pre_ping=True)

    try:
        await asyncio.to_thread(command.downgrade, alembic_config, "0006_content_ownership")
        async with engine.connect() as connection:
            downgraded_schema = await _collection_schema(connection)

        assert CASE_INSENSITIVE_INDEX_NAME not in downgraded_schema["indexes"]
        assert "ix_collections_user_id" in downgraded_schema["indexes"]
        assert any(
            constraint["name"] == ORIGINAL_CONSTRAINT_NAME
            and constraint["column_names"] == ["user_id", "name"]
            for constraint in downgraded_schema["unique_constraints"]
        )

        await asyncio.to_thread(command.upgrade, alembic_config, "head")
        async with engine.connect() as connection:
            upgraded_schema = await _collection_schema(connection)

        assert CASE_INSENSITIVE_INDEX_NAME in upgraded_schema["indexes"]
        _assert_case_insensitive_index(upgraded_schema)
        assert "ix_collections_user_created_desc" in upgraded_schema["indexes"]
        assert "ix_collections_user_id" not in upgraded_schema["indexes"]
        assert ORIGINAL_CONSTRAINT_NAME not in {
            constraint["name"] for constraint in upgraded_schema["unique_constraints"]
        }
    finally:
        await asyncio.to_thread(command.upgrade, alembic_config, "head")
        await engine.dispose()


@pytest.mark.asyncio
async def test_collection_migration_aborts_for_same_user_casing_conflicts(
    postgres_database_url: str,
    migrated_database: None,
) -> None:
    del migrated_database
    alembic_config = _alembic_config()
    engine = create_async_engine(postgres_database_url, pool_pre_ping=True)
    affected_user_id = uuid.uuid4()
    unaffected_user_id = uuid.uuid4()
    affected_collection_ids = [uuid.uuid4(), uuid.uuid4()]
    sensitive_description = "must-not-appear-in-migration-error"

    try:
        await asyncio.to_thread(command.downgrade, alembic_config, "0006_content_ownership")
        async with engine.begin() as connection:
            await _insert_user(
                connection,
                affected_user_id,
                f"affected-{affected_user_id}@example.com",
            )
            await _insert_user(
                connection,
                unaffected_user_id,
                f"unaffected-{unaffected_user_id}@example.com",
            )
            await _insert_collection(
                connection,
                collection_id=affected_collection_ids[0],
                user_id=affected_user_id,
                name="Research",
                description=sensitive_description,
            )
            await _insert_collection(
                connection,
                collection_id=affected_collection_ids[1],
                user_id=affected_user_id,
                name="RESEARCH",
            )
            await _insert_collection(
                connection,
                collection_id=uuid.uuid4(),
                user_id=unaffected_user_id,
                name="Research",
            )

        with pytest.raises(RuntimeError) as error:
            await asyncio.to_thread(command.upgrade, alembic_config, "head")

        message = str(error.value)
        assert str(affected_user_id) in message
        assert '"normalized_name": "research"' in message
        assert str(unaffected_user_id) not in message
        assert str(affected_collection_ids[0]) not in message
        assert str(affected_collection_ids[1]) not in message
        assert sensitive_description not in message
        assert "Research" not in message
        assert "RESEARCH" not in message

        async with engine.connect() as connection:
            schema_after_failure = await _collection_schema(connection)
            preserved_count = await connection.scalar(
                text("SELECT count(*) FROM collections WHERE user_id = :user_id"),
                {"user_id": affected_user_id},
            )

        assert preserved_count == 2
        assert CASE_INSENSITIVE_INDEX_NAME not in schema_after_failure["indexes"]
        assert any(
            constraint["name"] == ORIGINAL_CONSTRAINT_NAME
            for constraint in schema_after_failure["unique_constraints"]
        )
    finally:
        async with engine.begin() as connection:
            await connection.execute(
                text("DELETE FROM users WHERE id IN (:affected_id, :unaffected_id)"),
                {
                    "affected_id": affected_user_id,
                    "unaffected_id": unaffected_user_id,
                },
            )
        await asyncio.to_thread(command.upgrade, alembic_config, "head")
        await engine.dispose()


@pytest.mark.asyncio
async def test_collection_migration_allows_identical_names_for_different_users(
    postgres_database_url: str,
    migrated_database: None,
) -> None:
    del migrated_database
    alembic_config = _alembic_config()
    engine = create_async_engine(postgres_database_url, pool_pre_ping=True)
    user_ids = [uuid.uuid4(), uuid.uuid4()]
    collection_ids = [uuid.uuid4(), uuid.uuid4()]

    try:
        await asyncio.to_thread(command.downgrade, alembic_config, "0006_content_ownership")
        async with engine.begin() as connection:
            for position, user_id in enumerate(user_ids):
                await _insert_user(
                    connection,
                    user_id,
                    f"same-name-{position}-{user_id}@example.com",
                )
                await _insert_collection(
                    connection,
                    collection_id=collection_ids[position],
                    user_id=user_id,
                    name="Shared Name",
                )

        await asyncio.to_thread(command.upgrade, alembic_config, "head")

        async with engine.connect() as connection:
            preserved_ids = set(
                (
                    await connection.execute(
                        text(
                            """
                            SELECT id
                            FROM collections
                            WHERE id IN (:first_id, :second_id)
                            """
                        ),
                        {
                            "first_id": collection_ids[0],
                            "second_id": collection_ids[1],
                        },
                    )
                ).scalars()
            )
            schema = await _collection_schema(connection)

        assert preserved_ids == set(collection_ids)
        _assert_case_insensitive_index(schema)
    finally:
        async with engine.begin() as connection:
            await connection.execute(
                text("DELETE FROM users WHERE id IN (:first_id, :second_id)"),
                {"first_id": user_ids[0], "second_id": user_ids[1]},
            )
        await asyncio.to_thread(command.upgrade, alembic_config, "head")
        await engine.dispose()
