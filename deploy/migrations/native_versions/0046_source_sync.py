# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Expand durable source synchronization, immutable origins and reader snapshots.

Existing mappings are retained without an enabled sync state. No provider work is
activated by this migration. Reversal is a reviewed forward fix: disable the new
service paths and retain policies, snapshots and provenance, never drop them.
"""

from alembic import op

revision = "koinon_0046_source_sync"
down_revision = "koinon_0045_content_sources"
branch_labels = None
depends_on = None


def upgrade():
    # The one new referenced key on a retained table is built without blocking writes.
    with op.get_context().autocommit_block():
        op.execute(
            "CREATE UNIQUE INDEX CONCURRENTLY IF NOT EXISTS uq_content_mapping_owner_identity ON koinon_content_mappings(tenant_id,owner,id)"
        )
    op.execute("SET LOCAL lock_timeout = '5s'")
    op.execute(
        "ALTER TABLE koinon_content_mappings ADD CONSTRAINT uq_content_mapping_owner_identity UNIQUE USING INDEX uq_content_mapping_owner_identity"
    )
    op.execute("""
        ALTER TABLE koinon_content_objects
        ADD COLUMN remote_parent_id varchar(1024), ADD COLUMN remote_name varchar(1024),
        ADD COLUMN remote_kind varchar(32), ADD COLUMN remote_ancestry_json json,
        ADD COLUMN last_complete_scan_generation integer,
        ADD COLUMN published_native_version_id varchar(64), ADD COLUMN published_local_revision varchar(128),
        ADD COLUMN published_sha256 varchar(64), ADD COLUMN expected_local_revision varchar(128),
        ADD COLUMN expected_sha256 varchar(64)
    """)
    op.execute("""
        CREATE TABLE koinon_content_policies (
          id varchar(64) PRIMARY KEY, tenant_id varchar(64) NOT NULL, owner varchar(512) NOT NULL,
          mapping_id varchar(64) NOT NULL, revision integer NOT NULL CHECK(revision>0),
          mapping_revision integer NOT NULL CHECK(mapping_revision>0), authority_sha256 varchar(64) NOT NULL,
          policy_json json NOT NULL, policy_sha256 varchar(64) NOT NULL, root_ancestry_json json NOT NULL,
          review_id varchar(64) NOT NULL, review_digest varchar(64) NOT NULL,
          review_expires_at timestamptz NOT NULL, accepted_by varchar(512), accepted_session_hash varchar(64),
          accepted_operation_id varchar(64), accepted_at timestamptz, created_at timestamptz NOT NULL,
          FOREIGN KEY(tenant_id,owner,mapping_id) REFERENCES koinon_content_mappings(tenant_id,owner,id),
          CONSTRAINT uq_content_policy_identity UNIQUE(tenant_id,mapping_id,id),
          CONSTRAINT uq_content_policy_revision UNIQUE(tenant_id,mapping_id,revision),
          UNIQUE(tenant_id,owner,accepted_operation_id),
          CHECK(num_nonnulls(accepted_by,accepted_session_hash,accepted_operation_id,accepted_at)=0
            OR (num_nonnulls(accepted_by,accepted_session_hash,accepted_operation_id,accepted_at)=4
                AND accepted_by=owner AND accepted_at<=review_expires_at)),
          CHECK(jsonb_typeof(root_ancestry_json::jsonb)='array' AND jsonb_array_length(root_ancestry_json::jsonb)>0)
        )
    """)
    op.execute(
        "CREATE INDEX ix_content_policy_owner ON koinon_content_policies(tenant_id,owner,created_at,id)"
    )
    op.execute("""
        CREATE TABLE koinon_content_sync_states (
          mapping_id varchar(64) PRIMARY KEY REFERENCES koinon_content_mappings(id), tenant_id varchar(64) NOT NULL,
          accepted_policy_id varchar(64) NOT NULL, enabled boolean NOT NULL, revision integer NOT NULL CHECK(revision>0),
          next_run_at timestamptz, cursor_ciphertext bytea, scan_generation integer NOT NULL CHECK(scan_generation>=0),
          last_complete_scan_generation integer NOT NULL CHECK(last_complete_scan_generation>=0 AND last_complete_scan_generation<=scan_generation),
          updated_at timestamptz NOT NULL,
          FOREIGN KEY(tenant_id,mapping_id,accepted_policy_id) REFERENCES koinon_content_policies(tenant_id,mapping_id,id)
        )
    """)
    op.execute(
        "CREATE INDEX ix_content_sync_due ON koinon_content_sync_states(next_run_at,tenant_id,mapping_id) WHERE enabled AND next_run_at IS NOT NULL"
    )
    op.execute("""
        CREATE TABLE koinon_content_sync_runs (
          id varchar(64) PRIMARY KEY, tenant_id varchar(64) NOT NULL, mapping_id varchar(64) NOT NULL,
          policy_id varchar(64) NOT NULL, mapping_revision integer NOT NULL CHECK(mapping_revision>0),
          connection_revision integer NOT NULL CHECK(connection_revision>0),
          job_id varchar(64) NOT NULL UNIQUE REFERENCES lattice_jobs(id), trigger_kind varchar(32) NOT NULL,
          operation_id varchar(64) NOT NULL, payload_sha256 varchar(64) NOT NULL, occurrence_key varchar(255),
          status varchar(32) NOT NULL CHECK(status IN ('queued','running','reconciling','succeeded','failed','cancelled','reconnect_required')),
          page_sequence integer NOT NULL CHECK(page_sequence>=0), cursor_ciphertext bytea,
          scan_generation integer NOT NULL CHECK(scan_generation>0), enumeration_complete boolean NOT NULL,
          counters_json json NOT NULL, created_at timestamptz NOT NULL, updated_at timestamptz NOT NULL,
          finished_at timestamptz,
          FOREIGN KEY(tenant_id,mapping_id,policy_id) REFERENCES koinon_content_policies(tenant_id,mapping_id,id),
          CONSTRAINT uq_content_run_identity UNIQUE(tenant_id,mapping_id,id),
          CONSTRAINT uq_content_run_operation UNIQUE(tenant_id,mapping_id,operation_id),
          CONSTRAINT uq_content_run_occurrence UNIQUE(tenant_id,mapping_id,occurrence_key),
          CHECK(trigger_kind IN ('manual','interval','calendar','retry'))
        )
    """)
    op.execute(
        "CREATE UNIQUE INDEX uq_content_run_active ON koinon_content_sync_runs(tenant_id,mapping_id) WHERE status IN ('queued','running','reconciling')"
    )
    op.execute(
        "CREATE INDEX ix_content_run_history ON koinon_content_sync_runs(tenant_id,mapping_id,created_at,id)"
    )
    op.execute("""
        CREATE TABLE koinon_content_sync_work (
          id varchar(64) PRIMARY KEY, tenant_id varchar(64) NOT NULL, mapping_id varchar(64) NOT NULL,
          object_id varchar(64) NOT NULL, generation integer NOT NULL CHECK(generation>0), remote_version varchar(2048),
          event_sha256 varchar(64) NOT NULL, status varchar(32) NOT NULL,
          error_code varchar(64), attempt_id varchar(64) REFERENCES koinon_content_imports(id),
          expected_local_revision varchar(128), expected_sha256 varchar(64),
          created_at timestamptz NOT NULL, updated_at timestamptz NOT NULL,
          FOREIGN KEY(tenant_id,mapping_id,object_id) REFERENCES koinon_content_objects(tenant_id,mapping_id,id),
          CONSTRAINT uq_content_work_generation UNIQUE(tenant_id,mapping_id,object_id,generation),
          CONSTRAINT uq_content_work_identity UNIQUE(tenant_id,mapping_id,object_id,generation,id),
          CHECK(status IN ('admitted','skipped','conflict','processing','imported','failed','removed'))
        )
    """)
    op.execute(
        "CREATE INDEX ix_content_work_pending ON koinon_content_sync_work(tenant_id,mapping_id,status,id)"
    )
    op.execute(
        "CREATE INDEX ix_content_work_attempt ON koinon_content_sync_work(attempt_id) WHERE attempt_id IS NOT NULL"
    )
    op.execute("""
        CREATE TABLE koinon_content_sync_observations (
          id varchar(64) PRIMARY KEY, tenant_id varchar(64) NOT NULL, mapping_id varchar(64) NOT NULL,
          run_id varchar(64) NOT NULL, page_sequence integer NOT NULL CHECK(page_sequence>0),
          item_sequence integer NOT NULL CHECK(item_sequence>=0), object_id varchar(64) NOT NULL,
          generation integer NOT NULL CHECK(generation>0), remote_version varchar(2048), event_json json NOT NULL,
          event_sha256 varchar(64) NOT NULL, work_id varchar(64) NOT NULL, observed_at timestamptz NOT NULL,
          FOREIGN KEY(tenant_id,mapping_id,run_id) REFERENCES koinon_content_sync_runs(tenant_id,mapping_id,id),
          FOREIGN KEY(tenant_id,mapping_id,object_id,generation,work_id) REFERENCES koinon_content_sync_work(tenant_id,mapping_id,object_id,generation,id),
          CONSTRAINT uq_content_observation_position UNIQUE(run_id,page_sequence,item_sequence)
        )
    """)
    op.execute(
        "CREATE INDEX ix_content_observation_work ON koinon_content_sync_observations(work_id)"
    )
    op.execute("""
        CREATE TABLE koinon_content_folder_bindings (
          tenant_id varchar(64) NOT NULL, mapping_id varchar(64) NOT NULL, remote_folder_id varchar(1024) NOT NULL,
          local_folder_id varchar(64) NOT NULL REFERENCES lattice_catalog(id), remote_parent_id varchar(1024),
          local_parent_id varchar(64) NOT NULL REFERENCES lattice_catalog(id), ancestry_json json NOT NULL,
          revision integer NOT NULL CHECK(revision>0), updated_at timestamptz NOT NULL,
          PRIMARY KEY(tenant_id,mapping_id,remote_folder_id),
          FOREIGN KEY(tenant_id,mapping_id) REFERENCES koinon_content_mappings(tenant_id,id)
        )
    """)
    op.execute(
        "CREATE INDEX ix_content_folder_local ON koinon_content_folder_bindings(local_folder_id)"
    )
    op.execute("""
        CREATE TABLE koinon_content_imported_assets (
          asset_id varchar(64) PRIMARY KEY REFERENCES lattice_catalog(id), tenant_id varchar(64) NOT NULL REFERENCES lattice_tenants(id),
          source_id varchar(64) NOT NULL REFERENCES lattice_catalog(id),
          initial_attempt_id varchar(64) NOT NULL UNIQUE REFERENCES koinon_content_imports(id), created_at timestamptz NOT NULL,
          CONSTRAINT uq_content_imported_asset_identity UNIQUE(tenant_id,source_id,asset_id)
        )
    """)
    op.execute(
        "CREATE INDEX ix_content_imported_source ON koinon_content_imported_assets(tenant_id,source_id)"
    )
    op.execute("""
        CREATE TABLE koinon_content_imported_versions (
          attempt_id varchar(64) PRIMARY KEY REFERENCES koinon_content_imports(id), tenant_id varchar(64) NOT NULL,
          source_id varchar(64) NOT NULL, asset_id varchar(64) NOT NULL,
          domain varchar(32) NOT NULL CONSTRAINT ck_content_imported_domain CHECK(domain IN ('canon','structured')),
          native_workspace_id varchar(64) NOT NULL, native_source_id varchar(64) NOT NULL,
          native_asset_id varchar(64) NOT NULL, native_version_id varchar(64) NOT NULL, extraction_id varchar(64),
          created_at timestamptz NOT NULL,
          FOREIGN KEY(tenant_id,source_id,asset_id) REFERENCES koinon_content_imported_assets(tenant_id,source_id,asset_id),
          CONSTRAINT uq_content_imported_native_version UNIQUE(tenant_id,domain,native_workspace_id,native_asset_id,native_version_id)
        )
    """)
    op.execute(
        "CREATE INDEX ix_content_imported_version_asset ON koinon_content_imported_versions(tenant_id,asset_id,created_at)"
    )
    op.execute("""
        CREATE TABLE koinon_content_reader_sets (
          tenant_id varchar(64) NOT NULL REFERENCES lattice_tenants(id), owner varchar(512) NOT NULL,
          revision integer NOT NULL CONSTRAINT ck_content_reader_revision CHECK(revision>=0), updated_at timestamptz NOT NULL,
          PRIMARY KEY(tenant_id,owner)
        )
    """)
    op.execute("""
        CREATE TABLE koinon_content_reader_selections (
          tenant_id varchar(64) NOT NULL, owner varchar(512) NOT NULL, set_revision integer NOT NULL,
          provider varchar(32) NOT NULL, external_tenant_key varchar(1030) NOT NULL, external_tenant varchar(1024),
          connection_id varchar(64) NOT NULL, created_at timestamptz NOT NULL,
          PRIMARY KEY(tenant_id,owner,set_revision,provider,external_tenant_key),
          FOREIGN KEY(tenant_id,owner) REFERENCES koinon_content_reader_sets(tenant_id,owner),
          FOREIGN KEY(tenant_id,owner,connection_id) REFERENCES koinon_content_connections(tenant_id,owner,id),
          CONSTRAINT ck_content_reader_snapshot_revision CHECK(set_revision>0),
          CONSTRAINT ck_content_reader_external_key CHECK(external_tenant_key=CASE WHEN external_tenant IS NULL THEN 'none:' ELSE 'value:' || external_tenant END)
        )
    """)
    op.execute(
        "CREATE INDEX ix_content_reader_connection ON koinon_content_reader_selections(connection_id)"
    )
    op.execute("""
        CREATE TABLE koinon_content_reader_operations (
          tenant_id varchar(64) NOT NULL, owner varchar(512) NOT NULL, operation_id varchar(64) NOT NULL,
          payload_sha256 varchar(64) NOT NULL, result_revision integer NOT NULL, created_at timestamptz NOT NULL,
          PRIMARY KEY(tenant_id,owner,operation_id),
          FOREIGN KEY(tenant_id,owner) REFERENCES koinon_content_reader_sets(tenant_id,owner),
          CONSTRAINT uq_content_reader_operation_revision UNIQUE(tenant_id,owner,result_revision),
          CONSTRAINT ck_content_reader_operation_revision CHECK(result_revision>0)
        )
    """)
    _guards()


def _guards():
    op.execute("""
        CREATE FUNCTION koinon_content_retain_row() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN RAISE EXCEPTION 'retained source identity is immutable' USING ERRCODE='23514'; END $$
    """)
    retained = (
        "policies",
        "sync_states",
        "sync_runs",
        "sync_work",
        "sync_observations",
        "folder_bindings",
        "imported_assets",
        "imported_versions",
        "reader_sets",
        "reader_selections",
        "reader_operations",
    )
    immutable = {
        "sync_observations",
        "imported_assets",
        "imported_versions",
        "reader_selections",
        "reader_operations",
    }
    for suffix in retained:
        table = "koinon_content_" + suffix
        changes = "UPDATE OR DELETE" if suffix in immutable else "DELETE"
        op.execute(
            f"CREATE TRIGGER retain_rows BEFORE {changes} ON {table} FOR EACH ROW EXECUTE FUNCTION koinon_content_retain_row()"
        )
        op.execute(
            f"CREATE TRIGGER retain_table BEFORE TRUNCATE ON {table} EXECUTE FUNCTION koinon_content_retain_row()"
        )
    op.execute("""
        CREATE FUNCTION koinon_content_guard_policy() RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE root text;
        BEGIN
          IF TG_OP='UPDATE' AND (
            (to_jsonb(NEW)-ARRAY['accepted_by','accepted_session_hash','accepted_operation_id','accepted_at']) IS DISTINCT FROM
            (to_jsonb(OLD)-ARRAY['accepted_by','accepted_session_hash','accepted_operation_id','accepted_at'])
            OR (OLD.accepted_at IS NOT NULL AND to_jsonb(NEW) IS DISTINCT FROM to_jsonb(OLD))) THEN
            RAISE EXCEPTION 'review and acceptance are immutable' USING ERRCODE='23514';
          END IF;
          SELECT root_id INTO root FROM koinon_content_mappings WHERE tenant_id=NEW.tenant_id AND id=NEW.mapping_id AND owner=NEW.owner;
          IF root IS NULL OR NOT NEW.root_ancestry_json::jsonb @> jsonb_build_array(root) THEN
            RAISE EXCEPTION 'verified root ancestry required' USING ERRCODE='23514';
          END IF;
          RETURN NEW;
        END $$
    """)
    op.execute(
        "CREATE TRIGGER guard_policy BEFORE INSERT OR UPDATE ON koinon_content_policies FOR EACH ROW EXECUTE FUNCTION koinon_content_guard_policy()"
    )
    op.execute("""
        CREATE FUNCTION koinon_content_guard_mapping_identity() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
          IF (NEW.id,NEW.tenant_id,NEW.owner,NEW.connection_id,NEW.provider,NEW.external_subject,NEW.external_tenant,NEW.issuer,NEW.drive_id,NEW.root_id)
            IS DISTINCT FROM (OLD.id,OLD.tenant_id,OLD.owner,OLD.connection_id,OLD.provider,OLD.external_subject,OLD.external_tenant,OLD.issuer,OLD.drive_id,OLD.root_id) THEN
            RAISE EXCEPTION 'mapping source identity is immutable' USING ERRCODE='23503';
          END IF;
          IF NEW.revision<OLD.revision THEN
            RAISE EXCEPTION 'mapping revision cannot regress' USING ERRCODE='23514';
          END IF;
          RETURN NEW;
        END $$
    """)
    op.execute(
        "CREATE TRIGGER guard_mapping_identity BEFORE UPDATE ON koinon_content_mappings FOR EACH ROW EXECUTE FUNCTION koinon_content_guard_mapping_identity()"
    )
    op.execute("""
        CREATE FUNCTION koinon_content_guard_state() RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE mapping koinon_content_mappings; policy koinon_content_policies;
        BEGIN
          IF TG_OP='UPDATE' AND (NEW.tenant_id<>OLD.tenant_id OR NEW.mapping_id<>OLD.mapping_id
            OR NEW.revision<>OLD.revision+1 OR NEW.scan_generation<OLD.scan_generation
            OR NEW.last_complete_scan_generation<OLD.last_complete_scan_generation) THEN
            RAISE EXCEPTION 'sync state revision must advance' USING ERRCODE='23514';
          END IF;
          SELECT * INTO mapping FROM koinon_content_mappings WHERE tenant_id=NEW.tenant_id AND id=NEW.mapping_id;
          SELECT * INTO policy FROM koinon_content_policies WHERE tenant_id=NEW.tenant_id AND mapping_id=NEW.mapping_id AND id=NEW.accepted_policy_id;
          IF mapping.id IS NULL OR policy.accepted_at IS NULL THEN
            RAISE EXCEPTION 'accepted policy required' USING ERRCODE='23514';
          END IF;
          -- Serialize the external namespace within one local tenant, including across accounts.
          -- Callers lock canonical authority, connection and mapping before activating state.
          PERFORM pg_advisory_xact_lock(hashtextextended(jsonb_build_array(mapping.tenant_id,mapping.provider,mapping.external_tenant,mapping.drive_id)::text,0));
          IF NEW.enabled AND (policy.mapping_revision<>mapping.revision OR EXISTS (
            SELECT 1 FROM koinon_content_sync_states other
            JOIN koinon_content_mappings m ON m.id=other.mapping_id AND m.tenant_id=other.tenant_id
            JOIN koinon_content_policies p ON p.id=other.accepted_policy_id AND p.tenant_id=other.tenant_id
            WHERE other.enabled AND other.tenant_id=NEW.tenant_id AND other.mapping_id<>NEW.mapping_id
              AND m.provider=mapping.provider AND m.external_tenant IS NOT DISTINCT FROM mapping.external_tenant
              AND m.drive_id=mapping.drive_id
              AND (p.root_ancestry_json::jsonb @> jsonb_build_array(mapping.root_id)
                OR policy.root_ancestry_json::jsonb @> jsonb_build_array(m.root_id))
          )) THEN RAISE EXCEPTION 'source root overlaps or accepted revision is stale' USING ERRCODE='23514'; END IF;
          RETURN NEW;
        END $$
    """)
    op.execute(
        "CREATE TRIGGER guard_sync_state BEFORE INSERT OR UPDATE ON koinon_content_sync_states FOR EACH ROW EXECUTE FUNCTION koinon_content_guard_state()"
    )
    op.execute("""
        CREATE FUNCTION koinon_content_guard_object() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
          IF (NEW.id,NEW.tenant_id,NEW.mapping_id,NEW.item_id) IS DISTINCT FROM (OLD.id,OLD.tenant_id,OLD.mapping_id,OLD.item_id) THEN
            RAISE EXCEPTION 'object source identity is immutable' USING ERRCODE='23503';
          END IF;
          IF NEW.generation<OLD.generation OR NEW.generation>OLD.generation+1
            OR NEW.mapping_revision<OLD.mapping_revision
            OR NEW.last_complete_scan_generation<OLD.last_complete_scan_generation THEN
            RAISE EXCEPTION 'object identity or generation cannot be rewritten' USING ERRCODE='23514';
          END IF;
          RETURN NEW;
        END $$
    """)
    op.execute(
        "CREATE TRIGGER guard_sync_object BEFORE UPDATE ON koinon_content_objects FOR EACH ROW EXECUTE FUNCTION koinon_content_guard_object()"
    )
    op.execute("""
        CREATE FUNCTION koinon_content_guard_run() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
          IF TG_OP='INSERT' AND NOT EXISTS(SELECT 1 FROM koinon_content_policies
            WHERE id=NEW.policy_id AND tenant_id=NEW.tenant_id AND mapping_id=NEW.mapping_id
              AND mapping_revision=NEW.mapping_revision AND accepted_at IS NOT NULL) THEN
            RAISE EXCEPTION 'execution requires an accepted policy' USING ERRCODE='23514';
          END IF;
          IF TG_OP='INSERT' AND NOT EXISTS(SELECT 1 FROM lattice_jobs WHERE id=NEW.job_id AND tenant_id=NEW.tenant_id
            AND resource_id=NEW.mapping_id AND kind='content.source.reconcile') THEN
            RAISE EXCEPTION 'canonical source Job required' USING ERRCODE='23514';
          END IF;
          IF TG_OP='UPDATE' AND (
            (to_jsonb(NEW)-ARRAY['status','page_sequence','cursor_ciphertext','enumeration_complete','counters_json','updated_at','finished_at']) IS DISTINCT FROM
            (to_jsonb(OLD)-ARRAY['status','page_sequence','cursor_ciphertext','enumeration_complete','counters_json','updated_at','finished_at'])
            OR NEW.page_sequence<OLD.page_sequence OR NEW.page_sequence>OLD.page_sequence+1
            OR (OLD.enumeration_complete AND NOT NEW.enumeration_complete)
            OR (OLD.status NOT IN ('queued','running','reconciling') AND NEW.status<>OLD.status)) THEN
            RAISE EXCEPTION 'run identity or checkpoint cannot be rewritten' USING ERRCODE='23514';
          END IF;
          RETURN NEW;
        END $$
    """)
    op.execute(
        "CREATE TRIGGER guard_sync_run BEFORE INSERT OR UPDATE ON koinon_content_sync_runs FOR EACH ROW EXECUTE FUNCTION koinon_content_guard_run()"
    )
    op.execute("""
        CREATE FUNCTION koinon_content_guard_work() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
          IF TG_OP='UPDATE' AND (
            (to_jsonb(NEW)-ARRAY['status','error_code','attempt_id','updated_at']) IS DISTINCT FROM
            (to_jsonb(OLD)-ARRAY['status','error_code','attempt_id','updated_at'])
            OR (OLD.attempt_id IS NOT NULL AND OLD.attempt_id IS DISTINCT FROM NEW.attempt_id)) THEN
            RAISE EXCEPTION 'work identity and replacement baseline are immutable' USING ERRCODE='23514';
          END IF;
          IF NEW.attempt_id IS NOT NULL AND NOT EXISTS(SELECT 1 FROM koinon_content_imports
            WHERE id=NEW.attempt_id AND tenant_id=NEW.tenant_id AND mapping_id=NEW.mapping_id
              AND object_id=NEW.object_id AND generation=NEW.generation AND remote_version IS NOT DISTINCT FROM NEW.remote_version) THEN
            RAISE EXCEPTION 'work must bind its exact import' USING ERRCODE='23514';
          END IF;
          RETURN NEW;
        END $$
    """)
    op.execute(
        "CREATE TRIGGER guard_sync_work BEFORE INSERT OR UPDATE ON koinon_content_sync_work FOR EACH ROW EXECUTE FUNCTION koinon_content_guard_work()"
    )
    op.execute("""
        CREATE FUNCTION koinon_content_guard_marker() RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE attempt koinon_content_imports; receipt jsonb;
        BEGIN
          SELECT * INTO attempt FROM koinon_content_imports WHERE id=coalesce(to_jsonb(NEW)->>'initial_attempt_id',to_jsonb(NEW)->>'attempt_id');
          IF attempt.id IS NULL OR (attempt.tenant_id,attempt.source_id,attempt.asset_id) IS DISTINCT FROM (NEW.tenant_id,NEW.source_id,NEW.asset_id)
            OR NOT EXISTS(SELECT 1 FROM koinon_content_mappings m JOIN koinon_content_objects o
              ON o.mapping_id=m.id AND o.tenant_id=m.tenant_id
              WHERE m.id=attempt.mapping_id AND m.tenant_id=attempt.tenant_id AND o.id=attempt.object_id
                AND m.provider=attempt.provider AND m.external_subject=attempt.external_subject
                AND m.external_tenant IS NOT DISTINCT FROM attempt.external_tenant
                AND m.drive_id=attempt.drive_id AND o.item_id=attempt.remote_item_id)
            OR NOT EXISTS(SELECT 1 FROM lattice_catalog a JOIN lattice_catalog s ON s.id=a.parent_id
              WHERE a.id=NEW.asset_id AND a.tenant_id=NEW.tenant_id AND s.id=NEW.source_id AND s.tenant_id=NEW.tenant_id AND s.kind='source') THEN
            RAISE EXCEPTION 'import marker requires exact retained origin' USING ERRCODE='23514';
          END IF;
          IF TG_TABLE_NAME='koinon_content_imported_versions' THEN
            receipt=attempt.receipt_json::jsonb;
            IF attempt.committed_at IS NULL OR receipt IS NULL
              OR (NEW.domain,NEW.native_workspace_id,NEW.native_source_id,NEW.native_asset_id,NEW.native_version_id,NEW.extraction_id)
                IS DISTINCT FROM (receipt->>'domain',receipt->>'native_workspace_id',receipt->>'native_source_id',receipt->>'native_asset_id',
                  receipt->>CASE WHEN NEW.domain='canon' THEN 'source_version_id' ELSE 'file_version_id' END,receipt->>'extraction_id') THEN
              RAISE EXCEPTION 'version marker requires exact committed receipt' USING ERRCODE='23514';
            END IF;
          END IF;
          RETURN NEW;
        END $$
    """)
    for suffix in ("imported_assets", "imported_versions"):
        op.execute(
            f"CREATE TRIGGER guard_marker BEFORE INSERT ON koinon_content_{suffix} FOR EACH ROW EXECUTE FUNCTION koinon_content_guard_marker()"
        )
    op.execute("""
        CREATE FUNCTION koinon_content_guard_reader() RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE current_revision integer;
        BEGIN
          IF TG_TABLE_NAME='koinon_content_reader_sets' THEN
            IF TG_OP='INSERT' AND NEW.revision<>0 THEN RAISE EXCEPTION 'reader set starts at zero' USING ERRCODE='23514'; END IF;
            IF TG_OP='UPDATE' AND ((NEW.tenant_id,NEW.owner) IS DISTINCT FROM (OLD.tenant_id,OLD.owner)
              OR NEW.revision<>OLD.revision+1 OR NOT EXISTS(SELECT 1 FROM koinon_content_reader_operations
                WHERE tenant_id=NEW.tenant_id AND owner=NEW.owner AND result_revision=NEW.revision)) THEN
              RAISE EXCEPTION 'reader set requires the next operation revision' USING ERRCODE='23514';
            END IF;
          ELSE
            SELECT revision INTO current_revision FROM koinon_content_reader_sets WHERE tenant_id=NEW.tenant_id AND owner=NEW.owner FOR UPDATE;
            IF current_revision IS NULL OR coalesce(to_jsonb(NEW)->>'set_revision',to_jsonb(NEW)->>'result_revision')::integer <> current_revision+1 THEN
              RAISE EXCEPTION 'only the next reader snapshot can be appended' USING ERRCODE='23514';
            END IF;
            IF TG_TABLE_NAME='koinon_content_reader_selections' THEN
              IF NOT EXISTS(SELECT 1 FROM koinon_content_connections WHERE id=NEW.connection_id AND tenant_id=NEW.tenant_id
                AND owner=NEW.owner AND provider=NEW.provider AND external_tenant IS NOT DISTINCT FROM NEW.external_tenant) THEN
                RAISE EXCEPTION 'reader connection identity mismatch' USING ERRCODE='23514';
              END IF;
            END IF;
          END IF;
          RETURN NEW;
        END $$
    """)
    op.execute(
        "CREATE TRIGGER guard_reader_set BEFORE INSERT OR UPDATE ON koinon_content_reader_sets FOR EACH ROW EXECUTE FUNCTION koinon_content_guard_reader()"
    )
    for suffix in ("reader_selections", "reader_operations"):
        op.execute(
            f"CREATE TRIGGER guard_reader_append BEFORE INSERT ON koinon_content_{suffix} FOR EACH ROW EXECUTE FUNCTION koinon_content_guard_reader()"
        )
    op.execute("""
        CREATE FUNCTION koinon_content_complete_reader_snapshot() RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE snapshot_revision integer;
        BEGIN
          snapshot_revision=coalesce(to_jsonb(NEW)->>'set_revision',to_jsonb(NEW)->>'result_revision')::integer;
          IF NOT EXISTS(SELECT 1 FROM koinon_content_reader_sets s
            JOIN koinon_content_reader_operations o ON o.tenant_id=s.tenant_id AND o.owner=s.owner
            WHERE s.tenant_id=NEW.tenant_id AND s.owner=NEW.owner AND s.revision>=snapshot_revision AND o.result_revision=snapshot_revision) THEN
            RAISE EXCEPTION 'reader snapshot, operation and revision must commit together' USING ERRCODE='23514';
          END IF;
          RETURN NULL;
        END $$
    """)
    for suffix in ("reader_selections", "reader_operations"):
        op.execute(
            f"CREATE CONSTRAINT TRIGGER complete_reader_snapshot AFTER INSERT ON koinon_content_{suffix} DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION koinon_content_complete_reader_snapshot()"
        )
    op.execute("""
        CREATE FUNCTION koinon_content_guard_observation() RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE checkpoint integer;
        BEGIN
          SELECT page_sequence INTO checkpoint FROM koinon_content_sync_runs
            WHERE id=NEW.run_id AND tenant_id=NEW.tenant_id AND mapping_id=NEW.mapping_id FOR UPDATE;
          IF checkpoint IS NULL OR NEW.page_sequence<>checkpoint+1 OR NOT EXISTS(
            SELECT 1 FROM koinon_content_sync_work WHERE id=NEW.work_id AND tenant_id=NEW.tenant_id
              AND mapping_id=NEW.mapping_id AND object_id=NEW.object_id AND generation=NEW.generation
              AND remote_version IS NOT DISTINCT FROM NEW.remote_version) THEN
            RAISE EXCEPTION 'observation requires the next page and exact work version' USING ERRCODE='23514';
          END IF;
          RETURN NEW;
        END $$
    """)
    op.execute(
        "CREATE TRIGGER guard_observation BEFORE INSERT ON koinon_content_sync_observations FOR EACH ROW EXECUTE FUNCTION koinon_content_guard_observation()"
    )
    op.execute("""
        CREATE FUNCTION koinon_content_complete_page() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
          IF NOT EXISTS(SELECT 1 FROM koinon_content_sync_runs WHERE id=NEW.run_id
            AND tenant_id=NEW.tenant_id AND mapping_id=NEW.mapping_id AND page_sequence>=NEW.page_sequence) THEN
            RAISE EXCEPTION 'observations and checkpoint must commit together' USING ERRCODE='23514';
          END IF;
          RETURN NULL;
        END $$
    """)
    op.execute(
        "CREATE CONSTRAINT TRIGGER complete_page AFTER INSERT ON koinon_content_sync_observations DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION koinon_content_complete_page()"
    )
    op.execute("""
        CREATE FUNCTION koinon_content_guard_folder() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
          IF TG_OP='UPDATE' AND ((NEW.tenant_id,NEW.mapping_id,NEW.remote_folder_id,NEW.local_folder_id)
            IS DISTINCT FROM (OLD.tenant_id,OLD.mapping_id,OLD.remote_folder_id,OLD.local_folder_id) OR NEW.revision<>OLD.revision+1) THEN
            RAISE EXCEPTION 'folder identity is stable across moves' USING ERRCODE='23514';
          END IF;
          IF NOT EXISTS(SELECT 1 FROM lattice_catalog f JOIN lattice_catalog p ON p.id=f.parent_id
            JOIN koinon_content_mappings m ON m.id=NEW.mapping_id AND m.tenant_id=NEW.tenant_id
            WHERE f.id=NEW.local_folder_id AND f.tenant_id=NEW.tenant_id AND f.parent_id=NEW.local_parent_id
              AND p.tenant_id=NEW.tenant_id AND f.workspace_id=m.workspace_id AND f.project_id=m.project_id
              AND f.kind IN ('folder','collection','corpus')) THEN
            RAISE EXCEPTION 'folder binding requires verified local ancestry' USING ERRCODE='23514';
          END IF;
          RETURN NEW;
        END $$
    """)
    op.execute(
        "CREATE TRIGGER guard_folder BEFORE INSERT OR UPDATE ON koinon_content_folder_bindings FOR EACH ROW EXECUTE FUNCTION koinon_content_guard_folder()"
    )


def downgrade():
    raise RuntimeError(
        "Source sync provenance is retained; use a reviewed forward migration"
    )
