# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Bounded private reviews and immutable authenticated export/share records."""

import sqlalchemy as sa
from alembic import op
from pyfly.data.relational.sqlalchemy.types import UtcDateTime

revision = "koinon_0013_exports_shares"
down_revision = "koinon_0012_chat_attachments"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "koinon_evidence_reviews",
        sa.Column("id", sa.String(64), primary_key=True, nullable=False),
        sa.Column(
            "tenant_id",
            sa.String(64),
            sa.ForeignKey("lattice_tenants.id"),
            nullable=False,
        ),
        sa.Column("owner_subject", sa.String(512), nullable=False),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("revision", sa.String(64), nullable=False),
        sa.Column("request_json", sa.JSON(), nullable=False),
        sa.Column("snapshot_json", sa.JSON(), nullable=False),
        sa.Column("manifest_json", sa.JSON(), nullable=False),
        sa.Column("creator_token_id", sa.String(64), nullable=True),
        sa.Column("created_at", UtcDateTime(), nullable=False),
        sa.Column("expires_at", UtcDateTime(), nullable=False),
        sa.Column("consumed_at", UtcDateTime(), nullable=True),
    )
    op.create_index(
        "ix_koinon_review_owner_expiry",
        "koinon_evidence_reviews",
        ["tenant_id", "owner_subject", "expires_at"],
    )
    for table, index, ended in (
        ("koinon_exports", "ix_koinon_export_owner_expiry", "cancelled_at"),
        ("koinon_conversation_shares", "ix_koinon_share_owner_expiry", "revoked_at"),
    ):
        op.create_table(
            table,
            sa.Column("id", sa.String(64), primary_key=True, nullable=False),
            sa.Column(
                "review_id",
                sa.String(64),
                sa.ForeignKey("koinon_evidence_reviews.id"),
                unique=True,
                nullable=False,
            ),
            sa.Column(
                "tenant_id",
                sa.String(64),
                sa.ForeignKey("lattice_tenants.id"),
                nullable=False,
            ),
            sa.Column("owner_subject", sa.String(512), nullable=False),
            sa.Column("created_at", UtcDateTime(), nullable=False),
            sa.Column("expires_at", UtcDateTime(), nullable=False),
            sa.Column(ended, UtcDateTime(), nullable=True),
        )
        op.create_index(index, table, ["tenant_id", "owner_subject", "expires_at"])


def downgrade():
    raise RuntimeError(
        "Use a reviewed backup/restore recovery plan for private evidence snapshots"
    )
