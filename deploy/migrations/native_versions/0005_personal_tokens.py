# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Persist scoped personal tokens and immutable chat presentation metadata."""

import sqlalchemy as sa
from alembic import op
from pyfly.data.relational.sqlalchemy import UtcDateTime

revision = "koinon_0005_personal_tokens"
down_revision = "koinon_0004_profiles"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "koinon_personal_tokens",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("subject", sa.String(512), nullable=False),
        sa.Column(
            "tenant_id",
            sa.String(64),
            sa.ForeignKey("lattice_tenants.id"),
            nullable=False,
        ),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("prefix", sa.String(64), nullable=False),
        sa.Column("scopes", sa.JSON(), nullable=False),
        sa.Column("workspace_ids", sa.JSON(), nullable=True),
        sa.Column("asset_ids", sa.JSON(), nullable=True),
        sa.Column("resource_ids", sa.JSON(), nullable=True),
        sa.Column("expires_at", UtcDateTime(), nullable=False),
        sa.Column("revoked_at", UtcDateTime(), nullable=True),
        sa.Column("last_used_at", UtcDateTime(), nullable=True),
        sa.Column("created_at", UtcDateTime(), nullable=False),
    )
    op.create_index(
        "ix_koinon_personal_tokens_subject", "koinon_personal_tokens", ["subject"]
    )
    op.create_index(
        "ix_koinon_personal_tokens_tenant_id", "koinon_personal_tokens", ["tenant_id"]
    )
    op.add_column(
        "koinon_chat_runs", sa.Column("access_token_id", sa.String(64), nullable=True)
    )
    op.add_column(
        "koinon_chat_messages",
        sa.Column("presentation", sa.JSON(), nullable=False, server_default="{}"),
    )
    op.alter_column("koinon_chat_messages", "presentation", server_default=None)


def downgrade():
    raise RuntimeError(
        "Use a reviewed backup/restore recovery plan for personal tokens"
    )
