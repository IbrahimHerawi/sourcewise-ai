from __future__ import annotations

import asyncio
import uuid
from pathlib import Path
from typing import Any

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import AsyncConnection, create_async_engine

from app.db.models.documents import Document

ALEMBIC_INI_PATH = Path(__file__).resolve().parents[1] / "alembic.ini"
PREVIOUS_REVISION = "0007_collection_name_ci"


def _alembic_config() -> Config:
    return Config(str(ALEMBIC_INI_PATH))


async def _extracted_text_is_nullable(connection: AsyncConnection) -> bool:
    def inspect_column(sync_connection: Any) -> bool:
        columns = inspect(sync_connection).get_columns("documents")
        extracted_text = next(
            column for column in columns if column["name"] == "extracted_text"
        )
        return bool(extracted_text["nullable"])

    return await connection.run_sync(inspect_column)


async def _insert_user(
    connection: AsyncConnection,
    *,
    user_id: uuid.UUID,
    email: str,
) -> None:
    await connection.execute(
        text(
            """
            INSERT INTO users (id, email, password_hash, first_name, last_name)
            VALUES (:id, :email, 'test-password-hash', 'Document', 'Migration')
            """
        ),
        {"id": user_id, "email": email},
    )


async def _insert_document(
    connection: AsyncConnection,
    *,
    document_id: uuid.UUID,
    user_id: uuid.UUID,
    extracted_text: str | None,
) -> None:
    await connection.execute(
        text(
            """
            INSERT INTO documents (
                id,
                user_id,
                filename,
                original_extension,
                content_type,
                size_bytes,
                storage_path,
                extracted_text
            )
            VALUES (
                :id,
                :user_id,
                'migration.txt',
                '.txt',
                'text/plain',
                42,
                '/tmp/migration.txt',
                :extracted_text
            )
            """
        ),
        {
            "id": document_id,
            "user_id": user_id,
            "extracted_text": extracted_text,
        },
    )


def test_document_model_maps_extracted_text_as_nullable() -> None:
    assert Document.__table__.c.extracted_text.nullable is True
    assert Document.__annotations__["extracted_text"] == "Mapped[str | None]"


@pytest.mark.asyncio
async def test_document_extracted_text_migration_upgrades_and_preserves_text(
    postgres_database_url: str,
    migrated_database: None,
) -> None:
    del migrated_database
    alembic_config = _alembic_config()
    engine = create_async_engine(postgres_database_url, pool_pre_ping=True)
    user_id = uuid.uuid4()
    document_id = uuid.uuid4()
    preserved_text = "Text that must survive the nullable migration."

    try:
        await asyncio.to_thread(command.downgrade, alembic_config, PREVIOUS_REVISION)
        async with engine.begin() as connection:
            assert await _extracted_text_is_nullable(connection) is False
            await _insert_user(
                connection,
                user_id=user_id,
                email=f"document-migration-{user_id}@example.com",
            )
            await _insert_document(
                connection,
                document_id=document_id,
                user_id=user_id,
                extracted_text=preserved_text,
            )

        await asyncio.to_thread(command.upgrade, alembic_config, "head")

        async with engine.connect() as connection:
            assert await _extracted_text_is_nullable(connection) is True
            migrated_text = await connection.scalar(
                text("SELECT extracted_text FROM documents WHERE id = :id"),
                {"id": document_id},
            )

        assert migrated_text == preserved_text
    finally:
        await asyncio.to_thread(command.upgrade, alembic_config, "head")
        async with engine.begin() as connection:
            await connection.execute(
                text("DELETE FROM users WHERE id = :id"),
                {"id": user_id},
            )
        await engine.dispose()


@pytest.mark.asyncio
async def test_document_extracted_text_migration_rejects_nulls_on_downgrade(
    postgres_database_url: str,
    migrated_database: None,
) -> None:
    del migrated_database
    alembic_config = _alembic_config()
    engine = create_async_engine(postgres_database_url, pool_pre_ping=True)
    user_id = uuid.uuid4()
    document_id = uuid.uuid4()

    try:
        async with engine.begin() as connection:
            await _insert_user(
                connection,
                user_id=user_id,
                email=f"guarded-downgrade-{user_id}@example.com",
            )
            await _insert_document(
                connection,
                document_id=document_id,
                user_id=user_id,
                extracted_text=None,
            )

        with pytest.raises(RuntimeError) as error:
            await asyncio.to_thread(command.downgrade, alembic_config, PREVIOUS_REVISION)

        message = str(error.value)
        assert "documents.extracted_text" in message
        assert "1 document row(s)" in message
        assert "Extract or restore text" in message
        assert "rerun the downgrade" in message

        async with engine.connect() as connection:
            assert await _extracted_text_is_nullable(connection) is True
            preserved_null_count = await connection.scalar(
                text(
                    """
                    SELECT count(*)
                    FROM documents
                    WHERE id = :id AND extracted_text IS NULL
                    """
                ),
                {"id": document_id},
            )

        assert preserved_null_count == 1
    finally:
        async with engine.begin() as connection:
            await connection.execute(
                text("DELETE FROM users WHERE id = :id"),
                {"id": user_id},
            )
        await asyncio.to_thread(command.upgrade, alembic_config, "head")
        await engine.dispose()
