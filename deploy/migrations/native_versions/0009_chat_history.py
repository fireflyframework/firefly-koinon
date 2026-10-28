# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Private conversation folders, optimistic metadata and answer grounding state."""

import sqlalchemy as sa
from alembic import op
from pyfly.data.relational.sqlalchemy.types import UtcDateTime

revision = "koinon_0009_chat_history"
down_revision = "koinon_0008_invitations"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "koinon_chat_folders",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("tenant_id", sa.String(64), sa.ForeignKey("lattice_tenants.id"), nullable=False),
        sa.Column("subject", sa.String(512), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("scope", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("parent_id", sa.String(64), sa.ForeignKey("koinon_chat_folders.id", ondelete="SET NULL"), nullable=True),
        sa.Column("revision", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", UtcDateTime(), nullable=False),
        sa.Column("updated_at", UtcDateTime(), nullable=False),
    )
    op.create_index("ix_koinon_chat_folder_owner", "koinon_chat_folders", ["tenant_id", "subject", "parent_id"])
    op.add_column("koinon_chat_threads", sa.Column("folder_id", sa.String(64), nullable=True))
    op.create_foreign_key("fk_koinon_thread_folder", "koinon_chat_threads", "koinon_chat_folders", ["folder_id"], ["id"], ondelete="SET NULL")
    op.create_index("ix_koinon_chat_threads_folder_id", "koinon_chat_threads", ["folder_id"])
    op.add_column("koinon_chat_threads", sa.Column("revision", sa.Integer(), nullable=False, server_default="1"))
    op.add_column("koinon_chat_threads", sa.Column("title_source", sa.String(16), nullable=False, server_default="manual"))
    op.alter_column("koinon_chat_threads", "title_source", server_default="default")
    op.add_column("koinon_chat_threads", sa.Column("archived_at", UtcDateTime(), nullable=True))
    op.add_column("koinon_chat_messages", sa.Column("answer_policy", sa.JSON(), nullable=False, server_default="{}"))


def downgrade():
    raise RuntimeError("Use a reviewed backup/restore recovery plan for conversation history")
