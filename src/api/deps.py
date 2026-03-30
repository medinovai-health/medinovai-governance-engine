"""Shared service instances for API routes."""

from __future__ import annotations

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from governance.dua_manager import DuaManager
from governance.risk_scorer import RiskScorer
from integration.connector_framework import ConnectorRegistry
from integration.evidence_store import EvidenceStoreClient

mos_dua_manager = DuaManager()
mos_risk_scorer = RiskScorer()
mos_evidence_store = EvidenceStoreClient()
mos_connectors = ConnectorRegistry()

mos_engine: AsyncEngine | None = None
mos_session_factory: async_sessionmaker[AsyncSession] | None = None


async def get_db_session() -> AsyncIterator[AsyncSession]:
    """Yield a session and commit after successful request handler."""
    if mos_session_factory is None:
        raise RuntimeError("database_not_initialized")
    async with mos_session_factory() as mos_session:
        try:
            yield mos_session
            await mos_session.commit()
        except Exception:
            await mos_session.rollback()
            raise
