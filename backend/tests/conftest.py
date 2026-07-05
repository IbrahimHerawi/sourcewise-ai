from __future__ import annotations

import os
from collections.abc import AsyncGenerator, Generator
from pathlib import Path

import pytest
import pytest_asyncio
from alembic import command
from alembic.config import Config
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.core.settings import get_settings

PROJECT_ROOT = Path(__file__).resolve().parents[1]
ALEMBIC_INI_PATH = PROJECT_ROOT / "alembic.ini"

# Keep test runs deterministic even when local `.env` selects OpenAI.
os.environ.setdefault("OPENAI_API_KEY", "sk-test")


def _to_asyncpg_url(url: str) -> str:
    if url.startswith("postgresql+asyncpg://"):
        return url
    if url.startswith("postgresql+"):
        return f"postgresql+asyncpg://{url.split('://', 1)[1]}"
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+asyncpg://", 1)
    raise ValueError(f"Unsupported Postgres URL format: {url!r}")


@pytest.fixture(scope="session")
def postgres_database_url() -> Generator[str]:
    postgres_module = pytest.importorskip(
        "testcontainers.postgres",
        reason="Install testcontainers to run repository integration tests.",
    )
    PostgresContainer = postgres_module.PostgresContainer

    container = PostgresContainer("pgvector/pgvector:pg16")
    container.start()
    try:
        yield _to_asyncpg_url(container.get_connection_url())
    finally:
        container.stop()


@pytest.fixture(scope="session")
def migrated_database(postgres_database_url: str) -> Generator[None]:
    parsed_url = make_url(postgres_database_url)
    if not parsed_url.username:
        raise ValueError("Test Postgres URL is missing a username.")
    if not parsed_url.database:
        raise ValueError("Test Postgres URL is missing a database name.")
    if parsed_url.password is None:
        raise ValueError("Test Postgres URL is missing a password.")

    previous_values = {
        "POSTGRES_HOST": os.environ.get("POSTGRES_HOST"),
        "POSTGRES_PORT": os.environ.get("POSTGRES_PORT"),
        "POSTGRES_USER": os.environ.get("POSTGRES_USER"),
        "POSTGRES_DB": os.environ.get("POSTGRES_DB"),
        "POSTGRES_PASSWORD": os.environ.get("POSTGRES_PASSWORD"),
        "POSTGRES_PASSWORD_FILE": os.environ.get("POSTGRES_PASSWORD_FILE"),
    }

    os.environ["POSTGRES_HOST"] = parsed_url.host or "localhost"
    os.environ["POSTGRES_PORT"] = str(parsed_url.port or 5432)
    os.environ["POSTGRES_USER"] = parsed_url.username
    os.environ["POSTGRES_DB"] = parsed_url.database
    os.environ["POSTGRES_PASSWORD"] = parsed_url.password
    os.environ.pop("POSTGRES_PASSWORD_FILE", None)
    get_settings.cache_clear()

    alembic_config = Config(str(ALEMBIC_INI_PATH))
    alembic_config.set_main_option("sqlalchemy.url", get_settings().get_database_url())
    command.upgrade(alembic_config, "head")

    yield

    for key, value in previous_values.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value
    get_settings.cache_clear()


@pytest_asyncio.fixture
async def db_session(
    postgres_database_url: str,
    migrated_database: None,
) -> AsyncGenerator[AsyncSession]:
    engine = create_async_engine(postgres_database_url, pool_pre_ping=True)

    async with engine.connect() as connection:
        transaction = await connection.begin()
        session = AsyncSession(bind=connection, expire_on_commit=False, autoflush=False)
        try:
            yield session
        finally:
            await session.close()
            if transaction.is_active:
                await transaction.rollback()

    await engine.dispose()
