"""Governance policies and aggregate compliance checks."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from api import deps

router = APIRouter(prefix="/api/v1/governance", tags=["governance"])


class PolicyRegisterBody(BaseModel):
    policy_id: str
    definition: dict[str, Any] = Field(default_factory=dict)


class GovernanceComplianceBody(BaseModel):
    policy_ids: list[str]
    query_meta: dict[str, Any] = Field(default_factory=dict)
    cell_count: int | None = None
    risk_attributes: dict[str, Any] | None = None


def _engines() -> tuple[Any, Any]:
    return deps.mos_policy_engine, deps.mos_risk_scorer


@router.get("/policies")
async def policies_list() -> dict[str, Any]:
    """List registered governance policies."""
    return {"policies": deps.mos_policy_engine.list_policies()}


@router.post("/policies")
async def policies_register(mos_body: PolicyRegisterBody) -> dict[str, Any]:
    """Register or update a policy bundle."""
    deps.mos_policy_engine.register_policy(mos_body.policy_id, mos_body.definition)
    return {"id": mos_body.policy_id, "status": "registered"}


@router.post("/check-compliance")
async def governance_check_compliance(mos_body: GovernanceComplianceBody) -> dict[str, Any]:
    """Run policy bundle checks, optional cell size and risk scoring."""
    mos_policy, mos_risk = _engines()
    mos_out: dict[str, Any] = {
        "policies": mos_policy.evaluate_query_against_policies(
            mos_body.policy_ids,
            mos_body.query_meta,
        ),
    }
    if mos_body.cell_count is not None:
        mos_out["minimum_cell_size"] = mos_policy.check_minimum_cell_size(mos_body.cell_count)
    if mos_body.risk_attributes:
        mos_out["reidentification_risk"] = mos_risk.score_reidentification_risk(
            mos_body.risk_attributes
        )
    return mos_out
