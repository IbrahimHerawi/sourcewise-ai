from __future__ import annotations

import asyncio
import uuid
from pathlib import Path
from typing import Any

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import inspect, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncSession, create_async_engine
from sqlalchemy.orm import selectinload

from app.core.settings import get_settings
from app.db.models import DocumentChunk, Question, QuestionContextChunk, User

ALEMBIC_INI_PATH = Path(__file__).resolve().parents[1] / "alembic.ini"
PREVIOUS_REVISION = "0008_nullable_document_text"
CHUNK_FOREIGN_KEY_NAME = "fk_question_context_chunks_chunk_id_document_chunks"


def _alembic_config() -> Config:
    return Config(str(ALEMBIC_INI_PATH))


def _zero_vector() -> str:
    return "[" + ",".join("0" for _ in range(get_settings().embedding_dim)) + "]"


async def _insert_user(
    connection: AsyncConnection,
    *,
    user_id: uuid.UUID,
) -> None:
    await connection.execute(
        text(
            """
            INSERT INTO users (id, email, password_hash, first_name, last_name)
            VALUES (:id, :email, 'test-password-hash', 'Citation', 'Snapshot')
            """
        ),
        {"id": user_id, "email": f"citation-{user_id}@example.com"},
    )


async def _insert_document(
    connection: AsyncConnection,
    *,
    document_id: uuid.UUID,
    user_id: uuid.UUID,
    filename: str,
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
                :filename,
                '.txt',
                'text/plain',
                42,
                :storage_path,
                'Extracted source text.'
            )
            """
        ),
        {
            "id": document_id,
            "user_id": user_id,
            "filename": filename,
            "storage_path": f"/tmp/{filename}",
        },
    )


async def _insert_chunk(
    connection: AsyncConnection,
    *,
    chunk_id: uuid.UUID,
    document_id: uuid.UUID,
    chunk_index: int,
    content: str,
) -> None:
    await connection.execute(
        text(
            """
            INSERT INTO document_chunks (
                id,
                document_id,
                chunk_index,
                content,
                embedding
            )
            VALUES (
                :id,
                :document_id,
                :chunk_index,
                :content,
                CAST(:embedding AS vector)
            )
            """
        ),
        {
            "id": chunk_id,
            "document_id": document_id,
            "chunk_index": chunk_index,
            "content": content,
            "embedding": _zero_vector(),
        },
    )


async def _insert_question(
    connection: AsyncConnection,
    *,
    question_id: uuid.UUID,
    user_id: uuid.UUID,
) -> None:
    await connection.execute(
        text(
            """
            INSERT INTO questions (
                id,
                user_id,
                question_text,
                question_embedding,
                answer_text,
                ai_provider,
                model_used
            )
            VALUES (
                :id,
                :user_id,
                'What supports this answer?',
                CAST(:embedding AS vector),
                'The durable citation does.',
                'ollama',
                'citation-test-model'
            )
            """
        ),
        {"id": question_id, "user_id": user_id, "embedding": _zero_vector()},
    )


async def _insert_snapshot(
    connection: AsyncConnection,
    *,
    question_id: uuid.UUID,
    rank: int,
    document_id: uuid.UUID,
    document_filename: str,
    chunk_id: uuid.UUID,
    chunk_index: int,
    chunk_content: str,
    similarity_score: float,
) -> None:
    await connection.execute(
        text(
            """
            INSERT INTO question_context_chunks (
                question_id,
                rank,
                document_id,
                document_filename,
                chunk_id,
                chunk_index,
                chunk_content,
                similarity_score
            )
            VALUES (
                :question_id,
                :rank,
                :document_id,
                :document_filename,
                :chunk_id,
                :chunk_index,
                :chunk_content,
                :similarity_score
            )
            """
        ),
        {
            "question_id": question_id,
            "rank": rank,
            "document_id": document_id,
            "document_filename": document_filename,
            "chunk_id": chunk_id,
            "chunk_index": chunk_index,
            "chunk_content": chunk_content,
            "similarity_score": similarity_score,
        },
    )


async def _citation_schema(connection: AsyncConnection) -> dict[str, Any]:
    def inspect_schema(sync_connection: Any) -> dict[str, Any]:
        inspector = inspect(sync_connection)
        return {
            "columns": {
                column["name"]: column
                for column in inspector.get_columns("question_context_chunks")
            },
            "primary_key": inspector.get_pk_constraint("question_context_chunks"),
            "foreign_keys": inspector.get_foreign_keys("question_context_chunks"),
            "checks": inspector.get_check_constraints("question_context_chunks"),
            "indexes": inspector.get_indexes("question_context_chunks"),
        }

    return await connection.run_sync(inspect_schema)


def test_citation_model_uses_snapshot_fields_and_no_live_chunk_relationship() -> None:
    citation_mapper = inspect(QuestionContextChunk)
    chunk_mapper = inspect(DocumentChunk)
    question_mapper = inspect(Question)

    assert list(QuestionContextChunk.__table__.primary_key.columns.keys()) == [
        "question_id",
        "rank",
    ]
    assert set(QuestionContextChunk.__table__.columns.keys()) == {
        "question_id",
        "rank",
        "document_id",
        "document_filename",
        "chunk_id",
        "chunk_index",
        "chunk_content",
        "similarity_score",
    }
    assert set(citation_mapper.relationships.keys()) == {"question"}
    assert "question_links" not in chunk_mapper.relationships

    relationship = question_mapper.relationships["context_chunks"]
    assert relationship.cascade.delete_orphan is True
    assert [column.key for column in relationship.order_by] == ["rank"]


@pytest.mark.asyncio
async def test_citation_schema_has_only_question_foreign_key_and_required_constraints(
    db_session: AsyncSession,
) -> None:
    connection = await db_session.connection()
    schema = await _citation_schema(connection)

    assert list(schema["columns"]) == [
        "question_id",
        "chunk_id",
        "similarity_score",
        "rank",
        "document_id",
        "document_filename",
        "chunk_index",
        "chunk_content",
    ]
    assert all(column["nullable"] is False for column in schema["columns"].values())
    assert schema["primary_key"]["constrained_columns"] == ["question_id", "rank"]
    assert len(schema["foreign_keys"]) == 1
    assert schema["foreign_keys"][0]["referred_table"] == "questions"
    assert schema["foreign_keys"][0]["constrained_columns"] == ["question_id"]
    assert schema["foreign_keys"][0]["options"]["ondelete"] == "CASCADE"
    assert any("rank > 0" in check["sqltext"] for check in schema["checks"])
    assert schema["indexes"] == []


@pytest.mark.asyncio
async def test_upgrade_backfills_and_preserves_every_citation_field(
    postgres_database_url: str,
    migrated_database: None,
) -> None:
    del migrated_database
    config = _alembic_config()
    engine = create_async_engine(postgres_database_url, pool_pre_ping=True)
    user_id = uuid.uuid4()
    document_id = uuid.uuid4()
    chunk_id = uuid.uuid4()
    question_id = uuid.uuid4()
    filename = "preserved-source.txt"
    content = "The exact chunk content that must remain durable."

    try:
        await asyncio.to_thread(command.downgrade, config, PREVIOUS_REVISION)
        async with engine.begin() as connection:
            await _insert_user(connection, user_id=user_id)
            await _insert_document(
                connection,
                document_id=document_id,
                user_id=user_id,
                filename=filename,
            )
            await _insert_chunk(
                connection,
                chunk_id=chunk_id,
                document_id=document_id,
                chunk_index=7,
                content=content,
            )
            await _insert_question(
                connection,
                question_id=question_id,
                user_id=user_id,
            )
            await connection.execute(
                text(
                    """
                    INSERT INTO question_context_chunks (
                        question_id,
                        chunk_id,
                        similarity_score,
                        rank
                    )
                    VALUES (:question_id, :chunk_id, :similarity_score, :rank)
                    """
                ),
                {
                    "question_id": question_id,
                    "chunk_id": chunk_id,
                    "similarity_score": 0.125,
                    "rank": 3,
                },
            )

        await asyncio.to_thread(command.upgrade, config, "head")

        async with engine.connect() as connection:
            citation = (
                await connection.execute(
                    text(
                        """
                        SELECT *
                        FROM question_context_chunks
                        WHERE question_id = :question_id AND rank = 3
                        """
                    ),
                    {"question_id": question_id},
                )
            ).mappings().one()

        assert citation["question_id"] == question_id
        assert citation["rank"] == 3
        assert citation["document_id"] == document_id
        assert citation["document_filename"] == filename
        assert citation["chunk_id"] == chunk_id
        assert citation["chunk_index"] == 7
        assert citation["chunk_content"] == content
        assert citation["similarity_score"] == pytest.approx(0.125)
    finally:
        async with engine.begin() as connection:
            await connection.execute(text("DELETE FROM users WHERE id = :id"), {"id": user_id})
        await asyncio.to_thread(command.upgrade, config, "head")
        await engine.dispose()


@pytest.mark.asyncio
async def test_upgrade_aborts_without_data_loss_when_a_citation_cannot_be_backfilled(
    postgres_database_url: str,
    migrated_database: None,
) -> None:
    del migrated_database
    config = _alembic_config()
    engine = create_async_engine(postgres_database_url, pool_pre_ping=True)
    user_id = uuid.uuid4()
    document_id = uuid.uuid4()
    chunk_id = uuid.uuid4()
    question_id = uuid.uuid4()

    try:
        await asyncio.to_thread(command.downgrade, config, PREVIOUS_REVISION)
        async with engine.begin() as connection:
            await _insert_user(connection, user_id=user_id)
            await _insert_document(
                connection,
                document_id=document_id,
                user_id=user_id,
                filename="unbackfillable.txt",
            )
            await _insert_chunk(
                connection,
                chunk_id=chunk_id,
                document_id=document_id,
                chunk_index=1,
                content="This live chunk will be missing during backfill.",
            )
            await _insert_question(
                connection,
                question_id=question_id,
                user_id=user_id,
            )
            await connection.execute(
                text(
                    """
                    INSERT INTO question_context_chunks (
                        question_id,
                        chunk_id,
                        similarity_score,
                        rank
                    )
                    VALUES (:question_id, :chunk_id, 0.5, 1)
                    """
                ),
                {"question_id": question_id, "chunk_id": chunk_id},
            )
            await connection.execute(
                text(
                    """
                    ALTER TABLE question_context_chunks
                    DROP CONSTRAINT fk_question_context_chunks_chunk_id_document_chunks
                    """
                )
            )
            await connection.execute(
                text("DELETE FROM document_chunks WHERE id = :id"),
                {"id": chunk_id},
            )

        with pytest.raises(RuntimeError) as error:
            await asyncio.to_thread(command.upgrade, config, "head")

        message = str(error.value)
        assert "1 citation row(s) could not be backfilled" in message
        assert "Restore the referenced live chunk and document rows" in message
        assert "No citation history was changed" in message

        async with engine.connect() as connection:
            preserved_count = await connection.scalar(
                text(
                    """
                    SELECT count(*)
                    FROM question_context_chunks
                    WHERE question_id = :question_id AND chunk_id = :chunk_id
                    """
                ),
                {"question_id": question_id, "chunk_id": chunk_id},
            )
            schema = await _citation_schema(connection)

        assert preserved_count == 1
        assert set(schema["columns"]) == {
            "question_id",
            "chunk_id",
            "similarity_score",
            "rank",
        }
    finally:
        async with engine.begin() as connection:
            await connection.execute(text("DELETE FROM users WHERE id = :id"), {"id": user_id})
            schema = await _citation_schema(connection)
            if "document_id" not in schema["columns"] and not any(
                foreign_key["name"] == CHUNK_FOREIGN_KEY_NAME
                for foreign_key in schema["foreign_keys"]
            ):
                await connection.execute(
                    text(
                        """
                        ALTER TABLE question_context_chunks
                        ADD CONSTRAINT fk_question_context_chunks_chunk_id_document_chunks
                        FOREIGN KEY (chunk_id) REFERENCES document_chunks (id)
                        ON DELETE CASCADE
                        """
                    )
                )
        await asyncio.to_thread(command.upgrade, config, "head")
        await engine.dispose()


@pytest.mark.asyncio
async def test_rank_must_be_positive_and_unique_per_question(
    db_session: AsyncSession,
) -> None:
    user_id = uuid.uuid4()
    question_id = uuid.uuid4()
    document_id = uuid.uuid4()
    connection = await db_session.connection()
    await _insert_user(connection, user_id=user_id)
    await _insert_question(connection, question_id=question_id, user_id=user_id)
    await _insert_snapshot(
        connection,
        question_id=question_id,
        rank=1,
        document_id=document_id,
        document_filename="rank.txt",
        chunk_id=uuid.uuid4(),
        chunk_index=0,
        chunk_content="Valid rank.",
        similarity_score=0.1,
    )

    invalid_rank = await connection.begin_nested()
    with pytest.raises(IntegrityError):
        await _insert_snapshot(
            connection,
            question_id=question_id,
            rank=0,
            document_id=document_id,
            document_filename="rank.txt",
            chunk_id=uuid.uuid4(),
            chunk_index=1,
            chunk_content="Invalid rank.",
            similarity_score=0.2,
        )
    await invalid_rank.rollback()

    duplicate_rank = await connection.begin_nested()
    with pytest.raises(IntegrityError):
        await _insert_snapshot(
            connection,
            question_id=question_id,
            rank=1,
            document_id=document_id,
            document_filename="rank.txt",
            chunk_id=uuid.uuid4(),
            chunk_index=2,
            chunk_content="Duplicate rank.",
            similarity_score=0.3,
        )
    await duplicate_rank.rollback()

    citation_count = await connection.scalar(
        text("SELECT count(*) FROM question_context_chunks WHERE question_id = :id"),
        {"id": question_id},
    )
    assert citation_count == 1


@pytest.mark.asyncio
async def test_question_deletion_cascades_citation_snapshots(
    db_session: AsyncSession,
) -> None:
    user_id = uuid.uuid4()
    question_id = uuid.uuid4()
    connection = await db_session.connection()
    await _insert_user(connection, user_id=user_id)
    await _insert_question(connection, question_id=question_id, user_id=user_id)
    await _insert_snapshot(
        connection,
        question_id=question_id,
        rank=1,
        document_id=uuid.uuid4(),
        document_filename="deleted-question.txt",
        chunk_id=uuid.uuid4(),
        chunk_index=0,
        chunk_content="Citation removed only with its question.",
        similarity_score=0.4,
    )

    await connection.execute(
        text("DELETE FROM questions WHERE id = :question_id"),
        {"question_id": question_id},
    )

    citation_count = await connection.scalar(
        text("SELECT count(*) FROM question_context_chunks WHERE question_id = :id"),
        {"id": question_id},
    )
    assert citation_count == 0


@pytest.mark.asyncio
async def test_document_and_chunk_deletion_preserve_citation_snapshots(
    db_session: AsyncSession,
) -> None:
    user_id = uuid.uuid4()
    question_id = uuid.uuid4()
    document_ids = [uuid.uuid4(), uuid.uuid4()]
    chunk_ids = [uuid.uuid4(), uuid.uuid4()]
    filenames = ["chunk-deleted.txt", "document-deleted.txt"]
    contents = ["Chunk deletion must preserve me.", "Document deletion must preserve me."]
    connection = await db_session.connection()
    await _insert_user(connection, user_id=user_id)
    await _insert_question(connection, question_id=question_id, user_id=user_id)

    for position in range(2):
        await _insert_document(
            connection,
            document_id=document_ids[position],
            user_id=user_id,
            filename=filenames[position],
        )
        await _insert_chunk(
            connection,
            chunk_id=chunk_ids[position],
            document_id=document_ids[position],
            chunk_index=position + 4,
            content=contents[position],
        )
        await _insert_snapshot(
            connection,
            question_id=question_id,
            rank=position + 1,
            document_id=document_ids[position],
            document_filename=filenames[position],
            chunk_id=chunk_ids[position],
            chunk_index=position + 4,
            chunk_content=contents[position],
            similarity_score=0.1 * (position + 1),
        )

    await connection.execute(
        text("DELETE FROM document_chunks WHERE id = :id"),
        {"id": chunk_ids[0]},
    )
    await connection.execute(
        text("DELETE FROM documents WHERE id = :id"),
        {"id": document_ids[1]},
    )

    citations = (
        await connection.execute(
            text(
                """
                SELECT document_id, document_filename, chunk_id, chunk_index, chunk_content
                FROM question_context_chunks
                WHERE question_id = :question_id
                ORDER BY rank
                """
            ),
            {"question_id": question_id},
        )
    ).all()
    assert citations == [
        (document_ids[0], filenames[0], chunk_ids[0], 4, contents[0]),
        (document_ids[1], filenames[1], chunk_ids[1], 5, contents[1]),
    ]


@pytest.mark.asyncio
async def test_question_context_relationship_loads_snapshots_in_rank_order(
    db_session: AsyncSession,
) -> None:
    settings = get_settings()
    user = User(
        email=f"relationship-{uuid.uuid4()}@example.com",
        password_hash="test-password-hash",
        first_name="Citation",
        last_name="Ordering",
    )
    question = Question(
        user=user,
        question_text="Which citation comes first?",
        question_embedding=[0.0] * settings.embedding_dim,
        answer_text="Rank one.",
        ai_provider="ollama",
        model_used="citation-test-model",
        context_chunks=[
            QuestionContextChunk(
                rank=2,
                document_id=uuid.uuid4(),
                document_filename="second.txt",
                chunk_id=uuid.uuid4(),
                chunk_index=1,
                chunk_content="Second citation.",
                similarity_score=0.2,
            ),
            QuestionContextChunk(
                rank=1,
                document_id=uuid.uuid4(),
                document_filename="first.txt",
                chunk_id=uuid.uuid4(),
                chunk_index=0,
                chunk_content="First citation.",
                similarity_score=0.1,
            ),
        ],
    )
    db_session.add(question)
    await db_session.flush()
    question_id = question.id
    db_session.expunge_all()

    loaded_question = await db_session.scalar(
        select(Question)
        .where(Question.id == question_id)
        .options(selectinload(Question.context_chunks))
    )

    assert loaded_question is not None
    assert [citation.rank for citation in loaded_question.context_chunks] == [1, 2]


@pytest.mark.asyncio
async def test_downgrade_restores_live_chunk_link_when_every_chunk_exists(
    postgres_database_url: str,
    migrated_database: None,
) -> None:
    del migrated_database
    config = _alembic_config()
    engine = create_async_engine(postgres_database_url, pool_pre_ping=True)
    user_id = uuid.uuid4()
    document_id = uuid.uuid4()
    chunk_id = uuid.uuid4()
    question_id = uuid.uuid4()

    try:
        async with engine.begin() as connection:
            await _insert_user(connection, user_id=user_id)
            await _insert_document(
                connection,
                document_id=document_id,
                user_id=user_id,
                filename="downgrade.txt",
            )
            await _insert_chunk(
                connection,
                chunk_id=chunk_id,
                document_id=document_id,
                chunk_index=2,
                content="A live chunk still exists.",
            )
            await _insert_question(
                connection,
                question_id=question_id,
                user_id=user_id,
            )
            await _insert_snapshot(
                connection,
                question_id=question_id,
                rank=1,
                document_id=document_id,
                document_filename="downgrade.txt",
                chunk_id=chunk_id,
                chunk_index=2,
                chunk_content="A live chunk still exists.",
                similarity_score=0.33,
            )

        await asyncio.to_thread(command.downgrade, config, PREVIOUS_REVISION)

        async with engine.connect() as connection:
            citation = (
                await connection.execute(
                    text(
                        """
                        SELECT question_id, chunk_id, similarity_score, rank
                        FROM question_context_chunks
                        WHERE question_id = :question_id
                        """
                    ),
                    {"question_id": question_id},
                )
            ).one()
            schema = await _citation_schema(connection)

        assert citation == (question_id, chunk_id, 0.33, 1)
        assert schema["primary_key"]["constrained_columns"] == ["question_id", "chunk_id"]
        assert any(
            foreign_key["name"] == CHUNK_FOREIGN_KEY_NAME
            and foreign_key["referred_table"] == "document_chunks"
            and foreign_key["options"]["ondelete"] == "CASCADE"
            for foreign_key in schema["foreign_keys"]
        )
        assert [index["name"] for index in schema["indexes"]] == [
            "ix_question_context_chunks_chunk_id"
        ]
    finally:
        async with engine.begin() as connection:
            await connection.execute(text("DELETE FROM users WHERE id = :id"), {"id": user_id})
        await asyncio.to_thread(command.upgrade, config, "head")
        await engine.dispose()


@pytest.mark.asyncio
async def test_downgrade_aborts_without_data_loss_when_snapshot_chunk_is_missing(
    postgres_database_url: str,
    migrated_database: None,
) -> None:
    del migrated_database
    config = _alembic_config()
    engine = create_async_engine(postgres_database_url, pool_pre_ping=True)
    user_id = uuid.uuid4()
    document_id = uuid.uuid4()
    chunk_id = uuid.uuid4()
    question_id = uuid.uuid4()
    snapshot_content = "This history must survive a rejected downgrade."

    try:
        async with engine.begin() as connection:
            await _insert_user(connection, user_id=user_id)
            await _insert_document(
                connection,
                document_id=document_id,
                user_id=user_id,
                filename="missing-live-chunk.txt",
            )
            await _insert_chunk(
                connection,
                chunk_id=chunk_id,
                document_id=document_id,
                chunk_index=9,
                content=snapshot_content,
            )
            await _insert_question(
                connection,
                question_id=question_id,
                user_id=user_id,
            )
            await _insert_snapshot(
                connection,
                question_id=question_id,
                rank=1,
                document_id=document_id,
                document_filename="missing-live-chunk.txt",
                chunk_id=chunk_id,
                chunk_index=9,
                chunk_content=snapshot_content,
                similarity_score=0.27,
            )
            await connection.execute(
                text("DELETE FROM document_chunks WHERE id = :id"),
                {"id": chunk_id},
            )

        with pytest.raises(RuntimeError) as error:
            await asyncio.to_thread(command.downgrade, config, PREVIOUS_REVISION)

        message = str(error.value)
        assert str(chunk_id) in message
        assert "Restore those document_chunks rows" in message
        assert "No citation history was deleted or changed" in message

        async with engine.connect() as connection:
            citation = (
                await connection.execute(
                    text(
                        """
                        SELECT document_id, chunk_id, chunk_content
                        FROM question_context_chunks
                        WHERE question_id = :question_id AND rank = 1
                        """
                    ),
                    {"question_id": question_id},
                )
            ).one()
            schema = await _citation_schema(connection)

        assert citation == (document_id, chunk_id, snapshot_content)
        assert schema["primary_key"]["constrained_columns"] == ["question_id", "rank"]
        assert set(schema["columns"]) >= {
            "document_id",
            "document_filename",
            "chunk_index",
            "chunk_content",
        }
    finally:
        async with engine.begin() as connection:
            await connection.execute(text("DELETE FROM users WHERE id = :id"), {"id": user_id})
        await asyncio.to_thread(command.upgrade, config, "head")
        await engine.dispose()
