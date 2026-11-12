# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""File structural proof contract installed only by the forward structural migration."""

from sqlalchemy import inspect, text

TABLE = "koinon_content_structure_publications"

ENTRYPOINTS = (
    "koinon_begin_source_structure(text,text,text,text,integer,json)",
    "koinon_finalize_source_structure(text)",
)
READ_ENTRYPOINTS = (
    "koinon_resolve_source_publication(text,text,text,text)",
    "koinon_completed_source_structure(text,text,text)",
)

FUNCTIONS = [
    """CREATE OR REPLACE FUNCTION public.koinon_structure_hash(p_value jsonb) RETURNS text
    LANGUAGE sql IMMUTABLE SET search_path=pg_catalog AS $$
      SELECT encode(sha256(convert_to(p_value::text,'UTF8')),'hex')
    $$""",
    """CREATE OR REPLACE FUNCTION public.koinon_resolve_source_publication(
      p_tenant text,p_mapping text,p_object text,p_revision text) RETURNS jsonb
    LANGUAGE plpgsql STABLE SECURITY DEFINER SET search_path=pg_catalog AS $$
    DECLARE h public.koinon_content_publication_baselines;
      s public.koinon_content_structure_publications; a public.koinon_content_imports;
      vector jsonb;
    BEGIN
      IF p_revision ~ '^cpv1:[0-9a-f]{64}$' THEN
        SELECT * INTO h FROM public.koinon_content_publication_baselines
          WHERE tenant_id=p_tenant AND mapping_id=p_mapping AND object_id=p_object
            AND acknowledgement_sha256=substring(p_revision FROM 6);
        vector=h.acknowledgement_json->'live_vector';
      ELSIF p_revision ~ '^spv1:[0-9a-f]{64}$' THEN
        SELECT * INTO s FROM public.koinon_content_structure_publications
          WHERE proof_sha256=substring(p_revision FROM 6)
            AND tenant_id=p_tenant AND mapping_id=p_mapping AND object_id=p_object;
        IF s.id IS NULL THEN RETURN NULL; END IF;
        SELECT * INTO h FROM public.koinon_content_publication_baselines
          WHERE attempt_id=s.content_attempt_id AND tenant_id=p_tenant
            AND mapping_id=p_mapping AND object_id=p_object;
        IF h.acknowledgement_sha256 IS DISTINCT FROM s.payload_json->>'content_acknowledgement_sha256'
          THEN RETURN NULL; END IF;
        SELECT jsonb_agg(v->'pin' ORDER BY v->'pin'->>'catalog_id') INTO vector
          FROM jsonb_array_elements(s.payload_json->'after') v;
      ELSE RETURN NULL; END IF;
      IF h.attempt_id IS NULL OR h.acknowledgement_json IS NULL
        OR jsonb_typeof(vector) IS DISTINCT FROM 'array'
        OR jsonb_array_length(vector) NOT BETWEEN 2 AND 19 THEN RETURN NULL; END IF;
      SELECT * INTO a FROM public.koinon_content_imports WHERE id=h.attempt_id;
      IF a.committed_at IS NULL OR a.receipt_json IS NULL THEN RETURN NULL; END IF;
      RETURN jsonb_build_object('content_attempt_id',h.attempt_id,
        'content_acknowledgement_sha256',h.acknowledgement_sha256,
        'effective_revision',p_revision,'structure_publication_id',s.id,
        'source_id',h.source_id,'asset_id',h.asset_id,'generation',a.generation,
        'mapping_revision',a.mapping_revision,'native_receipt',h.acknowledgement_json->'native_receipt',
        'effective_vector',vector,'original_members',h.descriptor_json->'members');
    END $$""",
    """CREATE OR REPLACE FUNCTION public.koinon_structure_snapshot(p_attempt text,p_catalog text)
    RETURNS jsonb LANGUAGE sql STABLE SECURITY DEFINER SET search_path=pg_catalog AS $$
      SELECT jsonb_build_object('pin',public.koinon_publication_current(p_attempt,c.id),'name',c.name,
        'catalog_sha256',public.koinon_structure_hash(to_jsonb(c)-ARRAY[
          'name','parent_id','mutation_revision','updated_at','updated_by']),
        'bindings_sha256',public.koinon_structure_hash(coalesce((SELECT jsonb_agg(to_jsonb(b)
          ORDER BY b.id) FROM public.lattice_domain_bindings b WHERE b.catalog_id=c.id),'[]'::jsonb)))
      FROM public.lattice_catalog c WHERE c.id=p_catalog
    $$""",
    """CREATE OR REPLACE FUNCTION public.koinon_structure_states(p_attempt text,p_vector jsonb)
    RETURNS jsonb LANGUAGE sql STABLE SECURITY DEFINER SET search_path=pg_catalog AS $$
      SELECT jsonb_agg(public.koinon_structure_snapshot(p_attempt,v->>'catalog_id')
        ORDER BY v->>'catalog_id') FROM jsonb_array_elements(p_vector) v
    $$""",
    """CREATE OR REPLACE FUNCTION public.koinon_structure_descendants(p_source text)
    RETURNS jsonb LANGUAGE plpgsql STABLE SECURITY DEFINER SET search_path=pg_catalog AS $$
    DECLARE result jsonb; n integer; deepest integer;
    BEGIN
      WITH RECURSIVE tree(id,depth,path) AS (
        SELECT id,0,ARRAY[id]::text[] FROM public.lattice_catalog WHERE id=p_source
        UNION ALL SELECT c.id,t.depth+1,t.path||c.id FROM public.lattice_catalog c
          JOIN tree t ON c.parent_id=t.id WHERE t.depth<16 AND NOT c.id=ANY(t.path)
      ), bounded AS (SELECT * FROM tree LIMIT 4097)
      SELECT count(*),max(depth),jsonb_agg(jsonb_build_object('id',c.id,'revision',c.mutation_revision,
        'row_sha256',public.koinon_structure_hash(to_jsonb(c)-ARRAY['updated_at','updated_by']),
        'bindings_sha256',public.koinon_structure_hash(coalesce((SELECT jsonb_agg(to_jsonb(b)
          ORDER BY b.id) FROM public.lattice_domain_bindings b WHERE b.catalog_id=c.id),'[]'::jsonb)))
        ORDER BY c.id) INTO n,deepest,result FROM bounded t JOIN public.lattice_catalog c ON c.id=t.id;
      IF n=0 OR n>4096 OR deepest>=16 THEN
        RAISE EXCEPTION 'structural descendant bound exceeded' USING ERRCODE='23514';
      END IF;
      RETURN result;
    END $$""",
    """CREATE OR REPLACE FUNCTION public.koinon_structure_step(p_states jsonb,p_operation jsonb)
    RETURNS jsonb LANGUAGE plpgsql IMMUTABLE SET search_path=pg_catalog AS $$
    DECLARE state jsonb; result jsonb='[]'; found boolean=false;
    BEGIN
      FOR state IN SELECT value FROM jsonb_array_elements(p_states) LOOP
        IF state->'pin'->>'catalog_id'=p_operation->>'catalog_id' THEN
          found=true;
          IF p_operation->>'action'='rename' THEN
            state=jsonb_set(state,'{name}',p_operation->'fields'->'name');
          ELSE state=jsonb_set(state,'{pin,parent_id}',p_operation->'fields'->'parent_id'); END IF;
          state=jsonb_set(state,'{pin,mutation_revision}',
            to_jsonb((state->'pin'->>'mutation_revision')::bigint+1));
        END IF;
        result=result||jsonb_build_array(state);
      END LOOP;
      IF NOT found THEN RAISE EXCEPTION 'structural target is not live' USING ERRCODE='23514';
      END IF;
      RETURN result;
    END $$""",
]

FUNCTIONS.extend(
    [
        """CREATE OR REPLACE FUNCTION public.koinon_publication_predecessor(
      p public.koinon_content_publication_baselines) RETURNS jsonb
    LANGUAGE plpgsql STABLE SECURITY DEFINER SET search_path=pg_catalog AS $$
    DECLARE revision text; result jsonb;
    BEGIN
      IF p.previous_attempt_id IS NULL THEN RETURN NULL; END IF;
      IF p.previous_structure_publication_id IS NULL THEN
        SELECT 'cpv1:'||acknowledgement_sha256 INTO revision
          FROM public.koinon_content_publication_baselines WHERE attempt_id=p.previous_attempt_id;
      ELSE
        SELECT 'spv1:'||proof_sha256 INTO revision FROM public.koinon_content_structure_publications
          WHERE id=p.previous_structure_publication_id AND content_attempt_id=p.previous_attempt_id
            AND tenant_id=p.tenant_id AND mapping_id=p.mapping_id AND object_id=p.object_id;
      END IF;
      result=public.koinon_resolve_source_publication(p.tenant_id,p.mapping_id,p.object_id,revision);
      IF result->>'content_attempt_id' IS DISTINCT FROM p.previous_attempt_id THEN RETURN NULL; END IF;
      RETURN result;
    END $$""",
        """CREATE OR REPLACE FUNCTION public.koinon_structure_authority(
      p_run text,p_worker text,p_attempt integer) RETURNS jsonb
    LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
    DECLARE r public.koinon_content_sync_runs; m public.koinon_content_mappings;
      c public.koinon_content_connections; p public.koinon_content_policies;
      s public.koinon_content_sync_states; j public.lattice_jobs;
    BEGIN
      SELECT * INTO r FROM public.koinon_content_sync_runs WHERE id=p_run;
      SELECT * INTO m FROM public.koinon_content_mappings WHERE id=r.mapping_id;
      SELECT * INTO c FROM public.koinon_content_connections WHERE id=m.connection_id FOR UPDATE;
      SELECT * INTO m FROM public.koinon_content_mappings WHERE id=r.mapping_id FOR UPDATE;
      SELECT * INTO p FROM public.koinon_content_policies WHERE id=r.policy_id FOR UPDATE;
      SELECT * INTO s FROM public.koinon_content_sync_states WHERE mapping_id=m.id FOR UPDATE;
      SELECT * INTO r FROM public.koinon_content_sync_runs WHERE id=p_run FOR UPDATE;
      SELECT * INTO j FROM public.lattice_jobs WHERE id=r.job_id FOR UPDATE;
      IF r.id IS NULL OR m.id IS NULL OR c.id IS NULL OR p.id IS NULL OR s.mapping_id IS NULL
        OR j.id IS NULL OR r.status NOT IN ('running','reconciling') OR r.cancel_requested_at IS NOT NULL
        OR m.status<>'active' OR NOT s.enabled OR s.accepted_policy_id IS DISTINCT FROM p.id
        OR p.accepted_at IS NULL OR p.accepted_by IS DISTINCT FROM m.owner
        OR ROW(r.tenant_id,r.mapping_revision,r.connection_revision)
          IS DISTINCT FROM ROW(m.tenant_id,m.revision,c.revision)
        OR ROW(c.tenant_id,c.owner,c.provider,c.external_subject,c.external_tenant,
          c.issuer,c.config_fingerprint)
          IS DISTINCT FROM ROW(m.tenant_id,m.owner,m.provider,m.external_subject,m.external_tenant,
            m.issuer,m.config_fingerprint)
        OR c.status<>'connected' OR p.mapping_revision<>m.revision OR p.mapping_id<>m.id
        OR p.tenant_id<>m.tenant_id OR p.owner<>m.owner
        OR j.tenant_id<>m.tenant_id OR j.resource_id<>m.id OR j.kind<>'content.source.reconcile'
        OR j.status<>'running' OR j.worker_id IS DISTINCT FROM p_worker
        OR j.attempts IS DISTINCT FROM p_attempt OR j.lease_until IS NULL
        OR j.lease_until<=clock_timestamp() THEN
        RAISE EXCEPTION 'structural source authority is not current' USING ERRCODE='23514';
      END IF;
      RETURN jsonb_build_object('tenant_id',m.tenant_id,'owner',m.owner,'workspace_id',m.workspace_id,
        'project_id',m.project_id,'mapping_id',m.id,'mapping_revision',m.revision,
        'connection_id',c.id,'connection_revision',c.revision,'policy_id',p.id,
        'policy_revision',p.revision,'policy_sha256',p.policy_sha256,
        'authority_sha256',p.authority_sha256,'state_revision',s.revision,'run_id',r.id,
        'run_status',r.status,'run_page_sequence',r.page_sequence,'run_scan_generation',r.scan_generation,
        'job_id',j.id,'worker_id',j.worker_id,'job_attempt',j.attempts,'lease_until',j.lease_until);
    END $$""",
        """CREATE OR REPLACE FUNCTION public.koinon_structure_identity(
      p public.koinon_content_structure_publications) RETURNS jsonb
    LANGUAGE sql IMMUTABLE SET search_path=pg_catalog AS $$
      SELECT jsonb_build_object('proof_id',p.id,'effective_revision','spv1:'||p.proof_sha256,
        'content_attempt_id',p.content_attempt_id)
    $$""",
        """CREATE OR REPLACE FUNCTION public.koinon_structure_completed(
      p public.koinon_content_structure_publications) RETURNS boolean
    LANGUAGE sql STABLE SECURITY DEFINER SET search_path=pg_catalog AS $$
      SELECT EXISTS(SELECT 1 FROM public.lattice_audit a WHERE a.id=p.id
        AND a.tenant_id=p.tenant_id AND a.resource_id=p.object_id
        AND a.subject=p.payload_json->'authority'->>'owner' AND a.action='source.structure.published'
        AND a.details::jsonb=jsonb_build_object('proof_id',p.id,'proof_sha256',p.proof_sha256,
          'work_id',p.work_id,'observation_id',p.observation_id))
    $$""",
        """CREATE OR REPLACE FUNCTION public.koinon_completed_source_structure(
      p_tenant text,p_work text,p_observation text) RETURNS jsonb
    LANGUAGE sql STABLE SECURITY DEFINER SET search_path=pg_catalog AS $$
      SELECT public.koinon_structure_identity(p) FROM public.koinon_content_structure_publications p
        WHERE p.tenant_id=p_tenant AND p.work_id=p_work AND p.observation_id=p_observation
          AND public.koinon_structure_completed(p)
    $$""",
        """CREATE OR REPLACE FUNCTION public.koinon_structure_private_guard() RETURNS trigger
    LANGUAGE plpgsql SET search_path=pg_catalog AS $$
    BEGIN
      IF TG_OP='INSERT' AND current_user=pg_get_userbyid(
        (SELECT relowner FROM pg_class WHERE oid=TG_RELID))
        AND NEW.transaction_id=pg_current_xact_id()
        AND NEW.proof_sha256=public.koinon_structure_hash(NEW.payload_json)
        AND NEW.payload_json->>'schema'='koinon.source-structure-publication.v1'
        THEN RETURN NEW; END IF;
      RAISE EXCEPTION 'structural proofs are database-owned immutable evidence' USING ERRCODE='23514';
    END $$""",
        """CREATE OR REPLACE FUNCTION public.koinon_begin_source_structure(
      p_run text,p_work text,p_observation text,p_worker text,p_attempt integer,p_operations json)
    RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
    DECLARE o public.koinon_content_objects; observation public.koinon_content_sync_observations;
      w public.koinon_content_sync_work; h public.koinon_content_publication_baselines;
      m public.koinon_content_mappings; p public.koinon_content_structure_publications;
      anchor jsonb; authority jsonb; before_states jsonb; after_states jsonb; descendants jsonb;
      operation json; operations jsonb; state jsonb; item jsonb; dest public.lattice_catalog;
      body jsonb; scope jsonb; ancestors text[]; n integer; depth integer;
    BEGIN
      IF p_operations IS NULL OR octet_length(p_operations::text)>262144
        OR json_typeof(p_operations) IS DISTINCT FROM 'array'
        OR json_array_length(p_operations) NOT BETWEEN 1 AND 100 THEN
        RAISE EXCEPTION 'structural write program is not bounded' USING ERRCODE='23514';
      END IF;
      FOR operation IN SELECT value FROM json_array_elements(p_operations) LOOP
        IF json_typeof(operation) IS DISTINCT FROM 'object'
          OR (SELECT count(*) FROM json_each(operation))<>3
          OR (SELECT count(DISTINCT key) FROM json_each(operation))<>3
          OR NOT public.koinon_publication_closed(operation::jsonb,ARRAY['catalog_id','action','fields'])
          OR json_typeof(operation->'catalog_id') IS DISTINCT FROM 'string'
          OR length(operation->>'catalog_id') NOT BETWEEN 1 AND 64
          OR NOT coalesce(operation->>'action' IN ('rename','move'),false)
          OR json_typeof(operation->'fields') IS DISTINCT FROM 'object'
          OR (SELECT count(*) FROM json_each(operation->'fields'))<>1
          OR NOT public.koinon_publication_closed(operation::jsonb->'fields',
            ARRAY[CASE WHEN operation->>'action'='rename' THEN 'name' ELSE 'parent_id' END])
          OR json_typeof(operation->'fields'->CASE WHEN operation->>'action'='rename'
              THEN 'name' ELSE 'parent_id' END) IS DISTINCT FROM 'string'
          OR length(operation->'fields'->>CASE WHEN operation->>'action'='rename'
              THEN 'name' ELSE 'parent_id' END) NOT BETWEEN 1 AND
              (CASE WHEN operation->>'action'='rename' THEN 255 ELSE 64 END) THEN
          RAISE EXCEPTION 'structural write program is not closed' USING ERRCODE='23514';
      END IF;
      END LOOP;
      operations=p_operations::jsonb;
      SELECT * INTO observation FROM public.koinon_content_sync_observations WHERE id=p_observation;
      SELECT * INTO o FROM public.koinon_content_objects WHERE id=observation.object_id;
      SELECT * INTO m FROM public.koinon_content_mappings WHERE id=o.mapping_id;
      IF observation.id IS NULL OR o.id IS NULL OR m.id IS NULL THEN
        RAISE EXCEPTION 'structural observation is unavailable' USING ERRCODE='23514';
      END IF;
      PERFORM id FROM public.lattice_tenants WHERE id=o.tenant_id FOR UPDATE;
      anchor=public.koinon_resolve_source_publication(o.tenant_id,o.mapping_id,o.id,o.published_local_revision);
      IF anchor IS NULL THEN
        RAISE EXCEPTION 'structural content anchor is unavailable' USING ERRCODE='23514';
      END IF;
      SELECT * INTO h FROM public.koinon_content_publication_baselines
        WHERE attempt_id=anchor->>'content_attempt_id';
      descendants=public.koinon_structure_descendants(h.source_id);
      WITH RECURSIVE chain(id,parent_id,depth,path) AS (
        SELECT c.id,c.parent_id,0,ARRAY[c.id]::text[] FROM public.lattice_catalog c
          WHERE c.id=h.source_id OR c.id IN (
            SELECT v->'fields'->>'parent_id' FROM jsonb_array_elements(operations) v
              WHERE v->>'action'='move')
        UNION ALL SELECT c.id,c.parent_id,ancestor_node.depth+1,ancestor_node.path||c.id
          FROM public.lattice_catalog c
          JOIN chain ancestor_node ON c.id=ancestor_node.parent_id
            WHERE ancestor_node.depth<16 AND NOT c.id=ANY(ancestor_node.path))
      SELECT array_agg(DISTINCT chain.id),max(chain.depth) INTO ancestors,depth FROM chain;
      IF depth>=16 THEN
        RAISE EXCEPTION 'structural ancestry exceeds bound' USING ERRCODE='23514';
      END IF;
      PERFORM c.id FROM public.lattice_catalog c WHERE c.id=ANY(ancestors) OR c.id IN (
        SELECT v->>'id' FROM jsonb_array_elements(descendants) v
        UNION SELECT v->'fields'->>'parent_id' FROM jsonb_array_elements(operations) v
          WHERE v->>'action'='move') ORDER BY c.id FOR UPDATE;
      IF descendants IS DISTINCT FROM public.koinon_structure_descendants(h.source_id) THEN
        RAISE EXCEPTION 'structural descendants changed while locking' USING ERRCODE='23514';
      END IF;
      SELECT coalesce(jsonb_agg(jsonb_build_object('id',c.id,'row_sha256',
        public.koinon_structure_hash(to_jsonb(c))) ORDER BY c.id),'[]'::jsonb) INTO scope
        FROM public.lattice_catalog c WHERE c.id=ANY(ancestors) AND c.id<>h.source_id;
      PERFORM b.id FROM public.lattice_domain_bindings b WHERE b.catalog_id IN (
        SELECT v->>'id' FROM jsonb_array_elements(descendants) v) ORDER BY b.id FOR SHARE;
      SELECT * INTO o FROM public.koinon_content_objects WHERE id=observation.object_id FOR UPDATE;
      SELECT * INTO w FROM public.koinon_content_sync_work WHERE id=p_work FOR UPDATE;
      authority=public.koinon_structure_authority(p_run,p_worker,p_attempt);
      IF ROW(observation.tenant_id,observation.mapping_id,observation.object_id,observation.work_id,
          observation.run_id,observation.generation,observation.remote_version)
          IS DISTINCT FROM ROW(o.tenant_id,o.mapping_id,o.id,w.id,p_run,o.generation,o.remote_version)
        OR authority->>'tenant_id'<>o.tenant_id OR authority->>'mapping_id'<>o.mapping_id
        OR w.status<>'admitted' OR w.error_code IS DISTINCT FROM 'SOURCE_METADATA_PENDING'
        OR w.attempt_id IS DISTINCT FROM h.attempt_id OR o.state<>'imported'
        OR o.generation<>(anchor->>'generation')::integer
        OR o.mapping_revision<>(authority->>'mapping_revision')::integer
        OR o.published_local_revision IS DISTINCT FROM anchor->>'effective_revision'
        OR EXISTS(SELECT 1 FROM public.koinon_content_sync_observations later
          WHERE later.work_id=w.id AND later.run_id=p_run
            AND (later.page_sequence,later.item_sequence)>
              (observation.page_sequence,observation.item_sequence))
        THEN RAISE EXCEPTION 'structural observation is stale' USING ERRCODE='23514';
      END IF;
      item=observation.event_json::jsonb->'item';
      IF item->>'kind' IS DISTINCT FROM 'file' OR item->>'version' IS DISTINCT FROM o.remote_version
        OR item->>'item_id' IS DISTINCT FROM o.item_id OR jsonb_typeof(item->'name') IS DISTINCT FROM 'string'
        OR length(item->>'name') NOT BETWEEN 1 AND 255
        OR jsonb_typeof(item->'parents') IS DISTINCT FROM 'array'
        OR jsonb_array_length(item->'parents')<>1
        OR jsonb_typeof(observation.event_json::jsonb->'ancestry') IS DISTINCT FROM 'array'
        OR NOT observation.event_json::jsonb->'ancestry' @> jsonb_build_array(m.root_id) THEN
        RAISE EXCEPTION 'structural observation does not describe a scoped file' USING ERRCODE='23514';
      END IF;
      before_states=public.koinon_structure_states(h.attempt_id,anchor->'effective_vector');
      IF EXISTS(SELECT 1 FROM jsonb_array_elements(before_states) v
        WHERE v IS NULL OR v='null'::jsonb OR v->'pin' IS NULL)
        OR (SELECT jsonb_agg(v->'pin' ORDER BY v->'pin'->>'catalog_id')
          FROM jsonb_array_elements(before_states) v) IS DISTINCT FROM anchor->'effective_vector' THEN
        RAISE EXCEPTION 'structural before vector changed' USING ERRCODE='23514';
      END IF;
      after_states=before_states;
      FOR operation IN SELECT value FROM json_array_elements(p_operations) LOOP
        IF operation->>'action'='rename' THEN
          IF operation->>'catalog_id' NOT IN (h.source_id,h.asset_id)
            OR operation->'fields'->>'name' IS DISTINCT FROM item->>'name' THEN
            RAISE EXCEPTION 'structural rename differs from observed name' USING ERRCODE='23514';
      END IF;
        ELSE
          SELECT * INTO dest FROM public.lattice_catalog WHERE id=operation->'fields'->>'parent_id';
          IF operation->>'catalog_id'<>h.source_id OR dest.id IS NULL
            OR dest.kind NOT IN ('collection','corpus') OR dest.status<>'ready'
            OR ROW(dest.tenant_id,dest.workspace_id,dest.project_id)
              IS DISTINCT FROM ROW(h.tenant_id,h.workspace_id,h.project_id)
            OR EXISTS(SELECT 1 FROM jsonb_array_elements(descendants) d WHERE d->>'id'=dest.id)
            OR NOT (dest.id=m.parent_id OR EXISTS(SELECT 1 FROM public.koinon_content_folder_bindings b
              WHERE b.tenant_id=m.tenant_id AND b.mapping_id=m.id AND b.local_folder_id=dest.id
                AND b.remote_folder_id=item->'parents'->>0)) THEN
            RAISE EXCEPTION 'structural destination is not mapping-owned' USING ERRCODE='23514';
      END IF;
          WITH RECURSIVE chain(id,parent_id,depth,path) AS (
            SELECT id,parent_id,0,ARRAY[id]::text[] FROM public.lattice_catalog WHERE id=dest.id
            UNION ALL SELECT c.id,c.parent_id,ancestor_node.depth+1,ancestor_node.path||c.id
              FROM public.lattice_catalog c
              JOIN chain ancestor_node ON c.id=ancestor_node.parent_id
                WHERE ancestor_node.depth<16 AND NOT c.id=ANY(ancestor_node.path))
          SELECT array_agg(chain.id ORDER BY chain.depth),max(chain.depth) INTO ancestors,depth FROM chain;
          IF depth>=16 OR NOT h.workspace_id=ANY(ancestors) OR NOT h.project_id=ANY(ancestors) THEN
            RAISE EXCEPTION 'structural destination ancestry is invalid' USING ERRCODE='23514';
      END IF;
        END IF;
        after_states=public.koinon_structure_step(after_states,operation::jsonb);
      END LOOP;
      IF EXISTS(SELECT 1 FROM jsonb_array_elements(descendants) d WHERE NOT EXISTS(
        SELECT 1 FROM public.koinon_content_publication_baselines bh
          JOIN public.koinon_content_publication_targets bt ON bt.attempt_id=bh.attempt_id
          WHERE bh.tenant_id=h.tenant_id AND bh.object_id=h.object_id
            AND bt.catalog_id=d->>'id')) THEN
        RAISE EXCEPTION 'structural descendants include unowned entries' USING ERRCODE='23514';
      END IF;
      p.id=gen_random_uuid()::text;
      body=jsonb_build_object('schema','koinon.source-structure-publication.v1',
        'identity',jsonb_build_object('id',p.id,'tenant_id',h.tenant_id,'workspace_id',h.workspace_id,
          'project_id',h.project_id,'mapping_id',h.mapping_id,'object_id',h.object_id,
          'source_id',h.source_id,'asset_id',h.asset_id,'content_attempt_id',h.attempt_id,
          'previous_publication_id',anchor->'structure_publication_id'),
        'authority',authority,'content_acknowledgement_sha256',h.acknowledgement_sha256,
        'previous_effective_revision',anchor->>'effective_revision',
        'content',h.acknowledgement_json->'native_receipt','before',before_states,'after',after_states,
        'operations',operations,'descendants',descendants,'scope',scope,'observation',to_jsonb(observation),
        'object_before',to_jsonb(o)-'updated_at','work_before',to_jsonb(w)-'updated_at');
      IF octet_length(body::text)>262144 THEN
        RAISE EXCEPTION 'structural proof exceeds byte bound' USING ERRCODE='23514';
      END IF;
      INSERT INTO public.koinon_content_structure_publications(id,tenant_id,mapping_id,object_id,
        content_attempt_id,previous_publication_id,work_id,observation_id,transaction_id,proof_sha256,
        payload_json,created_at) VALUES(p.id,h.tenant_id,h.mapping_id,h.object_id,
          h.attempt_id,anchor->>'structure_publication_id',w.id,observation.id,pg_current_xact_id(),
          public.koinon_structure_hash(body),body,clock_timestamp()) RETURNING * INTO p;
      RETURN public.koinon_structure_identity(p);
    END $$""",
    ]
)


def _replace_once(statement: str, old: str, new: str) -> str:
    """Fail migration assembly if the frozen predecessor contract has changed."""
    if statement.count(old) != 1:
        raise RuntimeError("Frozen publication SQL no longer matches its structural upgrade")
    return statement.replace(old, new, 1)


def upgraded_publication_statements():
    """Upgrade only functions whose predecessor semantics gain structural evidence."""
    from koinon.integrations.content_sources.publication_guards import FUNCTIONS as original

    for statement in original:
        if "CREATE FUNCTION public.koinon_publication_target_guard()" in statement:
            statement = _replace_once(
                statement,
                "SELECT v INTO previous FROM public.koinon_content_publication_baselines p,\n"
                "          jsonb_array_elements(p.acknowledgement_json->'live_vector') v\n"
                "          WHERE p.attempt_id=h.previous_attempt_id AND v->>'catalog_id'=NEW.catalog_id;",
                "SELECT v INTO previous FROM jsonb_array_elements(\n"
                "          public.koinon_publication_predecessor(h)->'effective_vector') v\n"
                "          WHERE v->>'catalog_id'=NEW.catalog_id;",
            )
        elif "CREATE FUNCTION public.koinon_publication_replacement_guard()" in statement:
            statement = statement.replace(
                "prior.acknowledgement_json->'live_vector'",
                "public.koinon_publication_predecessor(h)->'effective_vector'",
            )
        elif "CREATE FUNCTION public.koinon_open_source_publication(" in statement:
            statement = _replace_once(
                statement,
                "o.published_local_revision='cpv1:'||prior.acknowledgement_sha256",
                "o.published_local_revision=public.koinon_publication_predecessor(h)->>'effective_revision'",
            )
        elif "CREATE FUNCTION public.koinon_publication_header_guard()" in statement:
            statement = _replace_once(
                statement,
                "IF i.id IS NULL OR a.content_operation_id IS NOT NULL "
                "OR NEW.previous_attempt_id IS NOT NULL",
                "IF i.id IS NULL OR a.content_operation_id IS NOT NULL "
                "OR NEW.previous_attempt_id IS NOT NULL\n"
                "            OR NEW.previous_structure_publication_id IS NOT NULL",
            )
            statement = _replace_once(
                statement,
                "o.published_local_revision='cpv1:'||prior.acknowledgement_sha256",
                "o.published_local_revision=public.koinon_publication_predecessor(NEW)->>'effective_revision'",
            )
            statement = _replace_once(
                statement,
                "'previous_acknowledgement_sha256','native','targets','members'])",
                "'previous_acknowledgement_sha256','native','targets','members'] ||\n"
                "            CASE WHEN NEW.previous_structure_publication_id IS NULL THEN ARRAY[]::text[]\n"
                "              ELSE ARRAY['previous_effective_revision','previous_structure_sha256'] END)",
            )
            statement = _replace_once(
                statement,
                "OR d->>'schema' IS DISTINCT FROM 'koinon.source-publication-descriptor.v1'",
                "OR d->>'schema' IS DISTINCT FROM (CASE WHEN NEW.previous_structure_publication_id IS NULL\n"
                "            THEN 'koinon.source-publication-descriptor.v1'\n"
                "            ELSE 'koinon.source-publication-descriptor.v2' END)\n"
                "          OR (NEW.previous_structure_publication_id IS NOT NULL AND\n"
                "            (d->>'previous_effective_revision' IS DISTINCT FROM\n"
                "              public.koinon_publication_predecessor(NEW)->>'effective_revision'\n"
                "             OR d->>'previous_structure_sha256' IS DISTINCT FROM substring(\n"
                "              public.koinon_publication_predecessor(NEW)->>'effective_revision' FROM 6)))",
            )
            statement = _replace_once(
                statement,
                "OR d->'identity' IS DISTINCT FROM (to_jsonb(NEW)-ARRAY['created_at','descriptor_json',\n"
                "            'descriptor_sha256','acknowledgement_json','acknowledgement_sha256'])",
                "OR d->'identity' IS DISTINCT FROM (to_jsonb(NEW)-(ARRAY['created_at','descriptor_json',\n"
                "            'descriptor_sha256','acknowledgement_json','acknowledgement_sha256'] ||\n"
                "            CASE WHEN NEW.previous_structure_publication_id IS NULL\n"
                "              THEN ARRAY['previous_structure_publication_id'] ELSE ARRAY[]::text[] END))",
            )
        elif "CREATE FUNCTION public.koinon_publication_pointer_complete()" in statement:
            statement = _replace_once(
                statement,
                "      IF NOT EXISTS(SELECT 1 FROM public.koinon_content_publication_baselines h",
                "      IF NEW.published_local_revision ~ '^spv1:[0-9a-f]{64}$' AND EXISTS(\n"
                "        SELECT 1 FROM public.koinon_content_structure_publications p\n"
                "        WHERE p.tenant_id=NEW.tenant_id AND p.mapping_id=NEW.mapping_id\n"
                "          AND p.object_id=NEW.id\n"
                "          AND p.transaction_id=pg_current_xact_id()\n"
                "          AND NEW.published_local_revision='spv1:'||p.proof_sha256\n"
                "          AND NEW.published_sha256=p.payload_json->'content'->>'sha256'\n"
                "          AND NEW.published_native_version_id=coalesce(\n"
                "            p.payload_json->'content'->>'source_version_id',\n"
                "            p.payload_json->'content'->>'file_version_id')\n"
                "          AND public.koinon_structure_completed(p)) THEN RETURN NULL; END IF;\n"
                "      IF NOT EXISTS(SELECT 1 FROM public.koinon_content_publication_baselines h",
            )
        else:
            continue
        yield statement.replace("CREATE FUNCTION", "CREATE OR REPLACE FUNCTION", 1)


PARTICIPANTS = (
    "koinon_content_objects",
    "koinon_content_sync_work",
    "koinon_content_sync_observations",
    "koinon_content_sync_runs",
    "lattice_jobs",
    "koinon_content_mappings",
    "koinon_content_policies",
    "koinon_content_sync_states",
    "koinon_content_connections",
    "lattice_memberships",
    "lattice_domain_bindings",
    "lattice_audit",
    "koinon_identity_grants",
    "koinon_identity_providers",
    "koinon_identity_mappings",
    "koinon_personal_tokens",
    "koinon_authorized_applications",
    "koinon_mcp_oauth_clients",
)


def statements():
    yield from FUNCTIONS
    yield """CREATE OR REPLACE FUNCTION public.koinon_content_guard_work() RETURNS trigger
    LANGUAGE plpgsql SET search_path=pg_catalog AS $$
    BEGIN
      IF TG_OP='UPDATE' AND (
        (to_jsonb(NEW)-ARRAY['status','error_code','attempt_id','updated_at']) IS DISTINCT FROM
        (to_jsonb(OLD)-ARRAY['status','error_code','attempt_id','updated_at'])
        OR (OLD.attempt_id IS NOT NULL AND OLD.attempt_id IS DISTINCT FROM NEW.attempt_id)) THEN
        RAISE EXCEPTION 'work identity and replacement baseline are immutable' USING ERRCODE='23514';
      END IF;
      IF NEW.attempt_id IS NOT NULL AND NOT EXISTS(SELECT 1 FROM public.koinon_content_imports
        WHERE id=NEW.attempt_id AND tenant_id=NEW.tenant_id AND mapping_id=NEW.mapping_id
          AND object_id=NEW.object_id AND generation=NEW.generation
          AND remote_version IS NOT DISTINCT FROM NEW.remote_version) THEN
        RAISE EXCEPTION 'work must bind its exact import' USING ERRCODE='23514';
      END IF;
      RETURN NEW;
    END $$"""
    yield """DO $$ BEGIN
      IF NOT EXISTS(SELECT 1 FROM pg_catalog.pg_trigger
        WHERE tgrelid='public.koinon_content_sync_work'::regclass AND tgname='guard_sync_work') THEN
        CREATE TRIGGER guard_sync_work BEFORE INSERT OR UPDATE ON public.koinon_content_sync_work
          FOR EACH ROW EXECUTE FUNCTION public.koinon_content_guard_work();
      END IF;
    END $$"""
    yield """CREATE OR REPLACE FUNCTION public.koinon_structure_audit_private() RETURNS trigger
      LANGUAGE plpgsql SET search_path=pg_catalog AS $$ BEGIN
        IF NEW.action='source.structure.published' AND current_user<>pg_get_userbyid(
          (SELECT relowner FROM pg_class WHERE oid=TG_RELID)) THEN
          RAISE EXCEPTION 'structural completion audit is database-owned' USING ERRCODE='23514';
      END IF;
        RETURN NEW;
      END $$"""
    yield from upgraded_publication_statements()
    yield f"REVOKE ALL ON TABLE public.{TABLE} FROM PUBLIC"
    yield (
        f"CREATE TRIGGER structure_private BEFORE INSERT OR UPDATE OR DELETE ON public.{TABLE} "
        "FOR EACH ROW EXECUTE FUNCTION public.koinon_structure_private_guard()"
    )
    yield (
        f"CREATE TRIGGER structure_private_truncate BEFORE TRUNCATE ON public.{TABLE} "
        "FOR EACH STATEMENT EXECUTE FUNCTION public.koinon_structure_private_guard()"
    )
    yield (
        f"CREATE CONSTRAINT TRIGGER structure_complete AFTER INSERT ON public.{TABLE} "
        "DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION public.koinon_structure_complete()"
    )
    yield (
        "CREATE TRIGGER zz_structure_catalog BEFORE INSERT OR UPDATE OR DELETE ON public.lattice_catalog "
        "FOR EACH ROW EXECUTE FUNCTION public.koinon_structure_catalog_write()"
    )
    yield (
        "CREATE TRIGGER structure_audit_private BEFORE INSERT ON public.lattice_audit "
        "FOR EACH ROW EXECUTE FUNCTION public.koinon_structure_audit_private()"
    )
    yield (
        "CREATE TRIGGER structure_catalog_truncate BEFORE TRUNCATE ON public.lattice_catalog "
        "FOR EACH STATEMENT EXECUTE FUNCTION public.koinon_structure_state_guard()"
    )
    for table in PARTICIPANTS:
        yield (
            f"CREATE TRIGGER structure_participant BEFORE INSERT OR UPDATE OR DELETE ON public.{table} "
            "FOR EACH ROW EXECUTE FUNCTION public.koinon_structure_state_guard()"
        )
        yield (
            f"CREATE TRIGGER structure_participant_truncate BEFORE TRUNCATE ON public.{table} "
            "FOR EACH STATEMENT EXECUTE FUNCTION public.koinon_structure_state_guard()"
        )
    for signature in ALL_SIGNATURES:
        yield f"REVOKE ALL ON FUNCTION public.{signature} FROM PUBLIC"


ALL_SIGNATURES = (
    *ENTRYPOINTS,
    *READ_ENTRYPOINTS,
    "koinon_structure_hash(jsonb)",
    "koinon_structure_snapshot(text,text)",
    "koinon_structure_states(text,jsonb)",
    "koinon_structure_descendants(text)",
    "koinon_structure_step(jsonb,jsonb)",
    "koinon_publication_predecessor(public.koinon_content_publication_baselines)",
    "koinon_structure_authority(text,text,integer)",
    "koinon_structure_identity(public.koinon_content_structure_publications)",
    "koinon_structure_completed(public.koinon_content_structure_publications)",
    "koinon_structure_private_guard()",
    "koinon_structure_catalog_write()",
    "koinon_structure_state_guard()",
    "koinon_structure_audit_private()",
    "koinon_structure_validate_completion(public.koinon_content_structure_publications,boolean)",
    "koinon_structure_complete()",
    "koinon_structure_validate_descendants(public.koinon_content_structure_publications)",
)


def install_on_create(_metadata, connection, **_kwargs):
    if connection.dialect.name != "postgresql":
        return
    if not {TABLE, *PARTICIPANTS, "koinon_content_publication_baselines"} <= set(
        inspect(connection).get_table_names()
    ):
        return
    if connection.scalar(text("SELECT to_regprocedure('public.koinon_structure_complete()')")):
        return
    for statement in statements():
        connection.execute(text(statement))


FUNCTIONS.extend(
    [
        """CREATE OR REPLACE FUNCTION public.koinon_structure_catalog_write() RETURNS trigger
    LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
    DECLARE p public.koinon_content_structure_publications; actual jsonb; expected jsonb;
      step jsonb; n integer; idx integer; oldrow jsonb; newrow jsonb; touches boolean;
    BEGIN
      FOR p IN SELECT * FROM public.koinon_content_structure_publications
        WHERE transaction_id=pg_current_xact_id() LOOP
        IF EXISTS(SELECT 1 FROM jsonb_array_elements(p.payload_json->'scope') s
          WHERE s->>'id'=CASE WHEN TG_OP<>'INSERT' THEN OLD.id ELSE NEW.id END) THEN
          RAISE EXCEPTION 'structural destination ancestry is frozen' USING ERRCODE='23514';
      END IF;
        touches=EXISTS(SELECT 1 FROM jsonb_array_elements(p.payload_json->'descendants') d
          WHERE d->>'id' IN (CASE WHEN TG_OP<>'INSERT' THEN OLD.id END,
            CASE WHEN TG_OP<>'DELETE' THEN NEW.id END,
            CASE WHEN TG_OP<>'DELETE' THEN NEW.parent_id END));
        IF NOT touches THEN CONTINUE; END IF;
        IF public.koinon_structure_completed(p) OR TG_OP<>'UPDATE' THEN
          RAISE EXCEPTION 'structural catalog set is frozen' USING ERRCODE='23514';
      END IF;
        PERFORM public.koinon_structure_validate_descendants(p);
        actual=public.koinon_structure_states(p.content_attempt_id,
          (SELECT jsonb_agg(v->'pin') FROM jsonb_array_elements(p.payload_json->'before') v));
        SELECT sum((v->'pin'->>'mutation_revision')::bigint-
          (b->'pin'->>'mutation_revision')::bigint)::integer INTO n
          FROM jsonb_array_elements(actual) v JOIN jsonb_array_elements(p.payload_json->'before') b
            ON v->'pin'->>'catalog_id'=b->'pin'->>'catalog_id';
        IF n IS NULL OR n<0 OR n>=jsonb_array_length(p.payload_json->'operations') THEN
          RAISE EXCEPTION 'structural write count is invalid' USING ERRCODE='23514';
      END IF;
        expected=p.payload_json->'before';
        FOR idx IN 0..n-1 LOOP
          expected=public.koinon_structure_step(expected,p.payload_json->'operations'->idx);
        END LOOP;
        step=p.payload_json->'operations'->n;
        IF actual IS DISTINCT FROM expected OR OLD.id IS DISTINCT FROM step->>'catalog_id'
          OR NEW.mutation_revision IS DISTINCT FROM OLD.mutation_revision+1 THEN
          RAISE EXCEPTION 'structural write does not extend exact global prefix' USING ERRCODE='23514';
      END IF;
        oldrow=to_jsonb(OLD)-ARRAY['mutation_revision','updated_at','updated_by'];
        newrow=to_jsonb(NEW)-ARRAY['mutation_revision','updated_at','updated_by'];
        IF step->>'action'='rename' THEN oldrow=jsonb_set(oldrow,'{name}',step->'fields'->'name');
        ELSE oldrow=jsonb_set(oldrow,'{parent_id}',step->'fields'->'parent_id'); END IF;
        IF newrow IS DISTINCT FROM oldrow OR NEW.updated_by IS DISTINCT FROM
            p.payload_json->'authority'->>'owner'
          OR NEW.updated_at<OLD.updated_at OR NEW.updated_at>clock_timestamp() THEN
          RAISE EXCEPTION 'structural write changes unplanned fields' USING ERRCODE='23514';
      END IF;
      END LOOP;
      IF TG_OP='DELETE' THEN RETURN OLD; ELSE RETURN NEW; END IF;
    END $$""",
        """CREATE OR REPLACE FUNCTION public.koinon_structure_state_guard() RETURNS trigger
    LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
    DECLARE p public.koinon_content_structure_publications; oldrow jsonb; newrow jsonb;
      rowvalue jsonb; touches boolean; rowtenant text;
    BEGIN
      IF TG_OP='TRUNCATE' THEN
        IF EXISTS(SELECT 1 FROM public.koinon_content_structure_publications
          WHERE transaction_id=pg_current_xact_id()) THEN
          RAISE EXCEPTION 'structural participating tables cannot truncate' USING ERRCODE='23514';
      END IF;
        RETURN NULL;
      END IF;
      IF TG_OP<>'INSERT' THEN oldrow=to_jsonb(OLD); END IF;
      IF TG_OP<>'DELETE' THEN newrow=to_jsonb(NEW); END IF;
      FOR p IN SELECT * FROM public.koinon_content_structure_publications
        WHERE transaction_id=pg_current_xact_id() LOOP
        touches=false;
        FOR rowvalue IN SELECT oldrow UNION SELECT newrow LOOP
          IF rowvalue IS NULL THEN CONTINUE; END IF;
          touches=touches OR CASE TG_TABLE_NAME
            WHEN 'koinon_content_objects' THEN rowvalue->>'id'=p.object_id
            WHEN 'koinon_content_sync_work' THEN rowvalue->>'id'=p.work_id
            WHEN 'koinon_content_sync_observations' THEN rowvalue->>'work_id'=p.work_id
            WHEN 'koinon_content_sync_runs' THEN rowvalue->>'id'=p.payload_json->'authority'->>'run_id'
            WHEN 'lattice_jobs' THEN rowvalue->>'id'=p.payload_json->'authority'->>'job_id'
            WHEN 'koinon_content_mappings' THEN rowvalue->>'id'=p.mapping_id
            WHEN 'koinon_content_policies' THEN rowvalue->>'id'=p.payload_json->'authority'->>'policy_id'
            WHEN 'koinon_content_sync_states' THEN rowvalue->>'mapping_id'=p.mapping_id
            WHEN 'koinon_content_connections' THEN
              rowvalue->>'id'=p.payload_json->'authority'->>'connection_id'
            WHEN 'lattice_memberships' THEN rowvalue->>'tenant_id'=p.tenant_id
              AND rowvalue->>'subject'=p.payload_json->'authority'->>'owner'
            WHEN 'koinon_identity_grants' THEN rowvalue->>'tenant_id'=p.tenant_id
              AND rowvalue->>'subject'=p.payload_json->'authority'->>'owner'
            WHEN 'koinon_identity_providers' THEN rowvalue->>'tenant_id'=p.tenant_id
            WHEN 'koinon_identity_mappings' THEN rowvalue->>'tenant_id'=p.tenant_id
            WHEN 'koinon_personal_tokens' THEN rowvalue->>'tenant_id'=p.tenant_id
              AND rowvalue->>'subject'=p.payload_json->'authority'->>'owner'
            WHEN 'koinon_authorized_applications' THEN rowvalue->>'tenant_id'=p.tenant_id
              AND rowvalue->>'subject'=p.payload_json->'authority'->>'owner'
            WHEN 'koinon_mcp_oauth_clients' THEN rowvalue->>'tenant_id'=p.tenant_id
            WHEN 'lattice_domain_bindings' THEN EXISTS(
              SELECT 1 FROM jsonb_array_elements(p.payload_json->'descendants') d
              WHERE d->>'id'=rowvalue->>'catalog_id')
            WHEN 'lattice_audit' THEN rowvalue->>'id'=p.id
              OR (rowvalue->>'action'='source.structure.published' AND rowvalue->>'resource_id'=p.object_id)
            ELSE false END;
        END LOOP;
        IF NOT touches THEN CONTINUE; END IF;
        IF public.koinon_structure_completed(p) THEN
          RAISE EXCEPTION 'structural finalization forbids later participant mutation' USING ERRCODE='23514';
      END IF;
        IF TG_TABLE_NAME='lattice_domain_bindings' OR TG_OP='DELETE' THEN
          RAISE EXCEPTION 'structural publication preserves bindings and participants' USING ERRCODE='23514';
      END IF;
        IF TG_TABLE_NAME='lattice_audit' AND (
          TG_OP<>'INSERT' OR current_user<>pg_get_userbyid(
            (SELECT relowner FROM pg_class WHERE oid=TG_RELID))
          OR newrow->>'id'<>p.id OR newrow->>'tenant_id'<>p.tenant_id
          OR newrow->>'subject'<>p.payload_json->'authority'->>'owner'
          OR newrow->>'resource_id'<>p.object_id OR newrow->>'action'<>'source.structure.published'
          OR newrow->'details' IS DISTINCT FROM jsonb_build_object('proof_id',p.id,
            'proof_sha256',p.proof_sha256,'work_id',p.work_id,'observation_id',p.observation_id)) THEN
          RAISE EXCEPTION 'structural completion audit is database-owned' USING ERRCODE='23514';
      END IF;
      END LOOP;
      IF TG_OP='DELETE' THEN RETURN OLD; ELSE RETURN NEW; END IF;
    END $$""",
        """CREATE OR REPLACE FUNCTION public.koinon_structure_validate_descendants(
      p public.koinon_content_structure_publications) RETURNS void
    LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
    DECLARE descendants jsonb;
    BEGIN
      descendants=public.koinon_structure_descendants(
        (SELECT source_id FROM public.koinon_content_publication_baselines
          WHERE attempt_id=p.content_attempt_id));
      IF (SELECT jsonb_agg(v->'id' ORDER BY v->>'id') FROM jsonb_array_elements(descendants) v)
          IS DISTINCT FROM (SELECT jsonb_agg(v->'id' ORDER BY v->>'id')
            FROM jsonb_array_elements(p.payload_json->'descendants') v)
        OR EXISTS(SELECT 1 FROM jsonb_array_elements(descendants) current_d
          JOIN jsonb_array_elements(p.payload_json->'descendants') previous_d
            ON current_d->>'id'=previous_d->>'id'
          WHERE NOT EXISTS(SELECT 1 FROM jsonb_array_elements(p.payload_json->'after') pin
            WHERE pin->'pin'->>'catalog_id'=current_d->>'id') AND current_d IS DISTINCT FROM previous_d) THEN
        RAISE EXCEPTION 'structural descendants changed' USING ERRCODE='23514';
      END IF;
      IF EXISTS(SELECT 1 FROM jsonb_array_elements(p.payload_json->'scope') s
        LEFT JOIN public.lattice_catalog c ON c.id=s->>'id'
        WHERE c.id IS NULL OR public.koinon_structure_hash(to_jsonb(c))
          IS DISTINCT FROM s->>'row_sha256') THEN
        RAISE EXCEPTION 'structural destination ancestry changed' USING ERRCODE='23514';
      END IF;
    END $$""",
        """CREATE OR REPLACE FUNCTION public.koinon_structure_validate_completion(
      p public.koinon_content_structure_publications,p_require_audit boolean) RETURNS void
    LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
    DECLARE actual jsonb; expected jsonb;
      o public.koinon_content_objects; w public.koinon_content_sync_work; item jsonb;
    BEGIN
      actual=public.koinon_structure_states(p.content_attempt_id,
        (SELECT jsonb_agg(v->'pin') FROM jsonb_array_elements(p.payload_json->'after') v));
      IF actual IS DISTINCT FROM p.payload_json->'after' THEN
        RAISE EXCEPTION 'structural transition is incomplete' USING ERRCODE='23514';
      END IF;
      PERFORM public.koinon_structure_validate_descendants(p);
      SELECT * INTO o FROM public.koinon_content_objects WHERE id=p.object_id;
      SELECT * INTO w FROM public.koinon_content_sync_work WHERE id=p.work_id;
      item=p.payload_json->'observation'->'event_json'->'item';
      expected=(p.payload_json->'object_before')||jsonb_build_object(
        'state','imported','remote_name',item->'name','remote_kind',item->'kind',
        'remote_parent_id',item->'parents'->0,
        'remote_ancestry_json',p.payload_json->'observation'->'event_json'->'ancestry',
        'published_local_revision','spv1:'||p.proof_sha256);
      IF (to_jsonb(o)-'updated_at') IS DISTINCT FROM expected
        OR (to_jsonb(w)-'updated_at') IS DISTINCT FROM
          ((p.payload_json->'work_before')||jsonb_build_object('status','imported','error_code',NULL))
        OR (p_require_audit AND NOT public.koinon_structure_completed(p)) THEN
        RAISE EXCEPTION 'structural completion state is incomplete' USING ERRCODE='23514';
      END IF;
    END $$""",
        """CREATE OR REPLACE FUNCTION public.koinon_finalize_source_structure(p_id text) RETURNS jsonb
    LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
    DECLARE p public.koinon_content_structure_publications; authority jsonb; item jsonb;
    BEGIN
      SELECT * INTO p FROM public.koinon_content_structure_publications WHERE id=p_id;
      IF p.id IS NULL OR p.transaction_id<>pg_current_xact_id() THEN
        RAISE EXCEPTION 'structural finalization requires its creation transaction' USING ERRCODE='23514';
      END IF;
      IF public.koinon_structure_completed(p) THEN
        PERFORM public.koinon_structure_validate_completion(p,true);
        RETURN public.koinon_structure_identity(p);
      END IF;
      authority=public.koinon_structure_authority(p.payload_json->'authority'->>'run_id',
        p.payload_json->'authority'->>'worker_id',(p.payload_json->'authority'->>'job_attempt')::integer);
      IF authority IS DISTINCT FROM p.payload_json->'authority' THEN
        RAISE EXCEPTION 'structural authority changed before finalization' USING ERRCODE='23514';
      END IF;
      IF EXISTS(SELECT 1 FROM public.koinon_content_sync_observations later
        WHERE later.work_id=p.work_id AND later.run_id=authority->>'run_id'
          AND (later.page_sequence,later.item_sequence)>(
            (p.payload_json->'observation'->>'page_sequence')::integer,
            (p.payload_json->'observation'->>'item_sequence')::integer)) THEN
        RAISE EXCEPTION 'structural observation changed before finalization' USING ERRCODE='23514';
      END IF;
      IF NOT EXISTS(SELECT 1 FROM public.koinon_content_objects o WHERE o.id=p.object_id
          AND (to_jsonb(o)-'updated_at')=p.payload_json->'object_before')
        OR NOT EXISTS(SELECT 1 FROM public.koinon_content_sync_work w WHERE w.id=p.work_id
          AND (to_jsonb(w)-'updated_at')=p.payload_json->'work_before') THEN
        RAISE EXCEPTION 'structural completion source changed' USING ERRCODE='23514';
      END IF;
      item=p.payload_json->'observation'->'event_json'->'item';
      UPDATE public.koinon_content_objects SET state='imported',remote_name=item->>'name',
        remote_kind=item->>'kind',remote_parent_id=item->'parents'->>0,
        remote_ancestry_json=(p.payload_json->'observation'->'event_json'->'ancestry')::json,
        published_local_revision='spv1:'||p.proof_sha256,updated_at=clock_timestamp()
        WHERE id=p.object_id;
      UPDATE public.koinon_content_sync_work SET status='imported',error_code=NULL,
        updated_at=clock_timestamp() WHERE id=p.work_id;
      PERFORM public.koinon_structure_validate_completion(p,false);
      INSERT INTO public.lattice_audit(id,tenant_id,subject,action,resource_id,details,created_at)
        VALUES(p.id,p.tenant_id,p.payload_json->'authority'->>'owner','source.structure.published',
          p.object_id,jsonb_build_object('proof_id',p.id,'proof_sha256',p.proof_sha256,
          'work_id',p.work_id,'observation_id',p.observation_id),clock_timestamp());
      PERFORM public.koinon_structure_validate_completion(p,true);
      RETURN public.koinon_structure_identity(p);
    END $$""",
        """CREATE OR REPLACE FUNCTION public.koinon_structure_complete() RETURNS trigger
    LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
    DECLARE p public.koinon_content_structure_publications;
    BEGIN
      SELECT * INTO p FROM public.koinon_content_structure_publications WHERE id=NEW.id;
      PERFORM public.koinon_structure_validate_completion(p,true);
      RETURN NULL;
    END $$""",
    ]
)
