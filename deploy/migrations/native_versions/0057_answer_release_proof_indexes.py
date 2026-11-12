# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Index bounded identity scans concurrently, with safe interrupted-build retries."""

import sqlalchemy as sa
from alembic import op

revision = "koinon_0057_proof_indexes"
down_revision = "koinon_0056_release_proofs"

INDEXES = {
    "ix_answer_release_keyset": "koinon_chat_tool_results(created_at,id) WHERE kind='answer_release'",
    "ix_answer_result_selector": "koinon_chat_tool_results(run_id,kind,id)",
    "ix_answer_event_selector": "koinon_chat_events(run_id,type,sequence)",
}


def upgrade():
    if op.get_bind().dialect.name != "postgresql":
        raise RuntimeError("Answer release proof enforcement requires PostgreSQL")
    with op.get_context().autocommit_block():
        op.execute("SET lock_timeout='5s'")
        try:
            for name, definition in INDEXES.items():
                invalid = (
                    op.get_bind()
                    .execute(
                        sa.text(
                            "SELECT NOT indisvalid FROM pg_catalog.pg_index WHERE "
                            "indexrelid=to_regclass(:name)"
                        ),
                        {"name": "public." + name},
                    )
                    .scalar()
                )
                if invalid:
                    op.execute(f"DROP INDEX CONCURRENTLY public.{name}")
                # An equivalent existing key is reused even under another name.
                table, columns = definition.split("(", 1)
                column_names = columns.split(")", 1)[0].split(",")
                predicate = "kind = 'answer_release'::text" if "WHERE" in definition else None
                equivalent = (
                    op.get_bind()
                    .execute(
                        sa.text("""
                  SELECT EXISTS(SELECT FROM pg_catalog.pg_index i WHERE i.indrelid=to_regclass(:table)
                   AND i.indisvalid AND i.indisready AND i.indexprs IS NULL
                   AND (SELECT array_agg(a.attname::text ORDER BY k.ordinality)
                    FROM unnest(i.indkey::smallint[]) WITH ORDINALITY k(attnum,ordinality)
                    JOIN pg_catalog.pg_attribute a ON a.attrelid=i.indrelid AND a.attnum=k.attnum
                    WHERE k.ordinality<=i.indnkeyatts)=CAST(:columns AS text[])
                   AND ((CAST(:predicate AS text) IS NULL AND i.indpred IS NULL) OR
                        (CAST(:predicate AS text) IS NOT NULL AND
  replace(replace(pg_get_expr(i.indpred,i.indrelid),'(',''),')','')=CAST(:predicate AS text))))
                """),
                        {"table": "public." + table, "columns": column_names, "predicate": predicate},
                    )
                    .scalar()
                )
                if not equivalent:
                    op.execute(f"CREATE INDEX CONCURRENTLY IF NOT EXISTS {name} ON public.{definition}")
        finally:
            op.execute("RESET lock_timeout")


def downgrade():
    raise RuntimeError("Retain release proof indexes; use a reviewed forward migration")
