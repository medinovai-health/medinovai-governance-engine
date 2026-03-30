"""Query submission, steward review, approve/deny, listing."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from api import deps
from api.temporal_client import mos_signal_query_workflow, mos_start_query_workflow
from db.models import E_ApprovalDecision, QueryRequest
from db.repository import ApprovalRepo, AuditRepo, DUARepo, QueryRequestRepo
from governance.constants import (
    E_DEFAULT_SENSITIVE_SIGNATURES_REQUIRED,
    E_DEFAULT_TENANT_ID,
    E_MODULE_ID,
)

router = APIRouter(prefix="/api/v1/query", tags=["query"])


class QuerySubmitBody(BaseModel):
    """Researcher query submission (metadata only in scaffold)."""

    stated_purpose: str
    dua_id: str
    sensitivity_tier: str = Field(default="standard", description="standard|sensitive")
    spec: dict[str, Any] = Field(default_factory=dict, description="Opaque query spec ref")
    requester_id: str = Field(default="anonymous")
    tenant_id: str = Field(default=E_DEFAULT_TENANT_ID)
    query_type: str = Field(default="cohort")


class QueryDecisionBody(BaseModel):
    """Steward decision payload (actor id only; no PHI)."""

    actor_id: str
    reason_code: str | None = None


def _query_to_item(mos_row: QueryRequest) -> dict[str, Any]:
    return {
        "id": str(mos_row.id),
        "status": mos_row.status.value,
        "submitted_at": mos_row.created_at.isoformat() if mos_row.created_at else None,
        "stated_purpose": mos_row.stated_purpose,
        "dua_id": str(mos_row.dua_id),
        "sensitivity_tier": mos_row.sensitivity_tier,
        "spec": mos_row.query_definition,
        "signatures_required": mos_row.signatures_required,
        "risk_score": mos_row.risk_score,
        "requester_id": mos_row.requester_id,
        "tenant_id": mos_row.tenant_id,
        "query_type": mos_row.query_type,
    }


@router.post("/submit")
async def query_submit(
    mos_body: QuerySubmitBody,
) -> dict[str, Any]:
    """Submit query for approval; persists to PostgreSQL then starts Temporal when reachable."""
    if deps.mos_session_factory is None:
        raise HTTPException(status_code=503, detail="database_unavailable")
    mos_sigs = (
        E_DEFAULT_SENSITIVE_SIGNATURES_REQUIRED
        if mos_body.sensitivity_tier == "sensitive"
        else 1
    )
    try:
        mos_dua_uuid = uuid.UUID(mos_body.dua_id)
    except ValueError as mos_exc:
        raise HTTPException(status_code=400, detail="invalid_dua_id") from mos_exc
    mos_query_uuid = uuid.uuid4()
    mos_risk_attrs = mos_body.spec.get("risk_attributes") or {
        "quasi_identifier_count": 0,
        "rare_combination_weight": 0.0,
        "includes_fine_geo": False,
    }
    async with deps.mos_session_factory() as mos_session:
        async with mos_session.begin():
            mos_audit = AuditRepo(mos_session)
            mos_dua_repo = DUARepo(mos_session, mos_audit)
            mos_dua_row = await mos_dua_repo.get_by_id(mos_dua_uuid)
            if mos_dua_row is None:
                raise HTTPException(status_code=400, detail="dua_not_found")
            mos_risk_result = await deps.mos_risk_scorer.score_reidentification_risk_with_audit(
                mos_risk_attrs,
                mos_audit,
                mos_tenantId=mos_body.tenant_id,
                mos_actorId=mos_body.requester_id,
                mos_queryRequestId=str(mos_query_uuid),
            )
            mos_qrepo = QueryRequestRepo(mos_session, mos_audit)
            mos_row = await mos_qrepo.create(
                mos_duaId=mos_dua_uuid,
                mos_requesterId=mos_body.requester_id,
                mos_queryType=mos_body.query_type,
                mos_queryDefinition=mos_body.spec,
                mos_riskScore=float(mos_risk_result["score"]),
                mos_tenantId=mos_body.tenant_id,
                mos_statedPurpose=mos_body.stated_purpose,
                mos_sensitivityTier=mos_body.sensitivity_tier,
                mos_signaturesRequired=mos_sigs,
                mos_actorId=mos_body.requester_id,
                mos_id=mos_query_uuid,
            )
            mos_item = _query_to_item(mos_row)
            mos_id = mos_item["id"]
            mos_status = mos_item["status"]
    mos_wf = await mos_start_query_workflow(mos_id, mos_sigs)
    await deps.mos_evidence_store.append_audit_event(
        {
            "event_type": "query_submitted",
            "module_id": E_MODULE_ID,
            "query_id": mos_id,
            "dua_id": mos_body.dua_id,
        }
    )
    mos_item["workflow_status"] = mos_wf
    return {"id": mos_id, "status": mos_status, "workflow": mos_wf}


@router.post("/{mos_queryId}/approve")
async def query_approve(mos_queryId: str, mos_body: QueryDecisionBody) -> dict[str, Any]:
    """Record steward signature and finalize approval when quorum met."""
    if deps.mos_session_factory is None:
        raise HTTPException(status_code=503, detail="database_unavailable")
    mos_now = datetime.now(timezone.utc).isoformat()
    mos_sig_payload = f"{mos_queryId}|approved|{mos_body.actor_id}|{mos_now}"
    async with deps.mos_session_factory() as mos_session:
        async with mos_session.begin():
            mos_audit = AuditRepo(mos_session)
            mos_qrepo = QueryRequestRepo(mos_session, mos_audit)
            mos_arepo = ApprovalRepo(mos_session, mos_audit)
            mos_row = await mos_qrepo.get_str(mos_queryId)
            if not mos_row:
                raise HTTPException(status_code=404, detail="query_not_found")
            await mos_arepo.record_decision(
                mos_row,
                mos_decision=E_ApprovalDecision.APPROVED,
                mos_approverId=mos_body.actor_id,
                mos_role="steward",
                mos_reason=mos_body.reason_code,
                mos_signaturePayload=mos_sig_payload,
            )
            await mos_qrepo.approve(mos_row, mos_actorId=mos_body.actor_id)
    await mos_signal_query_workflow(mos_queryId, "sign", mos_body.actor_id)
    await mos_signal_query_workflow(mos_queryId, "finalize_approve", None)
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
    if deps.mos_session_factory is None:
        raise HTTPException(status_code=503, detail="database_unavailable")
    mos_now = datetime.now(timezone.utc).isoformat()
    mos_sig_payload = f"{mos_queryId}|denied|{mos_body.actor_id}|{mos_now}"
    async with deps.mos_session_factory() as mos_session:
        async with mos_session.begin():
            mos_audit = AuditRepo(mos_session)
            mos_qrepo = QueryRequestRepo(mos_session, mos_audit)
            mos_arepo = ApprovalRepo(mos_session, mos_audit)
            mos_row = await mos_qrepo.get_str(mos_queryId)
            if not mos_row:
                raise HTTPException(status_code=404, detail="query_not_found")
            await mos_arepo.record_decision(
                mos_row,
                mos_decision=E_ApprovalDecision.DENIED,
                mos_approverId=mos_body.actor_id,
                mos_role="steward",
                mos_reason=mos_body.reason_code,
                mos_signaturePayload=mos_sig_payload,
            )
            await mos_qrepo.deny(
                mos_row,
                mos_actorId=mos_body.actor_id,
                mos_reason=mos_body.reason_code,
            )
    await mos_signal_query_workflow(mos_queryId, "deny", None)
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
async def query_list(
    mos_session: AsyncSession = Depends(deps.get_db_session),
) -> dict[str, Any]:
    """List queries in review queue from PostgreSQL."""
    mos_audit = AuditRepo(mos_session)
    mos_qrepo = QueryRequestRepo(mos_session, mos_audit)
    mos_rows = await mos_qrepo.list_all()
    return {"items": [_query_to_item(mos_r) for mos_r in mos_rows]}
