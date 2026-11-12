# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Retain source-control receipts and fence cancellation without changing policy.

Nullable run fields expand the retained schema without rewriting old rows. Retry
indexes are built concurrently before transactional constraints and guards. A
failed concurrent build can be resumed. Reversal is a reviewed forward fix:
disable control endpoints and retain receipts, run identities and provenance.
"""

import sqlalchemy as sa
from alembic import op

revision = "koinon_0047_source_controls"
down_revision = "koinon_0046_source_sync"
branch_labels = None
depends_on = None


def upgrade():
    with op.get_context().autocommit_block():
        op.execute("SET lock_timeout = '5s'")
        try:
            op.execute("""
                ALTER TABLE koinon_content_sync_runs
                ADD COLUMN IF NOT EXISTS cancel_requested_at timestamptz,
                ADD COLUMN IF NOT EXISTS cancel_operation_id varchar(64),
                ADD COLUMN IF NOT EXISTS retry_of_run_id varchar(64)
            """)
            invalid = (
                op.get_bind()
                .execute(
                    sa.text("""
                SELECT NOT indisvalid FROM pg_index
                WHERE indexrelid=to_regclass('public.ix_content_run_retry')
            """)
                )
                .scalar()
            )
            if invalid:
                op.execute("DROP INDEX CONCURRENTLY public.ix_content_run_retry")
            op.execute("""
                CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_content_run_retry
                ON koinon_content_sync_runs(tenant_id,mapping_id,retry_of_run_id)
                WHERE retry_of_run_id IS NOT NULL
            """)
        finally:
            op.execute("RESET lock_timeout")
    op.execute("SET LOCAL lock_timeout = '5s'")
    op.execute("""
        CREATE TABLE IF NOT EXISTS koinon_content_control_operations (
          id varchar(64) PRIMARY KEY, tenant_id varchar(64) NOT NULL,
          owner varchar(512) NOT NULL, operation_id varchar(64) NOT NULL,
          action varchar(32) NOT NULL, mapping_id varchar(64) NOT NULL,
          target_run_id varchar(64), expected_revision integer NOT NULL,
          result_revision integer NOT NULL, payload_sha256 varchar(64) NOT NULL,
          result_json json NOT NULL, created_at timestamptz NOT NULL,
          CONSTRAINT uq_content_control_operation UNIQUE(tenant_id,owner,operation_id),
          CONSTRAINT uq_content_control_identity UNIQUE(tenant_id,mapping_id,id),
          CONSTRAINT uq_content_control_revision UNIQUE(tenant_id,mapping_id,result_revision),
          CONSTRAINT fk_content_control_mapping FOREIGN KEY(tenant_id,owner,mapping_id)
            REFERENCES koinon_content_mappings(tenant_id,owner,id),
          CONSTRAINT fk_content_control_run FOREIGN KEY(tenant_id,mapping_id,target_run_id)
            REFERENCES koinon_content_sync_runs(tenant_id,mapping_id,id),
          CONSTRAINT ck_content_control_action CHECK(action IN ('sync','pause','resume','cancel','retry','retire')),
          CONSTRAINT ck_content_control_target CHECK(
            (action IN ('cancel','retry') AND target_run_id IS NOT NULL)
            OR (action IN ('pause','resume','retire') AND target_run_id IS NULL)
            OR action='sync'),
          CONSTRAINT ck_content_control_revision CHECK(
            expected_revision BETWEEN 1 AND 2147483646 AND result_revision=expected_revision+1),
          CONSTRAINT ck_content_control_operation CHECK(
            operation_id ~ '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'),
          CONSTRAINT ck_content_control_hash CHECK(payload_sha256 ~ '^[0-9a-f]{64}$'),
          CONSTRAINT ck_content_control_result CHECK(COALESCE((
            jsonb_typeof(result_json::jsonb)='object' AND octet_length(result_json::text)<=16384
            AND (result_json::jsonb - ARRAY['operation_id','receipt_id','action','control_revision',
              'run_id','disposition','status'])='{}'::jsonb
            AND result_json::jsonb ?& ARRAY['operation_id','receipt_id','action','control_revision','disposition']
            AND jsonb_typeof(result_json::jsonb->'operation_id')='string'
            AND jsonb_typeof(result_json::jsonb->'receipt_id')='string'
            AND jsonb_typeof(result_json::jsonb->'action')='string'
            AND jsonb_typeof(result_json::jsonb->'disposition')='string'
            AND result_json->>'operation_id'=operation_id AND result_json->>'receipt_id'=id
            AND result_json->>'action'=action
            AND jsonb_typeof(result_json::jsonb->'control_revision')='number'
            AND result_json->>'control_revision'=result_revision::text
            AND result_json->>'disposition' IN ('accepted','applied','queued','paused','active','stopping','reconciling','retired')
            AND (NOT result_json::jsonb ? 'run_id' OR result_json::jsonb->'run_id'='null'::jsonb
              OR (jsonb_typeof(result_json::jsonb->'run_id')='string' AND length(result_json->>'run_id') BETWEEN 1 AND 64))
            AND (NOT result_json::jsonb ? 'status' OR result_json->>'status' IN
              ('queued','running','reconciling','succeeded','partial','failed','cancelled',
               'reconnect_required','active','paused','retired'))), false))
        )
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_content_control_run
        ON koinon_content_control_operations(tenant_id,mapping_id,target_run_id)
        WHERE target_run_id IS NOT NULL
    """)
    op.execute("""
        CREATE OR REPLACE TRIGGER retain_rows BEFORE UPDATE OR DELETE ON koinon_content_control_operations
        FOR EACH ROW EXECUTE FUNCTION koinon_content_retain_row()
    """)
    op.execute("""
        CREATE OR REPLACE TRIGGER retain_table BEFORE TRUNCATE ON koinon_content_control_operations
        EXECUTE FUNCTION koinon_content_retain_row()
    """)
    constraints = {
        "fk_content_run_cancel": """FOREIGN KEY(tenant_id,mapping_id,cancel_operation_id)
          REFERENCES koinon_content_control_operations(tenant_id,mapping_id,id)""",
        "fk_content_run_retry": """FOREIGN KEY(tenant_id,mapping_id,retry_of_run_id)
          REFERENCES koinon_content_sync_runs(tenant_id,mapping_id,id)""",
        "ck_content_run_cancel_pair": """CHECK(
          (cancel_requested_at IS NULL)=(cancel_operation_id IS NULL))""",
        "ck_content_run_retry_self": "CHECK(retry_of_run_id IS NULL OR retry_of_run_id<>id)",
        "ck_content_run_status": """CHECK(status IN
          ('queued','running','reconciling','succeeded','partial','failed','cancelled','reconnect_required'))""",
    }
    op.execute("""ALTER TABLE koinon_content_sync_runs
        DROP CONSTRAINT IF EXISTS koinon_content_sync_runs_status_check""")
    for name, definition in constraints.items():
        present = (
            op.get_bind()
            .execute(
                sa.text("""
            SELECT 1 FROM pg_constraint WHERE conname=:name
            AND conrelid='koinon_content_sync_runs'::regclass
        """),
                {"name": name},
            )
            .scalar()
        )
        if not present:
            op.execute(
                f"ALTER TABLE koinon_content_sync_runs ADD CONSTRAINT {name} {definition} NOT VALID"
            )
    op.execute("""
        CREATE OR REPLACE FUNCTION koinon_content_guard_run() RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE cancellation koinon_content_control_operations;
        BEGIN
          IF TG_OP='INSERT' THEN
            IF NOT EXISTS(SELECT 1 FROM koinon_content_policies
              WHERE id=NEW.policy_id AND tenant_id=NEW.tenant_id AND mapping_id=NEW.mapping_id
                AND mapping_revision=NEW.mapping_revision AND accepted_at IS NOT NULL) THEN
              RAISE EXCEPTION 'execution requires an accepted policy' USING ERRCODE='23514';
            END IF;
            IF NOT EXISTS(SELECT 1 FROM lattice_jobs WHERE id=NEW.job_id AND tenant_id=NEW.tenant_id
              AND resource_id=NEW.mapping_id AND kind='content.source.reconcile') THEN
              RAISE EXCEPTION 'canonical source Job required' USING ERRCODE='23514';
            END IF;
            IF NEW.cancel_requested_at IS NOT NULL OR NEW.cancel_operation_id IS NOT NULL THEN
              RAISE EXCEPTION 'new execution cannot already be cancelled' USING ERRCODE='23514';
            END IF;
            IF NEW.trigger_kind='retry' THEN
              IF NEW.retry_of_run_id IS NULL OR NEW.retry_of_run_id=NEW.id OR NOT EXISTS(
                SELECT 1 FROM koinon_content_sync_runs WHERE id=NEW.retry_of_run_id
                  AND tenant_id=NEW.tenant_id AND mapping_id=NEW.mapping_id
                  AND status IN ('failed','partial','reconnect_required','cancelled')) THEN
                RAISE EXCEPTION 'retry requires an eligible retained predecessor' USING ERRCODE='23514';
              END IF;
            ELSIF NEW.retry_of_run_id IS NOT NULL THEN
              RAISE EXCEPTION 'only retries reference a predecessor' USING ERRCODE='23514';
            END IF;
          ELSE
            IF (to_jsonb(NEW)-ARRAY['status','page_sequence','cursor_ciphertext','enumeration_complete',
                'counters_json','updated_at','finished_at','cancel_requested_at','cancel_operation_id']) IS DISTINCT FROM
              (to_jsonb(OLD)-ARRAY['status','page_sequence','cursor_ciphertext','enumeration_complete',
                'counters_json','updated_at','finished_at','cancel_requested_at','cancel_operation_id'])
              OR NEW.page_sequence<OLD.page_sequence OR NEW.page_sequence>OLD.page_sequence+1
              OR (OLD.enumeration_complete AND NOT NEW.enumeration_complete)
              OR (OLD.status NOT IN ('queued','running','reconciling') AND NEW.status<>OLD.status) THEN
              RAISE EXCEPTION 'run identity or checkpoint cannot be rewritten' USING ERRCODE='23514';
            END IF;
            IF (NEW.cancel_requested_at,NEW.cancel_operation_id) IS DISTINCT FROM
                (OLD.cancel_requested_at,OLD.cancel_operation_id) THEN
              IF OLD.cancel_operation_id IS NOT NULL OR NEW.cancel_operation_id IS NULL
                OR NEW.cancel_requested_at IS NULL OR OLD.status NOT IN ('queued','running','reconciling') THEN
                RAISE EXCEPTION 'cancellation request is immutable' USING ERRCODE='23514';
              END IF;
              SELECT * INTO cancellation FROM koinon_content_control_operations
                WHERE id=NEW.cancel_operation_id AND tenant_id=NEW.tenant_id AND mapping_id=NEW.mapping_id;
              IF cancellation.id IS NULL OR NOT (
                (cancellation.action='cancel' AND cancellation.target_run_id=NEW.id)
                OR (cancellation.action='retire' AND cancellation.target_run_id IS NULL)) THEN
                RAISE EXCEPTION 'cancellation requires its exact control receipt' USING ERRCODE='23514';
              END IF;
            END IF;
          END IF;
          RETURN NEW;
        END $$
    """)
    # Release the short ACCESS EXCLUSIVE DDL lock before scanning retained rows.
    # Validation takes SHARE UPDATE EXCLUSIVE and allows ordinary reads/writes.
    # If validation is interrupted, the idempotent expansion and guards above
    # permit the same forward migration to resume without discarding any rows.
    with op.get_context().autocommit_block():
        op.execute("SET lock_timeout = '5s'")
        try:
            for name in constraints:
                op.execute(
                    f"ALTER TABLE koinon_content_sync_runs VALIDATE CONSTRAINT {name}"
                )
        finally:
            op.execute("RESET lock_timeout")
