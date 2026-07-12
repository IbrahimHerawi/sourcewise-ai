from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import inspect
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Collection, User


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
async def test_collection_migration_creates_constraints_and_user_index(
    db_session: AsyncSession,
) -> None:
    async_connection = await db_session.connection()

    def inspect_schema(connection: Any) -> dict[str, Any]:
        inspector = inspect(connection)
        return {
            "tables": set(inspector.get_table_names()),
            "indexes": {index["name"]: index for index in inspector.get_indexes("collections")},
            "foreign_keys": inspector.get_foreign_keys("collections"),
            "unique_constraints": inspector.get_unique_constraints("collections"),
        }

    schema = await async_connection.run_sync(inspect_schema)

    assert "collections" in schema["tables"]
    assert "ix_collections_user_id" in schema["indexes"]
    assert any(
        constraint["name"] == "uq_collections_user_id"
        and constraint["column_names"] == ["user_id", "name"]
        for constraint in schema["unique_constraints"]
    )

    user_foreign_keys = [
        foreign_key
        for foreign_key in schema["foreign_keys"]
        if foreign_key["referred_table"] == "users"
    ]
    assert len(user_foreign_keys) == 1
    assert user_foreign_keys[0]["options"]["ondelete"] == "CASCADE"


def test_collection_migration_downgrades_and_reupgrades(migrated_database: None) -> None:
    alembic_config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))

    try:
        command.downgrade(alembic_config, "0004_user_auth_tables")
    finally:
        command.upgrade(alembic_config, "head")
