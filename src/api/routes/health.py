"""Liveness and readiness probes."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Request

from db.connection import check_db_health
from governance.constants import E_MODULE_ID

router = APIRouter(tags=["health"])


@router.get("/health")
async def health(mos_request: Request) -> dict:
    """Liveness; includes database pool check when engine is configured."""
    mos_db = {"ok": True, "component": "postgresql_skipped"}
    mos_engine = getattr(mos_request.app.state, "db_engine", None)
    if mos_engine is not None:
        mos_db = await check_db_health(mos_engine)
    mos_status = "healthy" if mos_db.get("ok") else "degraded"
    return {
        "status": mos_status,
        "service": E_MODULE_ID,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "database": mos_db,
    }


@router.get("/ready")
async def ready(mos_request: Request) -> dict:
    """Readiness: require database when engine is present."""
    mos_engine = getattr(mos_request.app.state, "db_engine", None)
    if mos_engine is None:
        return {"status": "ready", "service": E_MODULE_ID, "database": {"ok": True}}
    mos_db = await check_db_health(mos_engine)
    if not mos_db.get("ok"):
        return {"status": "not_ready", "service": E_MODULE_ID, "database": mos_db}
    return {"status": "ready", "service": E_MODULE_ID, "database": mos_db}
