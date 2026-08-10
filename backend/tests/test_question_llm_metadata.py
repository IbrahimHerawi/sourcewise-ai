from __future__ import annotations

import asyncio
import uuid
from pathlib import Path
from typing import Any

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncSession, create_async_engine

from app.core.settings import get_settings
from app.db.models import Question, User

ALEMBIC_INI_PATH = Path(__file__).resolve().parents[1] / "alembic.ini"
PREVIOUS_REVISION = "0009_durable_citations"


def _alembic_config() -> Config:
    return Config(str(ALEMBIC_INI_PATH))


def _zero_embedding() -> list[float]:
    return [0.0] * get_settings().embedding_dim


def _vector_literal() -> str:
    return "[" + ",".join("0" for _ in range(get_settings().embedding_dim)) + "]"


async def _llm_metadata_nullability(connection: AsyncConnection) -> dict[str, bool]:
    def inspect_columns(sync_connection: Any) -> dict[str, bool]:
        columns = {
            column["name"]: column for column in inspect(sync_connection).get_columns("questions")
        }
        return {
            "ai_provider": bool(columns["ai_provider"]["nullable"]),
            "model_used": bool(columns["model_used"]["nullable"]),
        }

    return await connection.run_sync(inspect_columns)


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
            VALUES (:id, :email, 'test-password-hash', 'Question', 'Migration')
            """
        ),
        {"id": user_id, "email": email},
    )


async def _insert_question(
    connection: AsyncConnection,
    *,
    question_id: uuid.UUID,
    user_id: uuid.UUID,
    ai_provider: str | None,
    model_used: str | None,
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
                'What happened?',
                CAST(:embedding AS vector),
                'No usable context was found.',
                :ai_provider,
                :model_used
            )
            """
        ),
        {
            "id": question_id,
            "user_id": user_id,
            "embedding": _vector_literal(),
            "ai_provider": ai_provider,
            "model_used": model_used,
        },
    )


@pytest.mark.asyncio
async def test_question_allows_null_llm_metadata_for_fallback(
    db_session: AsyncSession,
) -> None:
    user = User(
        email="null-question-metadata@example.com",
        password_hash="hashed-password",
        first_name="Null",
        last_name="Metadata",
    )
    question = Question(
        question_text="What happened?",
        question_embedding=_zero_embedding(),
        answer_text="No usable context was found.",
        ai_provider=None,
        model_used=None,
    )
    user.questions.append(question)

    db_session.add(user)
    await db_session.flush()

    assert Question.__table__.c.ai_provider.nullable is True
    assert Question.__table__.c.model_used.nullable is True
    assert Question.__annotations__["ai_provider"] == "Mapped[str | None]"
    assert Question.__annotations__["model_used"] == "Mapped[str | None]"
    assert question.ai_provider is None
    assert question.model_used is None


@pytest.mark.asyncio
@pytest.mark.parametrize("provider", ["openai", "ollama"])
async def test_question_accepts_valid_non_null_provider(
    db_session: AsyncSession,
    provider: str,
) -> None:
    user = User(
        email=f"valid-{provider}-question-metadata@example.com",
        password_hash="hashed-password",
        first_name="Valid",
        last_name="Provider",
    )
    question = Question(
        question_text="What happened?",
        question_embedding=_zero_embedding(),
        answer_text="An LLM-generated answer.",
        ai_provider=provider,
        model_used=f"{provider}-model",
    )
    user.questions.append(question)

    db_session.add(user)
    await db_session.flush()

    assert question.ai_provider == provider
    assert question.model_used == f"{provider}-model"


@pytest.mark.asyncio
async def test_question_rejects_invalid_non_null_provider(db_session: AsyncSession) -> None:
    connection = await db_session.connection()
    user_id = uuid.uuid4()
    await _insert_user(
        connection,
        user_id=user_id,
        email=f"invalid-provider-{user_id}@example.com",
    )

    invalid_insert = await connection.begin_nested()
    with pytest.raises(IntegrityError):
        await _insert_question(
            connection,
            question_id=uuid.uuid4(),
            user_id=user_id,
            ai_provider="unsupported",
            model_used="invalid-model",
        )
    await invalid_insert.rollback()


@pytest.mark.asyncio
async def test_question_llm_metadata_upgrade_preserves_existing_values(
    postgres_database_url: str,
    migrated_database: None,
) -> None:
    del migrated_database
    alembic_config = _alembic_config()
    engine = create_async_engine(postgres_database_url, pool_pre_ping=True)
    user_id = uuid.uuid4()
    question_id = uuid.uuid4()

    try:
        await asyncio.to_thread(command.downgrade, alembic_config, PREVIOUS_REVISION)
        async with engine.begin() as connection:
            assert await _llm_metadata_nullability(connection) == {
                "ai_provider": False,
                "model_used": False,
            }
            await _insert_user(
                connection,
                user_id=user_id,
                email=f"upgrade-preservation-{user_id}@example.com",
            )
            await _insert_question(
                connection,
                question_id=question_id,
                user_id=user_id,
                ai_provider="openai",
                model_used="preserved-model",
            )

        await asyncio.to_thread(command.upgrade, alembic_config, "head")

        async with engine.connect() as connection:
            assert await _llm_metadata_nullability(connection) == {
                "ai_provider": True,
                "model_used": True,
            }
            metadata = (
                await connection.execute(
                    text(
                        """
                        SELECT ai_provider, model_used
                        FROM questions
                        WHERE id = :id
                        """
                    ),
                    {"id": question_id},
                )
            ).one()

        assert metadata.ai_provider == "openai"
        assert metadata.model_used == "preserved-model"
    finally:
        await asyncio.to_thread(command.upgrade, alembic_config, "head")
        async with engine.begin() as connection:
            await connection.execute(text("DELETE FROM users WHERE id = :id"), {"id": user_id})
        await engine.dispose()


@pytest.mark.asyncio
async def test_question_llm_metadata_downgrade_succeeds_without_null_rows(
    postgres_database_url: str,
    migrated_database: None,
) -> None:
    del migrated_database
    alembic_config = _alembic_config()
    engine = create_async_engine(postgres_database_url, pool_pre_ping=True)
    user_id = uuid.uuid4()
    question_id = uuid.uuid4()

    try:
        async with engine.begin() as connection:
            await _insert_user(
                connection,
                user_id=user_id,
                email=f"downgrade-success-{user_id}@example.com",
            )
            await _insert_question(
                connection,
                question_id=question_id,
                user_id=user_id,
                ai_provider="ollama",
                model_used="preserved-on-downgrade",
            )

        await asyncio.to_thread(command.downgrade, alembic_config, PREVIOUS_REVISION)

        async with engine.connect() as connection:
            assert await _llm_metadata_nullability(connection) == {
                "ai_provider": False,
                "model_used": False,
            }
            metadata = (
                await connection.execute(
                    text(
                        """
                        SELECT ai_provider, model_used
                        FROM questions
                        WHERE id = :id
                        """
                    ),
                    {"id": question_id},
                )
            ).one()

        assert metadata.ai_provider == "ollama"
        assert metadata.model_used == "preserved-on-downgrade"
    finally:
        await asyncio.to_thread(command.upgrade, alembic_config, "head")
        async with engine.begin() as connection:
            await connection.execute(text("DELETE FROM users WHERE id = :id"), {"id": user_id})
        await engine.dispose()


@pytest.mark.asyncio
async def test_question_llm_metadata_downgrade_refuses_null_rows_without_data_loss(
    postgres_database_url: str,
    migrated_database: None,
) -> None:
    del migrated_database
    alembic_config = _alembic_config()
    engine = create_async_engine(postgres_database_url, pool_pre_ping=True)
    user_id = uuid.uuid4()
    provider_null_id = uuid.uuid4()
    model_null_id = uuid.uuid4()

    try:
        async with engine.begin() as connection:
            await _insert_user(
                connection,
                user_id=user_id,
                email=f"downgrade-refusal-{user_id}@example.com",
            )
            await _insert_question(
                connection,
                question_id=provider_null_id,
                user_id=user_id,
                ai_provider=None,
                model_used="existing-model",
            )
            await _insert_question(
                connection,
                question_id=model_null_id,
                user_id=user_id,
                ai_provider="openai",
                model_used=None,
            )

        with pytest.raises(RuntimeError) as error:
            await asyncio.to_thread(command.downgrade, alembic_config, PREVIOUS_REVISION)

        message = str(error.value)
        assert "2 question record(s)" in message
        assert "Populate both metadata fields" in message
        assert "rerun the downgrade" in message
        assert str(provider_null_id) not in message
        assert str(model_null_id) not in message

        async with engine.connect() as connection:
            assert await _llm_metadata_nullability(connection) == {
                "ai_provider": True,
                "model_used": True,
            }
            metadata = (
                await connection.execute(
                    text(
                        """
                        SELECT id, ai_provider, model_used
                        FROM questions
                        WHERE id IN (:provider_null_id, :model_null_id)
                        ORDER BY id
                        """
                    ),
                    {
                        "provider_null_id": provider_null_id,
                        "model_null_id": model_null_id,
                    },
                )
            ).all()

        assert len(metadata) == 2
        assert {row.id: (row.ai_provider, row.model_used) for row in metadata} == {
            provider_null_id: (None, "existing-model"),
            model_null_id: ("openai", None),
        }
    finally:
        async with engine.begin() as connection:
            await connection.execute(text("DELETE FROM users WHERE id = :id"), {"id": user_id})
        await asyncio.to_thread(command.upgrade, alembic_config, "head")
        await engine.dispose()
