from __future__ import annotations

import asyncio
import uuid
from pathlib import Path
from typing import Any

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.core.security import verify_password
from app.core.settings import get_settings
from app.db.models import Collection, Document, Question, User

ALEMBIC_INI_PATH = Path(__file__).resolve().parents[1] / "alembic.ini"


def _zero_embedding() -> list[float]:
    return [0.0] * get_settings().embedding_dim


@pytest.mark.asyncio
async def test_documents_and_questions_belong_to_user_and_optional_collection(
    db_session: AsyncSession,
) -> None:
    user = User(
        email="content-owner@example.com",
        password_hash="hashed-password",
        first_name="Content",
        last_name="Owner",
    )
    collection = Collection(name="Research")
    document = Document(
        filename="owned.txt",
        original_extension=".txt",
        content_type="text/plain",
        size_bytes=12,
        storage_path="/tmp/owned.txt",
        extracted_text="Owned text",
    )
    question = Question(
        question_text="Who owns this?",
        question_embedding=_zero_embedding(),
        answer_text="The content owner.",
        ai_provider="ollama",
        model_used="test-model",
    )

    user.collections.append(collection)
    user.documents.append(document)
    user.questions.append(question)
    collection.documents.append(document)
    collection.questions.append(question)

    db_session.add(user)
    await db_session.flush()

    assert document.user_id == user.id
    assert document.collection_id == collection.id
    assert document.user is user
    assert document.collection is collection
    assert question.user_id == user.id
    assert question.collection_id == collection.id
    assert question.user is user
    assert question.collection is collection


@pytest.mark.asyncio
async def test_content_ownership_schema_has_nullability_indexes_and_delete_actions(
    db_session: AsyncSession,
) -> None:
    async_connection = await db_session.connection()

    def inspect_schema(connection: Any) -> dict[str, Any]:
        inspector = inspect(connection)
        return {
            table_name: {
                "columns": {
                    column["name"]: column for column in inspector.get_columns(table_name)
                },
                "indexes": {
                    index["name"]: index for index in inspector.get_indexes(table_name)
                },
                "foreign_keys": inspector.get_foreign_keys(table_name),
            }
            for table_name in ("documents", "questions")
        }

    schema = await async_connection.run_sync(inspect_schema)

    for table_name in ("documents", "questions"):
        table_schema = schema[table_name]
        assert table_schema["columns"]["user_id"]["nullable"] is False
        assert table_schema["columns"]["collection_id"]["nullable"] is True
        assert f"ix_{table_name}_user_created_desc" in table_schema["indexes"]
        assert f"ix_{table_name}_user_id" not in table_schema["indexes"]
        assert f"ix_{table_name}_collection_id" in table_schema["indexes"]

        foreign_keys = {
            foreign_key["referred_table"]: foreign_key
            for foreign_key in table_schema["foreign_keys"]
        }
        assert foreign_keys["users"]["options"]["ondelete"] == "CASCADE"
        assert foreign_keys["collections"]["options"]["ondelete"] == "SET NULL"


@pytest.mark.asyncio
async def test_ownership_migration_preserves_and_backfills_existing_content(
    postgres_database_url: str,
    migrated_database: None,
) -> None:
    del migrated_database
    alembic_config = Config(str(ALEMBIC_INI_PATH))
    engine = create_async_engine(postgres_database_url, pool_pre_ping=True)
    document_id = uuid.uuid4()
    question_id = uuid.uuid4()
    colliding_user_id = uuid.uuid4()

    try:
        await asyncio.to_thread(command.downgrade, alembic_config, "0005_add_collections")
        async with engine.begin() as connection:
            await connection.execute(
                text(
                    """
                    INSERT INTO users (
                        id,
                        email,
                        password_hash,
                        first_name,
                        last_name,
                        is_email_verified,
                        is_active
                    )
                    VALUES (
                        :id,
                        'legacy@sourcewise.local',
                        'preexisting-password-hash',
                        'Existing',
                        'User',
                        FALSE,
                        FALSE
                    )
                    """
                ),
                {"id": colliding_user_id},
            )
            await connection.execute(
                text(
                    """
                    INSERT INTO documents (
                        id,
                        filename,
                        original_extension,
                        content_type,
                        size_bytes,
                        storage_path,
                        extracted_text,
                        status
                    )
                    VALUES (
                        :id,
                        'legacy.txt',
                        '.txt',
                        'text/plain',
                        11,
                        '/tmp/legacy.txt',
                        'Legacy text',
                        'READY'
                    )
                    """
                ),
                {"id": document_id},
            )
            await connection.execute(
                text(
                    """
                    INSERT INTO questions (
                        id,
                        question_text,
                        question_embedding,
                        answer_text,
                        ai_provider,
                        model_used
                    )
                    VALUES (
                        :id,
                        'Legacy question?',
                        CAST(:embedding AS vector),
                        'Legacy answer.',
                        'ollama',
                        'legacy-model'
                    )
                    """
                ),
                {
                    "id": question_id,
                    "embedding": "[" + ",".join("0" for _ in _zero_embedding()) + "]",
                },
            )

        await asyncio.to_thread(command.upgrade, alembic_config, "head")

        async with engine.connect() as connection:
            document_owner = (
                await connection.execute(
                    text(
                        """
                        SELECT user_id, collection_id
                        FROM documents
                        WHERE id = :id
                        """
                    ),
                    {"id": document_id},
                )
            ).one()
            question_owner = (
                await connection.execute(
                    text(
                        """
                        SELECT user_id, collection_id
                        FROM questions
                        WHERE id = :id
                        """
                    ),
                    {"id": question_id},
                )
            ).one()
            legacy_user = (
                await connection.execute(
                    text(
                        """
                        SELECT id, email, password_hash, is_email_verified, is_active
                        FROM users
                        WHERE id = :id
                        """
                    ),
                    {"id": document_owner.user_id},
                )
            ).one()

        assert document_owner.user_id == question_owner.user_id
        assert document_owner.collection_id is None
        assert question_owner.collection_id is None
        assert legacy_user.id != colliding_user_id
        assert legacy_user.email == "legacy-content@sourcewise.local"
        assert verify_password("any-password", legacy_user.password_hash) is False
        assert legacy_user.is_email_verified is False
        assert legacy_user.is_active is False

        await asyncio.to_thread(command.downgrade, alembic_config, "0005_add_collections")
        async with engine.connect() as connection:
            remaining_document = await connection.scalar(
                text("SELECT id FROM documents WHERE id = :id"),
                {"id": document_id},
            )
            remaining_question = await connection.scalar(
                text("SELECT id FROM questions WHERE id = :id"),
                {"id": question_id},
            )
            remaining_colliding_user = await connection.scalar(
                text("SELECT id FROM users WHERE id = :id"),
                {"id": colliding_user_id},
            )
            removed_legacy_user = await connection.scalar(
                text("SELECT id FROM users WHERE id = :id"),
                {"id": legacy_user.id},
            )

        assert remaining_document == document_id
        assert remaining_question == question_id
        assert remaining_colliding_user == colliding_user_id
        assert removed_legacy_user is None

        await asyncio.to_thread(command.upgrade, alembic_config, "head")
        async with engine.connect() as connection:
            reupgraded_document_owner = await connection.scalar(
                text("SELECT user_id FROM documents WHERE id = :id"),
                {"id": document_id},
            )
            reupgraded_question_owner = await connection.scalar(
                text("SELECT user_id FROM questions WHERE id = :id"),
                {"id": question_id},
            )

        assert reupgraded_document_owner == reupgraded_question_owner
        assert reupgraded_document_owner != colliding_user_id
    finally:
        await asyncio.to_thread(command.upgrade, alembic_config, "head")
        async with engine.begin() as connection:
            await connection.execute(
                text("DELETE FROM documents WHERE id = :id"),
                {"id": document_id},
            )
            await connection.execute(
                text("DELETE FROM questions WHERE id = :id"),
                {"id": question_id},
            )
            await connection.execute(
                text(
                    """
                    DELETE FROM users
                    WHERE email IN (
                        'legacy@sourcewise.local',
                        'legacy-content@sourcewise.local'
                    )
                      AND NOT EXISTS (
                          SELECT 1 FROM documents WHERE documents.user_id = users.id
                      )
                      AND NOT EXISTS (
                          SELECT 1 FROM questions WHERE questions.user_id = users.id
                      )
                    """
                )
            )
        await engine.dispose()
