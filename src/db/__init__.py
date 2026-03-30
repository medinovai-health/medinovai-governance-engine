"""Async PostgreSQL access layer (SQLAlchemy 2.0)."""

from __future__ import annotations

from db.connection import check_db_health, create_engine_and_session_factory, dispose_engine
from db.models import (
    ApprovalRecord,
    Base,
    DataUseAgreement,
    GovernanceAuditEvent,
    GovernancePolicyRecord,
    QueryRequest,
)
from db.repository import ApprovalRepo, AuditRepo, DUARepo, PolicyRepo, QueryRequestRepo

__all__ = [
    "ApprovalRecord",
    "ApprovalRepo",
    "AuditRepo",
    "Base",
    "DataUseAgreement",
    "DUARepo",
    "GovernanceAuditEvent",
    "GovernancePolicyRecord",
    "PolicyRepo",
    "QueryRequest",
    "QueryRequestRepo",
    "check_db_health",
    "create_engine_and_session_factory",
    "dispose_engine",
]
