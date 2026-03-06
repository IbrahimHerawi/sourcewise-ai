from __future__ import annotations

import os
from collections.abc import AsyncGenerator, Generator
from pathlib import Path

import pytest
import pytest_asyncio
from alembic import command
from alembic.config import Config
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.core.settings import get_settings

PROJECT_ROOT = Path(__file__).resolve().parents[1]
ALEMBIC_INI_PATH = PROJECT_ROOT / "alembic.ini"


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
    previous_database_url = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = postgres_database_url
    get_settings.cache_clear()

    alembic_config = Config(str(ALEMBIC_INI_PATH))
    alembic_config.set_main_option("sqlalchemy.url", postgres_database_url)
    command.upgrade(alembic_config, "head")

    yield

    if previous_database_url is None:
        os.environ.pop("DATABASE_URL", None)
    else:
        os.environ["DATABASE_URL"] = previous_database_url
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
