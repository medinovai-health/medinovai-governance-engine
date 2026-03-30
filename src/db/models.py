"""SQLAlchemy 2.0 async ORM models for governance persistence."""

from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Enum, Float, ForeignKey, String, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Declarative base for governance tables."""


class E_DuaStatus(str, enum.Enum):
    """Lifecycle state for a Data Use Agreement."""

    DRAFT = "draft"
    ACTIVE = "active"
    EXPIRED = "expired"
    REVOKED = "revoked"
    SUSPENDED = "suspended"


class E_QueryRequestStatus(str, enum.Enum):
    """Query approval workflow state."""

    PENDING_REVIEW = "pending_review"
    APPROVED = "approved"
    DENIED = "denied"
    CANCELLED = "cancelled"
    RISK_HOLD = "risk_hold"


class E_ApprovalDecision(str, enum.Enum):
    """Recorded steward decision."""

    APPROVED = "approved"
    DENIED = "denied"
    DELEGATED = "delegated"


class DataUseAgreement(Base):
    """Stored DUA metadata (no PHI in text fields; use IDs in JSON where needed)."""

    __tablename__ = "data_use_agreements"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    institution: Mapped[str] = mapped_column(String(512), default="")
    principal_investigator: Mapped[str] = mapped_column(String(512), default="")
    purpose: Mapped[str] = mapped_column(Text, default="")
    data_categories: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    approved_uses: Mapped[list[Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'[]'::jsonb")
    )
    restrictions: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    start_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[E_DuaStatus] = mapped_column(
        Enum(E_DuaStatus, native_enum=False), nullable=False, default=E_DuaStatus.DRAFT
    )
    tenant_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    created_by: Mapped[str] = mapped_column(String(256), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    query_requests: Mapped[list["QueryRequest"]] = relationship(
        "QueryRequest", back_populates="dua", lazy="selectin"
    )


class QueryRequest(Base):
    """Submitted governed query awaiting or past approval."""

    __tablename__ = "query_requests"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    dua_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("data_use_agreements.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    requester_id: Mapped[str] = mapped_column(String(256), nullable=False)
    query_type: Mapped[str] = mapped_column(String(128), nullable=False, default="cohort")
    query_definition: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    risk_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    status: Mapped[E_QueryRequestStatus] = mapped_column(
        Enum(E_QueryRequestStatus, native_enum=False),
        nullable=False,
        default=E_QueryRequestStatus.PENDING_REVIEW,
        index=True,
    )
    tenant_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    approved_by: Mapped[str | None] = mapped_column(String(256), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    sensitivity_tier: Mapped[str] = mapped_column(String(64), default="standard")
    signatures_required: Mapped[int] = mapped_column(default=1)
    stated_purpose: Mapped[str] = mapped_column(String(512), default="")

    dua: Mapped[DataUseAgreement] = relationship(back_populates="query_requests")
    approval_records: Mapped[list[ApprovalRecord]] = relationship(
        back_populates="query_request", lazy="selectin", cascade="all, delete-orphan"
    )


class ApprovalRecord(Base):
    """Electronic approval / denial record for a query request."""

    __tablename__ = "approval_records"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    query_request_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("query_requests.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    approver_id: Mapped[str] = mapped_column(String(256), nullable=False)
    approver_role: Mapped[str] = mapped_column(String(128), default="steward")
    decision: Mapped[E_ApprovalDecision] = mapped_column(
        Enum(E_ApprovalDecision, native_enum=False), nullable=False
    )
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    signature_hash: Mapped[str | None] = mapped_column(String(128), nullable=True)
    signed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    query_request: Mapped[QueryRequest] = relationship(back_populates="approval_records")


class GovernancePolicyRecord(Base):
    """Registered policy bundles (replaces in-memory policy store)."""

    __tablename__ = "governance_policy_records"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    policy_id: Mapped[str] = mapped_column(
        String(256), nullable=False, unique=True, index=True
    )
    definition: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    tenant_id: Mapped[str] = mapped_column(
        String(128), nullable=False, default="default", index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class GovernanceAuditEvent(Base):
    """Append-only governance audit trail."""

    __tablename__ = "governance_audit_events"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    entity_type: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    entity_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    actor_id: Mapped[str] = mapped_column(String(256), nullable=False, default="system")
    tenant_id: Mapped[str] = mapped_column(
        String(128), nullable=False, default="default", index=True
    )
    details: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
