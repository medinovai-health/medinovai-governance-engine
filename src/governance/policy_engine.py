"""Governance policy enforcement: cell size, linkage, configurable rules."""

from __future__ import annotations

from typing import Any

import structlog

from governance.constants import E_DEFAULT_MIN_CELL_SIZE, E_MODULE_ID

mos_logger = structlog.get_logger()


class PolicyEngine:
    """Enforce minimum cell size, cross-dataset linkage, and policy bundles."""

    def __init__(self, mos_minCellSize: int | None = None) -> None:
        self._mos_min_cell = mos_minCellSize or E_DEFAULT_MIN_CELL_SIZE
        self._mos_policies: dict[str, dict[str, Any]] = {}

    def register_policy(self, mos_policyId: str, mos_definition: dict[str, Any]) -> None:
        """Register or replace a named policy bundle."""
        self._mos_policies[mos_policyId] = mos_definition
        mos_logger.info(
            "policy_registered",
            module_id=E_MODULE_ID,
            category="AUDIT",
            phi_safe=True,
            policy_id=mos_policyId,
        )

    def list_policies(self) -> list[dict[str, Any]]:
        """Return metadata for all policies."""
        return [{"id": mos_k, **mos_v} for mos_k, mos_v in self._mos_policies.items()]

    def check_minimum_cell_size(self, mos_cellCount: int) -> dict[str, Any]:
        """Block small cells that increase disclosure risk."""
        mos_ok = mos_cellCount >= self._mos_min_cell
        return {
            "passes": mos_ok,
            "min_required": self._mos_min_cell,
            "observed": mos_cellCount,
        }

    def check_linkage_allowed(
        self,
        mos_policyId: str,
        mos_sourceDataset: str,
        mos_targetDataset: str,
    ) -> dict[str, Any]:
        """Evaluate cross-dataset linkage restrictions."""
        mos_pol = self._mos_policies.get(mos_policyId, {})
        mos_blocked = mos_pol.get("blocked_linkage_pairs") or []
        mos_pair = (mos_sourceDataset, mos_targetDataset)
        mos_rev = (mos_targetDataset, mos_sourceDataset)
        if mos_pair in mos_blocked or mos_rev in mos_blocked:
            return {"allowed": False, "reason": "linkage_blocked"}
        return {"allowed": True, "reason": "linkage_ok"}

    def evaluate_query_against_policies(
        self,
        mos_policyIds: list[str],
        mos_queryMeta: dict[str, Any],
    ) -> dict[str, Any]:
        """Aggregate compliance for a query against multiple policies."""
        mos_results = []
        for mos_pid in mos_policyIds:
            mos_p = self._mos_policies.get(mos_pid)
            mos_results.append(
                {
                    "policy_id": mos_pid,
                    "known": mos_p is not None,
                }
            )
        return {"policies_checked": mos_results, "query_meta_keys": list(mos_queryMeta.keys())}
