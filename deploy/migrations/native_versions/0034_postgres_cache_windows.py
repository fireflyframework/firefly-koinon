# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Shared rolling-window admission with the framework's primary PostgreSQL cache."""

import sqlalchemy as sa
from alembic import op
from pyfly.data.relational.framework_schema import KeyString, UtcTimestamp
from sqlalchemy.dialects.postgresql import JSONB

revision = "koinon_0034_postgres_cache"
down_revision = "koinon_0033_bootstrap"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "pyfly_cache_windows",
        sa.Column(
            "cache_key",
            KeyString(512).with_variant(sa.Text(), "postgresql").with_variant(sa.Text(), "sqlite"),
            primary_key=True,
        ),
        sa.Column("events", sa.JSON().with_variant(JSONB(), "postgresql"), nullable=False),
        sa.Column("expires_at", UtcTimestamp(), nullable=False),
        sa.Column("window_microseconds", sa.BigInteger(), nullable=False),
        info={"pyfly_framework_table": "cache_windows"},
    )
    op.create_index("ix_pyfly_cache_windows_expires_at", "pyfly_cache_windows", ["expires_at"])


def downgrade():
    raise RuntimeError("Use a reviewed restore plan to preserve shared rate-limit windows")
