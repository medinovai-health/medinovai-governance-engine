"""Run Temporal worker for query approval (PYTHONPATH=src)."""

from __future__ import annotations

import asyncio
import os

import structlog
from temporalio.client import Client
from temporalio.worker import Worker

from governance.constants import E_MODULE_ID, E_TEMPORAL_TASK_QUEUE
from governance.query_activities import (
    log_query_submission_activity,
    notify_steward_queue_activity,
)
from governance.query_workflow import QueryApprovalWorkflow

mos_logger = structlog.get_logger()


async def mos_run() -> None:
    """Poll Temporal task queue for governance workflows."""
    mos_address = os.environ.get("TEMPORAL_ADDRESS", "localhost:7233")
    mos_client = await Client.connect(
        mos_address,
        namespace=os.environ.get("TEMPORAL_NAMESPACE", "default"),
    )
    mos_worker = Worker(
        mos_client,
        task_queue=E_TEMPORAL_TASK_QUEUE,
        workflows=[QueryApprovalWorkflow],
        activities=[log_query_submission_activity, notify_steward_queue_activity],
    )
    mos_logger.info(
        "temporal_worker_started",
        module_id=E_MODULE_ID,
        category="SYSTEM",
        phi_safe=True,
        task_queue=E_TEMPORAL_TASK_QUEUE,
    )
    await mos_worker.run()


if __name__ == "__main__":
    asyncio.run(mos_run())
