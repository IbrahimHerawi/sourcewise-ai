from __future__ import annotations

import asyncio
import io
from pathlib import Path
from typing import Any

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import inspect, text
from sqlalchemy.dialects import postgresql
from sqlalchemy.ext.asyncio import AsyncConnection, create_async_engine
from sqlalchemy.schema import CreateIndex

from app.core.settings import get_settings
from app.db.models import Collection, Document, DocumentChunk, Question

ALEMBIC_INI_PATH = Path(__file__).resolve().parents[1] / "alembic.ini"
PREVIOUS_REVISION = "0010_nullable_question_llm"
CURRENT_REVISION = "0011_owner_scoped_indexes"

EXPECTED_INDEXES = {
    "documents": {
        "ix_documents_collection_id": ("collection_id",),
        "ix_documents_user_created_desc": ("user_id", "created_at", "id"),
        "ix_documents_user_collection_created_desc": (
            "user_id",
            "collection_id",
            "created_at",
            "id",
        ),
        "ix_documents_user_status_collection": (
            "user_id",
            "status",
            "collection_id",
        ),
    },
    "questions": {
        "ix_questions_collection_id": ("collection_id",),
        "ix_questions_user_created_desc": ("user_id", "created_at", "id"),
        "ix_questions_user_collection_created_desc": (
            "user_id",
            "collection_id",
            "created_at",
            "id",
        ),
    },
    "collections": {
        "ix_collections_user_created_desc": ("user_id", "created_at", "id"),
        "uq_collections_user_lower_name": ("user_id", None),
    },
}

DESC_INDEXES = {
    "ix_documents_user_created_desc",
    "ix_documents_user_collection_created_desc",
    "ix_questions_user_created_desc",
    "ix_questions_user_collection_created_desc",
    "ix_collections_user_created_desc",
}
NEW_INDEXES = DESC_INDEXES | {"ix_documents_user_status_collection"}

REMOVED_INDEXES = {
    "documents": {
        "ix_documents_user_id": ("user_id",),
        "ix_documents_created_at": ("created_at",),
    },
    "questions": {
        "ix_questions_user_id": ("user_id",),
        "ix_questions_created_at": ("created_at",),
    },
    "collections": {"ix_collections_user_id": ("user_id",)},
}


def _alembic_config(*, output_buffer: io.StringIO | None = None) -> Config:
    return Config(str(ALEMBIC_INI_PATH), output_buffer=output_buffer)


async def _schema(connection: AsyncConnection) -> dict[str, Any]:
    def inspect_schema(sync_connection: Any) -> dict[str, Any]:
        inspector = inspect(sync_connection)
        return {
            "indexes": {
                table_name: {
                    index["name"]: index
                    for index in inspector.get_indexes(table_name)
                }
                for table_name in EXPECTED_INDEXES
            },
            "document_chunk_columns": {
                column["name"]
                for column in inspector.get_columns("document_chunks")
            },
            "document_chunk_indexes": {
                index["name"]: index
                for index in inspector.get_indexes("document_chunks")
            },
            "document_chunk_uniques": {
                constraint["name"]: constraint
                for constraint in inspector.get_unique_constraints("document_chunks")
            },
            "question_context_primary_key": inspector.get_pk_constraint(
                "question_context_chunks"
            ),
        }

    schema = await connection.run_sync(inspect_schema)
    vector_definition = await connection.scalar(
        text(
            """
            SELECT indexdef
            FROM pg_indexes
            WHERE schemaname = current_schema()
              AND tablename = 'document_chunks'
              AND indexname = 'ix_document_chunks_embedding_cosine'
            """
        )
    )
    schema["vector_index_definition"] = vector_definition
    return schema


def _assert_final_schema(schema: dict[str, Any]) -> None:
    for table_name, expected_indexes in EXPECTED_INDEXES.items():
        actual_indexes = schema["indexes"][table_name]
        assert set(actual_indexes) == set(expected_indexes)
        for index_name, expected_columns in expected_indexes.items():
            assert tuple(actual_indexes[index_name]["column_names"]) == expected_columns

    for table_indexes in REMOVED_INDEXES.values():
        assert table_indexes.keys().isdisjoint(
            index_name
            for indexes in schema["indexes"].values()
            for index_name in indexes
        )

    for index_name in DESC_INDEXES:
        table_name = next(
            table
            for table, indexes in EXPECTED_INDEXES.items()
            if index_name in indexes
        )
        column_sorting = schema["indexes"][table_name][index_name]["column_sorting"]
        assert column_sorting["created_at"] == ("desc",)
        assert column_sorting["id"] == ("desc",)

    collection_name_index = schema["indexes"]["collections"][
        "uq_collections_user_lower_name"
    ]
    assert collection_name_index["unique"] is True
    assert "lower" in collection_name_index["expressions"][1].lower()
    assert "name" in collection_name_index["expressions"][1].lower()

    assert "user_id" not in schema["document_chunk_columns"]
    assert "ix_document_chunks_embedding_cosine" in schema["document_chunk_indexes"]
    vector_definition = schema["vector_index_definition"].lower()
    assert "embedding vector_cosine_ops" in vector_definition
    assert "using hnsw" in vector_definition or "using ivfflat" in vector_definition
    assert (
        schema["document_chunk_uniques"][
            "uq_document_chunks_document_id_chunk_index"
        ]["column_names"]
        == ["document_id", "chunk_index"]
    )
    assert schema["question_context_primary_key"]["name"] == "pk_question_context_chunks"
    assert schema["question_context_primary_key"]["constrained_columns"] == [
        "question_id",
        "rank",
    ]


def _compiled_model_indexes(model: type[Any]) -> dict[str, str]:
    dialect = postgresql.dialect()
    return {
        index.name: str(CreateIndex(index).compile(dialect=dialect))
        for index in model.__table__.indexes
    }


def test_model_metadata_declares_only_final_owner_scoped_indexes() -> None:
    expected_sql = {
        "ix_documents_user_created_desc": (
            "CREATE INDEX ix_documents_user_created_desc ON documents "
            "(user_id, created_at DESC, id DESC)"
        ),
        "ix_documents_user_collection_created_desc": (
            "CREATE INDEX ix_documents_user_collection_created_desc ON documents "
            "(user_id, collection_id, created_at DESC, id DESC)"
        ),
        "ix_documents_user_status_collection": (
            "CREATE INDEX ix_documents_user_status_collection ON documents "
            "(user_id, status, collection_id)"
        ),
        "ix_questions_user_created_desc": (
            "CREATE INDEX ix_questions_user_created_desc ON questions "
            "(user_id, created_at DESC, id DESC)"
        ),
        "ix_questions_user_collection_created_desc": (
            "CREATE INDEX ix_questions_user_collection_created_desc ON questions "
            "(user_id, collection_id, created_at DESC, id DESC)"
        ),
        "ix_collections_user_created_desc": (
            "CREATE INDEX ix_collections_user_created_desc ON collections "
            "(user_id, created_at DESC, id DESC)"
        ),
    }
    model_indexes = {
        **_compiled_model_indexes(Document),
        **_compiled_model_indexes(Question),
        **_compiled_model_indexes(Collection),
    }

    for index_name, create_sql in expected_sql.items():
        assert model_indexes[index_name] == create_sql
    assert {
        index_name
        for table_indexes in REMOVED_INDEXES.values()
        for index_name in table_indexes
    }.isdisjoint(model_indexes)
    assert "ix_documents_collection_id" in model_indexes
    assert "ix_questions_collection_id" in model_indexes
    assert "uq_collections_user_lower_name" in model_indexes
    assert "user_id" not in DocumentChunk.__table__.columns


def test_offline_sql_has_exact_upgrade_and_downgrade(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("POSTGRES_PASSWORD", "offline-test-password")
    get_settings.cache_clear()
    try:
        upgrade_output = io.StringIO()
        command.upgrade(
            _alembic_config(output_buffer=upgrade_output),
            f"{PREVIOUS_REVISION}:{CURRENT_REVISION}",
            sql=True,
        )
        upgrade_sql = upgrade_output.getvalue()

        downgrade_output = io.StringIO()
        command.downgrade(
            _alembic_config(output_buffer=downgrade_output),
            f"{CURRENT_REVISION}:{PREVIOUS_REVISION}",
            sql=True,
        )
        downgrade_sql = downgrade_output.getvalue()
    finally:
        get_settings.cache_clear()

    for index_name in DESC_INDEXES:
        assert f"CREATE INDEX {index_name}" in upgrade_sql
    assert "(user_id, created_at DESC, id DESC)" in upgrade_sql
    assert "(user_id, collection_id, created_at DESC, id DESC)" in upgrade_sql
    assert "(user_id, status, collection_id)" in upgrade_sql

    for table_indexes in REMOVED_INDEXES.values():
        for index_name, columns in table_indexes.items():
            assert f"DROP INDEX {index_name}" in upgrade_sql
            joined_columns = ", ".join(columns)
            assert f"CREATE INDEX {index_name}" in downgrade_sql
            assert f"({joined_columns})" in downgrade_sql
    for expected_indexes in EXPECTED_INDEXES.values():
        for index_name in expected_indexes:
            if index_name.startswith("ix_") and index_name not in {
                "ix_documents_collection_id",
                "ix_questions_collection_id",
            }:
                assert f"DROP INDEX {index_name}" in downgrade_sql


@pytest.mark.asyncio
async def test_migration_upgrade_and_downgrade_preserve_required_indexes(
    postgres_database_url: str,
    migrated_database: None,
) -> None:
    del migrated_database
    config = _alembic_config()
    engine = create_async_engine(postgres_database_url, pool_pre_ping=True)

    try:
        async with engine.connect() as connection:
            upgraded_schema = await _schema(connection)
        _assert_final_schema(upgraded_schema)

        await asyncio.to_thread(command.downgrade, config, PREVIOUS_REVISION)
        async with engine.connect() as connection:
            downgraded_schema = await _schema(connection)

        for table_name, removed_indexes in REMOVED_INDEXES.items():
            table_indexes = downgraded_schema["indexes"][table_name]
            for index_name, expected_columns in removed_indexes.items():
                assert tuple(table_indexes[index_name]["column_names"]) == expected_columns
            assert NEW_INDEXES.isdisjoint(table_indexes)

        assert "ix_documents_collection_id" in downgraded_schema["indexes"]["documents"]
        assert "ix_questions_collection_id" in downgraded_schema["indexes"]["questions"]
        assert (
            "uq_collections_user_lower_name"
            in downgraded_schema["indexes"]["collections"]
        )
        assert (
            "ix_document_chunks_embedding_cosine"
            in downgraded_schema["document_chunk_indexes"]
        )
        assert downgraded_schema["question_context_primary_key"] == upgraded_schema[
            "question_context_primary_key"
        ]

        await asyncio.to_thread(command.upgrade, config, "head")
        async with engine.connect() as connection:
            reupgraded_schema = await _schema(connection)
        _assert_final_schema(reupgraded_schema)
    finally:
        await asyncio.to_thread(command.upgrade, config, "head")
        await engine.dispose()
