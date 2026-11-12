# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Build metadata reference indexes without blocking writers during table scans.

Expansion has its own committed revision. An interrupted index build leaves that
revision intact; rerun this migration to replace invalid indexes and finish
validation. New writes are already checked by the NOT VALID foreign keys.
"""

import sqlalchemy as sa
from alembic import op

revision = "0023_metadata_indexes"
down_revision = "0022_dataset_replacement"
TABLES = (
    "flyquery_relations",
    "flyquery_glossary_terms",
    "flyquery_semantic_metrics",
    "flyquery_semantic_dimensions",
    "flyquery_examples",
    "flyquery_semantic_versions",
)


def upgrade():
    if op.get_bind().dialect.name != "postgresql":
        raise RuntimeError("Metadata reference indexes require PostgreSQL")
    with op.get_context().autocommit_block():
        op.execute("SET lock_timeout='5s'")
        try:
            for table in TABLES:
                name = f"ix_{table}_source_provenance"
                invalid = (
                    op.get_bind()
                    .execute(
                        sa.text("SELECT NOT indisvalid FROM pg_index WHERE indexrelid=to_regclass(:name)"),
                        {"name": "public." + name},
                    )
                    .scalar()
                )
                if invalid:
                    op.execute(f"DROP INDEX CONCURRENTLY public.{name}")
                op.execute(
                    f"CREATE INDEX CONCURRENTLY IF NOT EXISTS {name} "
                    f"ON {table}(source_provenance_id) WHERE source_provenance_id IS NOT NULL"
                )
                op.execute(f"ALTER TABLE {table} VALIDATE CONSTRAINT fk_{table}_source_provenance")
        finally:
            op.execute("RESET lock_timeout")


def downgrade():
    raise RuntimeError("Recover metadata indexes with a reviewed forward migration")
