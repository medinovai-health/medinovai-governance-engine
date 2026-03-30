"""Repositories: DUA, query requests, approvals, audit (tenant-scoped, PHI-safe)."""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone
from typing import Any, Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import (
    ApprovalRecord,
    DataUseAgreement,
    E_ApprovalDecision,
    E_DuaStatus,
    E_QueryRequestStatus,
    GovernanceAuditEvent,
    GovernancePolicyRecord,
    QueryRequest,
)


class AuditRepo:
    """Append governance audit events."""

    def __init__(self, mos_session: AsyncSession) -> None:
        self._mos_session = mos_session

    async def record(
        self,
        *,
        mos_entityType: str,
        mos_entityId: str,
        mos_action: str,
        mos_actorId: str,
        mos_tenantId: str,
        mos_details: dict[str, Any] | None = None,
    ) -> GovernanceAuditEvent:
        """Persist a single audit row (IDs only in details; no PHI)."""
        mos_row = GovernanceAuditEvent(
            entity_type=mos_entityType,
            entity_id=mos_entityId,
            action=mos_action,
            actor_id=mos_actorId,
            tenant_id=mos_tenantId,
            details=mos_details or {},
            timestamp=datetime.now(timezone.utc),
        )
        self._mos_session.add(mos_row)
        await self._mos_session.flush()
        return mos_row


class DUARepo:
    """Data Use Agreement persistence."""

    def __init__(self, mos_session: AsyncSession, mos_audit: AuditRepo) -> None:
        self._mos_session = mos_session
        self._mos_audit = mos_audit

    async def create_from_payload(
        self,
        mos_payload: dict[str, Any],
        *,
        mos_tenantId: str,
        mos_actorId: str,
    ) -> DataUseAgreement:
        """Insert DUA from API JSON (maps legacy and structured fields)."""
        mos_id = mos_payload.get("id")
        mos_uuid = uuid.UUID(str(mos_id)) if mos_id else uuid.uuid4()
        mos_title = str(mos_payload.get("title") or mos_payload.get("dataset_id") or "dua")
        mos_start = _parse_dt(mos_payload.get("effective_from")) or datetime.now(timezone.utc)
        mos_end = _parse_dt(mos_payload.get("expires_at"))
        mos_src = mos_payload.get("permitted_purposes") or mos_payload.get("approved_uses")
        mos_approved = mos_src or []
        if not isinstance(mos_approved, list):
            mos_approved = [mos_approved]
        mos_status = E_DuaStatus.REVOKED if mos_payload.get("revoked") else E_DuaStatus.ACTIVE
        mos_hash = hashlib.sha256(
            json.dumps(mos_payload, sort_keys=True, default=str).encode()
        ).hexdigest()
        mos_restrictions = dict(mos_payload.get("restrictions") or {})
        mos_restrictions["_content_hash"] = mos_hash
        mos_row = DataUseAgreement(
            id=mos_uuid,
            title=mos_title,
            institution=str(mos_payload.get("institution", "")),
            principal_investigator=str(mos_payload.get("principal_investigator", "")),
            purpose=str(mos_payload.get("purpose", "")),
            data_categories=dict(mos_payload.get("data_categories") or {}),
            approved_uses=list(mos_approved),
            restrictions=mos_restrictions,
            start_date=mos_start,
            end_date=mos_end,
            status=mos_status,
            tenant_id=mos_tenantId,
            created_by=mos_actorId,
        )

        self._mos_session.add(mos_row)
        await self._mos_session.flush()
        await self._mos_audit.record(
            mos_entityType="data_use_agreement",
            mos_entityId=str(mos_row.id),
            mos_action="dua_created",
            mos_actorId=mos_actorId,
            mos_tenantId=mos_tenantId,
            mos_details={"title": mos_row.title, "status": mos_row.status.value},
        )
        return mos_row

    async def get_by_id(self, mos_duaId: uuid.UUID) -> DataUseAgreement | None:
        """Load DUA by primary key."""
        mos_res = await self._mos_session.get(DataUseAgreement, mos_duaId)
        return mos_res

    async def get_by_id_str(self, mos_duaId: str) -> DataUseAgreement | None:
        """Load DUA from string id (UUID)."""
        try:
            return await self.get_by_id(uuid.UUID(str(mos_duaId)))
        except ValueError:
            return None

    async def update_status(
        self,
        mos_dua: DataUseAgreement,
        mos_status: E_DuaStatus,
        *,
        mos_actorId: str,
    ) -> DataUseAgreement:
        """Change DUA status with audit."""
        mos_dua.status = mos_status
        mos_dua.updated_at = datetime.now(timezone.utc)
        await self._mos_session.flush()
        await self._mos_audit.record(
            mos_entityType="data_use_agreement",
            mos_entityId=str(mos_dua.id),
            mos_action="dua_status_changed",
            mos_actorId=mos_actorId,
            mos_tenantId=mos_dua.tenant_id,
            mos_details={"status": mos_status.value},
        )
        return mos_dua


class QueryRequestRepo:
    """Query submission and lifecycle."""

    def __init__(self, mos_session: AsyncSession, mos_audit: AuditRepo) -> None:
        self._mos_session = mos_session
        self._mos_audit = mos_audit

    async def create(
        self,
        *,
        mos_duaId: uuid.UUID,
        mos_requesterId: str,
        mos_queryType: str,
        mos_queryDefinition: dict[str, Any],
        mos_riskScore: float | None,
        mos_tenantId: str,
        mos_statedPurpose: str,
        mos_sensitivityTier: str,
        mos_signaturesRequired: int,
        mos_actorId: str,
        mos_id: uuid.UUID | None = None,
    ) -> QueryRequest:
        """Insert pending query with audit."""
        mos_row = QueryRequest(
            id=mos_id or uuid.uuid4(),
            dua_id=mos_duaId,
            requester_id=mos_requesterId,
            query_type=mos_queryType,
            query_definition=mos_queryDefinition,
            risk_score=mos_riskScore,
            status=E_QueryRequestStatus.PENDING_REVIEW,
            tenant_id=mos_tenantId,
            stated_purpose=mos_statedPurpose,
            sensitivity_tier=mos_sensitivityTier,
            signatures_required=mos_signaturesRequired,
        )
        self._mos_session.add(mos_row)
        await self._mos_session.flush()
        await self._mos_audit.record(
            mos_entityType="query_request",
            mos_entityId=str(mos_row.id),
            mos_action="query_submitted",
            mos_actorId=mos_actorId,
            mos_tenantId=mos_tenantId,
            mos_details={"dua_id": str(mos_duaId), "query_type": mos_queryType},
        )
        return mos_row

    async def get(self, mos_queryId: uuid.UUID) -> QueryRequest | None:
        return await self._mos_session.get(QueryRequest, mos_queryId)

    async def get_str(self, mos_queryId: str) -> QueryRequest | None:
        try:
            return await self.get(uuid.UUID(mos_queryId))
        except ValueError:
            return None

    async def list_all(self) -> Sequence[QueryRequest]:
        mos_stmt = select(QueryRequest).order_by(QueryRequest.created_at.desc())
        mos_res = await self._mos_session.execute(mos_stmt)
        return mos_res.scalars().all()

    async def approve(
        self,
        mos_row: QueryRequest,
        *,
        mos_actorId: str,
    ) -> QueryRequest:
        """Mark approved with audit."""
        mos_now = datetime.now(timezone.utc)
        mos_row.status = E_QueryRequestStatus.APPROVED
        mos_row.approved_by = mos_actorId
        mos_row.approved_at = mos_now
        mos_row.rejection_reason = None
        await self._mos_session.flush()
        await self._mos_audit.record(
            mos_entityType="query_request",
            mos_entityId=str(mos_row.id),
            mos_action="query_approved",
            mos_actorId=mos_actorId,
            mos_tenantId=mos_row.tenant_id,
            mos_details={},
        )
        return mos_row

    async def deny(
        self,
        mos_row: QueryRequest,
        *,
        mos_actorId: str,
        mos_reason: str | None,
    ) -> QueryRequest:
        """Mark denied with audit."""
        mos_row.status = E_QueryRequestStatus.DENIED
        mos_row.rejection_reason = mos_reason
        mos_row.approved_by = None
        mos_row.approved_at = None
        await self._mos_session.flush()
        await self._mos_audit.record(
            mos_entityType="query_request",
            mos_entityId=str(mos_row.id),
            mos_action="query_denied",
            mos_actorId=mos_actorId,
            mos_tenantId=mos_row.tenant_id,
            mos_details={"reason_code": mos_reason},
        )
        return mos_row


class ApprovalRepo:
    """Formal approval records (21 CFR Part 11 style metadata; hash only)."""

    def __init__(self, mos_session: AsyncSession, mos_audit: AuditRepo) -> None:
        self._mos_session = mos_session
        self._mos_audit = mos_audit

    async def record_decision(
        self,
        mos_query: QueryRequest,
        *,
        mos_decision: E_ApprovalDecision,
        mos_approverId: str,
        mos_role: str,
        mos_reason: str | None,
        mos_signaturePayload: str,
    ) -> ApprovalRecord:
        """Insert approval row and audit."""
        mos_hash = hashlib.sha256(mos_signaturePayload.encode()).hexdigest()
        mos_row = ApprovalRecord(
            query_request_id=mos_query.id,
            approver_id=mos_approverId,
            approver_role=mos_role,
            decision=mos_decision,
            reason=mos_reason,
            signature_hash=mos_hash,
            signed_at=datetime.now(timezone.utc),
        )
        self._mos_session.add(mos_row)
        await self._mos_session.flush()
        await self._mos_audit.record(
            mos_entityType="approval_record",
            mos_entityId=str(mos_row.id),
            mos_action="approval_recorded",
            mos_actorId=mos_approverId,
            mos_tenantId=mos_query.tenant_id,
            mos_details={
                "query_request_id": str(mos_query.id),
                "decision": mos_decision.value,
            },
        )
        return mos_row


class PolicyRepo:
    """Persist registered governance policies."""

    def __init__(self, mos_session: AsyncSession, mos_audit: AuditRepo) -> None:
        self._mos_session = mos_session
        self._mos_audit = mos_audit

    async def upsert(
        self,
        mos_policyId: str,
        mos_definition: dict[str, Any],
        *,
        mos_tenantId: str,
        mos_actorId: str,
    ) -> GovernancePolicyRecord:
        """Create or replace policy by policy_id."""
        mos_stmt = select(GovernancePolicyRecord).where(
            GovernancePolicyRecord.policy_id == mos_policyId
        )
        mos_existing = (await self._mos_session.execute(mos_stmt)).scalar_one_or_none()
        if mos_existing:
            mos_existing.definition = mos_definition
            mos_existing.tenant_id = mos_tenantId
            mos_existing.updated_at = datetime.now(timezone.utc)
            mos_row = mos_existing
            mos_action = "policy_updated"
        else:
            mos_row = GovernancePolicyRecord(
                policy_id=mos_policyId,
                definition=mos_definition,
                tenant_id=mos_tenantId,
            )
            self._mos_session.add(mos_row)
            mos_action = "policy_registered"
        await self._mos_session.flush()
        await self._mos_audit.record(
            mos_entityType="governance_policy",
            mos_entityId=mos_policyId,
            mos_action=mos_action,
            mos_actorId=mos_actorId,
            mos_tenantId=mos_tenantId,
            mos_details={"policy_id": mos_policyId},
        )
        return mos_row

    async def list_all(self) -> Sequence[GovernancePolicyRecord]:
        mos_stmt = select(GovernancePolicyRecord).order_by(GovernancePolicyRecord.policy_id)
        mos_res = await self._mos_session.execute(mos_stmt)
        return mos_res.scalars().all()


def _parse_dt(mos_val: Any) -> datetime | None:
    if mos_val is None:
        return None
    if isinstance(mos_val, datetime):
        return mos_val if mos_val.tzinfo else mos_val.replace(tzinfo=timezone.utc)
    if isinstance(mos_val, str):
        return datetime.fromisoformat(mos_val.replace("Z", "+00:00"))
    return None
