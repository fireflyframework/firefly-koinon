# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Persist explicit knowledge roles without moving credentials or existing domain data."""
import sqlalchemy as sa
from alembic import op
from pyfly.data.relational.sqlalchemy.types import UtcDateTime

revision = "koinon_0007_knowledge_bindings"
down_revision = "koinon_0006_connections"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "koinon_knowledge_connections",
        sa.Column("id", sa.String(64), nullable=False),
        sa.Column("tenant_id", sa.String(64), nullable=False),
        sa.Column("workspace_id", sa.String(64), nullable=True),
        sa.Column("scope_key", sa.String(64), nullable=False, server_default=""),
        sa.Column("domain", sa.String(32), nullable=False),
        sa.Column("role", sa.String(64), nullable=False),
        sa.Column("mode", sa.String(24), nullable=False),
        sa.Column("provider_id", sa.String(64), nullable=True),
        sa.Column("model_id", sa.String(255), nullable=True),
        sa.Column("model_options", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("dimensions", sa.Integer(), nullable=True),
        sa.Column("storage_dimensions", sa.Integer(), nullable=True),
        sa.Column("space_id", sa.String(256), nullable=True),
        sa.Column("embedding_fingerprint", sa.String(64), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("revision", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_by", sa.String(512), nullable=False),
        sa.Column("updated_by", sa.String(512), nullable=False),
        sa.Column("created_at", UtcDateTime(), nullable=False),
        sa.Column("updated_at", UtcDateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["tenant_id"], ["lattice_tenants.id"]),
        sa.ForeignKeyConstraint(["workspace_id"], ["lattice_catalog.id"]),
        sa.ForeignKeyConstraint(["provider_id"], ["koinon_providers.id"]),
        sa.UniqueConstraint("tenant_id", "scope_key", "domain", "role", name="uq_koinon_knowledge_role"),
        sa.CheckConstraint("scope_key = coalesce(workspace_id, '')", name="ck_koinon_knowledge_scope"),
        sa.CheckConstraint("mode in ('provider', 'current_agent')", name="ck_koinon_knowledge_mode"),
    )
    op.create_index("ix_koinon_knowledge_connections_tenant_id", "koinon_knowledge_connections", ["tenant_id"])
    op.create_index("ix_koinon_knowledge_connections_workspace_id", "koinon_knowledge_connections", ["workspace_id"])


def downgrade():
    raise RuntimeError("Use a reviewed backup/restore recovery plan for knowledge connections")
