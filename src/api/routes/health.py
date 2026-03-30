"""Liveness and readiness probes."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter

from governance.constants import E_MODULE_ID

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict:
    return {
        "status": "healthy",
        "service": E_MODULE_ID,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/ready")
async def ready() -> dict:
    return {"status": "ready", "service": E_MODULE_ID}
