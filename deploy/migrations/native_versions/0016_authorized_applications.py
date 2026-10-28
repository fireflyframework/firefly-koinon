# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Durable owner application connections and server-controlled credential purpose."""

import sqlalchemy as sa
from alembic import op
from pyfly.data.relational.sqlalchemy import UtcDateTime

revision = "koinon_0016_authorized_apps"
down_revision = "koinon_0015_mcp_authorization"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "koinon_authorized_applications",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("subject", sa.String(512), nullable=False),
        sa.Column("client_id", sa.String(128), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("resource", sa.String(2048), nullable=False),
        sa.Column(
            "tenant_id",
            sa.String(64),
            sa.ForeignKey("lattice_tenants.id"),
            nullable=False,
        ),
        sa.Column("tenant_name", sa.String(255), nullable=False),
        sa.Column("workspace_id", sa.String(64), nullable=False),
        sa.Column("workspace_name", sa.String(255), nullable=False),
        sa.Column("scopes", sa.JSON(), nullable=False),
        sa.Column("connected_at", UtcDateTime(), nullable=False),
        sa.Column("expires_at", UtcDateTime(), nullable=False),
        sa.Column("revoked_at", UtcDateTime(), nullable=True),
        sa.Column("last_used_at", UtcDateTime(), nullable=True),
    )
    for column in ("subject", "tenant_id", "expires_at"):
        op.create_index(
            "ix_koinon_authorized_applications_" + column,
            "koinon_authorized_applications",
            [column],
        )
    with op.batch_alter_table("koinon_personal_tokens") as batch:
        batch.add_column(
            sa.Column(
                "purpose", sa.String(24), nullable=False, server_default="personal"
            )
        )
        batch.add_column(
            sa.Column("authorized_application_id", sa.String(64), nullable=True)
        )
        batch.create_foreign_key(
            "fk_token_authorized_application",
            "koinon_authorized_applications",
            ["authorized_application_id"],
            ["id"],
        )
        batch.create_check_constraint(
            "ck_token_purpose_application",
            "(purpose = 'personal' AND authorized_application_id IS NULL) OR (purpose = 'application' AND authorized_application_id IS NOT NULL)",
        )
        batch.create_index("ix_koinon_personal_tokens_purpose", ["purpose"])
        batch.create_index(
            "ix_koinon_personal_tokens_authorized_application_id",
            ["authorized_application_id"],
        )


def downgrade():
    raise RuntimeError(
        "Use a reviewed backup/restore recovery plan for application connections"
    )
