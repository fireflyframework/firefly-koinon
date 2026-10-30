# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Add organization branding overrides without changing retained organization data."""
import sqlalchemy as sa
from alembic import op
from pyfly.data.relational.sqlalchemy import UtcDateTime

revision = "koinon_0019_org_branding"
down_revision = "koinon_0018_org_knowledge"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "koinon_organization_branding",
        sa.Column("tenant_id", sa.String(64), sa.ForeignKey("lattice_tenants.id"), primary_key=True),
        sa.Column("schema_version", sa.Integer(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("branding_json", sa.Text(), nullable=True),
        sa.Column("updated_by", sa.String(512), nullable=False),
        sa.Column("updated_at", UtcDateTime(), nullable=False),
        sa.CheckConstraint("schema_version = 1", name="ck_org_branding_schema"),
        sa.CheckConstraint("revision >= 1 AND revision <= 2147483647", name="ck_org_branding_revision"),
        sa.CheckConstraint(
            "branding_json IS NULL OR length(branding_json) <= 1572864", name="ck_org_branding_size"
        ),
    )


def downgrade():
    raise RuntimeError("Use a reviewed backup/restore recovery plan for organization branding")
