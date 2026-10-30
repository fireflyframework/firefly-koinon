# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Add tenant-owned organization metadata without changing profiles or access grants."""

import sqlalchemy as sa
from alembic import op
from pyfly.data.relational.sqlalchemy import UtcDateTime

revision = "koinon_0022_org_directory"
down_revision = "koinon_0021_mcp_oauth_clients"
branch_labels = None
depends_on = None


def upgrade():
    op.create_index(
        "uq_identity_provider_tenant_id",
        "koinon_identity_providers",
        ["tenant_id", "id"],
        unique=True,
    )
    op.create_table(
        "koinon_organization_units",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column(
            "tenant_id",
            sa.String(64),
            sa.ForeignKey("lattice_tenants.id"),
            nullable=False,
        ),
        sa.Column("parent_id", sa.String(64), nullable=True),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("kind", sa.String(24), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("provider_id", sa.String(64), nullable=True),
        sa.Column("external_key", sa.String(256), nullable=True),
        sa.Column("updated_by", sa.String(512), nullable=False),
        sa.Column("updated_at", UtcDateTime(), nullable=False),
        sa.UniqueConstraint("tenant_id", "id", name="uq_org_unit_tenant_id"),
        sa.UniqueConstraint(
            "tenant_id", "provider_id", "external_key", name="uq_org_unit_source"
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "parent_id"],
            ["koinon_organization_units.tenant_id", "koinon_organization_units.id"],
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "provider_id"],
            ["koinon_identity_providers.tenant_id", "koinon_identity_providers.id"],
        ),
    )
    op.create_index(
        "ix_org_unit_parent", "koinon_organization_units", ["tenant_id", "parent_id"]
    )
    op.create_table(
        "koinon_organization_people",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column(
            "tenant_id",
            sa.String(64),
            sa.ForeignKey("lattice_tenants.id"),
            nullable=False,
        ),
        sa.Column("subject", sa.String(512), nullable=False),
        sa.Column("job_title", sa.String(160), nullable=True),
        sa.Column("unit_id", sa.String(64), nullable=True),
        sa.Column("manager_id", sa.String(64), nullable=True),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("provider_id", sa.String(64), nullable=True),
        sa.Column("external_subject", sa.String(512), nullable=True),
        sa.Column("managed_fields", sa.JSON(), nullable=False),
        sa.Column("pending_manager", sa.Boolean(), nullable=False),
        sa.Column("observed_at", UtcDateTime(), nullable=True),
        sa.Column("observation_status", sa.String(24), nullable=False),
        sa.Column("updated_by", sa.String(512), nullable=False),
        sa.Column("updated_at", UtcDateTime(), nullable=False),
        sa.UniqueConstraint("tenant_id", "id", name="uq_org_person_tenant_id"),
        sa.UniqueConstraint("tenant_id", "subject", name="uq_org_person_subject"),
        sa.ForeignKeyConstraint(
            ["tenant_id", "unit_id"],
            ["koinon_organization_units.tenant_id", "koinon_organization_units.id"],
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "manager_id"],
            ["koinon_organization_people.tenant_id", "koinon_organization_people.id"],
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "provider_id"],
            ["koinon_identity_providers.tenant_id", "koinon_identity_providers.id"],
        ),
    )
    op.create_index(
        "ix_org_person_unit", "koinon_organization_people", ["tenant_id", "unit_id"]
    )
    op.create_index(
        "ix_org_person_manager",
        "koinon_organization_people",
        ["tenant_id", "manager_id"],
    )
    op.create_table(
        "koinon_organization_directory_settings",
        sa.Column(
            "tenant_id",
            sa.String(64),
            sa.ForeignKey("lattice_tenants.id"),
            primary_key=True,
        ),
        sa.Column("visibility", sa.String(32), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("updated_by", sa.String(512), nullable=False),
        sa.Column("updated_at", UtcDateTime(), nullable=False),
    )
    op.create_table(
        "koinon_organization_profile_mappings",
        sa.Column(
            "tenant_id",
            sa.String(64),
            sa.ForeignKey("lattice_tenants.id"),
            primary_key=True,
        ),
        sa.Column("provider_id", sa.String(64), primary_key=True),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("fields_json", sa.JSON(), nullable=False),
        sa.Column("updated_by", sa.String(512), nullable=False),
        sa.Column("updated_at", UtcDateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["tenant_id", "provider_id"],
            ["koinon_identity_providers.tenant_id", "koinon_identity_providers.id"],
        ),
    )


def downgrade():
    raise RuntimeError(
        "Use a reviewed backup/restore recovery plan for organization metadata"
    )
