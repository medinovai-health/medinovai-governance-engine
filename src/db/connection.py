"""Async SQLAlchemy engine, session factory, and pool health check."""

from __future__ import annotations

import os
from typing import Any

import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from governance.constants import E_MODULE_ID

mos_logger = structlog.get_logger()

E_DEFAULT_DATABASE_URL = (
    "postgresql+asyncpg://governance:governance@"
    "governance-postgres:5432/governance"
)


def mos_get_database_url() -> str:
    """Resolve async database URL from environment."""
    return os.environ.get("DATABASE_URL", E_DEFAULT_DATABASE_URL)


def create_engine_and_session_factory(
    mos_url: str | None = None,
) -> tuple[AsyncEngine, async_sessionmaker[AsyncSession]]:
    """Create async engine and session factory with connection pooling."""
    mos_effective = mos_url or mos_get_database_url()
    mos_engine = create_async_engine(
        mos_effective,
        pool_pre_ping=True,
        pool_size=int(os.environ.get("DB_POOL_SIZE", "5")),
        max_overflow=int(os.environ.get("DB_MAX_OVERFLOW", "10")),
        echo=os.environ.get("SQLALCHEMY_ECHO", "").lower() in ("1", "true", "yes"),
    )
    mos_factory = async_sessionmaker(
        mos_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )
    return mos_engine, mos_factory


async def check_db_health(mos_engine: AsyncEngine) -> dict[str, Any]:
    """Run a cheap query to verify the pool can reach PostgreSQL."""
    try:
        async with mos_engine.connect() as mos_conn:
            await mos_conn.execute(text("SELECT 1"))
        return {"ok": True, "component": "postgresql"}
    except Exception as mos_exc:
        mos_logger.error(
            "db_health_failed",
            module_id=E_MODULE_ID,
            category="SYSTEM",
            phi_safe=True,
            error_type=type(mos_exc).__name__,
        )
        return {"ok": False, "error": type(mos_exc).__name__}


async def dispose_engine(mos_engine: AsyncEngine | None) -> None:
    """Dispose engine on shutdown."""
    if mos_engine is not None:
        await mos_engine.dispose()
