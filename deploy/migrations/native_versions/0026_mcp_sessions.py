# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Shared authenticated MCP initialization metadata, with no response or transport replay."""

from alembic import op
from pyfly.data.relational.framework_schema import mcp_session_admission, mcp_sessions

revision = "koinon_0026_mcp_sessions"
down_revision = "koinon_0025_memory"
branch_labels = None
depends_on = None


def upgrade():
    mcp_sessions.create(op.get_bind())
    mcp_session_admission.create(op.get_bind())


def downgrade():
    raise RuntimeError(
        "Use a reviewed restore plan; active clients must reinitialize after metadata removal"
    )
