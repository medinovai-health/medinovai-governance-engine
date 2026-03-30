"""Data Use Agreement parsing, validation, and compliance checks."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

import structlog

from governance.constants import E_MODULE_ID

mos_logger = structlog.get_logger()


class DuaManager:
    """Parse DUA payloads, validate schema, enforce term and purpose rules."""

    def __init__(self) -> None:
        self._mos_store: dict[str, dict[str, Any]] = {}

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

    def check_term_compliance(
        self,
        mos_duaId: str,
        mos_at: datetime | None = None,
    ) -> dict[str, Any]:
        """Evaluate expiration and revocation for a stored DUA."""
        mos_now = mos_at or datetime.now(timezone.utc)
        mos_rec = self._mos_store.get(mos_duaId)
        if not mos_rec:
            return {"compliant": False, "reason": "dua_not_found"}
        if mos_rec.get("revoked"):
            return {"compliant": False, "reason": "dua_revoked"}
        mos_expires = mos_rec.get("expires_at")
        if mos_expires:
            mos_exp_dt = datetime.fromisoformat(mos_expires.replace("Z", "+00:00"))
            if mos_now > mos_exp_dt:
                return {"compliant": False, "reason": "dua_expired"}
        return {"compliant": True, "reason": "ok"}

    def purpose_allowed(
        self,
        mos_duaId: str,
        mos_statedPurpose: str,
    ) -> dict[str, Any]:
        """Purpose-based access control against permitted_purposes."""
        mos_rec = self._mos_store.get(mos_duaId)
        if not mos_rec:
            return {"allowed": False, "reason": "dua_not_found"}
        mos_allowed = set(mos_rec.get("permitted_purposes") or [])
        mos_ok = mos_statedPurpose in mos_allowed
        return {
            "allowed": mos_ok,
            "reason": "purpose_ok" if mos_ok else "purpose_denied",
        }

    def store_dua(self, mos_dua: dict[str, Any]) -> str:
        """Persist in-memory stub; returns DUA id."""
        mos_id = str(mos_dua.get("id") or uuid4())
        mos_copy = dict(mos_dua)
        mos_copy["id"] = mos_id
        mos_copy["content_hash"] = hashlib.sha256(
            json.dumps(mos_copy, sort_keys=True).encode()
        ).hexdigest()
        self._mos_store[mos_id] = mos_copy
        mos_logger.info(
            "dua_stored",
            module_id=E_MODULE_ID,
            category="AUDIT",
            phi_safe=True,
            dua_id=mos_id,
        )
        return mos_id

    def get_dua(self, mos_duaId: str) -> dict[str, Any] | None:
        """Return stored DUA or None."""
        return self._mos_store.get(mos_duaId)
