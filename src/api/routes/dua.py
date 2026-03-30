"""Data Use Agreement upload, validation, compliance."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel, Field

from api import deps
from governance.dua_manager import DuaManager

router = APIRouter(prefix="/api/v1/dua", tags=["dua"])


class DuaComplianceBody(BaseModel):
    """Request body for compliance checks (IDs only; no PHI)."""

    dua_id: str = Field(..., description="Stored DUA identifier")
    stated_purpose: str = Field(..., description="Purpose code for PBAC")
    at: str | None = Field(None, description="ISO-8601 evaluation time (optional)")


def _get_manager() -> DuaManager:
    return deps.mos_dua_manager


@router.post("/upload")
async def dua_upload(
    mos_file: UploadFile | None = File(None),
    mos_manager: DuaManager = Depends(_get_manager),
) -> dict[str, Any]:
    """Upload DUA document (JSON file) or use JSON APIs in production gateway."""
    if not mos_file:
        raise HTTPException(status_code=400, detail="file_required")
    mos_body = await mos_file.read()
    mos_parsed = mos_manager.parse_dua_payload(mos_body)
    mos_errors = mos_manager.validate_dua_structure(mos_parsed)
    if mos_errors:
        raise HTTPException(status_code=422, detail={"errors": mos_errors})
    mos_id = mos_manager.store_dua(mos_parsed)
    return {"id": mos_id, "status": "stored"}


@router.post("/validate")
async def dua_validate(
    mos_body: dict[str, Any],
    mos_manager: DuaManager = Depends(_get_manager),
) -> dict[str, Any]:
    """Validate DUA JSON structure without persisting."""
    mos_errors = mos_manager.validate_dua_structure(mos_body)
    return {"valid": len(mos_errors) == 0, "errors": mos_errors}


@router.post("/check-compliance")
async def dua_check_compliance(
    mos_body: DuaComplianceBody,
    mos_manager: DuaManager = Depends(_get_manager),
) -> dict[str, Any]:
    """Check term + purpose compliance for a stored DUA."""
    from datetime import datetime, timezone

    mos_at = None
    if mos_body.at:
        mos_at = datetime.fromisoformat(mos_body.at.replace("Z", "+00:00"))
    mos_term = mos_manager.check_term_compliance(mos_body.dua_id, mos_at)
    mos_purpose = mos_manager.purpose_allowed(mos_body.dua_id, mos_body.stated_purpose)
    mos_compliant = mos_term.get("compliant") and mos_purpose.get("allowed")
    return {
        "compliant": mos_compliant,
        "term": mos_term,
        "purpose": mos_purpose,
    }
