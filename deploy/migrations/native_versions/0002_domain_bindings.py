# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Persist immutable shared-to-retained domain bindings."""

import pyfly.data.relational.sqlalchemy.types
import sqlalchemy as sa
from alembic import op

revision = "koinon_0002"
down_revision = "koinon_0001"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "lattice_domain_bindings",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("tenant_id", sa.String(length=64), nullable=False),
        sa.Column("catalog_id", sa.String(length=64), nullable=False),
        sa.Column("workspace_id", sa.String(length=64), nullable=False),
        sa.Column("domain", sa.String(length=32), nullable=False),
        sa.Column("entity_kind", sa.String(length=32), nullable=False),
        sa.Column("native_id", sa.String(length=64), nullable=False),
        sa.Column("native_workspace_id", sa.String(length=64), nullable=False),
        sa.Column("details_json", sa.JSON(), nullable=False),
        sa.Column("created_by", sa.String(length=512), nullable=False),
        sa.Column(
            "created_at",
            pyfly.data.relational.sqlalchemy.types.UtcDateTime(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["catalog_id"],
            ["lattice_catalog.id"],
            name=op.f("fk_lattice_domain_bindings_catalog_id_lattice_catalog"),
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["lattice_tenants.id"],
            name=op.f("fk_lattice_domain_bindings_tenant_id_lattice_tenants"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_lattice_domain_bindings")),
        sa.UniqueConstraint(
            "tenant_id", "catalog_id", "domain", name="uq_lattice_domain_binding"
        ),
    )
    op.create_index(
        op.f("ix_lattice_domain_bindings_catalog_id"),
        "lattice_domain_bindings",
        ["catalog_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_lattice_domain_bindings_tenant_id"),
        "lattice_domain_bindings",
        ["tenant_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_lattice_domain_bindings_workspace_id"),
        "lattice_domain_bindings",
        ["workspace_id"],
        unique=False,
    )
    op.create_index(
        "ix_lattice_native_binding",
        "lattice_domain_bindings",
        ["tenant_id", "domain", "native_workspace_id", "native_id"],
        unique=False,
    )


def downgrade():
    raise RuntimeError("Use a reviewed backup/restore recovery plan for bindings")
