"""Governance policies and aggregate compliance checks."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from api import deps
from db.repository import AuditRepo, PolicyRepo
from governance.constants import E_DEFAULT_TENANT_ID, E_SYSTEM_ACTOR_ID
from governance.policy_engine import PolicyEngine

router = APIRouter(prefix="/api/v1/governance", tags=["governance"])


class PolicyRegisterBody(BaseModel):
    policy_id: str
    definition: dict[str, Any] = Field(default_factory=dict)
    tenant_id: str = Field(default=E_DEFAULT_TENANT_ID)


class GovernanceComplianceBody(BaseModel):
    policy_ids: list[str]
    query_meta: dict[str, Any] = Field(default_factory=dict)
    cell_count: int | None = None
    risk_attributes: dict[str, Any] | None = None


@router.get("/policies")
async def policies_list(mos_session: AsyncSession = Depends(deps.get_db_session)) -> dict[str, Any]:
    """List registered governance policies from PostgreSQL."""
    mos_audit = AuditRepo(mos_session)
    mos_repo = PolicyRepo(mos_session, mos_audit)
    mos_records = await mos_repo.list_all()
    return {"policies": [{"id": r.policy_id, **r.definition} for r in mos_records]}


@router.post("/policies")
async def policies_register(
    mos_body: PolicyRegisterBody,
    mos_session: AsyncSession = Depends(deps.get_db_session),
) -> dict[str, Any]:
    """Register or update a policy bundle (persisted + audit)."""
    mos_audit = AuditRepo(mos_session)
    mos_repo = PolicyRepo(mos_session, mos_audit)
    await mos_repo.upsert(
        mos_body.policy_id,
        mos_body.definition,
        mos_tenantId=mos_body.tenant_id,
        mos_actorId=E_SYSTEM_ACTOR_ID,
    )
    return {"id": mos_body.policy_id, "status": "registered"}


@router.post("/check-compliance")
async def governance_check_compliance(
    mos_body: GovernanceComplianceBody,
    mos_session: AsyncSession = Depends(deps.get_db_session),
) -> dict[str, Any]:
    """Run policy bundle checks, optional cell size and risk scoring (audited)."""
    mos_audit = AuditRepo(mos_session)
    mos_policy_repo = PolicyRepo(mos_session, mos_audit)
    mos_records = await mos_policy_repo.list_all()
    mos_map = {r.policy_id: r.definition for r in mos_records}
    mos_policy = PolicyEngine(mos_map)
    mos_tenant = mos_body.query_meta.get("tenant_id", E_DEFAULT_TENANT_ID)
    mos_actor = mos_body.query_meta.get("actor_id", E_SYSTEM_ACTOR_ID)
    mos_qid = mos_body.query_meta.get("query_request_id")
    mos_out: dict[str, Any] = {
        "policies": mos_policy.evaluate_query_against_policies(
            mos_body.policy_ids,
            mos_body.query_meta,
        ),
    }
    if mos_body.cell_count is not None:
        mos_out["minimum_cell_size"] = mos_policy.check_minimum_cell_size(mos_body.cell_count)
        await mos_audit.record(
            mos_entityType="governance_check",
            mos_entityId=mos_qid or "adhoc_cell_check",
            mos_action="cell_size_evaluated",
            mos_actorId=mos_actor,
            mos_tenantId=mos_tenant,
            mos_details=mos_out["minimum_cell_size"],
        )
    if mos_body.risk_attributes:
        mos_out["reidentification_risk"] = (
            await deps.mos_risk_scorer.score_reidentification_risk_with_audit(
                mos_body.risk_attributes,
                mos_audit,
                mos_tenantId=mos_tenant,
                mos_actorId=mos_actor,
                mos_queryRequestId=mos_qid,
            )
        )
    await mos_audit.record(
        mos_entityType="governance_check",
        mos_entityId=mos_qid or "adhoc_compliance",
        mos_action="compliance_check_completed",
        mos_actorId=mos_actor,
        mos_tenantId=mos_tenant,
        mos_details={"policy_ids": mos_body.policy_ids},
    )
    return mos_out
