# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Keep names unique among live tables without renaming retained history.

Deploy with ingestion conflict targets using WHERE is_active. Replacement writers
must deactivate the reviewed old set before renaming or activating the new set.
The partial unique index is immediate, so name swaps require that ordering.

Both DDL statements run in the migration transaction: interruption restores the
old constraint, and the upgrade can be retried. Lock acquisition and index builds
are bounded. Once committed, repair only through a reviewed forward migration;
restoring global uniqueness would reject valid retained same-name histories.
No rows, identifiers, names, grants, or row-level policies are changed.
"""

from alembic import op

revision = "0016_live_table_names"
down_revision = "0015_versioned_embedding_sets"


def upgrade():
    if op.get_bind().dialect.name != "postgresql":
        raise RuntimeError("Live table name migration requires PostgreSQL")
    op.execute("SET LOCAL lock_timeout='5s'")
    op.execute("SET LOCAL statement_timeout='60s'")
    op.execute(
        "CREATE UNIQUE INDEX uq_tables_dataset_live_name "
        "ON flyquery_tables(dataset_id,name) WHERE is_active"
    )
    op.execute("ALTER TABLE flyquery_tables DROP CONSTRAINT uq_tables_dataset_name")


def downgrade():
    raise RuntimeError("Retain table names and history; use a reviewed forward migration")
