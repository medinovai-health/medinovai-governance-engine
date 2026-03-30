"""Temporal activities: DB-backed hooks (QueryRequestRepo / ApprovalRepo alignment)."""

from __future__ import annotations

import structlog
from temporalio import activity

from db.repository import AuditRepo, QueryRequestRepo
from governance.activity_context import mos_activity_session_factory
from governance.constants import E_MODULE_ID

mos_logger = structlog.get_logger()


@activity.defn
async def ensure_query_request_activity(mos_queryId: str) -> None:
    """Verify the query row exists before the workflow proceeds (route must insert first)."""
    if mos_activity_session_factory is None:
        mos_logger.warning(
            "activity_no_db",
            module_id=E_MODULE_ID,
            category="SYSTEM",
            phi_safe=True,
            query_id=mos_queryId,
        )
        return
    async with mos_activity_session_factory() as mos_session:
        mos_audit = AuditRepo(mos_session)
        mos_qrepo = QueryRequestRepo(mos_session, mos_audit)
        mos_row = await mos_qrepo.get_str(mos_queryId)
        if mos_row is None:
            raise RuntimeError("query_request_not_found_for_workflow")
        await mos_audit.record(
            mos_entityType="query_request",
            mos_entityId=mos_queryId,
            mos_action="workflow_started",
            mos_actorId="temporal",
            mos_tenantId=mos_row.tenant_id,
            mos_details={},
        )
        await mos_session.commit()


@activity.defn
async def log_query_submission_activity(mos_queryId: str) -> None:
    """Legacy hook: log that submission reached the worker (audit if DB available)."""
    mos_logger.info(
        "query_submission_logged",
        module_id=E_MODULE_ID,
        category="AUDIT",
        phi_safe=True,
        query_id=mos_queryId,
    )


@activity.defn
async def notify_steward_queue_activity(mos_queryId: str) -> None:
    """Placeholder for outbound notifications (IDs only)."""
    mos_logger.info(
        "steward_queue_notify",
        module_id=E_MODULE_ID,
        category="BUSINESS",
        phi_safe=True,
        query_id=mos_queryId,
    )
