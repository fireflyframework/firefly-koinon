# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Add exact provider-version references without rewriting retained originals."""

import sqlalchemy as sa
from alembic import op

revision = "0021_pinned_originals"
down_revision = "0020_source_lineage"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("canon_source_artifacts", sa.Column("object_reference_json", sa.JSON(), nullable=True))


def downgrade():
    op.drop_column("canon_source_artifacts", "object_reference_json")
