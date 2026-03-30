"""Temporal client helpers for query approval workflows."""

from __future__ import annotations

import os
import structlog
from temporalio.client import Client

from governance.constants import E_MODULE_ID, E_TEMPORAL_TASK_QUEUE
from governance.query_workflow import QueryApprovalWorkflow

mos_logger = structlog.get_logger()


async def mos_connect_temporal() -> Client | None:
    """Connect to Temporal or return None if unavailable."""
    mos_address = os.environ.get("TEMPORAL_ADDRESS", "localhost:7233")
    try:
        mos_ns = os.environ.get("TEMPORAL_NAMESPACE", "default")
        mos_client = await Client.connect(mos_address, namespace=mos_ns)
        return mos_client
    except Exception as mos_exc:
        mos_logger.warning(
            "temporal_unavailable",
            module_id=E_MODULE_ID,
            category="SYSTEM",
            phi_safe=True,
            error_type=type(mos_exc).__name__,
        )
        return None


async def mos_start_query_workflow(mos_queryId: str, mos_signaturesRequired: int) -> str:
    """Start approval workflow; returns status token."""
    mos_client = await mos_connect_temporal()
    if not mos_client:
        return "local_only"
    mos_wid = f"query-approval-{mos_queryId}"
    await mos_client.start_workflow(
        QueryApprovalWorkflow.run,
        {"query_id": mos_queryId, "signatures_required": mos_signaturesRequired},
        id=mos_wid,
        task_queue=E_TEMPORAL_TASK_QUEUE,
    )
    return "temporal_started"


async def mos_signal_query_workflow(
    mos_queryId: str,
    mos_signal: str,
    mos_actorId: str | None,
) -> None:
    """Send signal to running workflow."""
    mos_client = await mos_connect_temporal()
    if not mos_client:
        return
    mos_wid = f"query-approval-{mos_queryId}"
    mos_handle = mos_client.get_workflow_handle(mos_wid)
    if mos_signal == "sign" and mos_actorId:
        await mos_handle.signal(QueryApprovalWorkflow.submit_signature, mos_actorId)
    elif mos_signal == "finalize_approve":
        await mos_handle.signal(QueryApprovalWorkflow.approve)
    elif mos_signal == "deny":
        await mos_handle.signal(QueryApprovalWorkflow.deny)
