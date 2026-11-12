# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Bind source-owned native operations to their frozen canonical descriptor.

Nullable expansion preserves local and retained legacy operations. No backfill.
The transaction can be retried after interruption; repair with a forward migration
once source-owned operations exist, retaining every original receipt and digest.
"""

from alembic import op

revision = "0025_source_publication_baseline"
down_revision = "0024_replacement_member_locators"


def upgrade():
    if op.get_bind().dialect.name != "postgresql":
        raise RuntimeError("Source publication binding requires PostgreSQL")
    op.execute("SET LOCAL lock_timeout='5s'")
    op.execute("""ALTER TABLE public.flyquery_bulk_operations
      ADD COLUMN source_attempt_id varchar(64), ADD COLUMN source_publication_sha256 varchar(64),
      ADD CONSTRAINT ck_structured_source_attempt CHECK(source_attempt_id IS NULL
        OR length(source_attempt_id) BETWEEN 1 AND 64),
      ADD CONSTRAINT ck_structured_source_digest CHECK(source_publication_sha256 IS NULL OR
        (source_attempt_id IS NOT NULL AND source_publication_sha256 ~ '^[0-9a-f]{64}$'))""")
    op.execute("""CREATE OR REPLACE FUNCTION public.koinon_structured_bulk_guard() RETURNS trigger
      LANGUAGE plpgsql SET search_path=pg_catalog AS $$
      BEGIN
        IF TG_OP='DELETE' THEN
          RAISE EXCEPTION 'Retain structured bulk receipts' USING ERRCODE='55000';
        END IF;
        IF TG_OP='INSERT' THEN
          IF NEW.status<>'admitted' OR NEW.plan_json IS NOT NULL OR NEW.prepared_json IS NOT NULL
            OR NEW.receipt_json IS NOT NULL OR NEW.source_publication_sha256 IS NOT NULL THEN
            RAISE EXCEPTION 'Start with an admitted operation' USING ERRCODE='23514';
          END IF;
          RETURN NEW;
        END IF;
        IF (to_jsonb(NEW)-ARRAY['status','plan_json','prepared_json','receipt_json',
          'source_publication_sha256']) IS DISTINCT FROM
          (to_jsonb(OLD)-ARRAY['status','plan_json','prepared_json','receipt_json',
          'source_publication_sha256'])
          OR (OLD.plan_json IS NOT NULL AND NEW.plan_json::jsonb IS DISTINCT FROM OLD.plan_json::jsonb)
          OR (OLD.prepared_json IS NOT NULL
            AND NEW.prepared_json::jsonb IS DISTINCT FROM OLD.prepared_json::jsonb)
          OR (OLD.receipt_json IS NOT NULL
            AND NEW.receipt_json::jsonb IS DISTINCT FROM OLD.receipt_json::jsonb)
          OR (OLD.status='admitted' AND NEW.status NOT IN ('admitted','prepared'))
          OR (OLD.status='prepared' AND NEW.status NOT IN ('prepared','committed'))
          OR (OLD.status='committed' AND NEW.status<>'committed')
          OR (OLD.source_publication_sha256 IS NOT NULL
            AND NEW.source_publication_sha256 IS DISTINCT FROM OLD.source_publication_sha256)
          OR (NEW.source_publication_sha256 IS DISTINCT FROM OLD.source_publication_sha256 AND
            (OLD.status<>'admitted' OR NEW.status<>'admitted'
              OR OLD.plan_json IS NULL OR NEW.source_attempt_id IS NULL))
        THEN RAISE EXCEPTION 'Immutable structured bulk operation' USING ERRCODE='55000'; END IF;
        IF NEW.source_attempt_id IS NOT NULL AND NEW.status IN ('prepared','committed')
          AND NEW.source_publication_sha256 IS NULL THEN
          RAISE EXCEPTION 'Source operation requires frozen publication digest' USING ERRCODE='23514';
        END IF;
        IF NEW.receipt_json IS NOT NULL AND
          ((NEW.source_attempt_id IS NOT NULL AND
            (NEW.receipt_json->>'source_attempt_id' IS DISTINCT FROM NEW.source_attempt_id OR
             NEW.receipt_json->>'source_publication_sha256' IS DISTINCT FROM NEW.source_publication_sha256))
           OR (NEW.source_attempt_id IS NULL AND
            (NEW.receipt_json->>'source_attempt_id' IS NOT NULL
              OR NEW.receipt_json->>'source_publication_sha256' IS NOT NULL))) THEN
          RAISE EXCEPTION 'Native receipt publication binding mismatch' USING ERRCODE='23514';
        END IF;
        RETURN NEW;
      END $$""")


def downgrade():
    raise RuntimeError("Retain source publication binding; use a reviewed forward migration")
