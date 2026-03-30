"""FastAPI application entry."""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from typing import AsyncIterator

import structlog
from fastapi import FastAPI

from api import deps
from api.routes import dua, governance_routes, health, query
from db.connection import check_db_health, create_engine_and_session_factory, dispose_engine
from governance.constants import E_MODULE_ID
from integration.evidence_store import EvidenceStoreClient

mos_logger = structlog.get_logger()


def _configure_logging() -> None:
    structlog.configure(
        processors=[
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(),
        ],
    )


@asynccontextmanager
async def lifespan(mos_app: FastAPI) -> AsyncIterator[None]:
    """Initialize PostgreSQL pool, Evidence Store client, and dispose on shutdown."""
    _configure_logging()
    mos_engine, mos_factory = create_engine_and_session_factory()
    deps.mos_engine = mos_engine
    deps.mos_session_factory = mos_factory
    mos_app.state.db_engine = mos_engine
    mos_app.state.session_factory = mos_factory
    mos_db_health = await check_db_health(mos_engine)
    mos_logger.info(
        "db_pool_ready",
        module_id=E_MODULE_ID,
        category="SYSTEM",
        phi_safe=True,
        database_ok=mos_db_health.get("ok"),
    )

    mos_url = os.environ.get("EVIDENCE_STORE_URL", "")
    mos_client = EvidenceStoreClient(mos_url or None)
    await mos_client.connect()
    deps.mos_evidence_store = mos_client
    mos_app.state.evidence_store = mos_client
    mos_logger.info(
        "app_startup",
        module_id=E_MODULE_ID,
        category="SYSTEM",
        phi_safe=True,
        evidence_configured=bool(mos_url),
    )
    yield
    await dispose_engine(mos_engine)
    deps.mos_engine = None
    deps.mos_session_factory = None
    await mos_client.aclose()
    mos_logger.info("app_shutdown", module_id=E_MODULE_ID, category="SYSTEM", phi_safe=True)


mos_app = FastAPI(
    title="medinovai-governance-engine",
    version="0.1.0",
    lifespan=lifespan,
)

mos_app.include_router(health.router)
mos_app.include_router(dua.router)
mos_app.include_router(query.router)
mos_app.include_router(governance_routes.router)
