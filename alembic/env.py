"""Alembic migration environment (async SQLAlchemy 2.0 + asyncpg)."""

from __future__ import annotations

import asyncio
import os
import sys
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

# Repo layout: alembic/ next to src/
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from db.models import Base  # noqa: E402

config = context.config
if config.config_file_name is not None and config.attributes.get("configure_logger", True):
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def mos_get_url() -> str:
    """Prefer DATABASE_URL; strip +asyncpg for sync fallbacks if needed."""
    return os.environ.get(
        "DATABASE_URL",
        "postgresql+asyncpg://governance:governance@localhost:5434/governance",
    )


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    mos_url = mos_get_url()
    context.configure(
        url=mos_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(mos_connection: Connection) -> None:
    context.configure(connection=mos_connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Run migrations in 'online' mode using async engine."""
    mos_ini = config.get_section(config.config_ini_section) or {}
    mos_ini["sqlalchemy.url"] = mos_get_url()
    mos_connectable = async_engine_from_config(
        mos_ini,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with mos_connectable.connect() as mos_connection:
        await mos_connection.run_sync(do_run_migrations)
    await mos_connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
