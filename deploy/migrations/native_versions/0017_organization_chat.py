# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Persistent organization chat defaults, independent of conversation lifecycle."""
import sqlalchemy as sa
from alembic import op
from pyfly.data.relational.sqlalchemy import UtcDateTime

revision = "koinon_0017_org_chat"
down_revision = "koinon_0016_authorized_apps"
branch_labels = None
depends_on = None


def upgrade():
    op.create_index("uq_koinon_agents_tenant_id", "koinon_agents", ["tenant_id", "id"], unique=True)
    op.create_table(
        "koinon_organization_chat_settings",
        sa.Column("tenant_id", sa.String(64), sa.ForeignKey("lattice_tenants.id"), primary_key=True),
        sa.Column("default_agent_id", sa.String(64), nullable=True),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("updated_by", sa.String(512), nullable=False),
        sa.Column("updated_at", UtcDateTime(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id", "default_agent_id"], ["koinon_agents.tenant_id", "koinon_agents.id"],
                                name="fk_org_chat_tenant_agent"),
        sa.CheckConstraint("revision >= 1 AND revision <= 2147483647", name="ck_org_chat_revision"),
    )


def downgrade():
    raise RuntimeError("Use a reviewed backup/restore recovery plan for organization chat settings")
