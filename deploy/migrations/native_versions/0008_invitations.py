# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Add hashed, expiring, single-use invitation grants without altering memberships."""

import sqlalchemy as sa
from alembic import op
from pyfly.data.relational.sqlalchemy.types import UtcDateTime

revision = "koinon_0008_invitations"
down_revision = "koinon_0007_knowledge_bindings"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "koinon_invitations",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column(
            "tenant_id",
            sa.String(64),
            sa.ForeignKey("lattice_tenants.id"),
            nullable=False,
        ),
        sa.Column(
            "workspace_id",
            sa.String(64),
            sa.ForeignKey("lattice_catalog.id"),
            nullable=True,
        ),
        sa.Column("role", sa.String(32), nullable=False),
        sa.Column("label", sa.String(120), nullable=False, server_default=""),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("created_by", sa.String(512), nullable=False),
        sa.Column("created_at", UtcDateTime(), nullable=False),
        sa.Column("expires_at", UtcDateTime(), nullable=False),
        sa.Column("revoked_at", UtcDateTime(), nullable=True),
        sa.Column("accepted_at", UtcDateTime(), nullable=True),
        sa.Column("accepted_by", sa.String(512), nullable=True),
    )
    op.create_index(
        "ix_koinon_invitations_tenant_id", "koinon_invitations", ["tenant_id"]
    )


def downgrade():
    raise RuntimeError("Use a reviewed backup/restore recovery plan for invitations")
