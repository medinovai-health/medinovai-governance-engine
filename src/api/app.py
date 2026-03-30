"""FastAPI application entry."""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from typing import AsyncIterator

import structlog
from fastapi import FastAPI

from api import deps
from api.routes import dua, governance_routes, health, query
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
    """Wire Evidence Store client from environment."""
    _configure_logging()
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
