"""Query submission, steward review, approve/deny, listing."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from api import deps
from api.temporal_client import mos_signal_query_workflow, mos_start_query_workflow
from governance.constants import E_DEFAULT_SENSITIVE_SIGNATURES_REQUIRED, E_MODULE_ID

router = APIRouter(prefix="/api/v1/query", tags=["query"])


class QuerySubmitBody(BaseModel):
    """Researcher query submission (metadata only in scaffold)."""

    stated_purpose: str
    dua_id: str
    sensitivity_tier: str = Field(default="standard", description="standard|sensitive")
    spec: dict[str, Any] = Field(default_factory=dict, description="Opaque query spec ref")


class QueryDecisionBody(BaseModel):
    """Steward decision payload (actor id only; no PHI)."""

    actor_id: str
    reason_code: str | None = None


@router.post("/submit")
async def query_submit(mos_body: QuerySubmitBody) -> dict[str, Any]:
    """Submit query for approval; starts Temporal workflow when reachable."""
    mos_id = str(uuid4())
    mos_sigs = (
        E_DEFAULT_SENSITIVE_SIGNATURES_REQUIRED
        if mos_body.sensitivity_tier == "sensitive"
        else 1
    )
    mos_row = {
        "id": mos_id,
        "status": "pending_review",
        "submitted_at": datetime.now(timezone.utc).isoformat(),
        "stated_purpose": mos_body.stated_purpose,
        "dua_id": mos_body.dua_id,
        "sensitivity_tier": mos_body.sensitivity_tier,
        "spec": mos_body.spec,
        "signatures_required": mos_sigs,
    }
    deps.mos_query_store[mos_id] = mos_row
    mos_wf = await mos_start_query_workflow(mos_id, mos_sigs)
    mos_row["workflow_status"] = mos_wf
    await deps.mos_evidence_store.append_audit_event(
        {
            "event_type": "query_submitted",
            "module_id": E_MODULE_ID,
            "query_id": mos_id,
            "dua_id": mos_body.dua_id,
        }
    )
    return {"id": mos_id, "status": mos_row["status"], "workflow": mos_wf}


@router.post("/{mos_queryId}/approve")
async def query_approve(mos_queryId: str, mos_body: QueryDecisionBody) -> dict[str, Any]:
    """Record steward signature and finalize approval when quorum met."""
    mos_row = deps.mos_query_store.get(mos_queryId)
    if not mos_row:
        raise HTTPException(status_code=404, detail="query_not_found")
    await mos_signal_query_workflow(mos_queryId, "sign", mos_body.actor_id)
    await mos_signal_query_workflow(mos_queryId, "finalize_approve", None)
    mos_row["status"] = "approved"
    mos_row["decided_at"] = datetime.now(timezone.utc).isoformat()
    mos_row["actor_id"] = mos_body.actor_id
    await deps.mos_evidence_store.request_electronic_signature(
        mos_queryId,
        "query_approval",
        mos_body.actor_id,
    )
    await deps.mos_evidence_store.append_audit_event(
        {
            "event_type": "query_approved",
            "module_id": E_MODULE_ID,
            "query_id": mos_queryId,
            "actor_id": mos_body.actor_id,
        }
    )
    return {"id": mos_queryId, "status": "approved"}


@router.post("/{mos_queryId}/deny")
async def query_deny(mos_queryId: str, mos_body: QueryDecisionBody) -> dict[str, Any]:
    """Deny query with audit trail."""
    mos_row = deps.mos_query_store.get(mos_queryId)
    if not mos_row:
        raise HTTPException(status_code=404, detail="query_not_found")
    await mos_signal_query_workflow(mos_queryId, "deny", None)
    mos_row["status"] = "denied"
    mos_row["decided_at"] = datetime.now(timezone.utc).isoformat()
    mos_row["denial_reason"] = mos_body.reason_code
    await deps.mos_evidence_store.append_audit_event(
        {
            "event_type": "query_denied",
            "module_id": E_MODULE_ID,
            "query_id": mos_queryId,
            "actor_id": mos_body.actor_id,
            "reason_code": mos_body.reason_code,
        }
    )
    return {"id": mos_queryId, "status": "denied"}


@router.get("/list")
async def query_list() -> dict[str, Any]:
    """List queries in review queue (stub store)."""
    return {"items": list(deps.mos_query_store.values())}
