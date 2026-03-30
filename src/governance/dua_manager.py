"""Data Use Agreement parsing, validation, and compliance checks (PostgreSQL-backed)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

import structlog

from db.models import DataUseAgreement, E_DuaStatus
from db.repository import DUARepo
from governance.constants import E_MODULE_ID

mos_logger = structlog.get_logger()


class DuaManager:
    """Parse DUA payloads, validate schema, enforce term and purpose rules via ``DUARepo``."""

    def parse_dua_payload(self, mos_rawBody: bytes) -> dict[str, Any]:
        """Parse JSON DUA body; raises ValueError on invalid JSON."""
        try:
            mos_parsed = json.loads(mos_rawBody.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as mos_exc:
            mos_logger.warning(
                "dua_parse_failed",
                module_id=E_MODULE_ID,
                category="SYSTEM",
                phi_safe=True,
                error_type=type(mos_exc).__name__,
            )
            raise ValueError("invalid_dua_payload") from mos_exc
        if not isinstance(mos_parsed, dict):
            raise ValueError("dua_must_be_object")
        return mos_parsed

    def validate_dua_structure(self, mos_dua: dict[str, Any]) -> list[str]:
        """Return list of validation error codes; empty if valid."""
        mos_errors: list[str] = []
        for mos_field in ("dataset_id", "permitted_purposes", "effective_from"):
            if mos_field not in mos_dua:
                mos_errors.append(f"missing_{mos_field}")
        mos_purposes = mos_dua.get("permitted_purposes")
        if mos_purposes is not None and not isinstance(mos_purposes, list):
            mos_errors.append("permitted_purposes_not_list")
        return mos_errors

    async def check_term_compliance(
        self,
        mos_repo: DUARepo,
        mos_duaId: str,
        mos_at: datetime | None = None,
    ) -> dict[str, Any]:
        """Evaluate expiration and revocation for a stored DUA."""
        mos_now = mos_at or datetime.now(timezone.utc)
        mos_rec = await mos_repo.get_by_id_str(mos_duaId)
        if not mos_rec:
            return {"compliant": False, "reason": "dua_not_found"}
        if mos_rec.status == E_DuaStatus.REVOKED:
            return {"compliant": False, "reason": "dua_revoked"}
        if mos_rec.status == E_DuaStatus.SUSPENDED:
            return {"compliant": False, "reason": "dua_suspended"}
        if mos_rec.end_date and mos_now > mos_rec.end_date:
            return {"compliant": False, "reason": "dua_expired"}
        if mos_rec.status not in (E_DuaStatus.ACTIVE,):
            return {"compliant": False, "reason": "dua_not_active"}
        return {"compliant": True, "reason": "ok"}

    async def purpose_allowed(
        self,
        mos_repo: DUARepo,
        mos_duaId: str,
        mos_statedPurpose: str,
    ) -> dict[str, Any]:
        """Purpose-based access control against approved uses."""
        mos_rec = await mos_repo.get_by_id_str(mos_duaId)
        if not mos_rec:
            return {"allowed": False, "reason": "dua_not_found"}
        mos_allowed = {str(mos_x) for mos_x in (mos_rec.approved_uses or [])}
        mos_ok = mos_statedPurpose in mos_allowed
        return {
            "allowed": mos_ok,
            "reason": "purpose_ok" if mos_ok else "purpose_denied",
        }

    async def store_dua(
        self,
        mos_repo: DUARepo,
        mos_dua: dict[str, Any],
        *,
        mos_tenantId: str,
        mos_actorId: str,
    ) -> str:
        """Persist via ``DUARepo``; returns DUA id (audit on create)."""
        mos_row = await mos_repo.create_from_payload(
            mos_dua,
            mos_tenantId=mos_tenantId,
            mos_actorId=mos_actorId,
        )
        mos_id = str(mos_row.id)
        mos_logger.info(
            "dua_stored",
            module_id=E_MODULE_ID,
            category="AUDIT",
            phi_safe=True,
            dua_id=mos_id,
        )
        return mos_id

    async def get_dua(self, mos_repo: DUARepo, mos_duaId: str) -> dict[str, Any] | None:
        """Return stored DUA as API-shaped dict or None."""
        mos_rec = await mos_repo.get_by_id_str(mos_duaId)
        if not mos_rec:
            return None
        return _dua_to_dict(mos_rec)


def _dua_to_dict(mos_row: DataUseAgreement) -> dict[str, Any]:
    """Map ORM row to JSON-friendly dict (IDs only)."""
    return {
        "id": str(mos_row.id),
        "title": mos_row.title,
        "institution": mos_row.institution,
        "principal_investigator": mos_row.principal_investigator,
        "purpose": mos_row.purpose,
        "data_categories": mos_row.data_categories,
        "approved_uses": mos_row.approved_uses,
        "restrictions": mos_row.restrictions,
        "start_date": mos_row.start_date.isoformat(),
        "end_date": mos_row.end_date.isoformat() if mos_row.end_date else None,
        "status": mos_row.status.value,
        "tenant_id": mos_row.tenant_id,
        "created_by": mos_row.created_by,
        "created_at": mos_row.created_at.isoformat() if mos_row.created_at else None,
        "updated_at": mos_row.updated_at.isoformat() if mos_row.updated_at else None,
    }
