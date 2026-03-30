"""Initial governance schema (DUA, queries, approvals, policies, audit).

Revision ID: 20260330_0001
Revises:
Create Date: 2026-03-30

"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260330_0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "data_use_agreements",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(length=512), nullable=False),
        sa.Column("institution", sa.String(length=512), nullable=False),
        sa.Column("principal_investigator", sa.String(length=512), nullable=False),
        sa.Column("purpose", sa.Text(), nullable=False),
        sa.Column(
            "data_categories",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "approved_uses",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "restrictions",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("start_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("tenant_id", sa.String(length=128), nullable=False),
        sa.Column("created_by", sa.String(length=256), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_data_use_agreements_tenant_id", "data_use_agreements", ["tenant_id"], unique=False)

    op.create_table(
        "governance_policy_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("policy_id", sa.String(length=256), nullable=False),
        sa.Column(
            "definition",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("tenant_id", sa.String(length=128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("policy_id"),
    )
    op.create_index(
        "ix_governance_policy_records_policy_id", "governance_policy_records", ["policy_id"], unique=False
    )
    op.create_index(
        "ix_governance_policy_records_tenant_id", "governance_policy_records", ["tenant_id"], unique=False
    )

    op.create_table(
        "query_requests",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("dua_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("requester_id", sa.String(length=256), nullable=False),
        sa.Column("query_type", sa.String(length=128), nullable=False),
        sa.Column(
            "query_definition",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("risk_score", sa.Float(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("tenant_id", sa.String(length=128), nullable=False),
        sa.Column("approved_by", sa.String(length=256), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rejection_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("sensitivity_tier", sa.String(length=64), nullable=False),
        sa.Column("signatures_required", sa.Integer(), nullable=False),
        sa.Column("stated_purpose", sa.String(length=512), nullable=False),
        sa.ForeignKeyConstraint(["dua_id"], ["data_use_agreements.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_query_requests_dua_id", "query_requests", ["dua_id"], unique=False)
    op.create_index("ix_query_requests_status", "query_requests", ["status"], unique=False)
    op.create_index("ix_query_requests_tenant_id", "query_requests", ["tenant_id"], unique=False)

    op.create_table(
        "approval_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("query_request_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("approver_id", sa.String(length=256), nullable=False),
        sa.Column("approver_role", sa.String(length=128), nullable=False),
        sa.Column("decision", sa.String(length=32), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("signature_hash", sa.String(length=128), nullable=True),
        sa.Column("signed_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["query_request_id"], ["query_requests.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_approval_records_query_request_id", "approval_records", ["query_request_id"], unique=False
    )

    op.create_table(
        "governance_audit_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("entity_type", sa.String(length=128), nullable=False),
        sa.Column("entity_id", sa.String(length=128), nullable=False),
        sa.Column("action", sa.String(length=128), nullable=False),
        sa.Column("actor_id", sa.String(length=256), nullable=False),
        sa.Column("tenant_id", sa.String(length=128), nullable=False),
        sa.Column(
            "details",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("timestamp", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_governance_audit_events_action", "governance_audit_events", ["action"], unique=False)
    op.create_index(
        "ix_governance_audit_events_entity_type", "governance_audit_events", ["entity_type"], unique=False
    )
    op.create_index("ix_governance_audit_events_entity_id", "governance_audit_events", ["entity_id"], unique=False)
    op.create_index("ix_governance_audit_events_tenant_id", "governance_audit_events", ["tenant_id"], unique=False)
    op.create_index("ix_governance_audit_events_timestamp", "governance_audit_events", ["timestamp"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_governance_audit_events_timestamp", table_name="governance_audit_events")
    op.drop_index("ix_governance_audit_events_tenant_id", table_name="governance_audit_events")
    op.drop_index("ix_governance_audit_events_entity_id", table_name="governance_audit_events")
    op.drop_index("ix_governance_audit_events_entity_type", table_name="governance_audit_events")
    op.drop_index("ix_governance_audit_events_action", table_name="governance_audit_events")
    op.drop_table("governance_audit_events")
    op.drop_index("ix_approval_records_query_request_id", table_name="approval_records")
    op.drop_table("approval_records")
    op.drop_index("ix_query_requests_tenant_id", table_name="query_requests")
    op.drop_index("ix_query_requests_status", table_name="query_requests")
    op.drop_index("ix_query_requests_dua_id", table_name="query_requests")
    op.drop_table("query_requests")
    op.drop_index("ix_governance_policy_records_tenant_id", table_name="governance_policy_records")
    op.drop_index("ix_governance_policy_records_policy_id", table_name="governance_policy_records")
    op.drop_table("governance_policy_records")
    op.drop_index("ix_data_use_agreements_tenant_id", table_name="data_use_agreements")
    op.drop_table("data_use_agreements")
