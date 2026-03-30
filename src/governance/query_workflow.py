"""Temporal workflow for query approval (deterministic workflow code only)."""

from __future__ import annotations

from datetime import timedelta

from temporalio import workflow

with workflow.unsafe.imports_passed_through():
    from governance.constants import E_QUERY_WORKFLOW_NAME


@workflow.defn(name=E_QUERY_WORKFLOW_NAME)
class QueryApprovalWorkflow:
    """Review queue: wait for steward decision; supports multi-signature gate."""

    def __init__(self) -> None:
        self._mos_decision: str | None = None
        self._mos_signatures: list[str] = []
        self._mos_required_sigs = 1

    @workflow.run
    async def run(self, mos_payload: dict) -> dict:
        """Drive approval from submission to terminal state."""
        self._mos_required_sigs = int(mos_payload.get("signatures_required") or 1)
        mos_query_id = str(mos_payload.get("query_id", ""))
        await workflow.wait_condition(
            lambda: self._mos_decision is not None,
            timeout=timedelta(days=30),
        )
        return {
            "query_id": mos_query_id,
            "decision": self._mos_decision,
            "signatures": list(self._mos_signatures),
        }

    @workflow.signal
    def submit_signature(self, mos_actorId: str) -> None:
        """Record an electronic signature event reference (actor id only, no PHI)."""
        if mos_actorId not in self._mos_signatures:
            self._mos_signatures.append(mos_actorId)

    @workflow.signal
    def approve(self) -> None:
        """Steward approval path."""
        if len(self._mos_signatures) >= self._mos_required_sigs:
            self._mos_decision = "approved"

    @workflow.signal
    def deny(self) -> None:
        """Steward denial path."""
        self._mos_decision = "denied"
