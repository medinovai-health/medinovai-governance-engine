"""Pluggable connectors for governed query execution (post-approval)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

import structlog

from governance.constants import E_MODULE_ID

mos_logger = structlog.get_logger()


class QueryExecutionConnector(ABC):
    """Execute or dispatch an approved query through a governed backend."""

    @abstractmethod
    async def execute(
        self,
        mos_querySpec: dict[str, Any],
        mos_governanceContext: dict[str, Any],
    ) -> dict[str, Any]:
        """Run approved query; context carries DUA ids, policy version, lineage refs."""


class StubConnector(QueryExecutionConnector):
    """No-op connector for local development."""

    async def execute(
        self,
        mos_querySpec: dict[str, Any],
        mos_governanceContext: dict[str, Any],
    ) -> dict[str, Any]:
        mos_logger.info(
            "connector_stub_execute",
            module_id=E_MODULE_ID,
            category="SYSTEM",
            phi_safe=True,
            keys=list(mos_querySpec.keys()),
        )
        return {"status": "stub", "governance_keys": list(mos_governanceContext.keys())}


class ConnectorRegistry:
    """Register named connectors (OMOP, FHIR export engine, cohort SQL, etc.)."""

    def __init__(self) -> None:
        self._mos_connectors: dict[str, QueryExecutionConnector] = {
            "stub": StubConnector(),
        }

    def register(self, mos_name: str, mos_connector: QueryExecutionConnector) -> None:
        self._mos_connectors[mos_name] = mos_connector

    def get(self, mos_name: str) -> QueryExecutionConnector | None:
        return self._mos_connectors.get(mos_name)
