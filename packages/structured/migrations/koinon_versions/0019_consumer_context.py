# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Retain server-bound consumer authority for independently addressed query output."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0019_consumer_context"
down_revision = "0018_bulk_operations"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("flyquery_queries", sa.Column("consumer_context", JSONB(), nullable=True))


def downgrade():
    raise RuntimeError("Retain stored query authority with a reviewed backup/restore plan")
