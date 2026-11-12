# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Private immutable metadata ancestry with atomic, replayable publication groups.

Existing metadata retains NULL provenance. Recovery uses a forward migration;
never derive historical authority from current pointers.
"""

from alembic import op

revision = "0021_metadata_provenance"
down_revision = "0020_bulk_query_operations"
TABLES = {
    "relation": "flyquery_relations",
    "glossary": "flyquery_glossary_terms",
    "metric": "flyquery_semantic_metrics",
    "dimension": "flyquery_semantic_dimensions",
    "example": "flyquery_examples",
}
FIELDS = {
    "relation": "dataset_id from_table_id from_column_name to_table_id to_column_name "
    "condition kind confidence reason",
    "glossary": "term definition synonyms_json tags_json related_columns_json related_metrics_json",
    "metric": "dataset_id name label description definition_yaml compiled_sql_template "
    "metric_type current_version metadata_json",
    "dimension": "dataset_id name label description definition_yaml compiled_sql_template "
    "metric_type dimension_type current_version metadata_json",
    "example": "dataset_id question generated_sql normalised_sql source citations_json",
}


def upgrade():
    if op.get_bind().dialect.name != "postgresql":
        raise RuntimeError("Structured metadata provenance requires PostgreSQL")
    _expand()


def _expand():
    op.execute("""CREATE FUNCTION public.koinon_json_sha256(value jsonb) RETURNS text
        LANGUAGE sql IMMUTABLE STRICT PARALLEL SAFE SET search_path=pg_catalog
        AS $$ SELECT encode(sha256(convert_to(value::text,'UTF8')),'hex') $$""")
    clauses = []
    for kind, fields in FIELDS.items():
        keys = ",".join("'" + key + "'" for key in ("id tenant_id workspace_id " + fields).split())
        clauses.append(f"WHEN '{kind}' THEN ARRAY[{keys}]::text[]")
    op.execute(
        """CREATE FUNCTION public.koinon_metadata_payload(kind text, value jsonb) RETURNS jsonb
        LANGUAGE sql IMMUTABLE STRICT PARALLEL SAFE SET search_path=pg_catalog AS $$
        SELECT jsonb_build_object('schema','koinon.structured-metadata-payload.v1','kind',kind)
          || coalesce((SELECT jsonb_object_agg(key,value->key) FROM unnest(CASE kind
        """
        + " ".join(clauses)
        + """ ELSE ARRAY[]::text[] END) AS key),'{}'::jsonb)
        $$"""
    )
    op.execute("""CREATE TABLE flyquery_metadata_provenance (
        id uuid PRIMARY KEY, tenant_id text NOT NULL, workspace_id uuid NOT NULL,
        entity_kind text NOT NULL CHECK(entity_kind IN
        ('relation','glossary','metric','dimension','example')),
        entity_id uuid NOT NULL, semantic_version integer CHECK(semantic_version>0),
        payload_json jsonb NOT NULL, payload_sha256 varchar(64) NOT NULL,
        manifest_json jsonb NOT NULL, manifest_sha256 varchar(64) NOT NULL,
        created_by text NOT NULL, created_at timestamptz NOT NULL DEFAULT now(),
        producer_kind text NOT NULL CHECK(producer_kind IN ('manual','query','ingest')),
        producer_operation_id uuid NOT NULL, producer_ordinal integer NOT NULL,
        producer_size integer NOT NULL CHECK(producer_size BETWEEN 1 AND 500), request_sha256 varchar(64)
        NOT NULL,
        CONSTRAINT uq_metadata_producer
        UNIQUE(tenant_id,workspace_id,created_by,producer_kind,producer_operation_id,producer_ordinal),
        CHECK(producer_ordinal>=0 AND producer_ordinal<producer_size),
        CHECK(request_sha256 ~ '^[0-9a-f]{64}$'),
        CHECK(jsonb_typeof(payload_json)='object' AND octet_length(payload_json::text)<=1048576
          AND payload_sha256=public.koinon_json_sha256(payload_json)),
        CHECK(jsonb_typeof(manifest_json)='object' AND octet_length(manifest_json::text)<=262144
          AND manifest_sha256=public.koinon_json_sha256(manifest_json)),
        CHECK((entity_kind IN ('metric','dimension'))=(semantic_version IS NOT NULL))
    )""")
    op.execute(
        "CREATE INDEX ix_metadata_provenance_scope ON "
        "flyquery_metadata_provenance(tenant_id,workspace_id,entity_kind,entity_id,id)"
    )
    for table in (*TABLES.values(), "flyquery_semantic_versions"):
        op.execute(f"ALTER TABLE {table} ADD COLUMN source_provenance_id uuid")
        op.execute(
            f"ALTER TABLE {table} ADD CONSTRAINT fk_{table}_source_provenance "
            "FOREIGN KEY(source_provenance_id) REFERENCES flyquery_metadata_provenance(id) NOT VALID"
        )
    op.execute("ALTER TABLE flyquery_metadata_provenance ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE flyquery_metadata_provenance FORCE ROW LEVEL SECURITY")
    op.execute("""CREATE POLICY pol_metadata_provenance ON flyquery_metadata_provenance
        USING(tenant_id=current_setting('app.tenant_id',true) AND
        workspace_id::text=current_setting('app.workspace_id',true))
        WITH CHECK(tenant_id=current_setting('app.tenant_id',true) AND
        workspace_id::text=current_setting('app.workspace_id',true))""")
    op.execute("REVOKE ALL ON flyquery_metadata_provenance FROM PUBLIC")
    _manifest_guard()
    _binding_guards()
    _group_guard()
    _query_guard()


def _manifest_guard():
    op.execute("""CREATE FUNCTION public.koinon_metadata_manifest_guard() RETURNS trigger
        LANGUAGE plpgsql SET search_path=pg_catalog,public AS $$
        DECLARE m jsonb; pin jsonb; previous text; current_key text; input_id text; other jsonb;
        BEGIN
          IF TG_OP<>'INSERT' THEN RAISE EXCEPTION 'metadata provenance is immutable' USING
          ERRCODE='23514'; END IF;
          m=NEW.manifest_json;
          IF m->>'schema' IS DISTINCT FROM 'koinon.structured-metadata-provenance.v1'
            OR m->'complete' IS DISTINCT FROM 'true'::jsonb
            OR jsonb_typeof(m->'tables') IS DISTINCT FROM 'array'
            OR jsonb_typeof(m->'provenance_ids') IS DISTINCT FROM 'array'
            OR jsonb_typeof(m->'query_ids') IS DISTINCT FROM 'array'
            OR (SELECT count(*) FROM jsonb_object_keys(m))<>5
            OR jsonb_array_length(m->'tables')>500
            OR jsonb_array_length(m->'provenance_ids')>500 OR jsonb_array_length(m->'query_ids')>500
            OR NEW.payload_json->>'schema' IS DISTINCT FROM 'koinon.structured-metadata-payload.v1'
            OR NEW.payload_json->>'kind' IS DISTINCT FROM NEW.entity_kind
            OR NEW.payload_json->>'id' IS DISTINCT FROM NEW.entity_id::text
            OR NEW.payload_json->>'tenant_id' IS DISTINCT FROM NEW.tenant_id
            OR NEW.payload_json->>'workspace_id' IS DISTINCT FROM NEW.workspace_id::text
          THEN RAISE EXCEPTION 'complete metadata provenance required' USING ERRCODE='23514'; END IF;
          previous=NULL;
          FOR pin IN SELECT value FROM jsonb_array_elements(m->'tables') LOOP
            IF jsonb_typeof(pin)<>'object' OR (SELECT count(*) FROM jsonb_object_keys(pin))<>3
              OR NOT EXISTS(SELECT 1 FROM public.flyquery_schema_snapshots s
                 WHERE s.id::text=pin->>'snapshot_id' AND s.table_id::text=pin->>'table_id'
                   AND s.dataset_id::text=pin->>'dataset_id' AND s.tenant_id=NEW.tenant_id
                   AND s.workspace_id=NEW.workspace_id AND s.status='READY')
            THEN RAISE EXCEPTION 'invalid metadata snapshot pin' USING ERRCODE='23514'; END IF;
            current_key=(pin->>'dataset_id')||'/'||(pin->>'table_id');
            IF previous IS NOT NULL AND current_key<=previous THEN
              RAISE EXCEPTION 'metadata pins must be sorted and unique' USING ERRCODE='23514'; END IF;
            previous=current_key;
          END LOOP;
          previous=NULL;
          FOR input_id IN SELECT jsonb_array_elements_text(m->'provenance_ids') LOOP
            IF input_id=NEW.id::text OR (previous IS NOT NULL AND input_id<=previous) THEN
              RAISE EXCEPTION 'metadata ancestors must be earlier and unique' USING ERRCODE='23514'; END
              IF;
            SELECT manifest_json INTO other FROM public.flyquery_metadata_provenance
              WHERE id::text=input_id AND tenant_id=NEW.tenant_id AND workspace_id=NEW.workspace_id;
            IF other IS NULL OR NOT (m->'tables') @> (other->'tables') THEN
              RAISE EXCEPTION 'metadata ancestor manifest is incomplete' USING ERRCODE='23514'; END IF;
            previous=input_id;
          END LOOP;
          previous=NULL;
          FOR input_id IN SELECT jsonb_array_elements_text(m->'query_ids') LOOP
            IF previous IS NOT NULL AND input_id<=previous THEN
              RAISE EXCEPTION 'query ancestors must be sorted and unique' USING ERRCODE='23514'; END IF;
            SELECT table_id_snapshot_pins_json INTO other FROM public.flyquery_queries
              WHERE id::text=input_id AND tenant_id=NEW.tenant_id AND workspace_id=NEW.workspace_id
                AND finalised_at IS NOT NULL AND consumer_context IS NOT NULL;
            IF other IS NULL OR jsonb_typeof(other)<>'object' OR EXISTS(
              SELECT 1 FROM jsonb_each_text(other) q WHERE NOT EXISTS(
                SELECT 1 FROM jsonb_array_elements(m->'tables') t
                WHERE t->>'table_id'=q.key AND t->>'snapshot_id'=q.value)) THEN
              RAISE EXCEPTION 'query ancestor manifest is incomplete' USING ERRCODE='23514'; END IF;
            previous=input_id;
          END LOOP;
          RETURN NEW;
        END $$""")
    op.execute(
        "CREATE TRIGGER metadata_provenance_guard BEFORE INSERT OR UPDATE OR DELETE ON "
        "flyquery_metadata_provenance FOR EACH ROW EXECUTE FUNCTION "
        "public.koinon_metadata_manifest_guard()"
    )
    op.execute(
        "CREATE TRIGGER metadata_provenance_retain BEFORE TRUNCATE ON "
        "flyquery_metadata_provenance EXECUTE FUNCTION "
        "public.koinon_metadata_manifest_guard()"
    )
    op.execute("REVOKE ALL ON FUNCTION public.koinon_metadata_manifest_guard() FROM PUBLIC")


def _binding_guards():
    op.execute("""CREATE FUNCTION public.koinon_metadata_binding_guard() RETURNS trigger
        LANGUAGE plpgsql SET search_path=pg_catalog,public AS $$
        DECLARE p public.flyquery_metadata_provenance; r jsonb; kind text; entity uuid; version integer;
        BEGIN
          IF TG_OP='UPDATE' AND TG_ARGV[0]='version' AND OLD.source_provenance_id IS NOT NULL
            AND to_jsonb(NEW) IS DISTINCT FROM to_jsonb(OLD) THEN
            RAISE EXCEPTION 'historical metadata provenance is immutable' USING ERRCODE='23514'; END IF;
          IF TG_OP='UPDATE' AND OLD.source_provenance_id IS NOT NULL AND NEW.source_provenance_id IS NULL
          THEN
            RAISE EXCEPTION 'metadata provenance cannot be cleared' USING ERRCODE='23514'; END IF;
          IF NEW.source_provenance_id IS NULL THEN RETURN NEW; END IF;
          r=to_jsonb(NEW); kind=TG_ARGV[0]; entity=NEW.id;
          IF kind='version' THEN kind=lower(r->>'kind'); entity=(r->>'parent_id')::uuid;
          version=(r->>'version')::integer;
          ELSIF kind IN ('metric','dimension') THEN version=(r->>'current_version')::integer; END IF;
          SELECT * INTO p FROM public.flyquery_metadata_provenance WHERE id=NEW.source_provenance_id;
          IF p.id IS NULL OR (p.tenant_id,p.workspace_id,p.entity_kind,p.entity_id,p.semantic_version)
             IS DISTINCT FROM (NEW.tenant_id,NEW.workspace_id,kind,entity,version)
            OR (TG_ARGV[0]<>'version' AND p.payload_json IS DISTINCT FROM
            public.koinon_metadata_payload(kind,r))
            OR (TG_ARGV[0]='version' AND (p.payload_json->'definition_yaml' IS DISTINCT FROM
            r->'definition_yaml'
                OR p.payload_json->'compiled_sql_template' IS DISTINCT FROM r->'compiled_sql_template'))
          THEN RAISE EXCEPTION 'metadata provenance binding mismatch' USING ERRCODE='23514'; END IF;
          RETURN NEW;
        END $$""")
    for kind, table in {**TABLES, "version": "flyquery_semantic_versions"}.items():
        op.execute(
            f"CREATE TRIGGER metadata_binding BEFORE INSERT OR UPDATE ON {table} "
            f"FOR EACH ROW EXECUTE FUNCTION public.koinon_metadata_binding_guard('{kind}')"
        )
    op.execute("REVOKE ALL ON FUNCTION public.koinon_metadata_binding_guard() FROM PUBLIC")


def _group_guard():
    op.execute("""CREATE FUNCTION public.koinon_metadata_group_guard() RETURNS trigger
        LANGUAGE plpgsql SET search_path=pg_catalog,public AS $$
        DECLARE n integer; minimum integer; maximum integer; sizes integer; hashes integer;
          p public.flyquery_metadata_provenance; relation text; bound boolean;
        BEGIN
          SELECT count(*),min(producer_ordinal),max(producer_ordinal),count(DISTINCT
          producer_size),count(DISTINCT request_sha256)
            INTO n,minimum,maximum,sizes,hashes FROM public.flyquery_metadata_provenance
            WHERE tenant_id=NEW.tenant_id AND workspace_id=NEW.workspace_id AND created_by=NEW.created_by
              AND producer_kind=NEW.producer_kind AND producer_operation_id=NEW.producer_operation_id;
          IF n<>NEW.producer_size OR minimum<>0 OR maximum<>NEW.producer_size-1 OR sizes<>1 OR hashes<>1
          THEN
            RAISE EXCEPTION 'metadata producer group must commit completely' USING ERRCODE='23514'; END
            IF;
          -- Each deferred row trigger checks its own effect; do not hydrate the
          -- entire bounded group again for every member.
          p=NEW;
            relation=CASE p.entity_kind WHEN 'relation' THEN 'flyquery_relations' WHEN 'glossary' THEN
            'flyquery_glossary_terms'
              WHEN 'metric' THEN 'flyquery_semantic_metrics' WHEN 'dimension' THEN
              'flyquery_semantic_dimensions'
              WHEN 'example' THEN 'flyquery_examples' END;
            EXECUTE format('SELECT EXISTS(SELECT 1 FROM public.%I '
              'WHERE id=$1 AND source_provenance_id=$2)',relation)
              INTO bound USING p.entity_id,p.id;
            IF NOT bound THEN RAISE EXCEPTION 'metadata producer effect must commit with provenance'
            USING ERRCODE='23514'; END IF;
          RETURN NULL;
        END $$""")
    op.execute(
        "CREATE CONSTRAINT TRIGGER metadata_group_complete AFTER INSERT ON "
        "flyquery_metadata_provenance DEFERRABLE INITIALLY DEFERRED FOR EACH ROW "
        "EXECUTE FUNCTION public.koinon_metadata_group_guard()"
    )
    op.execute("REVOKE ALL ON FUNCTION public.koinon_metadata_group_guard() FROM PUBLIC")


def _query_guard():
    op.execute("""CREATE FUNCTION public.koinon_published_query_authority_guard() RETURNS trigger
        LANGUAGE plpgsql SET search_path=pg_catalog AS $$ BEGIN
          IF OLD.finalised_at IS NOT NULL AND OLD.consumer_context IS NOT NULL AND (
            NEW.consumer_context IS DISTINCT FROM OLD.consumer_context
            OR NEW.table_id_snapshot_pins_json IS DISTINCT FROM OLD.table_id_snapshot_pins_json
            OR NEW.finalised_at IS DISTINCT FROM OLD.finalised_at
            OR (NEW.tenant_id,NEW.workspace_id,NEW.dataset_id) IS DISTINCT FROM
            (OLD.tenant_id,OLD.workspace_id,OLD.dataset_id))
          THEN RAISE EXCEPTION 'published query authority is immutable' USING ERRCODE='23514'; END IF;
          RETURN NEW;
        END $$""")
    op.execute(
        "CREATE TRIGGER published_query_authority BEFORE UPDATE ON flyquery_queries "
        "FOR EACH ROW EXECUTE FUNCTION public.koinon_published_query_authority_guard()"
    )
    op.execute("REVOKE ALL ON FUNCTION public.koinon_published_query_authority_guard() FROM PUBLIC")


def downgrade():
    raise RuntimeError("Recover metadata provenance through a reviewed forward migration")
