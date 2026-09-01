"""Alembic environment configuration.

Reads DATABASE_URL from settings, converts async driver suffixes to sync
drivers so Alembic (sync) can drive migrations, and autogenerates from the
SQLAlchemy metadata defined in ultimate_rag.db.models.
"""
from __future__ import annotations

import os
import sys
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

# make the project importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from ultimate_rag.core.config import get_settings
from ultimate_rag.db.models import Base  # noqa: E402

config = context.config
settings = get_settings()

# Interpret the config file for Python logging.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

# Runtime uses async SQLAlchemy with psycopg3. Alembic is synchronous, so
# convert async URLs to the synchronous psycopg3 dialect. Do not map to
# psycopg2: the project intentionally depends on psycopg (v3).
ASYNC_TO_SYNC = {
    "sqlite+aiosqlite": "sqlite",
    "postgresql+asyncpg": "postgresql+psycopg",
    "postgresql+psycopg": "postgresql+psycopg",
}


def _sync_url() -> str:
    url = settings.database_url
    original = url
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+psycopg://", 1)
    if url.startswith("postgresql+psycopg2://"):
        url = url.replace("postgresql+psycopg2://", "postgresql+psycopg://", 1)
    for async_prefix, sync in ASYNC_TO_SYNC.items():
        if url.startswith(async_prefix):
            url = url.replace(async_prefix, sync, 1)
    if original != url:
        print(f"ALCHEMY URL NORMALIZED: {original} -> {url}", flush=True)
    return url


def run_migrations_offline() -> None:
    url = _sync_url()
    context.config.set_main_option("sqlalchemy.url", url)
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    url = _sync_url()
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        url=url,
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
            render_as_batch=settings.is_sqlite,
            batch_render_derivation_times=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
