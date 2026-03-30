"""Re-identification risk scoring (heuristic scaffold for approved workflows)."""

from __future__ import annotations

import math
from typing import Any

import structlog

from governance.constants import E_MODULE_ID

mos_logger = structlog.get_logger()


class RiskScorer:
    """Compute a bounded risk score from query and cohort attributes."""

    def score_reidentification_risk(self, mos_attributes: dict[str, Any]) -> dict[str, Any]:
        """Return score in [0,1] plus contributing factors (no PHI in logs)."""
        mos_quasi = int(mos_attributes.get("quasi_identifier_count") or 0)
        mos_rare = float(mos_attributes.get("rare_combination_weight") or 0.0)
        mos_geo = 1.0 if mos_attributes.get("includes_fine_geo") else 0.0
        mos_raw = 0.15 * mos_quasi + 0.35 * min(mos_rare, 1.0) + 0.25 * mos_geo
        mos_score = max(0.0, min(1.0, 1.0 - math.exp(-mos_raw)))
        mos_logger.info(
            "risk_scored",
            module_id=E_MODULE_ID,
            category="CLINICAL",
            phi_safe=True,
            quasi_identifiers=mos_quasi,
            risk_band=self._band(mos_score),
        )
        return {
            "score": round(mos_score, 4),
            "band": self._band(mos_score),
            "factors": {
                "quasi_identifier_count": mos_quasi,
                "rare_combination_weight": mos_rare,
                "includes_fine_geo": bool(mos_geo),
            },
        }

    @staticmethod
    def _band(mos_score: float) -> str:
        if mos_score < 0.25:
            return "low"
        if mos_score < 0.5:
            return "medium"
        if mos_score < 0.75:
            return "high"
        return "critical"
