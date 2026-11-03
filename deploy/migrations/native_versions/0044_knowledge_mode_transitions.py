# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Durable answer-mode preparation without changing active organization settings."""

import sqlalchemy as sa
from alembic import op
from pyfly.data.relational.sqlalchemy import UtcDateTime

revision = "koinon_0044_knowledge_modes"
down_revision = "koinon_0043_ordinary_folders"
branch_labels = None
depends_on = None


def upgrade():
    from koinon.organization_knowledge.transitions.generation_schema_v1 import (
        TransactionId,
    )

    op.create_table(
        "koinon_knowledge_readiness_generations",
        sa.Column(
            "tenant_id",
            sa.String(64),
            sa.ForeignKey("lattice_tenants.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("generation", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("fence", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "last_transaction",
            sa.String(32).with_variant(TransactionId(), "postgresql"),
            nullable=True,
        ),
        sa.CheckConstraint("generation >= 0", name="ck_knowledge_readiness_generation"),
    )
    op.create_table(
        "koinon_knowledge_readiness_changes",
        sa.Column(
            "tenant_id",
            sa.String(64),
            sa.ForeignKey(
                "koinon_knowledge_readiness_generations.tenant_id", ondelete="CASCADE"
            ),
            primary_key=True,
        ),
        sa.Column("workspace_id", sa.String(64), primary_key=True),
        sa.Column("generation", sa.BigInteger(), nullable=False),
    )
    op.create_index(
        "ix_knowledge_readiness_changes",
        "koinon_knowledge_readiness_changes",
        ["tenant_id", "generation", "workspace_id"],
    )
    from koinon.organization_knowledge.transitions.generation_schema_v1 import install

    install(op.get_bind(), require_complete=True)
    if sa.inspect(op.get_bind()).has_table("koinon_knowledge_indexes"):
        op.create_index(
            "ix_koinon_index_status",
            "koinon_knowledge_indexes",
            ["tenant_id", "status", "id"],
        )
    op.create_table(
        "koinon_knowledge_mode_transitions",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column(
            "tenant_id",
            sa.String(64),
            sa.ForeignKey("lattice_tenants.id"),
            nullable=False,
        ),
        sa.Column("active_slot", sa.String(64), nullable=True),
        sa.Column(
            "job_id",
            sa.String(64),
            sa.ForeignKey("lattice_jobs.id"),
            nullable=False,
            unique=True,
        ),
        sa.Column("actor", sa.String(512), nullable=False),
        sa.Column("access_token_id", sa.String(64), nullable=True),
        sa.Column("base_revision", sa.Integer(), nullable=False),
        sa.Column("base_digest", sa.String(64), nullable=False),
        sa.Column("active_mode", sa.String(8), nullable=False),
        sa.Column("requested_settings", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("stage", sa.String(32), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("counters", sa.JSON(), nullable=False),
        sa.Column("stage_milliseconds", sa.JSON(), nullable=False),
        sa.Column("cursor", sa.JSON(), nullable=False),
        sa.Column("error_code", sa.String(64), nullable=True),
        sa.Column("error", sa.String(1000), nullable=True),
        sa.Column("created_at", UtcDateTime(), nullable=False),
        sa.Column("updated_at", UtcDateTime(), nullable=False),
        sa.UniqueConstraint("active_slot", name="uq_knowledge_mode_active"),
        sa.UniqueConstraint("tenant_id", "id", name="uq_knowledge_mode_tenant_id"),
        sa.CheckConstraint("revision >= 1", name="ck_knowledge_mode_revision"),
    )
    op.create_index(
        "ix_knowledge_mode_tenant_created",
        "koinon_knowledge_mode_transitions",
        ["tenant_id", "created_at", "id"],
    )
    op.create_table(
        "koinon_knowledge_mode_targets",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("tenant_id", sa.String(64), nullable=False),
        sa.Column("transition_id", sa.String(64), nullable=False),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("catalog_id", sa.String(64), nullable=False),
        sa.Column("workspace_id", sa.String(64), nullable=False),
        sa.Column("native_workspace_id", sa.String(64), nullable=True),
        sa.Column("native_id", sa.String(64), nullable=True),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("snapshot", sa.JSON(), nullable=False),
        sa.Column("result", sa.JSON(), nullable=False),
        sa.Column("index_id", sa.String(64), nullable=True),
        sa.Column("error_code", sa.String(64), nullable=True),
        sa.Column("updated_at", UtcDateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["tenant_id", "transition_id"],
            [
                "koinon_knowledge_mode_transitions.tenant_id",
                "koinon_knowledge_mode_transitions.id",
            ],
        ),
        sa.UniqueConstraint(
            "transition_id", "kind", "catalog_id", name="uq_knowledge_mode_target"
        ),
        sa.CheckConstraint(
            "kind in ('workspace','document','curated')",
            name="ck_knowledge_mode_target_kind",
        ),
    )
    op.create_index(
        "ix_knowledge_mode_target_page",
        "koinon_knowledge_mode_targets",
        ["tenant_id", "transition_id", "status", "id"],
    )
    for name, fields in (
        ("cursor", ["id"]),
        ("kind", ["kind", "id"]),
        ("scope", ["workspace_id", "id"]),
        ("scope_kind", ["workspace_id", "kind", "id"]),
    ):
        op.create_index(
            "ix_knowledge_mode_target_" + name,
            "koinon_knowledge_mode_targets",
            ["tenant_id", "transition_id", *fields],
        )

    op.create_table(
        "koinon_knowledge_mode_index_attempts",
        sa.Column("id", sa.String(64), primary_key=True),
        *[
            sa.Column(name, sa.String(size), nullable=nullable)
            for name, size, nullable in (
                ("tenant_id", 64, False),
                ("transition_id", 64, False),
                ("index_id", 64, False),
                ("workspace_id", 64, False),
                ("native_workspace_id", 64, False),
                ("native_id", 64, False),
                ("job_id", 64, True),
                ("provider_id", 64, False),
                ("model_id", 255, False),
                ("embedding_fingerprint", 64, False),
                ("actor", 512, False),
                ("access_token_id", 64, True),
                ("previous_native_id", 64, True),
            )
        ],
        *[
            sa.Column(name, sa.Integer(), nullable=False)
            for name in (
                "attempt_revision",
                "provider_revision",
                "dimensions",
                "storage_dimensions",
            )
        ],
        sa.Column("request", sa.JSON(), nullable=False),
        sa.Column("created_at", UtcDateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["tenant_id", "transition_id"],
            [
                "koinon_knowledge_mode_transitions.tenant_id",
                "koinon_knowledge_mode_transitions.id",
            ],
        ),
        sa.UniqueConstraint("tenant_id", "id", name="uq_mode_index_attempt_tenant"),
        sa.UniqueConstraint(
            "transition_id",
            "index_id",
            "attempt_revision",
            name="uq_mode_index_attempt",
        ),
    )
    op.create_index(
        "ix_mode_index_attempt_page",
        "koinon_knowledge_mode_index_attempts",
        ["tenant_id", "transition_id", "id"],
    )
    op.create_table(
        "koinon_knowledge_mode_index_resolutions",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("tenant_id", sa.String(64), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("updated_at", UtcDateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["tenant_id", "id"],
            [
                "koinon_knowledge_mode_index_attempts.tenant_id",
                "koinon_knowledge_mode_index_attempts.id",
            ],
        ),
        sa.CheckConstraint(
            "status in ('pending','finished','restored','aborted')",
            name="ck_mode_index_resolution_status",
        ),
        sa.CheckConstraint("revision >= 1", name="ck_mode_index_resolution_revision"),
    )
    op.create_index(
        "ix_mode_index_resolution_pending",
        "koinon_knowledge_mode_index_resolutions",
        ["tenant_id", "status", "id"],
    )
    from koinon.organization_knowledge.transitions.attempt_schema_v1 import (
        install as install_attempts,
    )

    install_attempts(op.get_bind())


def downgrade():
    raise RuntimeError(
        "Preserve preparation history; use a reviewed backup and restore recovery plan"
    )
