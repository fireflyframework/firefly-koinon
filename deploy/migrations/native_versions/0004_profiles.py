# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Persist self-owned profiles and the last verified catalog author."""

import sqlalchemy as sa
from alembic import op
from pyfly.data.relational.sqlalchemy import UtcDateTime

revision = "koinon_0004_profiles"
down_revision = "koinon_0003_assistants"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "koinon_profiles",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("subject", sa.String(512), nullable=False),
        sa.Column("display_name", sa.String(120), nullable=False),
        sa.Column("locale", sa.String(64), nullable=False),
        sa.Column("time_zone", sa.String(64), nullable=False),
        sa.Column("response_language", sa.String(64), nullable=False),
        sa.Column("avatar_bytes", sa.LargeBinary(), nullable=True),
        sa.Column("avatar_version", sa.String(64), nullable=True),
        sa.Column("updated_at", UtcDateTime(), nullable=False),
    )
    op.create_index(
        "ix_koinon_profiles_subject", "koinon_profiles", ["subject"], unique=True
    )
    op.add_column(
        "lattice_catalog",
        sa.Column("updated_by", sa.String(512), nullable=False, server_default=""),
    )
    op.execute("UPDATE lattice_catalog SET updated_by=created_by WHERE updated_by=''")
    op.alter_column("lattice_catalog", "updated_by", server_default=None)


def downgrade():
    raise RuntimeError("Use a reviewed backup/restore recovery plan for profiles")
