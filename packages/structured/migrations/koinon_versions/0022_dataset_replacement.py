# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Permit retained-dataset replacement with an immutable exact whole-file baseline."""

import sqlalchemy as sa
from alembic import op

revision = "0022_dataset_replacement"
down_revision = "0021_metadata_provenance"


def upgrade():
    if op.get_bind().dialect.name != "postgresql":
        raise RuntimeError("Dataset replacement requires PostgreSQL")
    op.execute("""ALTER TABLE flyquery_bulk_operations
        ADD COLUMN operation_kind varchar(16) NOT NULL DEFAULT 'initial',
        ADD COLUMN baseline_json json,
        ADD COLUMN baseline_sha256 varchar(64),
        ADD CONSTRAINT ck_structured_bulk_kind CHECK(operation_kind IN ('initial','replace')),
        ADD CONSTRAINT ck_structured_bulk_baseline CHECK(
          (operation_kind='initial' AND baseline_json IS NULL AND baseline_sha256 IS NULL)
          OR (operation_kind='replace' AND baseline_json IS NOT NULL AND baseline_sha256 IS NOT NULL
            AND jsonb_typeof(baseline_json::jsonb)='object' AND
            octet_length(baseline_json::jsonb::text)<=262144
            AND baseline_sha256=public.koinon_json_sha256(baseline_json::jsonb)))""")
    inspector = sa.inspect(op.get_bind())
    for constraint in inspector.get_unique_constraints("flyquery_bulk_operations"):
        if constraint["column_names"] == ["dataset_id"]:
            op.drop_constraint(constraint["name"], "flyquery_bulk_operations", type_="unique")
    op.execute(
        "CREATE UNIQUE INDEX uq_structured_bulk_initial_dataset ON "
        "flyquery_bulk_operations(dataset_id) WHERE operation_kind='initial'"
    )
    op.execute(
        "CREATE INDEX ix_structured_bulk_dataset ON "
        "flyquery_bulk_operations(tenant_id,workspace_id,dataset_id,id)"
    )
    # The existing whole-row guard excludes only status/plan/prepared/receipt, so
    # the added admission fields are automatically immutable on every update.
    op.execute("""CREATE FUNCTION public.koinon_dataset_baseline_guard() RETURNS trigger
        LANGUAGE plpgsql SET search_path=pg_catalog,public AS $$
        DECLARE b jsonb; member jsonb; n integer;
        BEGIN
          IF NEW.operation_kind='initial' THEN RETURN NEW; END IF;
          b=NEW.baseline_json::jsonb;
          IF b IS NULL OR b->>'schema' IS DISTINCT FROM 'koinon.dataset-replacement-baseline.v1'
            OR (SELECT count(*) FROM jsonb_object_keys(b))<>13
            OR b->>'dataset_id' IS DISTINCT FROM NEW.dataset_id::text
            OR b->>'catalog_dataset_id' IS DISTINCT FROM NEW.catalog_dataset_id
            OR jsonb_typeof(b->'members') IS DISTINCT FROM 'array'
            OR jsonb_array_length(b->'members') NOT BETWEEN 1 AND 16
            OR jsonb_typeof(b->'source_generation') IS DISTINCT FROM 'number'
            OR jsonb_typeof(b->'policy_revision') IS DISTINCT FROM 'number'
            OR (b->>'source_generation') !~ '^[1-9][0-9]{0,9}$'
            OR (b->>'policy_revision') !~ '^[1-9][0-9]{0,9}$'
            OR NOT coalesce(b->>'sha256' ~ '^[0-9a-f]{64}$',false)
            OR EXISTS(SELECT 1 FROM
            unnest(ARRAY['source_attempt_id','imported_version_id','catalog_file_version_id',
              'policy_id','local_revision']) key
              WHERE jsonb_typeof(b->key) IS DISTINCT FROM 'string' OR length(b->>key) NOT BETWEEN 1 AND
              128)
            OR NOT EXISTS(SELECT 1 FROM public.flyquery_datasets d WHERE d.id=NEW.dataset_id
              AND d.tenant_id=NEW.tenant_id AND d.workspace_id=NEW.workspace_id)
            OR NOT EXISTS(SELECT 1 FROM public.flyquery_files f WHERE f.id::text=b->>'native_file_id'
              AND f.dataset_id=NEW.dataset_id AND f.tenant_id=NEW.tenant_id AND
              f.workspace_id=NEW.workspace_id
              AND f.id<>NEW.file_id AND f.content_hash_sha256=b->>'sha256' AND f.status='PARSED')
          THEN RAISE EXCEPTION 'complete dataset replacement baseline required' USING ERRCODE='23514';
          END IF;
          FOR member IN SELECT value FROM jsonb_array_elements(b->'members') LOOP
            IF jsonb_typeof(member)<>'object' OR (SELECT count(*) FROM jsonb_object_keys(member))<>7
              OR EXISTS(SELECT 1 FROM
              unnest(ARRAY['member_key','table_id','catalog_table_id','snapshot_id',
                'source_file_id','local_revision','sha256']) key
                WHERE jsonb_typeof(member->key) IS DISTINCT FROM 'string' OR length(member->>key) NOT
                BETWEEN 1 AND 2048)
              OR member->>'source_file_id' IS DISTINCT FROM b->>'native_file_id'
              OR NOT coalesce(member->>'sha256' ~ '^[0-9a-f]{64}$',false)
              OR NOT EXISTS(SELECT 1 FROM public.flyquery_tables t JOIN public.flyquery_schema_snapshots s
                ON s.id=t.current_snapshot_id AND s.table_id=t.id AND s.dataset_id=t.dataset_id
                WHERE t.id::text=member->>'table_id' AND t.dataset_id=NEW.dataset_id
                  AND t.tenant_id=NEW.tenant_id AND t.workspace_id=NEW.workspace_id
                  AND t.source_file_id::text=member->>'source_file_id' AND t.is_active
                  AND t.current_snapshot_id::text=member->>'snapshot_id' AND s.status='READY'
                  AND s.tenant_id=NEW.tenant_id AND s.workspace_id=NEW.workspace_id)
            THEN RAISE EXCEPTION 'replacement member baseline mismatch' USING ERRCODE='23514'; END IF;
          END LOOP;
          n=jsonb_array_length(b->'members');
          IF (SELECT count(DISTINCT value->>'member_key') FROM jsonb_array_elements(b->'members'))<>n
            OR (SELECT count(DISTINCT value->>'table_id') FROM jsonb_array_elements(b->'members'))<>n
            OR (SELECT count(DISTINCT value->>'catalog_table_id') FROM
            jsonb_array_elements(b->'members'))<>n
            OR (SELECT count(DISTINCT value->>'snapshot_id') FROM jsonb_array_elements(b->'members'))<>n
            OR (SELECT count(*) FROM public.flyquery_tables t WHERE t.dataset_id=NEW.dataset_id
                AND t.tenant_id=NEW.tenant_id AND t.workspace_id=NEW.workspace_id AND t.is_active
                AND t.source_file_id::text=b->>'native_file_id')<>n
          THEN RAISE EXCEPTION 'replacement requires the complete unique member set' USING
          ERRCODE='23514'; END IF;
          RETURN NEW;
        END $$""")
    op.execute(
        "CREATE TRIGGER validate_replacement_baseline BEFORE INSERT ON "
        "flyquery_bulk_operations FOR EACH ROW EXECUTE FUNCTION "
        "public.koinon_dataset_baseline_guard()"
    )
    op.execute("REVOKE ALL ON FUNCTION public.koinon_dataset_baseline_guard() FROM PUBLIC")
    _replacement_plan_guard()
    op.execute("""CREATE FUNCTION public.koinon_retain_bulk_table() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN RAISE EXCEPTION 'Retain structured bulk receipts' USING ERRCODE='23514'; END $$""")
    op.execute(
        "CREATE TRIGGER retain_bulk_table BEFORE TRUNCATE ON flyquery_bulk_operations "
        "EXECUTE FUNCTION public.koinon_retain_bulk_table()"
    )
    op.execute("REVOKE ALL ON FUNCTION public.koinon_retain_bulk_table() FROM PUBLIC")


def _replacement_plan_guard():
    op.execute("""CREATE FUNCTION public.koinon_replacement_plan_guard() RETURNS trigger
        LANGUAGE plpgsql SET search_path=pg_catalog AS $$
        DECLARE plan jsonb; member jsonb; prior jsonb; n integer;
        BEGIN
          IF NEW.operation_kind<>'replace' OR NEW.plan_json IS NULL THEN RETURN NEW; END IF;
          plan=NEW.plan_json::jsonb;
          IF jsonb_typeof(plan) IS DISTINCT FROM 'array' OR jsonb_array_length(plan) NOT BETWEEN 1 AND 32
            OR (SELECT count(*) FROM jsonb_array_elements(plan) p WHERE p->>'action' IN ('retain','add'))
            NOT BETWEEN 1 AND 16
          THEN RAISE EXCEPTION 'invalid replacement member plan' USING ERRCODE='23514'; END IF;
          n=jsonb_array_length(plan);
          IF (SELECT count(DISTINCT p->>'member_key') FROM jsonb_array_elements(plan) p)<>n
            OR (SELECT count(DISTINCT p->>'table_id') FROM jsonb_array_elements(plan) p)<>n
            OR (SELECT count(DISTINCT p->>'catalog_table_id') FROM jsonb_array_elements(plan) p)<>n
          THEN RAISE EXCEPTION 'replacement plan identities must be unique' USING ERRCODE='23514'; END IF;
          FOR member IN SELECT value FROM jsonb_array_elements(plan) LOOP
            IF member->>'schema' IS DISTINCT FROM 'koinon.dataset-replacement-member.v1'
              OR NOT coalesce(member->>'action' IN ('retain','add','remove'),false)
              OR EXISTS(SELECT 1 FROM
              unnest(ARRAY['member_key','table_id','catalog_table_id','snapshot_id']) key
                WHERE jsonb_typeof(member->key) IS DISTINCT FROM 'string' OR length(member->>key) NOT
                BETWEEN 1 AND 2048)
            THEN RAISE EXCEPTION 'invalid replacement member plan' USING ERRCODE='23514'; END IF;
            SELECT p INTO prior FROM jsonb_array_elements(NEW.baseline_json::jsonb->'members') p
              WHERE p->>'table_id'=member->>'table_id';
            IF (member->>'action'='add' AND prior IS NOT NULL)
              OR (member->>'action' IN ('retain','remove') AND (prior IS NULL
                OR prior->>'catalog_table_id' IS DISTINCT FROM member->>'catalog_table_id'))
              OR (member->>'action'='retain' AND prior->>'snapshot_id'=member->>'snapshot_id')
              OR (member->>'action'='remove' AND prior->>'snapshot_id' IS DISTINCT FROM
              member->>'snapshot_id')
            THEN RAISE EXCEPTION 'replacement plan must preserve baseline identities' USING
            ERRCODE='23514'; END IF;
          END LOOP;
          IF EXISTS(SELECT 1 FROM jsonb_array_elements(NEW.baseline_json::jsonb->'members')
          baseline_member
            WHERE NOT EXISTS(SELECT 1 FROM jsonb_array_elements(plan) p
              WHERE p->>'table_id'=baseline_member->>'table_id' AND p->>'action' IN ('retain','remove')))
          THEN RAISE EXCEPTION 'replacement plan must cover the whole baseline' USING ERRCODE='23514';
          END IF;
          RETURN NEW;
        END $$""")
    op.execute(
        "CREATE TRIGGER validate_replacement_plan BEFORE UPDATE ON "
        "flyquery_bulk_operations FOR EACH ROW EXECUTE FUNCTION "
        "public.koinon_replacement_plan_guard()"
    )
    op.execute("REVOKE ALL ON FUNCTION public.koinon_replacement_plan_guard() FROM PUBLIC")


def downgrade():
    raise RuntimeError("Recover dataset replacement through a reviewed forward migration")
