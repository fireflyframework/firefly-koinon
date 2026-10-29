# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Organization knowledge policy and nullable, historical-safe run snapshots."""

import sqlalchemy as sa
from alembic import op
from pyfly.data.relational.sqlalchemy import UtcDateTime

revision = "koinon_0018_org_knowledge"
down_revision = "koinon_0017_org_chat"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "koinon_organization_knowledge_settings",
        sa.Column("tenant_id", sa.String(64), sa.ForeignKey("lattice_tenants.id"), primary_key=True),
        sa.Column("schema_version", sa.Integer(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("documents", sa.JSON(), nullable=False),
        sa.Column("structured", sa.JSON(), nullable=False),
        sa.Column("updated_by", sa.String(512), nullable=False),
        sa.Column("updated_at", UtcDateTime(), nullable=False),
        sa.CheckConstraint("schema_version = 1", name="ck_org_knowledge_schema"),
        sa.CheckConstraint("revision >= 1 AND revision <= 2147483647", name="ck_org_knowledge_revision"),
    )
    op.add_column("koinon_chat_runs", sa.Column("knowledge_settings_snapshot", sa.JSON(), nullable=True))


def downgrade():
    raise RuntimeError("Use a reviewed backup/restore recovery plan for organization knowledge settings")
