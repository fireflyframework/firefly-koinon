# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Frozen PostgreSQL publication contract installed by primary migration 0052."""

from sqlalchemy import inspect, text

BASELINES = "koinon_content_publication_baselines"
TARGETS = "koinon_content_publication_targets"
TRANSACTIONS = "koinon_content_publication_transactions"

CREATION = """CREATE OR REPLACE FUNCTION public.koinon_history_catalog_identity() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
BEGIN
  IF TG_OP='INSERT' THEN
    INSERT INTO public.koinon_catalog_history_identities(tenant_id,resource_id,coverage,
      creation_transaction)
      VALUES(NEW.tenant_id,NEW.id,'complete',pg_current_xact_id());
    IF EXISTS(SELECT 1 FROM public.lattice_audit WHERE resource_id=NEW.id) THEN
      RAISE EXCEPTION 'catalog identity is already retained in audit' USING ERRCODE='23514';
    END IF;
  ELSIF NEW.id IS DISTINCT FROM OLD.id OR NEW.tenant_id IS DISTINCT FROM OLD.tenant_id THEN
    RAISE EXCEPTION 'catalog history identity is immutable' USING ERRCODE='23514';
  END IF;
  RETURN NEW;
END $$"""

FUNCTIONS = [
    CREATION,
    """CREATE FUNCTION public.koinon_publication_closed(value jsonb, keys text[]) RETURNS boolean
    LANGUAGE sql IMMUTABLE SET search_path=pg_catalog AS $$
      SELECT coalesce(jsonb_typeof(value)='object' AND value ?& keys
        AND (SELECT count(*) FROM jsonb_object_keys(value))=cardinality(keys),false)
    $$""",
    """CREATE FUNCTION public.koinon_publication_current(p_attempt text,p_catalog text) RETURNS jsonb
    LANGUAGE sql STABLE SECURITY DEFINER SET search_path=pg_catalog AS $$
      SELECT jsonb_build_object('catalog_id',c.id,'tenant_id',c.tenant_id,
        'workspace_id',c.workspace_id,'project_id',c.project_id,'role',t.role,'disposition',
          t.disposition,
        'parent_id',c.parent_id,'kind',c.kind,'mutation_revision',c.mutation_revision,'status',
          c.status,
        'native_domain',b.domain,'native_workspace_id',b.native_workspace_id,'native_id',b.native_id,
        'native_version_id',CASE WHEN b.domain='canon' THEN b.details_json->>'source_version_id'
          WHEN c.kind='index_version' THEN b.native_id ELSE b.details_json->>'file_id' END,
        'native_snapshot_id',CASE WHEN b.domain='canon' THEN b.details_json->>'extraction_id'
          ELSE b.details_json->>'snapshot_id' END)
      FROM public.koinon_content_publication_targets t
      JOIN public.koinon_content_publication_baselines h ON h.attempt_id=t.attempt_id
      JOIN public.lattice_catalog c ON c.id=t.catalog_id
      LEFT JOIN public.lattice_domain_bindings b ON b.tenant_id=c.tenant_id AND b.catalog_id=c.id
        AND b.domain=CASE WHEN h.producer_kind LIKE '%document' THEN 'canon' ELSE 'structured' END
      WHERE t.attempt_id=p_attempt AND t.catalog_id=p_catalog
        AND (b.id IS NULL OR (b.workspace_id=c.workspace_id AND b.entity_kind=c.kind))
    $$""",
    """CREATE FUNCTION public.koinon_publication_target_guard() RETURNS trigger
    LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
    DECLARE h public.koinon_content_publication_baselines; a public.koinon_content_imports;
      c public.lattice_catalog; previous jsonb; binding public.lattice_domain_bindings; count_targets
        integer; producer jsonb;
    BEGIN
      IF TG_OP<>'INSERT' THEN
        RAISE EXCEPTION 'publication targets are append-only' USING ERRCODE='23514';
      END IF;
      SELECT * INTO h FROM public.koinon_content_publication_baselines
        WHERE attempt_id=NEW.attempt_id FOR UPDATE;
      IF h.attempt_id IS NULL OR h.descriptor_json IS NOT NULL THEN
        RAISE EXCEPTION 'publication targets are frozen' USING ERRCODE='23514';
      END IF;
      SELECT * INTO a FROM public.koinon_content_imports WHERE id=h.attempt_id;
      SELECT * INTO c FROM public.lattice_catalog WHERE id=NEW.catalog_id FOR UPDATE;
      SELECT * INTO binding FROM public.lattice_domain_bindings WHERE catalog_id=NEW.catalog_id
        AND tenant_id=h.tenant_id AND domain=CASE WHEN h.producer_kind LIKE '%document' THEN 'canon'
          ELSE 'structured' END;
      IF c.id IS NULL OR ROW(NEW.tenant_id,NEW.workspace_id,NEW.project_id)
           IS DISTINCT FROM ROW(h.tenant_id,h.workspace_id,h.project_id)
        OR ROW(c.tenant_id,c.workspace_id,c.project_id,c.parent_id,c.kind,c.status,
          c.mutation_revision)
           IS DISTINCT FROM ROW(NEW.tenant_id,NEW.workspace_id,NEW.project_id,NEW.parent_id,NEW.kind,
             NEW.status,NEW.mutation_revision)
        OR ROW(NEW.native_domain,NEW.native_workspace_id,NEW.native_id)
           IS DISTINCT FROM ROW(binding.domain,binding.native_workspace_id,binding.native_id)
        OR (binding.id IS NOT NULL AND ROW(binding.workspace_id,binding.entity_kind)
            IS DISTINCT FROM ROW(c.workspace_id,c.kind))
        OR NEW.native_version_id IS DISTINCT FROM (CASE WHEN binding.domain='canon' THEN
          binding.details_json->>'source_version_id'
           WHEN c.kind='index_version' THEN binding.native_id ELSE binding.details_json->>'file_id'
             END)
        OR NEW.native_snapshot_id IS DISTINCT FROM (CASE WHEN binding.domain='canon' THEN
          binding.details_json->>'extraction_id'
           ELSE binding.details_json->>'snapshot_id' END)
      THEN RAISE EXCEPTION 'publication pin differs from canonical reservation' USING
        ERRCODE='23514'; END IF;
      IF (NEW.role='source' AND (NEW.catalog_id<>h.source_id OR NEW.kind<>'source'))
        OR (NEW.role='asset' AND (NEW.catalog_id<>h.asset_id OR NEW.parent_id<>h.source_id
          OR NEW.kind<>(CASE WHEN h.producer_kind LIKE '%document' THEN 'document' ELSE 'dataset'
            END)))
        OR (NEW.role IN ('old_index','new_index','member') AND
          (h.producer_kind NOT LIKE '%dataset' OR NEW.parent_id<>h.asset_id OR
           NEW.kind<>(CASE WHEN NEW.role='member' THEN 'table' ELSE 'index_version' END)))
      THEN RAISE EXCEPTION 'publication target role mismatch' USING ERRCODE='23514'; END IF;
      IF NEW.disposition='add' THEN
        IF NEW.status<>'pending' OR NOT EXISTS(SELECT 1 FROM public.koinon_catalog_history_identities
          WHERE tenant_id=NEW.tenant_id AND resource_id=NEW.catalog_id AND
            creation_transaction=pg_current_xact_id())
        THEN RAISE EXCEPTION 'publication requires actual INSERT in reservation transaction' USING
          ERRCODE='23514'; END IF;
      ELSE
        SELECT v INTO previous FROM public.koinon_content_publication_baselines p,
          jsonb_array_elements(p.acknowledgement_json->'live_vector') v
          WHERE p.attempt_id=h.previous_attempt_id AND v->>'catalog_id'=NEW.catalog_id;
        IF previous IS NULL OR (previous-ARRAY['role','disposition']) IS DISTINCT FROM
          (to_jsonb(NEW)-ARRAY['attempt_id','role','disposition']) THEN
          RAISE EXCEPTION 'publication requires original predecessor live vector' USING
            ERRCODE='23514';
        END IF;
      END IF;
      IF h.producer_kind LIKE 'initial_%' THEN
        IF NEW.disposition<>'add' OR NEW.role='old_index'
          OR (NEW.role='source' AND NOT EXISTS(SELECT 1 FROM public.koinon_bulk_items bi
            JOIN public.koinon_bulk_batches bb ON bb.id=bi.batch_id
            WHERE bi.id=a.intake_item_id AND NEW.parent_id=bb.parent_id))
          OR (NEW.role='member' AND NOT EXISTS(SELECT 1 FROM public.koinon_bulk_table_reservations
            WHERE item_id=a.intake_item_id AND catalog_table_id=NEW.catalog_id))
          OR (NEW.role='new_index' AND NOT EXISTS(SELECT 1 FROM public.koinon_bulk_items
            WHERE id=a.intake_item_id AND
              reservation_json->>'catalog_file_version_id'=NEW.catalog_id))
        THEN RAISE EXCEPTION 'publication target lacks exact producer reservation' USING
          ERRCODE='23514'; END IF;
      ELSE
        SELECT metadata_json::jsonb->'_koinon_source_replacement' INTO producer FROM
          public.lattice_catalog
          WHERE id=a.content_operation_id;
        IF producer IS NULL OR producer->>'attempt_id' IS DISTINCT FROM a.id
          OR (NEW.role='new_index' AND NEW.catalog_id<>a.content_operation_id)
          OR (NEW.role='old_index' AND (NEW.catalog_id IS DISTINCT FROM
            producer->>'previous_index_id' OR NEW.disposition<>'retain'))
          OR (NEW.role IN ('source','asset') AND NEW.disposition<>'retain')
          OR (NEW.role='member' AND NOT EXISTS(SELECT 1 FROM
            jsonb_array_elements(producer->'members') p
            WHERE p->>'catalog_table_id'=NEW.catalog_id AND p->>'action'=NEW.disposition)) THEN
          RAISE EXCEPTION 'publication target lacks exact replacement plan' USING ERRCODE='23514';
        END IF;
      END IF;
      SELECT count(*) INTO count_targets FROM public.koinon_content_publication_targets WHERE
        attempt_id=h.attempt_id;
      IF count_targets>=(CASE WHEN h.producer_kind LIKE '%document' THEN 2
          WHEN h.producer_kind='initial_dataset' THEN 19 ELSE 36 END) THEN
        RAISE EXCEPTION 'publication target bound exceeded' USING ERRCODE='23514';
      END IF;
      RETURN NEW;
    END $$""",
]

FUNCTIONS.extend(
    [
        """CREATE FUNCTION public.koinon_publication_replacement_guard() RETURNS trigger
    LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
    DECLARE p jsonb; prior_value jsonb; a public.koinon_content_imports;
      h public.koinon_content_publication_baselines; prior
        public.koinon_content_publication_baselines;
      member jsonb; old_member jsonb; n integer; live_count integer;
    BEGIN
      p=NEW.metadata_json::jsonb->'_koinon_source_replacement';
      IF TG_OP='UPDATE' THEN prior_value=OLD.metadata_json::jsonb->'_koinon_source_replacement'; END
        IF;
      IF prior_value IS NOT NULL THEN
        IF p IS DISTINCT FROM prior_value THEN RAISE EXCEPTION
          'replacement producer plan is immutable' USING ERRCODE='23514'; END IF;
        RETURN NEW;
      END IF;
      IF p IS NULL THEN RETURN NEW; END IF;
      IF NOT public.koinon_publication_closed(p,ARRAY['schema','attempt_id','previous_attempt_id',
        'baseline_sha256',
        'native_workspace_id','native_dataset_id','native_file_id','previous_index_id','members'])
        OR p->>'schema' IS DISTINCT FROM 'koinon.source-replacement-producer.v1'
        OR octet_length(p::text)>262144 OR jsonb_typeof(p->'members') IS DISTINCT FROM 'array' THEN
        RAISE EXCEPTION 'invalid closed replacement producer plan' USING ERRCODE='23514';
      END IF;
      SELECT * INTO a FROM public.koinon_content_imports WHERE id=p->>'attempt_id';
      SELECT * INTO h FROM public.koinon_content_publication_baselines WHERE attempt_id=a.id FOR
        UPDATE;
      SELECT * INTO prior FROM public.koinon_content_publication_baselines WHERE
        attempt_id=h.previous_attempt_id;
      IF h.attempt_id IS NULL OR h.descriptor_json IS NOT NULL OR h.producer_kind NOT LIKE 'replace_%'
        OR a.content_operation_id IS DISTINCT FROM NEW.id OR h.previous_attempt_id IS DISTINCT FROM
          p->>'previous_attempt_id'
        OR ROW(NEW.tenant_id,NEW.workspace_id,NEW.project_id) IS DISTINCT FROM ROW(h.tenant_id,
          h.workspace_id,h.project_id)
        OR prior.acknowledgement_json IS NULL OR p->>'native_workspace_id' IS DISTINCT FROM
          prior.acknowledgement_json->'native_receipt'->>'native_workspace_id'
        OR NEW.kind<>'index_version' OR NEW.status<>'pending'
        OR NEW.metadata_json->>'sha256' IS DISTINCT FROM a.sha256
        OR NEW.metadata_json->>'bytes' IS DISTINCT FROM a.size_bytes::text THEN
        RAISE EXCEPTION 'replacement producer identity mismatch' USING ERRCODE='23514';
      END IF;
      IF h.producer_kind='replace_document' THEN
        IF p->'members'<>'[]'::jsonb OR p->'native_dataset_id'<>'null'::jsonb
          OR p->'native_file_id'<>'null'::jsonb OR p->'previous_index_id'<>'null'::jsonb
          OR p->'baseline_sha256'<>'null'::jsonb OR NEW.parent_id<>h.source_id THEN
          RAISE EXCEPTION 'replacement document producer mismatch' USING ERRCODE='23514';
        END IF;
        RETURN NEW;
      END IF;
      IF NEW.parent_id<>h.asset_id OR jsonb_array_length(p->'members') NOT BETWEEN 1 AND 32
        OR p->>'native_dataset_id' IS DISTINCT FROM
          prior.acknowledgement_json->'native_receipt'->>'native_asset_id'
        OR p->>'previous_index_id' IS DISTINCT FROM
          prior.acknowledgement_json->'native_receipt'->>'file_version_id'
        OR jsonb_typeof(p->'native_file_id') IS DISTINCT FROM 'string' OR
          length(p->>'native_file_id') NOT BETWEEN 1 AND 64
        OR p->>'native_file_id'=prior.acknowledgement_json->'native_receipt'->>'native_file_id'
        OR jsonb_typeof(p->'baseline_sha256') IS DISTINCT FROM 'string' OR NOT
          coalesce(p->>'baseline_sha256' ~ '^[0-9a-f]{64}$',false) THEN
        RAISE EXCEPTION 'replacement dataset producer mismatch' USING ERRCODE='23514';
      END IF;
      live_count=0;
      FOR member IN SELECT value FROM jsonb_array_elements(p->'members') LOOP
        IF NOT public.koinon_publication_closed(member,ARRAY['schema','member_key','action',
          'table_id','catalog_table_id','snapshot_id','ordinal','name','parser_fingerprint'])
          OR member->>'schema' IS DISTINCT FROM 'koinon.dataset-replacement-member.v1'
          OR NOT coalesce(member->>'action' IN ('retain','add','remove'),false)
          OR EXISTS(SELECT 1 FROM unnest(ARRAY['member_key','table_id','catalog_table_id',
            'snapshot_id','parser_fingerprint']) k
            WHERE jsonb_typeof(member->k) IS DISTINCT FROM 'string' OR length(member->>k) NOT BETWEEN
              1 AND 2048) THEN
          RAISE EXCEPTION 'replacement member plan is not closed' USING ERRCODE='23514';
        END IF;
        SELECT v INTO old_member FROM jsonb_array_elements(prior.acknowledgement_json->'live_vector')
          v
          WHERE v->>'role'='member' AND v->>'catalog_id'=member->>'catalog_table_id';
        IF member->>'action'='add' THEN
          IF old_member IS NOT NULL OR NOT EXISTS(SELECT 1 FROM
            public.koinon_catalog_history_identities ci
            JOIN public.lattice_catalog c ON c.id=ci.resource_id WHERE
              c.id=member->>'catalog_table_id'
              AND ci.creation_transaction=pg_current_xact_id() AND ci.tenant_id=h.tenant_id
              AND c.tenant_id=h.tenant_id AND c.workspace_id=h.workspace_id AND
                c.project_id=h.project_id
              AND c.parent_id=h.asset_id AND c.kind='table' AND c.status='pending') THEN
            RAISE EXCEPTION 'replacement new member requires exact actual INSERT' USING
              ERRCODE='23514';
          END IF;
        ELSIF old_member IS NULL OR old_member->>'native_id' IS DISTINCT FROM member->>'table_id'
          OR (member->>'action'='remove' AND old_member->>'native_snapshot_id' IS DISTINCT FROM
            member->>'snapshot_id')
          OR (member->>'action'='retain' AND
            old_member->>'native_snapshot_id'=member->>'snapshot_id') THEN
          RAISE EXCEPTION 'replacement member differs from predecessor live vector' USING
            ERRCODE='23514';
        END IF;
        IF member->>'action'<>'remove' THEN
          IF member->'ordinal' IS DISTINCT FROM to_jsonb(live_count) OR (member->>'ordinal') !~
            '^(0|[1-9][0-9]*)$'
            OR jsonb_typeof(member->'name') IS DISTINCT FROM 'string' OR length(member->>'name') NOT
              BETWEEN 1 AND 255 THEN
            RAISE EXCEPTION 'replacement member ordinal mismatch' USING ERRCODE='23514';
          END IF;
          live_count=live_count+1;
        END IF;
      END LOOP;
      n=jsonb_array_length(p->'members');
      IF live_count NOT BETWEEN 1 AND 16
        OR (SELECT count(DISTINCT v->>'catalog_table_id') FROM jsonb_array_elements(p->'members')
          v)<>n
        OR (SELECT count(DISTINCT v->>'table_id') FROM jsonb_array_elements(p->'members') v)<>n
        OR (SELECT count(DISTINCT v->>'snapshot_id') FROM jsonb_array_elements(p->'members') v)<>n
        OR EXISTS(SELECT 1 FROM jsonb_array_elements(p->'members') v GROUP BY v->>'member_key',
          (v->>'action'='remove') HAVING count(*)>1)
        OR EXISTS(SELECT 1 FROM jsonb_array_elements(prior.acknowledgement_json->'live_vector') v
          WHERE v->>'role'='member' AND NOT EXISTS(SELECT 1 FROM jsonb_array_elements(p->'members') m
            WHERE m->>'catalog_table_id'=v->>'catalog_id' AND m->>'action' IN ('retain','remove')))
              THEN
        RAISE EXCEPTION 'replacement requires complete bounded member correspondence' USING
          ERRCODE='23514';
      END IF;
      RETURN NEW;
    END $$""",
        """CREATE FUNCTION public.koinon_publication_private_guard() RETURNS trigger
    LANGUAGE plpgsql SET search_path=pg_catalog AS $$
    BEGIN
      IF TG_OP IN ('INSERT','UPDATE') AND current_user=pg_get_userbyid(
        (SELECT relowner FROM pg_class WHERE oid=TG_RELID)) THEN RETURN NEW; END IF;
      RAISE EXCEPTION 'publication transaction evidence is database-owned' USING ERRCODE='23514';
    END $$""",
        """CREATE FUNCTION public.koinon_open_source_publication(p_attempt text,p_receipt jsonb) RETURNS void
    LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
    DECLARE h public.koinon_content_publication_baselines; t
      public.koinon_content_publication_targets;
    BEGIN
      SELECT * INTO h FROM public.koinon_content_publication_baselines WHERE attempt_id=p_attempt FOR
        UPDATE;
      IF h.descriptor_json IS NULL OR h.acknowledgement_json IS NOT NULL THEN
        RAISE EXCEPTION 'publication requires frozen unacknowledged baseline' USING ERRCODE='23514';
      END IF;
      PERFORM c.id FROM public.lattice_catalog c JOIN public.koinon_content_publication_targets p
        ON p.catalog_id=c.id WHERE p.attempt_id=p_attempt ORDER BY c.id FOR UPDATE OF c;
      FOR t IN SELECT * FROM public.koinon_content_publication_targets WHERE attempt_id=p_attempt
        ORDER BY catalog_id LOOP
        IF (to_jsonb(t)-'attempt_id') IS DISTINCT FROM public.koinon_publication_current(p_attempt,
          t.catalog_id) THEN
          RAISE EXCEPTION 'publication original pin changed before publication' USING ERRCODE='23514';
        END IF;
      END LOOP;
      PERFORM public.koinon_publication_receipt(p_attempt,p_receipt);
      IF h.previous_attempt_id IS NOT NULL AND NOT EXISTS(SELECT 1 FROM public.koinon_content_objects
        o
        JOIN public.koinon_content_publication_baselines prior ON
          prior.attempt_id=h.previous_attempt_id
        WHERE o.id=h.object_id AND o.tenant_id=h.tenant_id
          AND o.published_local_revision='cpv1:'||prior.acknowledgement_sha256) THEN
        RAISE EXCEPTION 'publication predecessor changed before publication' USING ERRCODE='23514';
      END IF;
      INSERT INTO public.koinon_content_publication_transactions(attempt_id,transaction_id,
        native_receipt,write_counts,closed)
        VALUES(p_attempt,pg_current_xact_id(),p_receipt,'{}',false);
    END $$""",
        """CREATE FUNCTION public.koinon_publication_catalog_write() RETURNS trigger
    LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
    DECLARE e record; target jsonb; step jsonb; count_done integer; key text; value jsonb;
      expected jsonb; actual jsonb;
    BEGIN
      FOR e IN SELECT x.*,h.descriptor_json FROM public.koinon_content_publication_transactions x
        JOIN public.koinon_content_publication_baselines h ON h.attempt_id=x.attempt_id
        JOIN public.koinon_content_publication_targets p ON p.attempt_id=x.attempt_id
        WHERE x.transaction_id=pg_current_xact_id() AND p.catalog_id=OLD.id
      LOOP
        IF e.closed THEN RAISE EXCEPTION 'publication transaction already closed' USING
          ERRCODE='23514'; END IF;
        SELECT v INTO target FROM jsonb_array_elements(e.descriptor_json->'targets') v
          WHERE v->'pin'->>'catalog_id'=OLD.id;
        count_done=coalesce((e.write_counts->>OLD.id)::integer,0);
        step=target->'writes'->count_done;
        IF TG_OP<>'UPDATE' OR step IS NULL
          OR OLD.mutation_revision<>(target->'pin'->>'mutation_revision')::bigint+count_done
          OR NEW.mutation_revision<>OLD.mutation_revision+1 THEN
          RAISE EXCEPTION 'publication write count or intermediate revision mismatch' USING
            ERRCODE='23514';
        END IF;
        expected=to_jsonb(OLD)-ARRAY['mutation_revision','updated_at','updated_by'];
        FOR key,value IN SELECT * FROM jsonb_each(step->'fields') LOOP
          expected=jsonb_set(expected,ARRAY[CASE WHEN key='metadata' THEN 'metadata_json' ELSE key
            END],value);
        END LOOP;
        actual=to_jsonb(NEW)-ARRAY['mutation_revision','updated_at','updated_by'];
        IF actual IS DISTINCT FROM expected THEN
          RAISE EXCEPTION 'publication write does not match frozen action' USING ERRCODE='23514';
        END IF;
        UPDATE public.koinon_content_publication_transactions
          SET write_counts=jsonb_set(write_counts,ARRAY[OLD.id],to_jsonb(count_done+1)) WHERE
            attempt_id=e.attempt_id;
      END LOOP;
      RETURN NULL;
    END $$""",
        """CREATE FUNCTION public.koinon_publication_complete() RETURNS trigger
    LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
    DECLARE h public.koinon_content_publication_baselines; a public.koinon_content_imports;
      e public.koinon_content_publication_transactions; receipt jsonb; native_version text; target
        jsonb;
    BEGIN
      SELECT * INTO h FROM public.koinon_content_publication_baselines WHERE
        attempt_id=NEW.attempt_id;
      SELECT * INTO a FROM public.koinon_content_imports WHERE id=NEW.attempt_id;
      SELECT * INTO e FROM public.koinon_content_publication_transactions WHERE
        attempt_id=NEW.attempt_id;
      IF h.acknowledgement_json IS NULL OR e.closed IS DISTINCT FROM true
        OR e.transaction_id IS DISTINCT FROM pg_current_xact_id() THEN
        RAISE EXCEPTION 'publication transaction requires complete acknowledgement' USING
          ERRCODE='23514';
      END IF;
      receipt=h.acknowledgement_json->'native_receipt';
      native_version=coalesce(receipt->>'source_version_id',receipt->>'file_version_id');
      IF a.receipt_json IS NULL OR a.committed_at IS NULL
        OR a.receipt_json->>'source_attempt_id' IS DISTINCT FROM a.id
        OR a.receipt_json->>'source_publication_sha256' IS DISTINCT FROM h.descriptor_sha256
        OR NOT EXISTS(SELECT 1 FROM public.koinon_content_objects o WHERE o.id=h.object_id
          AND o.tenant_id=h.tenant_id AND o.mapping_id=h.mapping_id AND o.state='imported'
          AND o.published_local_revision='cpv1:'||h.acknowledgement_sha256
          AND o.published_native_version_id=native_version AND o.published_sha256=a.sha256)
        OR NOT EXISTS(SELECT 1 FROM public.koinon_content_imported_versions v WHERE v.attempt_id=a.id
          AND v.tenant_id=h.tenant_id AND v.source_id=h.source_id AND v.asset_id=h.asset_id
          AND v.domain=receipt->>'domain' AND v.native_workspace_id=receipt->>'native_workspace_id'
          AND v.native_source_id=receipt->>'native_source_id' AND
            v.native_asset_id=receipt->>'native_asset_id'
          AND v.native_version_id=native_version AND v.extraction_id IS NOT DISTINCT FROM
            receipt->>'extraction_id')
        OR NOT EXISTS(SELECT 1 FROM public.koinon_content_sync_work w WHERE
          w.id=h.descriptor_json->'observation'->>'work_id'
          AND w.attempt_id=a.id AND w.status='imported') THEN
        RAISE EXCEPTION 'publication completion is incomplete' USING ERRCODE='23514';
      END IF;
      IF a.intake_item_id IS NOT NULL AND NOT EXISTS(SELECT 1 FROM public.koinon_bulk_items i
        JOIN public.lattice_jobs j ON j.id=i.job_id WHERE i.id=a.intake_item_id AND
          i.status='succeeded'
          AND i.receipt_json IS NOT NULL AND j.status='succeeded') THEN
        RAISE EXCEPTION 'publication bulk completion is incomplete' USING ERRCODE='23514';
      END IF;
      FOR target IN SELECT value FROM
        jsonb_array_elements(h.acknowledgement_json->'transition_vector') LOOP
        IF target IS DISTINCT FROM public.koinon_publication_current(a.id,target->>'catalog_id') THEN
          RAISE EXCEPTION 'publication vector changed before completion' USING ERRCODE='23514';
        END IF;
      END LOOP;
      RETURN NULL;
    END $$""",
        """CREATE FUNCTION public.koinon_publication_pointer_complete() RETURNS trigger
    LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
    BEGIN
      IF NEW.published_local_revision IS NULL AND NEW.published_native_version_id IS NULL
        AND NEW.published_sha256 IS NULL THEN RETURN NULL; END IF;
      IF TG_OP='UPDATE' THEN
        IF ROW(NEW.published_local_revision,NEW.published_native_version_id,NEW.published_sha256)
          IS NOT DISTINCT FROM
          ROW(OLD.published_local_revision,OLD.published_native_version_id,OLD.published_sha256)
          THEN RETURN NULL; END IF;
      END IF;
      IF NEW.remote_kind='folder' AND NEW.published_native_version_id IS NULL
        AND EXISTS(SELECT 1 FROM public.koinon_content_folder_publications f
          WHERE f.tenant_id=NEW.tenant_id AND f.mapping_id=NEW.mapping_id AND f.object_id=NEW.id
          AND f.canonical_revision::text=NEW.published_local_revision
          AND f.canonical_sha256=NEW.published_sha256) THEN RETURN NULL; END IF;
      IF NOT EXISTS(SELECT 1 FROM public.koinon_content_publication_baselines h
        JOIN public.koinon_content_publication_transactions e ON e.attempt_id=h.attempt_id
        JOIN public.koinon_content_imports a ON a.id=h.attempt_id
        WHERE h.tenant_id=NEW.tenant_id AND h.mapping_id=NEW.mapping_id AND h.object_id=NEW.id
          AND e.closed AND e.transaction_id=pg_current_xact_id()
          AND h.acknowledgement_json IS NOT NULL
          AND NEW.published_local_revision='cpv1:'||h.acknowledgement_sha256
          AND NEW.published_sha256=a.sha256
          AND NEW.published_native_version_id=coalesce(
            h.acknowledgement_json->'native_receipt'->>'source_version_id',
            h.acknowledgement_json->'native_receipt'->>'file_version_id')) THEN
        RAISE EXCEPTION 'publication pointer requires same-transaction acknowledgement'
          USING ERRCODE='23514';
      END IF;
      RETURN NULL;
    END $$""",
        """CREATE FUNCTION public.koinon_publication_receipt(p_attempt text, receipt jsonb) RETURNS void
    LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
    DECLARE h public.koinon_content_publication_baselines; a public.koinon_content_imports;
      member jsonb; planned jsonb; n integer; previous_receipt jsonb; producer jsonb;
    BEGIN
      SELECT * INTO h FROM public.koinon_content_publication_baselines WHERE attempt_id=p_attempt;
      SELECT * INTO a FROM public.koinon_content_imports WHERE id=p_attempt;
      IF h.descriptor_json IS NULL OR NOT public.koinon_publication_closed(receipt,
        ARRAY['domain','native_workspace_id','native_source_id','native_asset_id','sha256',
          'size_bytes',
        'source_version_id','extraction_id','n_chunks','object_key','file_version_id',
          'native_file_id',
        'tables','source_attempt_id','source_publication_sha256'])
        OR octet_length(receipt::text)>262144
        OR receipt->>'source_attempt_id' IS DISTINCT FROM h.attempt_id
        OR receipt->>'source_publication_sha256' IS DISTINCT FROM h.descriptor_sha256
        OR receipt->>'domain' IS DISTINCT FROM h.descriptor_json->'native'->>'domain'
        OR receipt->>'native_workspace_id' IS DISTINCT FROM
          h.descriptor_json->'native'->>'workspace_id'
        OR receipt->>'sha256' IS DISTINCT FROM a.sha256
        OR receipt->'size_bytes' IS DISTINCT FROM to_jsonb(a.size_bytes)
        OR jsonb_typeof(receipt->'size_bytes') IS DISTINCT FROM 'number'
        OR (receipt->>'size_bytes') !~ '^[1-9][0-9]*$'
        OR jsonb_typeof(receipt->'n_chunks') IS DISTINCT FROM 'number'
        OR (receipt->>'n_chunks') !~ '^(0|[1-9][0-9]*)$'
        OR (receipt->>'n_chunks')::numeric>2147483647
        OR jsonb_typeof(receipt->'object_key') IS DISTINCT FROM 'string'
        OR length(receipt->>'object_key')>2048
        OR jsonb_typeof(receipt->'tables') IS DISTINCT FROM 'array'
        OR EXISTS(SELECT 1 FROM unnest(ARRAY['native_source_id','native_asset_id',
          'native_workspace_id','source_attempt_id','source_publication_sha256','sha256']) k
          WHERE jsonb_typeof(receipt->k) IS DISTINCT FROM 'string' OR length(receipt->>k) NOT BETWEEN
            1 AND 64)
      THEN RAISE EXCEPTION 'publication native receipt mismatch' USING ERRCODE='23514'; END IF;
      IF h.producer_kind LIKE '%document' THEN
        IF jsonb_array_length(receipt->'tables')<>0 OR receipt->'file_version_id'<>'null'::jsonb
          OR receipt->'native_file_id'<>'null'::jsonb
          OR EXISTS(SELECT 1 FROM unnest(ARRAY['source_version_id','extraction_id']) k
            WHERE jsonb_typeof(receipt->k) IS DISTINCT FROM 'string' OR length(receipt->>k) NOT
              BETWEEN 1 AND 64)
        THEN RAISE EXCEPTION 'publication document receipt mismatch' USING ERRCODE='23514'; END IF;
      ELSE
        IF receipt->'source_version_id'<>'null'::jsonb OR receipt->'extraction_id'<>'null'::jsonb
          OR jsonb_array_length(receipt->'tables') NOT BETWEEN 1 AND 16
          OR EXISTS(SELECT 1 FROM unnest(ARRAY['file_version_id','native_file_id']) k
            WHERE jsonb_typeof(receipt->k) IS DISTINCT FROM 'string' OR length(receipt->>k) NOT
              BETWEEN 1 AND 64)
        THEN RAISE EXCEPTION 'publication dataset receipt mismatch' USING ERRCODE='23514'; END IF;
        n=0;
        FOR member IN SELECT value FROM jsonb_array_elements(receipt->'tables') LOOP
          SELECT value INTO planned FROM jsonb_array_elements(h.descriptor_json->'members')
            WHERE value->>'catalog_table_id'=member->>'catalog_table_id';
          IF NOT public.koinon_publication_closed(member,ARRAY['catalog_table_id','table_id',
            'snapshot_id','n_columns','n_rows_actual'])
            OR planned IS NULL OR planned->>'action'='remove'
            OR planned->'ordinal' IS DISTINCT FROM to_jsonb(n)
            OR EXISTS(SELECT 1 FROM unnest(ARRAY['catalog_table_id','table_id','snapshot_id']) k
              WHERE jsonb_typeof(member->k) IS DISTINCT FROM 'string' OR length(member->>k) NOT
                BETWEEN 1 AND 64)
            OR member->>'table_id' IS DISTINCT FROM planned->>'table_id'
            OR member->>'snapshot_id' IS DISTINCT FROM planned->>'snapshot_id'
            OR jsonb_typeof(member->'n_columns') IS DISTINCT FROM 'number'
            OR (member->>'n_columns') !~ '^[1-9][0-9]*$'
            OR (member->>'n_columns')::numeric>10000
            OR jsonb_typeof(member->'n_rows_actual') IS DISTINCT FROM 'number'
            OR (member->>'n_rows_actual') !~ '^(0|[1-9][0-9]*)$'
            OR (member->>'n_rows_actual')::numeric>9223372036854775807
          THEN RAISE EXCEPTION 'publication member receipt mismatch' USING ERRCODE='23514'; END IF;
          n=n+1;
        END LOOP;
        IF (SELECT count(DISTINCT value->>'catalog_table_id') FROM
          jsonb_array_elements(receipt->'tables'))<>n
          OR n<>(SELECT count(*) FROM jsonb_array_elements(h.descriptor_json->'members') m
            WHERE coalesce(m->>'action','add')<>'remove') THEN
          RAISE EXCEPTION 'publication receipt member set mismatch' USING ERRCODE='23514';
        END IF;
        IF h.producer_kind='initial_dataset' AND NOT EXISTS(SELECT 1 FROM public.koinon_bulk_items i
          WHERE i.id=a.intake_item_id AND
            i.reservation_json->>'catalog_file_version_id'=receipt->>'file_version_id'
          AND i.reservation_json->>'native_file_id'=receipt->>'native_file_id'
          AND i.reservation_json->>'native_dataset_id'=receipt->>'native_source_id'
          AND i.reservation_json->>'native_dataset_id'=receipt->>'native_asset_id') THEN
          RAISE EXCEPTION 'publication dataset reservation receipt mismatch' USING ERRCODE='23514';
        END IF;
      END IF;
      IF h.previous_attempt_id IS NOT NULL THEN
        SELECT acknowledgement_json->'native_receipt' INTO previous_receipt
          FROM public.koinon_content_publication_baselines WHERE attempt_id=h.previous_attempt_id;
        SELECT metadata_json::jsonb->'_koinon_source_replacement' INTO producer FROM
          public.lattice_catalog WHERE id=a.content_operation_id;
        IF receipt->'native_source_id' IS DISTINCT FROM previous_receipt->'native_source_id'
          OR receipt->'native_asset_id' IS DISTINCT FROM previous_receipt->'native_asset_id'
          OR (h.producer_kind='replace_dataset' AND
            (receipt->>'file_version_id' IS DISTINCT FROM a.content_operation_id
             OR receipt->'native_file_id' IS DISTINCT FROM producer->'native_file_id'))
          OR (h.producer_kind='replace_document' AND
            (receipt->'source_version_id'=previous_receipt->'source_version_id'
             OR receipt->'extraction_id'=previous_receipt->'extraction_id')) THEN
          RAISE EXCEPTION 'replacement receipt differs from exact retained producer' USING
            ERRCODE='23514';
        END IF;
      END IF;
    END $$""",
        """CREATE FUNCTION public.koinon_publication_header_guard() RETURNS trigger
    LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
    DECLARE a public.koinon_content_imports; m public.koinon_content_mappings;
      i public.koinon_bulk_items; b public.koinon_bulk_batches;
      prior public.koinon_content_publication_baselines; d jsonb; target jsonb; member jsonb;
      pins jsonb; selected_pins jsonb; expected_ids text[]; actual_ids text[]; native jsonb;
      evidence public.koinon_content_publication_transactions; vector jsonb; live jsonb; actual jsonb;
      patch jsonb; resolved jsonb; key text; bound_value jsonb; expected_binding jsonb; idx integer;
      producer jsonb; expected_heads jsonb; metadata jsonb; expected_writes jsonb;
    BEGIN
      IF TG_OP IN ('DELETE','TRUNCATE') THEN
        RAISE EXCEPTION 'publication baselines are immutable' USING ERRCODE='23514';
      END IF;
      SELECT * INTO a FROM public.koinon_content_imports WHERE id=NEW.attempt_id;
      SELECT * INTO m FROM public.koinon_content_mappings WHERE id=NEW.mapping_id;
      SELECT * INTO i FROM public.koinon_bulk_items WHERE id=a.intake_item_id;
      SELECT * INTO b FROM public.koinon_bulk_batches WHERE id=i.batch_id;
      SELECT * INTO prior FROM public.koinon_content_publication_baselines WHERE
        attempt_id=NEW.previous_attempt_id;
      IF TG_OP='INSERT' THEN
        IF a.id IS NULL OR m.id IS NULL OR
          ROW(NEW.tenant_id,NEW.mapping_id,NEW.object_id,NEW.source_id,NEW.asset_id)
            IS DISTINCT FROM ROW(a.tenant_id,a.mapping_id,a.object_id,a.source_id,a.asset_id)
          OR ROW(NEW.tenant_id,NEW.workspace_id,NEW.project_id)
            IS DISTINCT FROM ROW(m.tenant_id,m.workspace_id,m.project_id)
          OR NOT EXISTS(SELECT 1 FROM public.koinon_content_objects o WHERE o.id=a.object_id
            AND o.tenant_id=a.tenant_id AND o.mapping_id=a.mapping_id)
          OR NEW.descriptor_json IS NOT NULL OR NEW.descriptor_sha256 IS NOT NULL
          OR NEW.acknowledgement_json IS NOT NULL OR NEW.acknowledgement_sha256 IS NOT NULL
        THEN RAISE EXCEPTION 'publication header scope mismatch' USING ERRCODE='23514'; END IF;
        IF NEW.producer_kind LIKE 'initial_%' THEN
          IF i.id IS NULL OR a.content_operation_id IS NOT NULL OR NEW.previous_attempt_id IS NOT NULL
            OR ROW(b.tenant_id,b.workspace_id,b.project_id,i.source_id,i.asset_id)
              IS DISTINCT FROM ROW(NEW.tenant_id,NEW.workspace_id,NEW.project_id,NEW.source_id,
                NEW.asset_id)
            OR NEW.producer_kind<>'initial_'||i.mode
          THEN RAISE EXCEPTION 'publication requires exact initial producer' USING ERRCODE='23514';
            END IF;
        ELSE
          IF a.intake_item_id IS NOT NULL OR a.content_operation_id IS NULL OR
            prior.acknowledgement_json IS NULL
            OR ROW(prior.tenant_id,prior.mapping_id,prior.object_id,prior.source_id,prior.asset_id)
              IS DISTINCT FROM ROW(NEW.tenant_id,NEW.mapping_id,NEW.object_id,NEW.source_id,
                NEW.asset_id)
            OR NOT EXISTS(SELECT 1 FROM public.lattice_catalog c WHERE c.id=a.content_operation_id
              AND c.tenant_id=NEW.tenant_id AND c.workspace_id=NEW.workspace_id AND
                c.project_id=NEW.project_id)
            OR NOT EXISTS(SELECT 1 FROM public.koinon_content_objects o WHERE o.id=NEW.object_id
              AND o.published_local_revision='cpv1:'||prior.acknowledgement_sha256)
          THEN RAISE EXCEPTION 'publication requires exact replacement predecessor' USING
            ERRCODE='23514'; END IF;
        END IF;
        RETURN NEW;
      END IF;
      IF (to_jsonb(NEW)-ARRAY['descriptor_json','descriptor_sha256','acknowledgement_json',
        'acknowledgement_sha256'])
          IS DISTINCT FROM (to_jsonb(OLD)-ARRAY['descriptor_json','descriptor_sha256',
            'acknowledgement_json','acknowledgement_sha256'])
        OR (OLD.descriptor_json IS NOT NULL AND ROW(NEW.descriptor_json,NEW.descriptor_sha256)
          IS DISTINCT FROM ROW(OLD.descriptor_json,OLD.descriptor_sha256))
        OR OLD.acknowledgement_json IS NOT NULL THEN
        RAISE EXCEPTION 'publication baseline identity and evidence are immutable' USING
          ERRCODE='23514';
      END IF;
      IF OLD.descriptor_json IS NULL THEN
        d=NEW.descriptor_json;
        IF NEW.acknowledgement_json IS NOT NULL OR NEW.acknowledgement_sha256 IS NOT NULL
          OR NOT public.koinon_publication_closed(d,ARRAY['schema','identity','producer',
            'observation','content',
            'previous_acknowledgement_sha256','native','targets','members'])
          OR d->>'schema' IS DISTINCT FROM 'koinon.source-publication-descriptor.v1'
          OR octet_length(d::text)>262144
          OR d->'identity' IS DISTINCT FROM (to_jsonb(NEW)-ARRAY['created_at','descriptor_json',
            'descriptor_sha256','acknowledgement_json','acknowledgement_sha256'])
             ||jsonb_build_object('generation',a.generation,'mapping_revision',a.mapping_revision)
          OR d->'producer' IS DISTINCT FROM jsonb_build_object('intake_item_id',a.intake_item_id,
            'content_operation_id',a.content_operation_id)
          OR d->'content' IS DISTINCT FROM jsonb_build_object('remote_version',a.remote_version,
            'sha256',a.sha256,'size_bytes',a.size_bytes)
          OR d->'previous_acknowledgement_sha256' IS DISTINCT FROM
            coalesce(to_jsonb(prior.acknowledgement_sha256),'null'::jsonb)
          OR NOT public.koinon_publication_closed(d->'observation',ARRAY['run_id','work_id',
            'observation_id'])
          OR NOT public.koinon_publication_closed(d->'native',ARRAY['domain','workspace_id',
            'operation_id','expected_heads'])
          OR jsonb_typeof(d->'targets') IS DISTINCT FROM 'array' OR jsonb_typeof(d->'members') IS
            DISTINCT FROM 'array'
        THEN RAISE EXCEPTION 'invalid closed publication descriptor' USING ERRCODE='23514'; END IF;
        IF (d->'identity'->>'generation') !~ '^[1-9][0-9]*$'
          OR (d->'identity'->>'mapping_revision') !~ '^[1-9][0-9]*$'
          OR (d->'content'->>'size_bytes') !~ '^[1-9][0-9]*$'
          OR NOT EXISTS(SELECT 1 FROM public.koinon_content_sync_observations o
            JOIN public.koinon_content_sync_work w ON w.id=o.work_id
            WHERE o.id=d->'observation'->>'observation_id' AND o.work_id=d->'observation'->>'work_id'
              AND o.run_id=d->'observation'->>'run_id' AND o.tenant_id=NEW.tenant_id
              AND o.mapping_id=NEW.mapping_id AND o.object_id=NEW.object_id AND
                o.generation=a.generation
              AND o.remote_version=a.remote_version AND w.attempt_id=a.id)
        THEN RAISE EXCEPTION 'publication observation mismatch' USING ERRCODE='23514'; END IF;
        native=d->'native';
        IF native->>'domain' IS DISTINCT FROM (CASE WHEN NEW.producer_kind LIKE '%document' THEN
          'canon' ELSE 'structured' END)
          OR jsonb_typeof(native->'workspace_id') IS DISTINCT FROM 'string'
          OR length(native->>'workspace_id') NOT BETWEEN 1 AND 64
          OR jsonb_typeof(native->'operation_id') IS DISTINCT FROM 'string'
          OR length(native->>'operation_id') NOT BETWEEN 1 AND 128 THEN
          RAISE EXCEPTION 'publication native operation mismatch' USING ERRCODE='23514';
        END IF;
        IF NEW.producer_kind LIKE 'initial_%' AND
          (native->>'workspace_id' IS DISTINCT FROM i.native_workspace_id OR
            native->'expected_heads'<>'null'::jsonb
           OR native->>'operation_id' IS DISTINCT FROM (CASE WHEN i.mode='document' THEN
             'upload:'||NEW.source_id ELSE i.id END)) THEN
          RAISE EXCEPTION 'publication initial native operation mismatch' USING ERRCODE='23514';
        END IF;
        SELECT coalesce(jsonb_agg(to_jsonb(t)-'attempt_id' ORDER BY catalog_id),'[]'::jsonb),
          array_agg(catalog_id ORDER BY catalog_id)
          INTO pins,actual_ids FROM public.koinon_content_publication_targets t WHERE
            attempt_id=NEW.attempt_id;
        SELECT coalesce(jsonb_agg(value->'pin' ORDER BY ordinality),'[]'::jsonb) INTO selected_pins
          FROM jsonb_array_elements(d->'targets') WITH ORDINALITY;
        IF pins IS DISTINCT FROM selected_pins THEN
          RAISE EXCEPTION 'publication descriptor must contain exact sorted original pins' USING
            ERRCODE='23514';
        END IF;
        IF NEW.producer_kind LIKE 'initial_%' THEN
          SELECT array_agg(identifier ORDER BY identifier) INTO expected_ids FROM (
            SELECT NEW.source_id identifier UNION ALL SELECT NEW.asset_id
            UNION ALL SELECT i.reservation_json->>'catalog_file_version_id' WHERE i.mode='dataset'
            UNION ALL SELECT catalog_table_id FROM public.koinon_bulk_table_reservations WHERE
              item_id=i.id
          ) expected;
          IF actual_ids IS DISTINCT FROM expected_ids OR (i.mode='document' AND
            d->'members'<>'[]'::jsonb)
            OR (i.mode='dataset' AND (jsonb_array_length(d->'members') NOT BETWEEN 1 AND 16
              OR jsonb_array_length(d->'members')<>(SELECT count(*) FROM
                public.koinon_bulk_table_reservations WHERE item_id=i.id))) THEN
            RAISE EXCEPTION 'publication requires complete producer target set' USING ERRCODE='23514';
          END IF;
          idx=0;
          FOR member IN SELECT value FROM jsonb_array_elements(d->'members') LOOP
            IF NOT public.koinon_publication_closed(member,ARRAY['ordinal','table_id','snapshot_id',
              'name','catalog_table_id','member_key','parser_fingerprint'])
              OR member->'ordinal' IS DISTINCT FROM to_jsonb(idx) OR (member->>'ordinal') !~
                '^(0|[1-9][0-9]*)$'
              OR NOT EXISTS(SELECT 1 FROM public.koinon_bulk_table_reservations r WHERE
                r.item_id=i.id AND r.ordinal=idx
                AND r.catalog_table_id=member->>'catalog_table_id' AND r.table_id=member->>'table_id'
                AND r.snapshot_id=member->>'snapshot_id' AND r.name=member->>'name') THEN
              RAISE EXCEPTION 'publication member plan reservation mismatch' USING ERRCODE='23514';
            END IF;
            idx=idx+1;
          END LOOP;
        ELSE
          SELECT metadata_json::jsonb->'_koinon_source_replacement' INTO producer FROM
            public.lattice_catalog
            WHERE id=a.content_operation_id;
          SELECT jsonb_build_object('baseline_sha256',producer->'baseline_sha256',
            'source_version_id',prior.acknowledgement_json->'native_receipt'->'source_version_id',
            'extraction_id',prior.acknowledgement_json->'native_receipt'->'extraction_id',
            'native_file_id',prior.acknowledgement_json->'native_receipt'->'native_file_id',
            'tables',coalesce((SELECT jsonb_agg(jsonb_build_object('catalog_table_id',
              v->'catalog_table_id',
              'table_id',v->'table_id','snapshot_id',v->'snapshot_id') ORDER BY ordinal)
              FROM jsonb_array_elements(prior.acknowledgement_json->'native_receipt'->'tables') WITH
                ORDINALITY t(v,ordinal)),'[]'::jsonb))
            INTO expected_heads;
          IF producer IS NULL OR producer->>'attempt_id' IS DISTINCT FROM a.id
            OR d->'members' IS DISTINCT FROM producer->'members'
            OR native->>'operation_id' IS DISTINCT FROM a.content_operation_id
            OR native->>'workspace_id' IS DISTINCT FROM producer->>'native_workspace_id'
            OR native->'expected_heads' IS DISTINCT FROM expected_heads THEN
            RAISE EXCEPTION 'publication replacement descriptor producer mismatch' USING
              ERRCODE='23514';
          END IF;
          SELECT array_agg(identifier ORDER BY identifier) INTO expected_ids FROM (
            SELECT NEW.source_id identifier UNION ALL SELECT NEW.asset_id
            UNION ALL SELECT a.content_operation_id WHERE NEW.producer_kind='replace_dataset'
            UNION ALL SELECT producer->>'previous_index_id' WHERE NEW.producer_kind='replace_dataset'
            UNION ALL SELECT p->>'catalog_table_id' FROM jsonb_array_elements(producer->'members') p
          ) expected;
          IF actual_ids IS DISTINCT FROM expected_ids THEN
            RAISE EXCEPTION 'publication replacement requires complete transition set' USING
              ERRCODE='23514';
          END IF;
        END IF;
        FOR target IN SELECT value FROM jsonb_array_elements(d->'targets') LOOP
          IF NOT public.koinon_publication_closed(target,ARRAY['pin','writes','binding'])
            OR jsonb_typeof(target->'writes') IS DISTINCT FROM 'array'
            OR NOT public.koinon_publication_closed(target->'binding',ARRAY['domain',
              'native_workspace_id','native_id','native_version_id','native_snapshot_id'])
            OR (target->'pin'->>'mutation_revision') !~ '^[1-9][0-9]*$'
            OR target->'pin' IS DISTINCT FROM public.koinon_publication_current(NEW.attempt_id,
              target->'pin'->>'catalog_id')
          THEN RAISE EXCEPTION 'publication original pin changed before freeze' USING
            ERRCODE='23514'; END IF;
          IF NEW.producer_kind LIKE 'initial_%' AND
            target->'writes'<>'[{"action":"update","fields":{"status":"ready"}}]'::jsonb THEN
            RAISE EXCEPTION 'publication initial write plan mismatch' USING ERRCODE='23514';
          END IF;
          IF NEW.producer_kind LIKE 'replace_%' THEN
            SELECT metadata_json::jsonb INTO metadata FROM public.lattice_catalog WHERE
              id=target->'pin'->>'catalog_id';
            CASE
              WHEN target->'pin'->>'role'='old_index' THEN expected_writes='[]'::jsonb;
              WHEN target->'pin'->>'disposition'='remove' THEN
                expected_writes='[{"action":"update","fields":{"status":"archived"}}]'::jsonb;
              WHEN target->'pin'->>'role'='new_index' THEN
                expected_writes='[{"action":"update","fields":{"status":"ready"}}]'::jsonb;
              WHEN target->'pin'->>'role' IN ('source','asset') THEN
                expected_writes=jsonb_build_array(jsonb_build_object('action','update','fields',
                  jsonb_build_object('status','ready',
                  'metadata',metadata||jsonb_build_object('sha256',a.sha256,'bytes',a.size_bytes,
                    'latest_content_version_id',a.content_operation_id))));
              ELSE
                SELECT p INTO member FROM jsonb_array_elements(producer->'members') p WHERE
                  p->>'catalog_table_id'=target->'pin'->>'catalog_id';
                expected_writes=jsonb_build_array(jsonb_build_object('action','update','fields',
                  jsonb_build_object('status','ready',
                  'metadata',metadata||jsonb_build_object('snapshot_id',member->>'snapshot_id'))));
            END CASE;
            IF target->'writes' IS DISTINCT FROM expected_writes THEN
              RAISE EXCEPTION 'publication replacement write plan mismatch' USING ERRCODE='23514';
            END IF;
          END IF;
          IF target->'pin'->>'role'='old_index' OR target->'pin'->>'disposition'='remove' THEN
            expected_binding=jsonb_build_object('domain',target->'pin'->'native_domain',
              'native_workspace_id',target->'pin'->'native_workspace_id','native_id',
                target->'pin'->'native_id',
              'native_version_id',target->'pin'->'native_version_id','native_snapshot_id',
                target->'pin'->'native_snapshot_id');
          ELSE
            expected_binding=jsonb_build_object('domain',native->'domain',
              'native_workspace_id',jsonb_build_object('receipt_field','native_workspace_id'),
              'native_id',jsonb_build_object('receipt_field',CASE target->'pin'->>'role'
                WHEN 'source' THEN 'native_source_id' WHEN 'asset' THEN 'native_asset_id' ELSE
                  'native_file_id' END),
              'native_version_id',NULL,'native_snapshot_id',NULL);
            IF NEW.producer_kind LIKE '%document' THEN
              expected_binding=expected_binding||jsonb_build_object('native_version_id',
                jsonb_build_object('receipt_field','source_version_id'),
                'native_snapshot_id',jsonb_build_object('receipt_field','extraction_id'));
            ELSIF target->'pin'->>'role'='new_index' THEN
              expected_binding=expected_binding||jsonb_build_object('native_version_id',
                jsonb_build_object('receipt_field','native_file_id'));
            ELSIF target->'pin'->>'role'='member' THEN
              SELECT (p->>'ordinal')::integer INTO idx FROM jsonb_array_elements(d->'members') p
                WHERE p->>'catalog_table_id'=target->'pin'->>'catalog_id';
              IF idx IS NULL OR idx NOT BETWEEN 0 AND 15 THEN
                RAISE EXCEPTION 'publication member receipt ordinal mismatch' USING ERRCODE='23514';
              END IF;
              expected_binding=expected_binding||jsonb_build_object(
                'native_id',jsonb_build_object('receipt_field','tables.'||idx||'.table_id'),
                'native_version_id',jsonb_build_object('receipt_field','native_file_id'),
                'native_snapshot_id',jsonb_build_object('receipt_field',
                  'tables.'||idx||'.snapshot_id'));
            END IF;
          END IF;
          IF target->'binding' IS DISTINCT FROM expected_binding THEN
            RAISE EXCEPTION 'publication binding plan is not exact producer projection' USING
              ERRCODE='23514';
          END IF;
          FOR patch IN SELECT value FROM jsonb_array_elements(target->'writes') LOOP
            IF NOT public.koinon_publication_closed(patch,ARRAY['action','fields']) OR
              patch->>'action'<>'update'
              OR jsonb_typeof(patch->'fields') IS DISTINCT FROM 'object' OR
                patch->'fields'='{}'::jsonb
              OR EXISTS(SELECT 1 FROM jsonb_object_keys(patch->'fields') k WHERE k NOT IN ('status',
                'metadata','name','parent_id')) THEN
              RAISE EXCEPTION 'publication write plan is not closed' USING ERRCODE='23514';
            END IF;
          END LOOP;
        END LOOP;
        IF NEW.descriptor_sha256 IS NOT NULL AND
          NEW.descriptor_sha256<>encode(sha256(convert_to(d::text,'UTF8')),'hex') THEN
          RAISE EXCEPTION 'publication descriptor digest mismatch' USING ERRCODE='23514';
        END IF;
        NEW.descriptor_sha256=encode(sha256(convert_to(d::text,'UTF8')),'hex');
        RETURN NEW;
      END IF;
      IF NEW.acknowledgement_json IS NULL THEN
        RAISE EXCEPTION 'publication evidence must transition once' USING ERRCODE='23514';
      END IF;
      d=NEW.acknowledgement_json;
      SELECT * INTO evidence FROM public.koinon_content_publication_transactions WHERE
        attempt_id=NEW.attempt_id FOR UPDATE;
      IF evidence.attempt_id IS NULL OR evidence.closed OR
        evidence.transaction_id<>pg_current_xact_id()
        OR NOT public.koinon_publication_closed(d,ARRAY['schema','attempt_id','descriptor_sha256',
          'native_receipt','transition_vector','live_vector'])
        OR d->>'schema' IS DISTINCT FROM 'koinon.source-publication-acknowledgement.v1'
        OR d->>'attempt_id' IS DISTINCT FROM NEW.attempt_id OR d->>'descriptor_sha256' IS DISTINCT
          FROM NEW.descriptor_sha256
        OR d->'native_receipt' IS DISTINCT FROM evidence.native_receipt OR
          octet_length(d::text)>262144 THEN
        RAISE EXCEPTION 'publication acknowledgement requires exact open transaction' USING
          ERRCODE='23514';
      END IF;
      vector='[]'::jsonb; live='[]'::jsonb;
      FOR target IN SELECT value FROM jsonb_array_elements(NEW.descriptor_json->'targets') LOOP
        key=target->'pin'->>'catalog_id';
        actual=public.koinon_publication_current(NEW.attempt_id,key);
        IF actual IS NULL OR coalesce((evidence.write_counts->>key)::integer,
          0)<>jsonb_array_length(target->'writes')
          OR (actual->>'mutation_revision')::bigint <>
            (target->'pin'->>'mutation_revision')::bigint + jsonb_array_length(target->'writes') THEN
          RAISE EXCEPTION 'publication acknowledgement final revision mismatch' USING ERRCODE='23514';
        END IF;
        expected_binding='{}'::jsonb;
        FOR key,bound_value IN SELECT * FROM jsonb_each(target->'binding') LOOP
          resolved=bound_value;
          IF jsonb_typeof(bound_value)='object' THEN
            resolved=evidence.native_receipt #> string_to_array(bound_value->>'receipt_field','.');
          END IF;
          expected_binding=expected_binding||jsonb_build_object(CASE WHEN key='domain' THEN
            'native_domain' ELSE key END,resolved);
        END LOOP;
        IF actual @> expected_binding IS NOT TRUE THEN
          RAISE EXCEPTION 'publication acknowledgement native binding mismatch' USING ERRCODE='23514';
        END IF;
        vector=vector||jsonb_build_array(actual);
        IF actual->>'disposition'<>'remove' AND actual->>'role'<>'old_index' THEN
          live=live||jsonb_build_array(actual); END IF;
      END LOOP;
      IF d->'transition_vector' IS DISTINCT FROM vector OR d->'live_vector' IS DISTINCT FROM live THEN
        RAISE EXCEPTION 'publication acknowledgement vector mismatch' USING ERRCODE='23514';
      END IF;
      IF EXISTS(SELECT 1 FROM jsonb_array_elements(d->'transition_vector') v WHERE
        (v->>'mutation_revision') !~ '^[1-9][0-9]*$')
        OR EXISTS(SELECT 1 FROM jsonb_array_elements(d->'live_vector') v WHERE
          (v->>'mutation_revision') !~ '^[1-9][0-9]*$') THEN
        RAISE EXCEPTION 'publication vector requires strict integer revisions' USING ERRCODE='23514';
      END IF;
      IF NEW.acknowledgement_sha256 IS NOT NULL AND
        NEW.acknowledgement_sha256<>encode(sha256(convert_to(d::text,'UTF8')),'hex') THEN
        RAISE EXCEPTION 'publication acknowledgement digest mismatch' USING ERRCODE='23514';
      END IF;
      NEW.acknowledgement_sha256=encode(sha256(convert_to(d::text,'UTF8')),'hex');
      UPDATE public.koinon_content_publication_transactions SET closed=true WHERE
        attempt_id=NEW.attempt_id;
      RETURN NEW;
    END $$""",
    ]
)


def statements():
    yield from FUNCTIONS
    for table in (BASELINES, TARGETS, TRANSACTIONS):
        yield f"REVOKE ALL ON TABLE public.{table} FROM PUBLIC"
    for table, name, function in (
        (TARGETS, "targets", "target"),
        (BASELINES, "baseline", "header"),
        (TRANSACTIONS, "transaction", "private"),
    ):
        yield (
            f"CREATE TRIGGER publication_{name}_rows BEFORE INSERT OR UPDATE OR DELETE ON public.{table} "
            f"FOR EACH ROW EXECUTE FUNCTION public.koinon_publication_{function}_guard()"
        )
        yield (
            f"CREATE TRIGGER publication_{name}_truncate BEFORE TRUNCATE ON public.{table} "
            f"FOR EACH STATEMENT EXECUTE FUNCTION public.koinon_publication_{function}_guard()"
        )
    yield (
        "CREATE TRIGGER publication_catalog_write AFTER UPDATE OR DELETE ON "
        "public.lattice_catalog FOR EACH ROW EXECUTE FUNCTION "
        "public.koinon_publication_catalog_write()"
    )
    yield (
        "CREATE TRIGGER publication_replacement_producer BEFORE INSERT OR UPDATE OF "
        "metadata_json ON public.lattice_catalog FOR EACH ROW EXECUTE FUNCTION "
        "public.koinon_publication_replacement_guard()"
    )
    yield (
        f"CREATE CONSTRAINT TRIGGER publication_complete AFTER INSERT ON public.{TRANSACTIONS} "
        "DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION public.koinon_publication_complete()"
    )
    yield (
        "CREATE CONSTRAINT TRIGGER publication_imported_complete AFTER INSERT ON "
        "public.koinon_content_imported_versions DEFERRABLE INITIALLY DEFERRED "
        "FOR EACH ROW EXECUTE FUNCTION public.koinon_publication_complete()"
    )
    yield (
        "CREATE CONSTRAINT TRIGGER publication_pointer_complete AFTER INSERT OR UPDATE ON "
        "public.koinon_content_objects DEFERRABLE INITIALLY DEFERRED "
        "FOR EACH ROW EXECUTE FUNCTION public.koinon_publication_pointer_complete()"
    )
    for function in (
        "koinon_publication_closed(jsonb,text[])",
        "koinon_publication_current(text,text)",
        "koinon_publication_target_guard()",
        "koinon_publication_header_guard()",
        "koinon_publication_private_guard()",
        "koinon_open_source_publication(text,jsonb)",
        "koinon_publication_catalog_write()",
        "koinon_publication_complete()",
        "koinon_publication_pointer_complete()",
        "koinon_publication_receipt(text,jsonb)",
        "koinon_publication_replacement_guard()",
    ):
        yield f"REVOKE ALL ON FUNCTION public.{function} FROM PUBLIC"


def install_on_create(_metadata, connection, **_kwargs):
    """Install the same guards for fresh PostgreSQL metadata test databases."""
    if connection.dialect.name != "postgresql":
        return
    required = {
        BASELINES,
        TARGETS,
        TRANSACTIONS,
        "koinon_catalog_history_identities",
        "lattice_domain_bindings",
    }
    if not required <= set(inspect(connection).get_table_names()):
        return
    if not connection.scalar(text("SELECT to_regprocedure('public.koinon_publication_target_guard()')")):
        for statement in statements():
            connection.execute(text(statement))
    from koinon.integrations.content_sources.structure_publication_guards import (
        install_on_create as install_structure,
    )

    install_structure(_metadata, connection)
