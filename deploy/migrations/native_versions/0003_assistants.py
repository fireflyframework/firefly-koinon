# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Persist provider configuration and authorized assistant/chat records."""

import pyfly.data.relational.sqlalchemy.types
import sqlalchemy as sa
from alembic import op

revision = "koinon_0003_assistants"
down_revision = "koinon_0002"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "koinon_chat_threads",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("tenant_id", sa.String(length=64), nullable=False),
        sa.Column("subject", sa.String(length=512), nullable=False),
        sa.Column("title", sa.String(length=160), nullable=False),
        sa.Column("scope", sa.JSON(), nullable=False),
        sa.Column(
            "created_at",
            pyfly.data.relational.sqlalchemy.types.UtcDateTime(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            pyfly.data.relational.sqlalchemy.types.UtcDateTime(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["lattice_tenants.id"],
            name=op.f("fk_koinon_chat_threads_tenant_id_lattice_tenants"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_koinon_chat_threads")),
    )
    op.create_index(
        op.f("ix_koinon_chat_threads_subject"),
        "koinon_chat_threads",
        ["subject"],
        unique=False,
    )
    op.create_index(
        op.f("ix_koinon_chat_threads_tenant_id"),
        "koinon_chat_threads",
        ["tenant_id"],
        unique=False,
    )
    op.create_table(
        "koinon_providers",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("tenant_id", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("base_url", sa.String(length=2048), nullable=False),
        sa.Column("model_ids", sa.JSON(), nullable=False),
        sa.Column("secret_ciphertext", sa.LargeBinary(), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("validated_revision", sa.Integer(), nullable=False),
        sa.Column("checks", sa.JSON(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            pyfly.data.relational.sqlalchemy.types.UtcDateTime(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            pyfly.data.relational.sqlalchemy.types.UtcDateTime(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["lattice_tenants.id"],
            name=op.f("fk_koinon_providers_tenant_id_lattice_tenants"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_koinon_providers")),
    )
    op.create_index(
        op.f("ix_koinon_providers_tenant_id"),
        "koinon_providers",
        ["tenant_id"],
        unique=False,
    )
    op.create_table(
        "koinon_agents",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("tenant_id", sa.String(length=64), nullable=False),
        sa.Column("provider_id", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("description", sa.String(length=2000), nullable=False),
        sa.Column("model_id", sa.String(length=255), nullable=False),
        sa.Column("tools", sa.JSON(), nullable=False),
        sa.Column("scope", sa.JSON(), nullable=False),
        sa.Column("instructions", sa.Text(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            pyfly.data.relational.sqlalchemy.types.UtcDateTime(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            pyfly.data.relational.sqlalchemy.types.UtcDateTime(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["provider_id"],
            ["koinon_providers.id"],
            name=op.f("fk_koinon_agents_provider_id_koinon_providers"),
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["lattice_tenants.id"],
            name=op.f("fk_koinon_agents_tenant_id_lattice_tenants"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_koinon_agents")),
    )
    op.create_index(
        op.f("ix_koinon_agents_tenant_id"), "koinon_agents", ["tenant_id"], unique=False
    )
    op.create_table(
        "koinon_chat_messages",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("thread_id", sa.String(length=64), nullable=False),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("citations", sa.JSON(), nullable=False),
        sa.Column("artifacts", sa.JSON(), nullable=False),
        sa.Column(
            "created_at",
            pyfly.data.relational.sqlalchemy.types.UtcDateTime(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["thread_id"],
            ["koinon_chat_threads.id"],
            name=op.f("fk_koinon_chat_messages_thread_id_koinon_chat_threads"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_koinon_chat_messages")),
    )
    op.create_index(
        op.f("ix_koinon_chat_messages_thread_id"),
        "koinon_chat_messages",
        ["thread_id"],
        unique=False,
    )
    op.create_table(
        "koinon_chat_runs",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("tenant_id", sa.String(length=64), nullable=False),
        sa.Column("thread_id", sa.String(length=64), nullable=False),
        sa.Column("message_id", sa.String(length=64), nullable=False),
        sa.Column("user_message_id", sa.String(length=64), nullable=False),
        sa.Column("agent_id", sa.String(length=64), nullable=False),
        sa.Column("agent_revision", sa.Integer(), nullable=False),
        sa.Column("provider_revision", sa.Integer(), nullable=False),
        sa.Column("scope", sa.JSON(), nullable=False),
        sa.Column("client_request_id", sa.String(length=255), nullable=False),
        sa.Column("payload_hash", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("worker_id", sa.String(length=64), nullable=True),
        sa.Column(
            "lease_until",
            pyfly.data.relational.sqlalchemy.types.UtcDateTime(),
            nullable=True,
        ),
        sa.Column(
            "available_at",
            pyfly.data.relational.sqlalchemy.types.UtcDateTime(),
            nullable=False,
        ),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.Column(
            "created_at",
            pyfly.data.relational.sqlalchemy.types.UtcDateTime(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            pyfly.data.relational.sqlalchemy.types.UtcDateTime(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["agent_id"],
            ["koinon_agents.id"],
            name=op.f("fk_koinon_chat_runs_agent_id_koinon_agents"),
        ),
        sa.ForeignKeyConstraint(
            ["message_id"],
            ["koinon_chat_messages.id"],
            name=op.f("fk_koinon_chat_runs_message_id_koinon_chat_messages"),
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["lattice_tenants.id"],
            name=op.f("fk_koinon_chat_runs_tenant_id_lattice_tenants"),
        ),
        sa.ForeignKeyConstraint(
            ["thread_id"],
            ["koinon_chat_threads.id"],
            name=op.f("fk_koinon_chat_runs_thread_id_koinon_chat_threads"),
        ),
        sa.ForeignKeyConstraint(
            ["user_message_id"],
            ["koinon_chat_messages.id"],
            name=op.f("fk_koinon_chat_runs_user_message_id_koinon_chat_messages"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_koinon_chat_runs")),
        sa.UniqueConstraint(
            "thread_id", "client_request_id", name="uq_koinon_chat_request"
        ),
    )
    op.create_index(
        "ix_koinon_chat_queue",
        "koinon_chat_runs",
        ["status", "available_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_koinon_chat_runs_tenant_id"),
        "koinon_chat_runs",
        ["tenant_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_koinon_chat_runs_thread_id"),
        "koinon_chat_runs",
        ["thread_id"],
        unique=False,
    )
    op.create_table(
        "koinon_chat_events",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("run_id", sa.String(length=64), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("type", sa.String(length=32), nullable=False),
        sa.Column("data", sa.JSON(), nullable=False),
        sa.Column(
            "created_at",
            pyfly.data.relational.sqlalchemy.types.UtcDateTime(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["run_id"],
            ["koinon_chat_runs.id"],
            name=op.f("fk_koinon_chat_events_run_id_koinon_chat_runs"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_koinon_chat_events")),
        sa.UniqueConstraint("run_id", "sequence", name="uq_koinon_chat_event"),
    )
    op.create_index(
        op.f("ix_koinon_chat_events_run_id"),
        "koinon_chat_events",
        ["run_id"],
        unique=False,
    )
    op.create_table(
        "koinon_chat_tool_results",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("run_id", sa.String(length=64), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column(
            "created_at",
            pyfly.data.relational.sqlalchemy.types.UtcDateTime(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["run_id"],
            ["koinon_chat_runs.id"],
            name=op.f("fk_koinon_chat_tool_results_run_id_koinon_chat_runs"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_koinon_chat_tool_results")),
    )
    op.create_index(
        op.f("ix_koinon_chat_tool_results_run_id"),
        "koinon_chat_tool_results",
        ["run_id"],
        unique=False,
    )


def downgrade():
    raise RuntimeError("Use a reviewed backup/restore recovery plan for bindings")
