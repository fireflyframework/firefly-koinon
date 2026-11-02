# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Preserve existing preferences while allowing one-time device defaults for new profiles."""

import sqlalchemy as sa
from alembic import op

revision = "koinon_0042_profile_preferences"
down_revision = "koinon_0041_email_recovery"
branch_labels = None
depends_on = None


def upgrade():
    # Existing profiles, including explicit en-US/UTC choices, must not be reset.
    op.add_column(
        "koinon_profiles",
        sa.Column("preferences_initialized", sa.Boolean(), nullable=False, server_default=sa.true()),
    )


def downgrade():
    raise RuntimeError("Use a reviewed backup/restore recovery plan for personal preferences")
