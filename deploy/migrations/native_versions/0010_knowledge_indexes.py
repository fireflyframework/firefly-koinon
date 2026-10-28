# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Durable scoped index lifecycle; native vectors remain in their owning sources."""

import sqlalchemy as sa
from alembic import op
from pyfly.data.relational.sqlalchemy.types import UtcDateTime

revision = "koinon_0010_knowledge_indexes"
down_revision = "koinon_0009_chat_history"
branch_labels = None
depends_on = None


def upgrade():
    columns = [
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column(
            "tenant_id",
            sa.String(64),
            sa.ForeignKey("lattice_tenants.id"),
            nullable=False,
        ),
        sa.Column(
            "workspace_id",
            sa.String(64),
            sa.ForeignKey("lattice_catalog.id"),
            nullable=False,
        ),
        sa.Column(
            "provider_id",
            sa.String(64),
            sa.ForeignKey("koinon_providers.id"),
            nullable=False,
        ),
    ]
    for name, width in (
        ("native_workspace_id", 64),
        ("domain", 32),
        ("native_id", 64),
        ("provider_kind", 32),
        ("model_id", 255),
        ("embedding_fingerprint", 64),
        ("created_by", 512),
        ("updated_by", 512),
    ):
        columns.append(sa.Column(name, sa.String(width), nullable=False))
    for name, width in (
        ("build_slot", 64),
        ("active_slot", 64),
        ("job_id", 64),
        ("access_token_id", 64),
        ("error_code", 64),
        ("error", 2000),
    ):
        columns.append(sa.Column(name, sa.String(width), nullable=True))
    for name in ("provider_revision", "dimensions", "storage_dimensions"):
        columns.append(sa.Column(name, sa.Integer(), nullable=False))
    for name, default in (
        ("revision", 1),
        ("batch_size", 32),
        ("chunk_count", 0),
        ("vector_count", 0),
    ):
        columns.append(
            sa.Column(name, sa.Integer(), nullable=False, server_default=str(default))
        )
    columns.extend(
        [
            sa.Column("status", sa.String(32), nullable=False, server_default="queued"),
            sa.Column(
                "indexed", sa.Boolean(), nullable=False, server_default=sa.false()
            ),
            sa.Column(
                "qualification",
                sa.String(64),
                nullable=False,
                server_default="probe_passed",
            ),
            sa.Column("cursor", sa.JSON(), nullable=False, server_default="{}"),
            sa.Column("transition", sa.JSON(), nullable=False, server_default="{}"),
            sa.Column("previous_binding", sa.JSON(), nullable=True),
            sa.Column("created_at", UtcDateTime(), nullable=False),
            sa.Column("updated_at", UtcDateTime(), nullable=False),
        ]
    )
    for name in ("ready_at", "activated_at", "retired_at"):
        columns.append(sa.Column(name, UtcDateTime(), nullable=True))
    op.create_table(
        "koinon_knowledge_indexes",
        *columns,
        sa.UniqueConstraint(
            "tenant_id",
            "domain",
            "native_workspace_id",
            "native_id",
            name="uq_koinon_index_native",
        ),
        sa.UniqueConstraint("build_slot", name="uq_koinon_index_build"),
        sa.UniqueConstraint("active_slot", name="uq_koinon_index_active"),
        sa.CheckConstraint(
            "domain in ('documents','structured')", name="ck_koinon_index_domain"
        ),
        sa.CheckConstraint(
            "dimensions between 64 and 4096", name="ck_koinon_index_dimensions"
        ),
    )
    op.create_index(
        "ix_koinon_index_scope",
        "koinon_knowledge_indexes",
        ["tenant_id", "workspace_id", "domain"],
    )


def downgrade():
    raise RuntimeError(
        "Use a reviewed backup/restore plan; preserved index versions must not be dropped"
    )
