"""Temporal activity runtime: async session factory (set by worker entrypoint)."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

mos_activity_session_factory: async_sessionmaker[AsyncSession] | None = None


def set_activity_session_factory(mos_factory: async_sessionmaker[AsyncSession]) -> None:
    """Called from temporal_worker after engine creation."""
    global mos_activity_session_factory
    mos_activity_session_factory = mos_factory
