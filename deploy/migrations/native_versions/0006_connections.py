# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Preserve native API selection and bounded model options as additive configuration."""
import sqlalchemy as sa
from alembic import op

revision = 'koinon_0006_connections'
down_revision = 'koinon_0005_personal_tokens'
branch_labels = None
depends_on = None


def upgrade():
    # Nullable API retains inference for writes from an older application during rollout.
    op.add_column('koinon_providers',sa.Column('api',sa.String(16),nullable=True))
    op.execute("UPDATE koinon_providers SET api=CASE WHEN kind='anthropic' THEN 'messages' ELSE 'chat' END")
    op.add_column('koinon_agents',sa.Column('model_options',sa.JSON(),nullable=False,server_default='{}'))


def downgrade():
    raise RuntimeError('Use a reviewed backup/restore recovery plan for connection configuration')
