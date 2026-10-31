# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Organization-owned OAuth registrations and explicit legacy registration gaps."""

import sqlalchemy as sa
from alembic import op
from pyfly.data.relational.sqlalchemy import UtcDateTime

revision = "koinon_0021_mcp_oauth_clients"
down_revision = "koinon_0020_external_reviews"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "koinon_mcp_oauth_clients",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column(
            "tenant_id",
            sa.String(64),
            sa.ForeignKey("lattice_tenants.id"),
            nullable=False,
        ),
        sa.Column("client_id", sa.String(128), nullable=False, unique=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("client_type", sa.String(16), nullable=False),
        sa.Column("redirect_uris", sa.JSON(), nullable=False),
        sa.Column("scopes", sa.JSON(), nullable=False),
        sa.Column("client_secret_hash", sa.String(64), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("created_by", sa.String(512), nullable=False),
        sa.Column("updated_by", sa.String(512), nullable=False),
        sa.Column("created_at", UtcDateTime(), nullable=False),
        sa.Column("updated_at", UtcDateTime(), nullable=False),
        sa.CheckConstraint(
            "revision >= 1 AND revision <= 2147483647", name="ck_mcp_client_revision"
        ),
        sa.CheckConstraint(
            "(client_type = 'public' AND client_secret_hash IS NULL) OR "
            "(client_type = 'confidential' AND client_secret_hash IS NOT NULL)",
            name="ck_mcp_client_authentication",
        ),
    )
    op.create_index(
        "ix_koinon_mcp_oauth_clients_tenant_id",
        "koinon_mcp_oauth_clients",
        ["tenant_id"],
    )
    for table in ("koinon_mcp_authorizations", "koinon_authorized_applications"):
        op.add_column(table, sa.Column("client_registration", sa.JSON(), nullable=True))


def downgrade():
    raise RuntimeError(
        "Use a reviewed backup/restore recovery plan for OAuth application registrations"
    )
