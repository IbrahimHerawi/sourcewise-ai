from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import pytest
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import inspect
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.settings import get_settings

ALEMBIC_INI_PATH = Path(__file__).resolve().parents[1] / "alembic.ini"
PREVIOUS_REVISION = "0011_owner_scoped_indexes"
REFRESH_REVISION = "0012_refresh_tokens"


def _alembic_config() -> Config:
    config = Config(str(ALEMBIC_INI_PATH))
    config.set_main_option("sqlalchemy.url", get_settings().get_database_url())
    return config


async def _table_names(database_url: str) -> set[str]:
    engine = create_async_engine(database_url)
    try:
        async with engine.connect() as connection:
            return await connection.run_sync(
                lambda sync_connection: set(inspect(sync_connection).get_table_names())
            )
    finally:
        await engine.dispose()


async def _refresh_schema(database_url: str) -> dict[str, Any]:
    engine = create_async_engine(database_url)
    try:
        async with engine.connect() as connection:

            def inspect_schema(sync_connection: Any) -> dict[str, Any]:
                inspector = inspect(sync_connection)
                return {
                    "columns": {
                        column["name"]: column
                        for column in inspector.get_columns("refresh_tokens")
                    },
                    "indexes": {
                        index["name"]: index
                        for index in inspector.get_indexes("refresh_tokens")
                    },
                    "foreign_keys": inspector.get_foreign_keys("refresh_tokens"),
                }

            return await connection.run_sync(inspect_schema)
    finally:
        await engine.dispose()


def test_refresh_token_revision_is_the_single_alembic_head() -> None:
    script = ScriptDirectory.from_config(_alembic_config())

    assert script.get_heads() == [REFRESH_REVISION]
    assert script.get_revision(REFRESH_REVISION).down_revision == PREVIOUS_REVISION


@pytest.mark.asyncio
async def test_refresh_token_migration_schema_and_downgrade(
    postgres_database_url: str,
    migrated_database: None,
) -> None:
    config = _alembic_config()
    upgraded_schema = await _refresh_schema(postgres_database_url)

    assert set(upgraded_schema["columns"]) == {
        "id",
        "user_id",
        "family_id",
        "token_hash",
        "expires_at",
        "used_at",
        "revoked_at",
        "replaced_by_id",
        "created_at",
    }
    assert upgraded_schema["columns"]["used_at"]["nullable"] is True
    assert upgraded_schema["columns"]["revoked_at"]["nullable"] is True
    assert upgraded_schema["columns"]["replaced_by_id"]["nullable"] is True
    assert upgraded_schema["columns"]["created_at"]["default"] is not None
    assert set(upgraded_schema["indexes"]) == {
        "ix_refresh_tokens_expires_at",
        "ix_refresh_tokens_family_id",
        "ix_refresh_tokens_token_hash",
        "ix_refresh_tokens_user_id",
    }
    assert upgraded_schema["indexes"]["ix_refresh_tokens_token_hash"]["unique"] is True

    try:
        await asyncio.to_thread(command.downgrade, config, PREVIOUS_REVISION)
        downgraded_tables = await _table_names(postgres_database_url)
        assert "refresh_tokens" not in downgraded_tables
        assert "users" in downgraded_tables
        assert "email_verification_tokens" in downgraded_tables
        assert "password_reset_tokens" in downgraded_tables
    finally:
        await asyncio.to_thread(command.upgrade, config, "head")

    assert "refresh_tokens" in await _table_names(postgres_database_url)
