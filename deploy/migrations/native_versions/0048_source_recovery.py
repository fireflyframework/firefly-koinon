# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Retain policy decisions and distinguish replacement and query commit identities.

Expansion preserves existing producers and receipts. Recovery is a reviewed forward
migration; never delete retained origins or downgrade these constraints.
"""

import sqlalchemy as sa
from alembic import op

revision = "koinon_0048_source_recovery"
down_revision = "koinon_0047_source_controls"


def upgrade():
    if op.get_bind().dialect.name != "postgresql":
        raise RuntimeError("Source recovery requires PostgreSQL")
    with op.get_context().autocommit_block():
        op.execute("SET lock_timeout='5s'")
        try:
            invalid = (
                op.get_bind()
                .execute(
                    sa.text(
                        "SELECT NOT indisvalid FROM pg_index "
                        "WHERE indexrelid=to_regclass('public.ix_content_producer_audit')"
                    )
                )
                .scalar()
            )
            if invalid:
                op.execute("DROP INDEX CONCURRENTLY public.ix_content_producer_audit")
            op.execute(
                "CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_content_producer_audit "
                "ON lattice_audit(tenant_id,resource_id,subject) WHERE action='knowledge.content.recorded'"
            )
        finally:
            op.execute("RESET lock_timeout")
    op.execute(
        "ALTER TABLE koinon_content_imports ALTER COLUMN intake_item_id DROP NOT NULL"
    )
    op.execute("""ALTER TABLE koinon_content_imports
        ADD COLUMN content_operation_id varchar(64) REFERENCES lattice_catalog(id),
        ADD CONSTRAINT uq_content_import_operation UNIQUE(content_operation_id),
        ADD CONSTRAINT ck_content_import_producer CHECK
            ((intake_item_id IS NULL) <> (content_operation_id IS NULL))""")
    _policy_receipts()
    _query_descriptor()
    _replacement_guard()


def _policy_receipts():
    op.execute("""CREATE TABLE koinon_content_policy_operations (
        id varchar(64) PRIMARY KEY, tenant_id varchar(64) NOT NULL,
        owner varchar(512) NOT NULL, operation_id varchar(64) NOT NULL,
        action varchar(32) NOT NULL CHECK(action IN ('review','apply')),
        mapping_id varchar(64) NOT NULL, policy_id varchar(64) NOT NULL,
        expected_policy_revision integer CHECK(expected_policy_revision>0),
        result_policy_revision integer NOT NULL CHECK(result_policy_revision>0),
        payload_sha256 varchar(64) NOT NULL CHECK(payload_sha256 ~ '^[0-9a-f]{64}$'),
        result_json json NOT NULL, created_at timestamptz NOT NULL,
        CONSTRAINT uq_content_policy_operation UNIQUE(tenant_id,owner,operation_id),
        FOREIGN KEY(tenant_id,owner,mapping_id) REFERENCES koinon_content_mappings(tenant_id,owner,id),
        FOREIGN KEY(tenant_id,mapping_id,policy_id) REFERENCES
        koinon_content_policies(tenant_id,mapping_id,id),
        CHECK(operation_id ~ '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$')
    )""")
    op.execute(
        "CREATE INDEX ix_content_policy_operation_policy ON "
        "koinon_content_policy_operations(tenant_id,mapping_id,policy_id)"
    )
    op.execute("REVOKE ALL ON koinon_content_policy_operations FROM PUBLIC")
    op.execute("""CREATE FUNCTION public.koinon_policy_receipt_guard() RETURNS trigger
        LANGUAGE plpgsql SET search_path=pg_catalog,public AS $$
        DECLARE p public.koinon_content_policies; r jsonb;
        BEGIN
          IF TG_OP<>'INSERT' THEN RAISE EXCEPTION 'policy receipts are immutable' USING ERRCODE='23514';
          END IF;
          SELECT * INTO p FROM public.koinon_content_policies
            WHERE id=NEW.policy_id AND tenant_id=NEW.tenant_id AND mapping_id=NEW.mapping_id AND
            owner=NEW.owner;
          r=NEW.result_json::jsonb;
          IF p.id IS NULL OR p.revision<>NEW.result_policy_revision
            OR (NEW.action='apply' AND NEW.expected_policy_revision IS DISTINCT FROM p.revision)
            OR (NEW.action='review' AND NEW.expected_policy_revision IS DISTINCT FROM
                CASE WHEN p.revision=1 THEN NULL ELSE p.revision-1 END)
            OR jsonb_typeof(r) IS DISTINCT FROM 'object' OR octet_length(r::text)>16384
            OR (SELECT count(*) FROM jsonb_object_keys(r))<>11
            OR r IS DISTINCT FROM jsonb_build_object(
              'schema','koinon.source-policy-operation.v1','receipt_id',NEW.id,
              'operation_id',NEW.operation_id,'action',NEW.action,'mapping_id',NEW.mapping_id,
              'policy_id',NEW.policy_id,'expected_policy_revision',NEW.expected_policy_revision,
              'result_policy_revision',NEW.result_policy_revision,'review_digest',p.review_digest,
              'review_expires_at',r->>'review_expires_at',
              'disposition',CASE WHEN NEW.action='apply' THEN 'accepted' ELSE 'reviewed' END)
            OR jsonb_typeof(r->'review_expires_at') IS DISTINCT FROM 'string'
            OR (r->>'review_expires_at')::timestamptz IS DISTINCT FROM p.review_expires_at
          THEN RAISE EXCEPTION 'invalid policy operation receipt' USING ERRCODE='23514'; END IF;
          RETURN NEW;
        EXCEPTION WHEN invalid_datetime_format OR datetime_field_overflow THEN
          RAISE EXCEPTION 'invalid policy operation receipt expiry' USING ERRCODE='23514';
        END $$""")
    # There are eleven bounded fields; JSON equality also rejects any extra key.
    op.execute("""CREATE TRIGGER guard_policy_receipt BEFORE INSERT OR UPDATE OR DELETE
        ON koinon_content_policy_operations FOR EACH ROW EXECUTE FUNCTION
        public.koinon_policy_receipt_guard()""")
    op.execute("""CREATE TRIGGER retain_policy_receipts BEFORE TRUNCATE ON koinon_content_policy_operations
        EXECUTE FUNCTION public.koinon_policy_receipt_guard()""")
    op.execute("""CREATE FUNCTION public.koinon_policy_acceptance_guard() RETURNS trigger
        LANGUAGE plpgsql SET search_path=pg_catalog,public AS $$
        DECLARE p public.koinon_content_policies;
        BEGIN
          IF TG_TABLE_NAME='koinon_content_policies' THEN
            IF TG_OP='UPDATE' AND OLD.accepted_at IS NOT NULL THEN RETURN NULL; END IF;
            SELECT * INTO p FROM public.koinon_content_policies WHERE id=NEW.id;
          ELSE
            IF NEW.action<>'apply' THEN RETURN NULL; END IF;
            SELECT * INTO p FROM public.koinon_content_policies WHERE id=NEW.policy_id;
          END IF;
          IF p.accepted_at IS NOT NULL OR TG_TABLE_NAME='koinon_content_policy_operations' THEN
            IF p.accepted_at IS NULL OR EXISTS(SELECT 1 FROM public.koinon_content_policies newer
                WHERE newer.tenant_id=p.tenant_id AND newer.mapping_id=p.mapping_id AND
                newer.revision>p.revision)
              OR NOT EXISTS(
              SELECT 1 FROM public.koinon_content_policy_operations r
              WHERE r.tenant_id=p.tenant_id AND r.owner=p.owner AND r.mapping_id=p.mapping_id
                AND r.policy_id=p.id AND r.action='apply' AND r.operation_id=p.accepted_operation_id
                AND r.result_policy_revision=p.revision AND p.accepted_by=p.owner)
            THEN RAISE EXCEPTION 'matching policy acceptance receipt required' USING ERRCODE='23514'; END
            IF;
          END IF;
          RETURN NULL;
        END $$""")
    for table in ("koinon_content_policies", "koinon_content_policy_operations"):
        op.execute(
            f"CREATE CONSTRAINT TRIGGER complete_policy_acceptance AFTER INSERT OR UPDATE ON {table} DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION public.koinon_policy_acceptance_guard()"
        )
    op.execute(
        "REVOKE ALL ON FUNCTION "
        "public.koinon_policy_receipt_guard(),public.koinon_policy_acceptance_guard() "
        "FROM PUBLIC"
    )


def _query_descriptor():
    op.execute(
        "ALTER TABLE koinon_query_batch_items ADD COLUMN native_commit_json json"
    )
    op.execute(
        "ALTER TABLE koinon_query_batch_items DROP CONSTRAINT ck_query_item_receipt"
    )
    op.execute("""ALTER TABLE koinon_query_batch_items ADD CONSTRAINT ck_query_item_receipt
        CHECK(status<>'succeeded' OR result_json IS NOT NULL OR native_commit_json IS NOT NULL)""")
    op.execute("""CREATE OR REPLACE FUNCTION public.koinon_query_batch_items_guard() RETURNS trigger
        LANGUAGE plpgsql SET search_path=pg_catalog AS $$
        BEGIN
          IF TG_OP='DELETE' THEN RAISE EXCEPTION 'Retain query manifests and receipts'; END IF;
          IF (to_jsonb(NEW)-ARRAY['status','result_json','error_code','native_commit_json']) IS DISTINCT
          FROM
             (to_jsonb(OLD)-ARRAY['status','result_json','error_code','native_commit_json'])
             OR (OLD.result_json IS NOT NULL AND NEW.result_json::jsonb IS DISTINCT FROM
             OLD.result_json::jsonb)
             OR (OLD.native_commit_json IS NOT NULL AND NEW.native_commit_json::jsonb IS DISTINCT FROM
             OLD.native_commit_json::jsonb)
             OR (OLD.status='succeeded' AND NEW.status<>'succeeded')
          THEN RAISE EXCEPTION 'Immutable query identity or receipt'; END IF;
          RETURN NEW;
        END $$""")
    op.execute("""CREATE FUNCTION public.koinon_query_descriptor_guard() RETURNS trigger
        LANGUAGE plpgsql SET search_path=pg_catalog AS $$
        DECLARE r jsonb;
        BEGIN
          r=NEW.native_commit_json::jsonb;
          IF r IS NULL THEN RETURN NEW; END IF;
          IF jsonb_typeof(r) IS DISTINCT FROM 'object' OR octet_length(r::text)>4096
            OR (SELECT count(*) FROM jsonb_object_keys(r))<>7
            OR r->>'schema' IS DISTINCT FROM 'koinon.native-query-commit.v1'
            OR r->>'operation_id' IS DISTINCT FROM NEW.id
            OR NOT coalesce(r->>'operation_id' ~
            '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$',false)
            OR NOT coalesce(r->>'query_id' ~
            '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$',false)
            OR NOT coalesce(r->>'identity_sha256' ~ '^[0-9a-f]{64}$',false)
            OR NOT coalesce(r->>'receipt_sha256' ~ '^[0-9a-f]{64}$',false)
            OR NOT coalesce(r->>'manifest_sha256' ~ '^[0-9a-f]{64}$',false)
            OR r->>'outcome' IS DISTINCT FROM NEW.status OR NEW.status NOT IN ('succeeded','failed')
            OR EXISTS(SELECT 1 FROM jsonb_each(r) WHERE jsonb_typeof(value)<>'string')
          THEN RAISE EXCEPTION 'invalid native commit descriptor' USING ERRCODE='23514'; END IF;
          RETURN NEW;
        END $$""")
    op.execute(
        "CREATE TRIGGER check_query_descriptor BEFORE INSERT OR UPDATE ON "
        "koinon_query_batch_items FOR EACH ROW EXECUTE FUNCTION "
        "public.koinon_query_descriptor_guard()"
    )
    op.execute(
        "REVOKE ALL ON FUNCTION public.koinon_query_descriptor_guard() FROM PUBLIC"
    )


def _replacement_guard():
    op.execute("""CREATE FUNCTION public.koinon_replacement_producer_guard() RETURNS trigger
        LANGUAGE plpgsql SET search_path=pg_catalog,public AS $$
        DECLARE m public.koinon_content_mappings; c public.lattice_catalog; original_receipt jsonb;
        BEGIN
          IF NEW.content_operation_id IS NULL THEN RETURN NEW; END IF;
          IF TG_OP='UPDATE' THEN
            SELECT a.receipt_json::jsonb INTO original_receipt FROM public.koinon_content_imported_assets
            b
              JOIN public.koinon_content_imports a ON a.id=b.initial_attempt_id
              WHERE b.asset_id=NEW.asset_id AND b.tenant_id=NEW.tenant_id;
            IF NEW.receipt_json IS NOT NULL AND (
                NEW.receipt_json::jsonb->>'operation_id' IS DISTINCT FROM NEW.content_operation_id
                OR NEW.receipt_json::jsonb->>'sha256' IS DISTINCT FROM NEW.sha256
                OR NEW.receipt_json::jsonb->>'size_bytes' IS DISTINCT FROM NEW.size_bytes::text
                OR original_receipt IS NULL
                OR NEW.receipt_json::jsonb->>'domain' IS DISTINCT FROM original_receipt->>'domain'
                OR NEW.receipt_json::jsonb->>'native_workspace_id' IS DISTINCT FROM
                original_receipt->>'native_workspace_id'
                OR NEW.receipt_json::jsonb->>'native_source_id' IS DISTINCT FROM
                original_receipt->>'native_source_id'
                OR NEW.receipt_json::jsonb->>'native_asset_id' IS DISTINCT FROM
                original_receipt->>'native_asset_id'
                OR coalesce(length(NEW.receipt_json::jsonb->>CASE WHEN
                original_receipt->>'domain'='canon' THEN 'source_version_id' ELSE 'file_version_id'
                END),0) NOT BETWEEN 1 AND 64
                OR (original_receipt->>'domain'='canon' AND
                coalesce(length(NEW.receipt_json::jsonb->>'extraction_id'),0) NOT BETWEEN 1 AND 64))
            THEN RAISE EXCEPTION 'replacement receipt producer mismatch' USING ERRCODE='23514'; END IF;
            RETURN NEW;
          END IF;
          SELECT * INTO m FROM public.koinon_content_mappings WHERE id=NEW.mapping_id AND
          tenant_id=NEW.tenant_id;
          SELECT * INTO c FROM public.lattice_catalog WHERE id=NEW.content_operation_id AND
          tenant_id=NEW.tenant_id;
          IF m.id IS NULL OR c.id IS NULL OR c.kind<>'index_version' OR c.created_by<>m.owner OR
          c.status<>'pending'
            OR c.workspace_id IS DISTINCT FROM m.workspace_id OR c.project_id IS DISTINCT FROM
            m.project_id
            OR c.metadata_json::jsonb->>'sha256' IS DISTINCT FROM NEW.sha256
            OR c.metadata_json::jsonb->>'bytes' IS DISTINCT FROM NEW.size_bytes::text
            OR c.metadata_json::jsonb->'_koinon_processing'->>'state' IS DISTINCT FROM 'unknown'
            OR c.metadata_json::jsonb->'_koinon_processing'->>'operation' IS DISTINCT FROM
            c.metadata_json::jsonb->>'operation'
            OR NOT EXISTS(SELECT 1 FROM public.koinon_content_imported_assets a
              JOIN public.koinon_content_imports original ON original.id=a.initial_attempt_id
              JOIN public.lattice_catalog asset ON asset.id=a.asset_id
              WHERE a.tenant_id=NEW.tenant_id AND a.source_id=NEW.source_id AND a.asset_id=NEW.asset_id
                AND original.object_id=NEW.object_id AND original.mapping_id=NEW.mapping_id
                AND ((asset.kind='document' AND c.parent_id=NEW.source_id
                    AND c.metadata_json::jsonb->>'operation' IN ('document.replace','document.reingest'))
                  OR (asset.kind='dataset' AND c.parent_id=NEW.asset_id
                    AND c.metadata_json::jsonb->>'operation'='dataset.replace')))
            OR NOT EXISTS(SELECT 1 FROM public.koinon_content_objects o WHERE o.id=NEW.object_id
                AND o.mapping_id=m.id AND o.tenant_id=m.tenant_id AND o.item_id=NEW.remote_item_id
                AND NEW.provider=m.provider AND NEW.external_subject=m.external_subject
                AND NEW.external_tenant IS NOT DISTINCT FROM m.external_tenant AND
                NEW.drive_id=m.drive_id)
            OR NOT EXISTS(SELECT 1 FROM public.lattice_audit a WHERE a.tenant_id=NEW.tenant_id
                AND a.subject=m.owner AND a.resource_id=c.id AND a.action='knowledge.content.recorded'
                AND a.details::jsonb->>'operation'=c.metadata_json::jsonb->>'operation'
                AND a.details::jsonb->>'state'='unknown')
          THEN RAISE EXCEPTION 'replacement requires retained source and recorded producer proof' USING
          ERRCODE='23514'; END IF;
          IF NEW.receipt_json IS NOT NULL THEN RAISE EXCEPTION 'replacement starts uncommitted' USING
          ERRCODE='23514'; END IF;
          RETURN NEW;
        END $$""")
    op.execute(
        "CREATE TRIGGER check_replacement_producer BEFORE INSERT OR UPDATE ON "
        "koinon_content_imports FOR EACH ROW EXECUTE FUNCTION "
        "public.koinon_replacement_producer_guard()"
    )
    op.execute(
        "REVOKE ALL ON FUNCTION public.koinon_replacement_producer_guard() FROM PUBLIC"
    )


def downgrade():
    raise RuntimeError("Recover source identities with a reviewed forward migration")
