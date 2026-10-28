# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Persist hashed single-use MCP authorization codes and explicit consent context."""

import sqlalchemy as sa
from alembic import op
from pyfly.data.relational.sqlalchemy import UtcDateTime

revision = "koinon_0015_mcp_authorization"
down_revision = "koinon_0014_curated_knowledge"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "koinon_mcp_authorizations",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("subject", sa.String(512), nullable=False),
        sa.Column("client_id", sa.String(128), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("request_json", sa.JSON(), nullable=False),
        sa.Column("grant_json", sa.JSON(), nullable=True),
        sa.Column("code_hash", sa.String(64), nullable=True, unique=True),
        sa.Column("expires_at", UtcDateTime(), nullable=False),
        sa.Column("created_at", UtcDateTime(), nullable=False),
    )
    for column in ("subject", "expires_at"):
        op.create_index("ix_koinon_mcp_authorizations_" + column, "koinon_mcp_authorizations", [column])


def downgrade():
    raise RuntimeError("Use a reviewed backup/restore recovery plan for MCP authorizations")
