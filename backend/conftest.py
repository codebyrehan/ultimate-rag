"""Shared pytest fixtures.

Sets up an isolated, in-memory SQLite test database so the suite runs with
**no external services** (no Postgres, Redis, or Docker required).
Environment variables must be set before settings are first imported.
"""

import os

os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite://")
os.environ.setdefault("SECRET_KEY", "test-secret-key-0123456789abcdef")
os.environ.setdefault("INLINE_WORKER", "1")
os.environ.setdefault("VECTOR_STORE_PROVIDER", "in_memory")
os.environ.setdefault("EMBEDDING_PROVIDER", "local")
os.environ.setdefault("LLM_PROVIDER", "stub")
os.environ.setdefault("RERANKER_PROVIDER", "stub")

import pytest
from sqlalchemy import StaticPool
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from ultimate_rag.core.config import get_settings
from ultimate_rag.db.connection import Base, dispose_engine, dispose_engine_sync

TEST_DB_URL = os.environ["DATABASE_URL"]


@pytest.fixture(scope="session", autouse=True)
def _settings() -> None:
    """Force settings to re-read env once for the test session."""
    get_settings.cache_clear()
    dispose_engine_sync()  # drop any cached engine from imports
    get_settings()


@pytest.fixture(scope="session")
async def test_engine(_settings):
    engine = create_async_engine(
        TEST_DB_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()
    await dispose_engine()


@pytest.fixture
async def db_session(test_engine) -> AsyncSession:
    """Function-scoped session with full schema reset + rollback per test.

    Using a shared in-memory SQLite engine, we drop & recreate all tables
    for every test so committed data never leaks between tests.
    """
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        yield session
        await session.rollback()


@pytest.fixture
def container():
    from ultimate_rag.services.container import get_container, reset_container

    reset_container()
    return get_container()
