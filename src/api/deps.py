"""Shared service instances for API routes."""

from __future__ import annotations

from governance.dua_manager import DuaManager
from governance.policy_engine import PolicyEngine
from governance.risk_scorer import RiskScorer
from integration.connector_framework import ConnectorRegistry
from integration.evidence_store import EvidenceStoreClient

mos_dua_manager = DuaManager()
mos_policy_engine = PolicyEngine()
mos_risk_scorer = RiskScorer()
mos_evidence_store = EvidenceStoreClient()
mos_connectors = ConnectorRegistry()

# In-memory query submissions (replace with persistence)
mos_query_store: dict[str, dict] = {}
