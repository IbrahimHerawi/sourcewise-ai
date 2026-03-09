"""Async SQLAlchemy engine and session configuration."""

from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.settings import get_settings

_engine: AsyncEngine | None = None
_session_maker: async_sessionmaker[AsyncSession] | None = None


def get_engine() -> AsyncEngine:
    """Return the lazily initialized async SQLAlchemy engine."""
    global _engine, _session_maker

    if _engine is None:
        settings = get_settings()
        _engine = create_async_engine(
            settings.get_database_url(),
            pool_pre_ping=True,
        )
        _session_maker = async_sessionmaker(
            bind=_engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False,
        )

    return _engine


def _get_session_maker() -> async_sessionmaker[AsyncSession]:
    if _session_maker is None:
        get_engine()

    assert _session_maker is not None
    return _session_maker


class _LazyAsyncSessionMaker:
    """Proxy that initializes the underlying session maker on first use."""

    def __call__(self, *args: object, **kwargs: object) -> AsyncSession:
        return _get_session_maker()(*args, **kwargs)


AsyncSessionMaker = _LazyAsyncSessionMaker()


async def get_db_session() -> AsyncGenerator[AsyncSession]:
    """Yield an async database session for FastAPI dependencies."""
    async with _get_session_maker()() as session:
        yield session


__all__ = ["get_engine", "AsyncSessionMaker", "get_db_session"]
