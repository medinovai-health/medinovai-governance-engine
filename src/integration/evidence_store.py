"""Evidence Store client: electronic signatures, audit trail, artifact lineage."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

import httpx
import structlog

from governance.constants import E_MODULE_ID

mos_logger = structlog.get_logger()


class EvidenceStoreClient:
    """HTTP client scaffold for Evidence Store (signatures + immutable audit)."""

    def __init__(self, mos_baseUrl: str | None = None) -> None:
        self._mos_base_url = (mos_baseUrl or "").rstrip("/")
        self._mos_client: httpx.AsyncClient | None = None

    async def connect(self) -> None:
        """Initialize async HTTP client when base URL configured."""
        if self._mos_base_url and self._mos_client is None:
            self._mos_client = httpx.AsyncClient(base_url=self._mos_base_url, timeout=30.0)

    async def aclose(self) -> None:
        """Close underlying client."""
        if self._mos_client:
            await self._mos_client.aclose()
            self._mos_client = None

    async def request_electronic_signature(
        self,
        mos_recordId: str,
        mos_meaning: str,
        mos_actorId: str,
    ) -> dict[str, Any]:
        """Request 21 CFR Part 11 style e-signature binding (stub if offline)."""
        mos_payload = {
            "record_id": mos_recordId,
            "meaning": mos_meaning,
            "actor_id": mos_actorId,
            "requested_at": datetime.now(timezone.utc).isoformat(),
        }
        if not self._mos_client:
            mos_sig_id = str(uuid4())
            mos_logger.info(
                "evidence_signature_stub",
                module_id=E_MODULE_ID,
                category="AUDIT",
                phi_safe=True,
                signature_id=mos_sig_id,
                record_id=mos_recordId,
            )
            return {"status": "stub", "signature_id": mos_sig_id, **mos_payload}
        mos_resp = await self._mos_client.post(
            "/api/v1/signatures",
            json=mos_payload,
        )
        mos_resp.raise_for_status()
        return mos_resp.json()

    async def append_audit_event(self, mos_event: dict[str, Any]) -> dict[str, Any]:
        """Append governance audit event for WORM-backed trail integration."""
        if not self._mos_client:
            mos_eid = str(uuid4())
            mos_logger.info(
                "evidence_audit_stub",
                module_id=E_MODULE_ID,
                category="AUDIT",
                phi_safe=True,
                event_id=mos_eid,
                event_type=mos_event.get("event_type"),
            )
            return {"status": "stub", "event_id": mos_eid}
        mos_resp = await self._mos_client.post("/api/v1/audit/events", json=mos_event)
        mos_resp.raise_for_status()
        return mos_resp.json()

    async def record_lineage(self, mos_artifact: dict[str, Any]) -> dict[str, Any]:
        """Register approved-query artifact lineage (upstream DUAs, policies)."""
        if not self._mos_client:
            mos_lid = str(uuid4())
            return {"status": "stub", "lineage_id": mos_lid}
        mos_resp = await self._mos_client.post("/api/v1/lineage", json=mos_artifact)
        mos_resp.raise_for_status()
        return mos_resp.json()
