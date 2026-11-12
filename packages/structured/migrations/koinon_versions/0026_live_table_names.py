# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Join the preserved product and standalone live-name migration histories.

The standalone parent owns the DDL. Both fresh and existing product installations
apply it exactly once; the merge changes no rows or schema objects.
"""

revision = "0026_live_table_names"
down_revision = ("0025_source_publication_baseline", "0016_live_table_names")


def upgrade():
    """Both parents already supply the complete schema."""


def downgrade():
    raise RuntimeError("Retain live table identities; use a reviewed forward migration")
