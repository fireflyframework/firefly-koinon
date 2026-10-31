# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Opt-in personal project memory and retained conversation removal."""

import sqlalchemy as sa
from alembic import op
from pyfly.data.relational.sqlalchemy import UtcDateTime

revision = "koinon_0025_memory"
down_revision = "koinon_0024_bulk"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("koinon_organization_chat_settings", sa.Column("memory_policy_json", sa.JSON(), nullable=True))
    op.add_column("koinon_chat_threads", sa.Column("deleted_at", UtcDateTime(), nullable=True))
    op.add_column(
        "koinon_chat_folders",
        sa.Column("memory_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.create_table(
        "koinon_chat_memory_manifests",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("generation_id", sa.String(64), sa.ForeignKey("koinon_chat_tool_results.id"), nullable=False),
        sa.Column("run_id", sa.String(64), sa.ForeignKey("koinon_chat_runs.id"), nullable=False),
        sa.Column("tenant_id", sa.String(64), sa.ForeignKey("lattice_tenants.id"), nullable=False),
        sa.Column("subject", sa.String(512), nullable=False),
        sa.Column("thread_id", sa.String(64), sa.ForeignKey("koinon_chat_threads.id"), nullable=False),
        sa.Column("folder_id", sa.String(64), nullable=True),
        sa.Column("policy_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("start_sequence", sa.Integer(), nullable=False),
        sa.Column("scope_sha256", sa.String(64), nullable=False),
        sa.Column("manifest_json", sa.JSON(), nullable=False),
        sa.Column("manifest_sha256", sa.String(64), nullable=False),
        sa.Column("created_at", UtcDateTime(), nullable=False),
        sa.UniqueConstraint("generation_id", name="uq_chat_memory_generation"),
        sa.CheckConstraint("policy_version >= 1", name="ck_chat_memory_policy"),
        sa.CheckConstraint("start_sequence >= 0", name="ck_chat_memory_sequence"),
    )
    op.create_index(
        "ix_chat_memory_owner", "koinon_chat_memory_manifests", ["tenant_id", "subject", "thread_id"]
    )
    op.create_index("ix_chat_memory_run", "koinon_chat_memory_manifests", ["run_id"])


def downgrade():
    raise RuntimeError("Use a reviewed backup/restore plan to retain conversation history")
