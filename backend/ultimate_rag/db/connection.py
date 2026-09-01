"""Database connection and session management.

Supports async SQLAlchemy (aiosqlite / psycopg) for runtime and a sync
engine for Alembic migrations. SQLite is kept as a local-development
fallback; PostgreSQL schema changes are owned by Alembic in production.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncGenerator

from sqlalchemy import MetaData, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import declarative_base

from ultimate_rag.core.config import get_settings

logger = logging.getLogger("ultimate_rag.db")

convention = {
    "ix": "ix_%(table_name)s_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(referred_table_name)s_%(column_0_name)s",
    "pk": "pk_%(table_name)s",
}

metadata = MetaData(naming_convention=convention)
Base = declarative_base(metadata=metadata)

_async_engine = None
_async_session_factory: async_sessionmaker[AsyncSession] | None = None


def _db_url() -> str:
    """Return a SQLAlchemy async URL with an explicitly selected DBAPI."""
    url = get_settings().database_url
    if url.startswith("postgresql+asyncpg://"):
        return url.replace("postgresql+asyncpg://", "postgresql+psycopg://", 1)
    if url.startswith("postgresql+psycopg2://"):
        return url.replace("postgresql+psycopg2://", "postgresql+psycopg://", 1)
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+psycopg://", 1)
    return url


def get_async_engine():
    global _async_engine
    if _async_engine is None:
        url = _db_url()
        settings = get_settings()
        if settings.is_sqlite:
            _async_engine = create_async_engine(url, echo=False)
        else:
            _async_engine = create_async_engine(
                url,
                pool_size=settings.db_pool_size,
                max_overflow=settings.db_max_overflow,
                pool_pre_ping=True,
                pool_recycle=1800,
                echo=False,
            )
    return _async_engine


def get_async_session_factory() -> async_sessionmaker[AsyncSession]:
    global _async_session_factory
    if _async_session_factory is None:
        _async_session_factory = async_sessionmaker(
            get_async_engine(), class_=AsyncSession, expire_on_commit=False
        )
    return _async_session_factory


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency: yields an async session."""
    factory = get_async_session_factory()
    async with factory() as session:
        yield session


async def init_db() -> None:
    """Initialize only the SQLite development schema.

    PostgreSQL schema management is deliberately delegated to Alembic. Running
    metadata.create_all() from every Uvicorn worker races with migrations and
    can create PostgreSQL enum/type objects concurrently. For PostgreSQL we
    therefore only verify connectivity here; the entrypoint runs
    ``alembic upgrade head`` before starting the application.
    """
    engine = get_async_engine()
    settings = get_settings()

    async with engine.begin() as conn:
        if settings.is_sqlite:
            await conn.run_sync(metadata.create_all)
        else:
            await conn.execute(text("SELECT 1"))

    logger.info("Database initialized (%s)", "sqlite" if settings.is_sqlite else "postgresql")


async def dispose_engine() -> None:
    """Dispose the async engine and clear cached factories."""
    global _async_engine, _async_session_factory
    if _async_engine is not None:
        await _async_engine.dispose()
        _async_engine = None
        _async_session_factory = None


def dispose_engine_sync() -> None:
    """Synchronous wrapper for dispose — used in sync contexts (e.g. conftest)."""
    global _async_engine, _async_session_factory
    if _async_engine is None:
        return
    import asyncio

    coro = _async_engine.dispose()
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            loop.create_task(coro)  # noqa: RUF006
        else:
            loop.run_until_complete(coro)
    except RuntimeError:
        asyncio.run(coro)
    _async_engine = None
    _async_session_factory = None
