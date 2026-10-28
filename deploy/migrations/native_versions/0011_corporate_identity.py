# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Separate corporate access policy and expiring grants from preserved manual memberships."""

import sqlalchemy as sa
from alembic import op
from pyfly.data.relational.sqlalchemy.types import UtcDateTime

revision = "koinon_0011_corporate_identity"
down_revision = "koinon_0010_knowledge_indexes"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "koinon_identity_providers",
        sa.Column("id", sa.String(64), primary_key=True, nullable=False),
        sa.Column("tenant_id", sa.String(64), sa.ForeignKey("lattice_tenants.id"), nullable=False),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("canonical_issuer", sa.String(2048), nullable=False),
        sa.Column("broker_alias", sa.String(64), nullable=True),
        sa.Column("source_key", sa.String(64), nullable=False),
        sa.Column("settings_json", sa.JSON(), nullable=False),
        sa.Column("secret_ciphertext", sa.LargeBinary(), nullable=True),
        sa.Column("credential_reference", sa.String(120), nullable=True),
        sa.Column("ownership", sa.String(24), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("policy_revision", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("checks_json", sa.JSON(), nullable=False),
        sa.Column("observed_at", UtcDateTime(), nullable=True),
        sa.Column("created_by", sa.String(512), nullable=False),
        sa.Column("updated_by", sa.String(512), nullable=False),
        sa.Column("created_at", UtcDateTime(), nullable=False),
        sa.Column("updated_at", UtcDateTime(), nullable=False),
        sa.UniqueConstraint("tenant_id", "source_key", name="uq_koinon_identity_source"),
    )
    op.create_index("ix_koinon_identity_providers_tenant_id", "koinon_identity_providers", ["tenant_id"])
    op.create_table(
        "koinon_identity_mappings",
        sa.Column("id", sa.String(64), primary_key=True, nullable=False),
        sa.Column("tenant_id", sa.String(64), sa.ForeignKey("lattice_tenants.id"), nullable=False),
        sa.Column(
            "provider_id", sa.String(64), sa.ForeignKey("koinon_identity_providers.id"), nullable=False
        ),
        sa.Column("group_id", sa.String(256), nullable=False),
        sa.Column("group_name", sa.String(255), nullable=False),
        sa.Column("role", sa.String(32), nullable=False),
        sa.Column("workspace_id", sa.String(64), sa.ForeignKey("lattice_catalog.id"), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
    )
    op.create_index("ix_koinon_identity_mappings_provider_id", "koinon_identity_mappings", ["provider_id"])
    op.create_index("ix_koinon_identity_mappings_tenant_id", "koinon_identity_mappings", ["tenant_id"])
    op.create_table(
        "koinon_identity_grants",
        sa.Column("id", sa.String(64), primary_key=True, nullable=False),
        sa.Column("tenant_id", sa.String(64), sa.ForeignKey("lattice_tenants.id"), nullable=False),
        sa.Column(
            "provider_id", sa.String(64), sa.ForeignKey("koinon_identity_providers.id"), nullable=False
        ),
        sa.Column("mapping_id", sa.String(64), sa.ForeignKey("koinon_identity_mappings.id"), nullable=False),
        sa.Column("subject", sa.String(512), nullable=False),
        sa.Column("external_subject", sa.String(512), nullable=False),
        sa.Column("workspace_id", sa.String(64), sa.ForeignKey("lattice_catalog.id"), nullable=True),
        sa.Column("role", sa.String(32), nullable=False),
        sa.Column("policy_revision", sa.Integer(), nullable=False),
        sa.Column("mapping_revision", sa.Integer(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("observed_at", UtcDateTime(), nullable=False),
        sa.Column("expires_at", UtcDateTime(), nullable=False),
        sa.UniqueConstraint("provider_id", "subject", "mapping_id", name="uq_koinon_managed_grant"),
    )
    op.create_index("ix_koinon_identity_grants_expires_at", "koinon_identity_grants", ["expires_at"])
    op.create_index("ix_koinon_identity_grants_provider_id", "koinon_identity_grants", ["provider_id"])
    op.create_index("ix_koinon_identity_grants_subject", "koinon_identity_grants", ["subject"])
    op.create_index("ix_koinon_identity_grants_tenant_id", "koinon_identity_grants", ["tenant_id"])
    op.create_table(
        "koinon_identity_validations",
        sa.Column("id", sa.String(64), primary_key=True, nullable=False),
        sa.Column("tenant_id", sa.String(64), sa.ForeignKey("lattice_tenants.id"), nullable=False),
        sa.Column(
            "provider_id", sa.String(64), sa.ForeignKey("koinon_identity_providers.id"), nullable=False
        ),
        sa.Column("requested_by", sa.String(512), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("policy_revision", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("checks_json", sa.JSON(), nullable=False),
        sa.Column("issued_at", UtcDateTime(), nullable=False),
        sa.Column("expires_at", UtcDateTime(), nullable=False),
        sa.Column("started_at", UtcDateTime(), nullable=True),
        sa.Column("completed_at", UtcDateTime(), nullable=True),
    )
    op.create_index(
        "ix_koinon_identity_validations_expires_at", "koinon_identity_validations", ["expires_at"]
    )
    op.create_index(
        "ix_koinon_identity_validations_provider_id", "koinon_identity_validations", ["provider_id"]
    )
    op.create_index("ix_koinon_identity_validations_tenant_id", "koinon_identity_validations", ["tenant_id"])


def downgrade():
    raise RuntimeError("Use a reviewed backup/restore recovery plan for corporate identity")
