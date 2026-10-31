# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Tenant-bound corporate presentation with retained personal profiles."""

import sqlalchemy as sa
from alembic import op
from pyfly.data.relational.sqlalchemy import UtcDateTime

revision = "koinon_0023_ciam_profiles"
down_revision = "koinon_0022_org_directory"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "koinon_organization_profile_mappings",
        sa.Column("profile_sync_json", sa.JSON(), nullable=True),
    )
    op.create_table(
        "koinon_corporate_profile_snapshots",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column(
            "tenant_id",
            sa.String(64),
            sa.ForeignKey("lattice_tenants.id"),
            nullable=False,
        ),
        sa.Column("subject", sa.String(512), nullable=False),
        sa.Column("provider_id", sa.String(64), nullable=True),
        sa.Column("external_subject", sa.String(512), nullable=True),
        sa.Column("source_fingerprint", sa.String(64), nullable=False),
        sa.Column("verified_domain", sa.String(253), nullable=True),
        sa.Column("verified_external_tenant", sa.String(64), nullable=True),
        sa.Column("binding_revision", sa.Integer(), nullable=False),
        sa.Column("provider_revision", sa.Integer(), nullable=False),
        sa.Column("mapping_revision", sa.Integer(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("display_name", sa.String(256), nullable=True),
        sa.Column("name_available", sa.Boolean(), nullable=False),
        sa.Column("department", sa.String(160), nullable=True),
        sa.Column("avatar_bytes", sa.LargeBinary(), nullable=True),
        sa.Column("avatar_version", sa.String(64), nullable=True),
        sa.Column("avatar_available", sa.Boolean(), nullable=False),
        sa.Column("fields_json", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("last_attempt_at", UtcDateTime(), nullable=True),
        sa.Column("last_success_at", UtcDateTime(), nullable=True),
        sa.Column("next_due_at", UtcDateTime(), nullable=False),
        sa.Column("worker_id", sa.String(64), nullable=True),
        sa.Column("lease_until", UtcDateTime(), nullable=True),
        sa.Column("lease_generation", sa.Integer(), nullable=False),
        sa.Column("claims_observed_at", UtcDateTime(), nullable=True),
        sa.Column("verified_at", UtcDateTime(), nullable=False),
        sa.Column("updated_at", UtcDateTime(), nullable=False),
        sa.CheckConstraint(
            "(provider_id IS NOT NULL AND external_subject IS NOT NULL) OR "
            "(provider_id IS NULL AND external_subject IS NULL AND status = 'conflict')",
            name="ck_corporate_profile_binding",
        ),
        sa.UniqueConstraint("tenant_id", "subject", name="uq_corporate_profile_owner"),
        sa.UniqueConstraint(
            "tenant_id",
            "provider_id",
            "external_subject",
            name="uq_corporate_profile_external",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "provider_id"],
            ["koinon_identity_providers.tenant_id", "koinon_identity_providers.id"],
        ),
    )
    op.create_index(
        "ix_corporate_profile_due",
        "koinon_corporate_profile_snapshots",
        ["next_due_at", "lease_until"],
    )
    op.create_table(
        "koinon_organization_presentation_preferences",
        sa.Column(
            "tenant_id",
            sa.String(64),
            sa.ForeignKey("lattice_tenants.id"),
            primary_key=True,
        ),
        sa.Column("subject", sa.String(512), primary_key=True),
        sa.Column("name_mode", sa.String(24), nullable=False),
        sa.Column("avatar_mode", sa.String(24), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("updated_at", UtcDateTime(), nullable=False),
    )


def downgrade():
    raise RuntimeError(
        "Use a reviewed backup/restore recovery plan for corporate presentation"
    )
