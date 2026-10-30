# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Private credential-bound external proposals; never a publication by staging."""

import sqlalchemy as sa
from alembic import op
from pyfly.data.relational.sqlalchemy import UtcDateTime

revision = "koinon_0020_external_reviews"
down_revision = "koinon_0019_org_branding"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "koinon_external_knowledge_reviews",
        sa.Column(
            "id",
            sa.String(64),
            sa.ForeignKey("koinon_knowledge_intents.id"),
            primary_key=True,
        ),
        sa.Column(
            "tenant_id",
            sa.String(64),
            sa.ForeignKey("lattice_tenants.id"),
            nullable=False,
        ),
        sa.Column("subject", sa.String(512), nullable=False),
        sa.Column("workspace_id", sa.String(64), nullable=False),
        sa.Column("credential_id", sa.String(64), nullable=False),
        sa.Column("application_id", sa.String(64), nullable=True),
        sa.Column("credential_sha256", sa.String(64), nullable=False),
        sa.Column("stage_key", sa.String(128), nullable=False),
        sa.Column("request_sha256", sa.String(64), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("authorization_digest", sa.String(64), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("nonce_sha256", sa.String(64), nullable=True),
        sa.Column("confirmation_key", sa.String(128), nullable=True),
        sa.Column("created_at", UtcDateTime(), nullable=False),
        sa.Column("expires_at", UtcDateTime(), nullable=False),
        sa.Column("decided_at", UtcDateTime(), nullable=True),
        sa.UniqueConstraint(
            "tenant_id",
            "subject",
            "credential_id",
            "stage_key",
            name="uq_external_review_stage",
        ),
    )
    op.create_index(
        "ix_external_review_owner",
        "koinon_external_knowledge_reviews",
        ["tenant_id", "subject", "status"],
    )
    op.create_table(
        "koinon_external_file_reviews",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("tenant_id", sa.String(64), sa.ForeignKey("lattice_tenants.id"), nullable=False),
        sa.Column("subject", sa.String(512), nullable=False),
        sa.Column("credential_id", sa.String(64), nullable=False),
        sa.Column("application_id", sa.String(64), nullable=True),
        sa.Column("credential_sha256", sa.String(64), nullable=False),
        sa.Column("stage_key", sa.String(128), nullable=False),
        sa.Column("request_json", sa.JSON(), nullable=False),
        sa.Column("destination_json", sa.JSON(), nullable=False),
        sa.Column("authorization_digest", sa.String(64), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("chunks_json", sa.JSON(), nullable=False),
        sa.Column("blob_key", sa.String(255), nullable=True),
        sa.Column("nonce_sha256", sa.String(64), nullable=True),
        sa.Column("confirmation_key", sa.String(128), nullable=True),
        sa.Column("source_id", sa.String(64), nullable=True),
        sa.Column("receipt_json", sa.JSON(), nullable=True),
        sa.Column("gc_status", sa.String(16), nullable=False),
        sa.Column("gc_cursor", sa.Integer(), nullable=False),
        sa.Column("created_at", UtcDateTime(), nullable=False),
        sa.Column("expires_at", UtcDateTime(), nullable=False),
        sa.Column("decided_at", UtcDateTime(), nullable=True),
        sa.UniqueConstraint("tenant_id", "subject", "credential_id", "stage_key", name="uq_external_file_stage"),
    )
    op.create_index("ix_external_file_owner", "koinon_external_file_reviews", ["tenant_id", "subject", "status"])
    op.create_table(
        "koinon_mcp_read_receipts",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("tenant_id", sa.String(64), sa.ForeignKey("lattice_tenants.id"), nullable=False),
        sa.Column("subject", sa.String(512), nullable=False),
        sa.Column("credential_id", sa.String(64), nullable=False),
        sa.Column("application_id", sa.String(64), nullable=True),
        sa.Column("credential_sha256", sa.String(64), nullable=False),
        sa.Column("operation", sa.String(16), nullable=False),
        sa.Column("request_sha256", sa.String(64), nullable=False),
        sa.Column("result_sha256", sa.String(64), nullable=False),
        sa.Column("sources_json", sa.JSON(), nullable=False),
        sa.Column("provenance_json", sa.JSON(), nullable=False),
        sa.Column("receipt_sha256", sa.String(64), nullable=False),
        sa.Column("created_at", UtcDateTime(), nullable=False),
        sa.Column("expires_at", UtcDateTime(), nullable=False),
    )
    op.create_index("ix_mcp_read_receipt_owner", "koinon_mcp_read_receipts", ["tenant_id", "subject", "expires_at"])


def downgrade():
    raise RuntimeError(
        "Preserve review consent and receipts through a reviewed backup/restore recovery plan"
    )
