# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""PostgreSQL derived identity attestations and restricted writer boundaries.

SQL fingerprints preserve stored JSON text. They deliberately do not implement
the Python canonical verifier. EXECUTE possession is a trusted process boundary.
"""

OWNER = "koinon_release_proof_owner"
TABLE_NAMES = (
    "koinon_answer_release_proofs",
    "koinon_answer_release_proof_pins",
    "koinon_answer_release_proof_sources",
    "koinon_answer_release_projection_jobs",
)

HASH_SQL = r"""
CREATE OR REPLACE FUNCTION public.koinon_release_native_hash(domain text, fields jsonb)
RETURNS text LANGUAGE sql IMMUTABLE STRICT PARALLEL SAFE
SET search_path=pg_catalog,public AS $$
 SELECT
  encode(sha256(convert_to(jsonb_build_array('release-proof-v1',domain,fields)::text,'UTF8')),'hex')
$$
"""

SOURCE_SQL = r"""
CREATE OR REPLACE FUNCTION public.koinon_release_source_identity(s jsonb)
RETURNS jsonb LANGUAGE sql IMMUTABLE STRICT PARALLEL SAFE
SET search_path=pg_catalog,public AS $$
 SELECT jsonb_build_object(
  'source_reference_id',s->'id','kind',s->'kind','asset_id',s->'asset_id',
  'source_id',s->'source_id','source_version_id',s->'source_version_id',
  'extraction_id',s->'extraction_id','source_part_id',s->'source_part_id',
  'source_part_sha256',s->'source_part_sha256','used_revision',s->'used_revision',
  'recorded_page',s->'recorded_page','page_basis',s->'page_basis',
  'knowledge_item_id',s->'knowledge_item_id','knowledge_version_id',s->'knowledge_version_id',
  'knowledge_version',s->'knowledge_version','snapshot_id',s->'snapshot_id')
$$
"""

CAPTURE_SQL = r"""
CREATE OR REPLACE FUNCTION public.koinon_capture_release_proof(release_id text)
RETURNS jsonb LANGUAGE plpgsql STABLE SECURITY DEFINER
SET search_path=pg_catalog,public AS $$
DECLARE
 r public.koinon_chat_tool_results%ROWTYPE;
 u public.koinon_chat_runs%ROWTYPE;
 m public.koinon_chat_messages%ROWTYPE;
 t public.koinon_chat_threads%ROWTYPE;
 g record; p record; s record; occurrence record;
 receipt jsonb; pin jsonb; ref jsonb; manifest jsonb; identity jsonb;
 pins jsonb := '[]'; sources jsonb := '[]'; supports jsonb;
 selector jsonb; header jsonb; state jsonb; reset_at bigint; has_reset boolean;
 generation_id text; generation_seq bigint; generation_at timestamptz;
 complete boolean := true; n bigint; byte_count bigint; supported boolean;
BEGIN
 SELECT * INTO r FROM public.koinon_chat_tool_results WHERE id=release_id AND kind='answer_release';
 IF NOT FOUND THEN RETURN NULL; END IF;
 SELECT * INTO u FROM public.koinon_chat_runs WHERE id=r.run_id;
 SELECT * INTO t FROM public.koinon_chat_threads WHERE id=u.thread_id;
 SELECT * INTO m FROM public.koinon_chat_messages WHERE id=u.message_id;
 IF t.tenant_id IS DISTINCT FROM u.tenant_id OR m.thread_id IS DISTINCT FROM t.id OR m.role<>'assistant'
 OR NOT EXISTS (SELECT FROM public.koinon_chat_messages WHERE id=u.user_message_id AND thread_id=t.id AND
  role='user')
 THEN RETURN NULL; END IF;
 SELECT count(*) INTO n FROM (SELECT id FROM public.koinon_chat_tool_results WHERE run_id=u.id LIMIT
  2001) bounded;
 IF n>2000 THEN RAISE EXCEPTION 'result identity bound' USING ERRCODE='P5501'; END IF;
 SELECT count(*) INTO n FROM (SELECT id FROM public.koinon_chat_events WHERE run_id=u.id LIMIT 10001)
  bounded;
 IF n>10000 THEN RAISE EXCEPTION 'event identity bound' USING ERRCODE='P5501'; END IF;
 -- Size is measured without transferring or parsing protected values in Python.
 SELECT coalesce(sum(octet_length(payload::text)),0) INTO byte_count
 FROM public.koinon_chat_tool_results WHERE run_id=u.id;
 byte_count := byte_count + octet_length(coalesce(m.text,''))
   + octet_length(coalesce(m.citations::text,'')) + octet_length(coalesce(m.artifacts::text,''))
   + octet_length(coalesce(m.answer_policy::text,''));
 IF byte_count>16777216 THEN RAISE EXCEPTION 'protected byte bound' USING ERRCODE='P5501'; END IF;
 receipt := r.payload::jsonb->'release';
 IF jsonb_typeof(receipt)<>'object' OR receipt->>'run_id' IS DISTINCT FROM u.id
 OR receipt->>'message_id' IS DISTINCT FROM m.id OR receipt->>'tenant_id' IS DISTINCT FROM t.tenant_id
 OR receipt->>'policy_version' NOT IN ('knowledge-only-v1','knowledge-only-v2')
 OR receipt->>'outcome' NOT IN ('grounded','refused','review_required','product_help')
 OR (r.payload->>'seal_sha256') !~ '^[a-f0-9]{64}$'
 OR jsonb_typeof(receipt->'result_pins')<>'array' OR jsonb_typeof(receipt->'source_refs')<>'array'
 THEN RETURN NULL; END IF;
 IF jsonb_array_length(receipt->'result_pins')>100 OR jsonb_array_length(receipt->'source_refs')>500
 THEN RAISE EXCEPTION 'receipt identity bound' USING ERRCODE='P5501'; END IF;
 SELECT max(sequence),count(*)>0 INTO reset_at,has_reset FROM public.koinon_chat_events
 WHERE run_id=u.id AND type='message_reset';
 reset_at:=coalesce(reset_at,0);
 IF (r.payload->>'reset_sequence')::bigint IS DISTINCT FROM reset_at
 OR (receipt->>'publication_sequence')::bigint<=reset_at THEN RETURN NULL; END IF;
 SELECT id,(payload->'generation'->>'start_sequence')::bigint AS seq,created_at INTO g
 FROM public.koinon_chat_tool_results WHERE run_id=u.id AND kind='generation'
 AND (NOT has_reset OR (payload->'generation'->>'start_sequence')::bigint>=reset_at)
 ORDER BY (payload->'generation'->>'start_sequence')::bigint DESC,created_at DESC LIMIT 1;
 IF FOUND THEN
  generation_id:=g.id; generation_seq:=g.seq; generation_at:=g.created_at;
  SELECT count(*) INTO n FROM public.koinon_chat_tool_results WHERE run_id=u.id AND kind='generation'
   AND (payload->'generation'->>'start_sequence')::bigint=g.seq AND created_at=g.created_at;
  IF n<>1 THEN RAISE EXCEPTION 'ambiguous generation selector' USING ERRCODE='P5502'; END IF;
 END IF;
 IF receipt->>'generation_id' IS DISTINCT FROM generation_id
 OR r.payload->>'generation_id' IS DISTINCT FROM generation_id THEN RETURN NULL; END IF;
 IF jsonb_typeof(coalesce(m.artifacts::jsonb,'[]'))<>'array' THEN RETURN NULL; END IF;
 SELECT jsonb_build_array(reset_at,generation_id,generation_seq,generation_at,
    coalesce((SELECT jsonb_agg(jsonb_build_array(a->>'id',a->>'run_id') ORDER BY a->>'id',a->>'run_id')
       FROM jsonb_array_elements(coalesce(m.artifacts::jsonb,'[]')) a),'[]'),
    coalesce(jsonb_agg(jsonb_build_array(id,kind,payload->>'generation_id',
      CASE WHEN kind='generation' THEN payload->'generation'->>'start_sequence' END,
      CASE WHEN kind='generation' THEN created_at END) ORDER BY id),'[]')) INTO selector
 FROM public.koinon_chat_tool_results WHERE run_id=u.id;
 FOR pin IN SELECT value FROM jsonb_array_elements(receipt->'result_pins') ORDER BY value->>'id' LOOP
  IF NOT (pin->>'sha256' ~ '^[a-f0-9]{64}$') OR length(pin->>'id') NOT BETWEEN 1 AND 64
   OR EXISTS (SELECT FROM jsonb_array_elements(pins) x WHERE x->>'result_id'=pin->>'id') THEN RETURN
  NULL; END IF;
  SELECT * INTO p FROM public.koinon_chat_tool_results WHERE id=pin->>'id' AND run_id=u.id;
  IF NOT FOUND OR p.kind='answer_release' THEN RETURN NULL; END IF;
  IF has_reset AND NOT (
    EXISTS(SELECT FROM jsonb_array_elements(coalesce(m.artifacts::jsonb,'[]')) a WHERE a->>'id'=p.id AND
  a->>'run_id'=u.id)
    OR generation_id IS NOT NULL AND (p.id=generation_id OR p.payload->>'generation_id'=generation_id)
  ) THEN RETURN NULL; END IF;
  pins:=pins||jsonb_build_array(jsonb_build_object('result_id',p.id,'result_kind',p.kind,
   'canonical_sha256',pin->>'sha256','native_sha256',public.koinon_release_native_hash('pin',
      jsonb_build_array(p.id,p.run_id,p.kind,p.payload::text))));
 END LOOP;
 FOR ref IN SELECT value FROM jsonb_array_elements(receipt->'source_refs') ORDER BY value->>'id' LOOP
  identity:=public.koinon_release_source_identity(ref); supports:='[]'; supported:=false;
  IF EXISTS(SELECT FROM jsonb_array_elements(sources) x WHERE x->>'source_reference_id'=ref->>'id')
   THEN RETURN NULL; END IF;
  FOR p IN SELECT tr.* FROM public.koinon_chat_tool_results tr
     JOIN jsonb_array_elements(pins) x ON x->>'result_id'=tr.id WHERE tr.kind<>'attachment' ORDER BY
  tr.id LOOP
   manifest:=p.payload::jsonb->'source_manifest';
   IF manifest->>'version'='1' AND manifest->'complete'='true'::jsonb
      AND jsonb_typeof(manifest->'sources')='array' THEN
    IF jsonb_array_length(manifest->'sources')>500 THEN RAISE EXCEPTION 'manifest identity bound' USING
  ERRCODE='P5501'; END IF;
    IF jsonb_typeof(p.payload::jsonb->'asset_ids') IS DISTINCT FROM 'array' THEN
      RAISE EXCEPTION 'manifest scope is missing' USING ERRCODE='P5503'; END IF;
    IF (SELECT coalesce(jsonb_agg(a ORDER BY a),'[]') FROM
        (SELECT DISTINCT value AS a FROM jsonb_array_elements(p.payload::jsonb->'asset_ids')) assets)
      IS DISTINCT FROM
       (SELECT coalesce(jsonb_agg(a ORDER BY a),'[]') FROM
        (SELECT DISTINCT value->'asset_id' AS a FROM jsonb_array_elements(manifest->'sources')) assets)
    THEN RAISE EXCEPTION 'manifest source scope conflict' USING ERRCODE='P5503'; END IF;
    FOR occurrence IN SELECT value FROM jsonb_array_elements(manifest->'sources')
       WHERE value->>'id'=ref->>'id' LOOP
     IF public.koinon_release_source_identity(occurrence.value) IS DISTINCT FROM identity THEN
      RAISE EXCEPTION 'conflicting source identity' USING ERRCODE='P5503'; END IF;
     supported:=true;
     IF NOT supports ? p.id THEN supports:=supports||jsonb_build_array(p.id); END IF;
    END LOOP;
   END IF;
  END LOOP;
  IF NOT supported THEN complete:=false; CONTINUE; END IF;
  IF ref->>'kind' NOT IN ('document','dataset','knowledge_version')
   OR length(ref->>'id') NOT BETWEEN 1 AND 64 OR length(ref->>'asset_id') NOT BETWEEN 1 AND 64
   THEN RETURN NULL; END IF;
  IF ref->>'kind'='document' AND (
    coalesce(ref->>'source_version_id','')='' OR coalesce(ref->>'extraction_id','')=''
    OR coalesce(ref->>'source_part_id','')='' OR NOT coalesce(ref->>'source_part_sha256','') ~
  '^[a-f0-9]{64}$'
    OR ref->>'page_basis' IS DISTINCT FROM 'recorded_loader'
    OR ref->>'used_revision' IS DISTINCT FROM 'source-part-sha256:'||(ref->>'source_part_sha256')
  ) THEN complete:=false; CONTINUE; END IF;
  sources:=sources||jsonb_build_array(identity||jsonb_build_object('supporting_result_ids',supports));
 END LOOP;
 header:=jsonb_build_object(
 'release_result_id',r.id,'projection_version',1,'tenant_id',t.tenant_id,'thread_id',t.id,
 'owner_subject',t.subject,'run_id',u.id,'message_id',m.id,'user_message_id',u.user_message_id,
 'generation_id',generation_id,'generation_start_sequence',generation_seq,'generation_created_at',generation_at,
 'reset_sequence',reset_at,'publication_sequence',(receipt->>'publication_sequence')::bigint,
 'policy_version',receipt->>'policy_version','outcome',receipt->>'outcome','canonical_seal_sha256',r.payload->>'seal_sha256',
 'release_native_sha256',public.koinon_release_native_hash('release',jsonb_build_array(r.id,r.run_id,r.kind,r.payload::text)),
 'message_native_sha256',public.koinon_release_native_hash('message',jsonb_build_array(m.id,m.thread_id,m.role,m.text,m.citations::text,m.artifacts::text,m.answer_policy::text)),
 'selection_native_sha256',public.koinon_release_native_hash('selection',jsonb_build_array(u.reader_source_selection::text)),
 'active_selector_sha256',public.koinon_release_native_hash('selector',selector),
 'pin_count',jsonb_array_length(pins),'source_count',jsonb_array_length(sources),'provenance_complete',complete);
 state:=jsonb_build_object('header',header,'pins',pins,'sources',sources);
 IF octet_length(state::text)>4194304 THEN RAISE EXCEPTION 'projection identity byte bound' USING
  ERRCODE='P5501'; END IF;
 RETURN state||jsonb_build_object('state_sha256',public.koinon_release_native_hash('state',state));
EXCEPTION WHEN invalid_text_representation OR numeric_value_out_of_range OR invalid_parameter_value THEN
 RETURN NULL;
END $$
"""

INSERT_GUARD_SQL = r"""
CREATE OR REPLACE FUNCTION public.koinon_release_proof_immutable()
RETURNS trigger LANGUAGE plpgsql SECURITY INVOKER
SET search_path=pg_catalog,public AS $$
BEGIN
 IF TG_OP<>'INSERT' OR current_user<>'koinon_release_proof_owner' THEN
  RAISE EXCEPTION 'answer release proofs are immutable and privately published' USING ERRCODE='42501';
 END IF;
 IF TG_TABLE_NAME<>'koinon_answer_release_proofs' AND NOT EXISTS (
   SELECT FROM public.koinon_answer_release_proofs
   WHERE release_result_id=NEW.release_result_id AND projection_version=NEW.projection_version
    AND xmin::text=pg_current_xact_id()::text
 ) THEN RAISE EXCEPTION 'proof children must be inserted with their new header' USING ERRCODE='42501';
  END IF;
 RETURN NEW;
END $$
"""

EXACT_SET_SQL = r"""
CREATE OR REPLACE FUNCTION public.koinon_release_proof_exact_set()
RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER
SET search_path=pg_catalog,public AS $$
DECLARE current_state jsonb; pins jsonb; sources jsonb; header jsonb; field text;
BEGIN
 current_state:=public.koinon_capture_release_proof(NEW.release_result_id);
 header:=to_jsonb(NEW)-ARRAY['state_sha256','verifier','writer_kind','worker_id','attempt','maintenance_claim_id','created_at'];
 FOREACH field IN ARRAY ARRAY['canonical_seal_sha256','release_native_sha256',
   'message_native_sha256','selection_native_sha256','active_selector_sha256'] LOOP
  header:=jsonb_set(header,ARRAY[field],to_jsonb(substring(header->>field FROM 3)));
 END LOOP;
 SELECT coalesce(jsonb_agg(jsonb_build_object('result_id',p.result_id,'result_kind',p.result_kind,
   'canonical_sha256',encode(p.canonical_sha256,'hex'),'native_sha256',encode(p.native_sha256,'hex'))
   ORDER BY p.result_id),'[]') INTO pins
 FROM public.koinon_answer_release_proof_pins p
 WHERE release_result_id=NEW.release_result_id AND projection_version=NEW.projection_version;
 SELECT coalesce(jsonb_agg((to_jsonb(s)-'release_result_id'-'projection_version'-'source_part_sha256')||
   jsonb_build_object('source_part_sha256',encode(s.source_part_sha256,'hex')) ORDER BY
  s.source_reference_id),'[]') INTO sources
 FROM public.koinon_answer_release_proof_sources s
 WHERE release_result_id=NEW.release_result_id AND projection_version=NEW.projection_version;
 IF current_state IS NULL OR current_state->>'state_sha256' IS DISTINCT FROM
  encode(NEW.state_sha256,'hex')
  OR header IS DISTINCT FROM current_state->'header'
  OR pins IS DISTINCT FROM current_state->'pins' OR sources IS DISTINCT FROM current_state->'sources'
  OR jsonb_array_length(pins)<>NEW.pin_count OR jsonb_array_length(sources)<>NEW.source_count THEN
  RAISE EXCEPTION 'proof must contain the complete exact derived child sets' USING ERRCODE='23514';
 END IF;
 RETURN NULL;
END $$
"""

STORE_SQL = r"""
CREATE OR REPLACE FUNCTION public.koinon_store_release_proof(release_id text,expected text,writer
  text,worker text,attempt_no integer,claim text)
RETURNS jsonb LANGUAGE plpgsql SECURITY INVOKER
SET search_path=pg_catalog,public AS $$
DECLARE state jsonb; h jsonb; pin jsonb; source jsonb; existing bytea; field text;
BEGIN
 IF current_user<>'koinon_release_proof_owner' THEN RAISE EXCEPTION 'private writer only' USING
  ERRCODE='42501'; END IF;
 state:=public.koinon_capture_release_proof(release_id);
 IF state IS NULL OR state->>'state_sha256' IS DISTINCT FROM expected THEN
  RAISE EXCEPTION 'release projection changed or is unprojectable' USING ERRCODE='P5503'; END IF;
 SELECT state_sha256 INTO existing FROM public.koinon_answer_release_proofs
  WHERE release_result_id=release_id AND projection_version=1;
 IF FOUND THEN
  IF encode(existing,'hex')<>expected THEN RAISE EXCEPTION 'immutable proof conflict' USING
  ERRCODE='P5503'; END IF;
  RETURN jsonb_build_object('header',state->'header','state_sha256',expected,'source',NULL);
 END IF;
 h:=state->'header'||jsonb_build_object('state_sha256',expected,'verifier','python:active_results+verified_release:v1',
   'writer_kind',writer,'worker_id',worker,'attempt',attempt_no,'maintenance_claim_id',claim,'created_at',clock_timestamp());
 FOREACH field IN ARRAY ARRAY['state_sha256','canonical_seal_sha256','release_native_sha256',
   'message_native_sha256','selection_native_sha256','active_selector_sha256'] LOOP
  h:=jsonb_set(h,ARRAY[field],to_jsonb('\x'||(h->>field)));
 END LOOP;
 INSERT INTO public.koinon_answer_release_proofs SELECT
  (jsonb_populate_record(NULL::public.koinon_answer_release_proofs,h)).*;
 FOR pin IN SELECT value FROM jsonb_array_elements(state->'pins') LOOP
  pin:=pin||jsonb_build_object('release_result_id',release_id,'projection_version',1,
    'canonical_sha256','\x'||(pin->>'canonical_sha256'),'native_sha256','\x'||(pin->>'native_sha256'));
  INSERT INTO public.koinon_answer_release_proof_pins SELECT
  (jsonb_populate_record(NULL::public.koinon_answer_release_proof_pins,pin)).*;
 END LOOP;
 FOR source IN SELECT value FROM jsonb_array_elements(state->'sources') LOOP
  source:=source||jsonb_build_object('release_result_id',release_id,'projection_version',1,
    'source_part_sha256',CASE WHEN source->>'source_part_sha256' IS NOT NULL THEN
  '\x'||(source->>'source_part_sha256') END);
  INSERT INTO public.koinon_answer_release_proof_sources SELECT
  (jsonb_populate_record(NULL::public.koinon_answer_release_proof_sources,source)).*;
 END LOOP;
 RETURN jsonb_build_object('header',state->'header','state_sha256',expected,'source',NULL);
END $$
"""

LOCK_SQL = r"""
CREATE OR REPLACE FUNCTION public.koinon_lock_release_proof(release_id text)
RETURNS void LANGUAGE plpgsql SECURITY INVOKER
SET search_path=pg_catalog,public AS $$
DECLARE run_key text; thread_key text; n integer;
BEGIN
 SELECT r.run_id,u.thread_id INTO run_key,thread_key FROM public.koinon_chat_tool_results r
 JOIN public.koinon_chat_runs u ON u.id=r.run_id WHERE r.id=release_id AND r.kind='answer_release';
 IF NOT FOUND THEN RAISE EXCEPTION 'release missing' USING ERRCODE='P5503'; END IF;
 SELECT count(*) INTO n FROM (SELECT id FROM public.koinon_chat_tool_results WHERE run_id=run_key LIMIT
  2001) bounded;
 IF n>2000 THEN RAISE EXCEPTION 'result lock bound' USING ERRCODE='P5501'; END IF;
 PERFORM id FROM public.koinon_chat_threads WHERE id=thread_key FOR UPDATE;
 PERFORM id FROM public.koinon_chat_runs WHERE id=run_key FOR UPDATE;
 IF NOT EXISTS (SELECT FROM public.koinon_chat_runs WHERE id=run_key AND thread_id=thread_key) THEN
  RAISE EXCEPTION 'run parent changed before locking' USING ERRCODE='P5503'; END IF;
 SELECT count(*) INTO n FROM (SELECT id FROM public.koinon_chat_tool_results
   WHERE run_id=run_key LIMIT 2001) bounded;
 IF n>2000 THEN RAISE EXCEPTION 'result lock bound' USING ERRCODE='P5501'; END IF;
 PERFORM m.id FROM public.koinon_chat_messages m JOIN public.koinon_chat_runs u
  ON m.id IN (u.message_id,u.user_message_id) WHERE u.id=run_key ORDER BY m.id FOR UPDATE OF m;
 PERFORM id FROM public.koinon_chat_tool_results WHERE run_id=run_key ORDER BY id FOR UPDATE;
END $$
"""

PUBLISH_SQL = r"""
CREATE OR REPLACE FUNCTION public.koinon_publish_release_proof(release_id text,expected text,worker
  text,attempt_no integer)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER
SET search_path=pg_catalog,public AS $$
BEGIN
 PERFORM public.koinon_lock_release_proof(release_id);
 IF NOT EXISTS (SELECT FROM public.koinon_chat_tool_results r JOIN public.koinon_chat_runs u ON
  u.id=r.run_id
    WHERE r.id=release_id AND u.worker_id=worker AND u.attempts=attempt_no
    AND u.lease_until>clock_timestamp() AND u.status='running'
    AND r.xmin::text=pg_current_xact_id()::text) THEN
  RAISE EXCEPTION 'live publication attempt and new transactional release required' USING
  ERRCODE='P5504'; END IF;
 RETURN public.koinon_store_release_proof(release_id,expected,'publication',worker,attempt_no,NULL);
END $$
"""

CLAIM_CHECK_SQL = r"""
CREATE OR REPLACE FUNCTION public.koinon_check_release_projection_claim(release_id text,job text,
 claim text,job_revision integer,lock_claim boolean)
RETURNS void LANGUAGE plpgsql SECURITY INVOKER
SET search_path=pg_catalog,public AS $$
DECLARE j public.koinon_answer_release_projection_jobs%ROWTYPE;
BEGIN
 IF EXISTS (SELECT FROM public.koinon_answer_release_projection_jobs
   WHERE job_id=job AND projection_version=1 AND xmin::text=pg_current_xact_id()::text) THEN
  RAISE EXCEPTION 'commit the claim before acquiring release locks' USING ERRCODE='P5504'; END IF;
 IF lock_claim THEN
  SELECT * INTO j FROM public.koinon_answer_release_projection_jobs
   WHERE job_id=job AND projection_version=1 FOR UPDATE;
 ELSE
  SELECT * INTO j FROM public.koinon_answer_release_projection_jobs
   WHERE job_id=job AND projection_version=1;
 END IF;
 IF j.claim_token IS DISTINCT FROM claim OR j.revision IS DISTINCT FROM job_revision
   OR j.claim_until IS NULL OR j.claim_until<=clock_timestamp() OR j.state<>'running'
   OR NOT EXISTS (SELECT FROM public.koinon_chat_tool_results r JOIN public.koinon_chat_runs u ON
  u.id=r.run_id
     WHERE r.id=release_id AND (j.tenant_id IS NULL OR j.tenant_id=u.tenant_id)
     AND (r.created_at,r.id)<=(j.high_water_created_at,j.high_water_release_id)
     AND (j.cursor_created_at IS NULL OR (r.created_at,r.id)>(j.cursor_created_at,j.cursor_release_id)))
  THEN
   RAISE EXCEPTION 'live exact maintenance claim required' USING ERRCODE='P5504'; END IF;
END $$
"""

PREPARE_BACKFILL_SQL = r"""
CREATE OR REPLACE FUNCTION public.koinon_prepare_release_backfill(release_id text,job text,
 claim text,job_revision integer)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER
SET search_path=pg_catalog,public AS $$
BEGIN
 -- Caller source/canonical fences and transaction timeouts precede these locks.
 PERFORM public.koinon_check_release_projection_claim(release_id,job,claim,job_revision,false);
 PERFORM public.koinon_lock_release_proof(release_id);
 PERFORM public.koinon_check_release_projection_claim(release_id,job,claim,job_revision,true);
 RETURN public.koinon_capture_release_proof(release_id);
END $$
"""

BACKFILL_SQL = r"""
CREATE OR REPLACE FUNCTION public.koinon_backfill_release_proof(release_id text,expected text,job text,
 claim text,job_revision integer)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER
SET search_path=pg_catalog,public AS $$
BEGIN
 PERFORM public.koinon_check_release_projection_claim(release_id,job,claim,job_revision,false);
 PERFORM public.koinon_lock_release_proof(release_id);
 PERFORM public.koinon_check_release_projection_claim(release_id,job,claim,job_revision,true);
 RETURN public.koinon_store_release_proof(release_id,expected,'backfill',NULL,NULL,claim);
END $$
"""

COMPARE_SQL = r"""
CREATE OR REPLACE FUNCTION public.koinon_compare_release_proofs(requests jsonb)
RETURNS SETOF jsonb LANGUAGE plpgsql STABLE SECURITY DEFINER
SET search_path=pg_catalog,public AS $$
DECLARE request jsonb; state jsonb; stored bytea; requested_source jsonb; n bigint;
BEGIN
 IF jsonb_typeof(requests)<>'array' OR octet_length(requests::text)>4194304
   OR jsonb_array_length(requests)>200 THEN RAISE EXCEPTION 'request identity bound' USING
  ERRCODE='P5501'; END IF;
 IF (SELECT count(DISTINCT value->>'release_result_id') FROM
  jsonb_array_elements(requests))<>jsonb_array_length(requests)
 THEN RAISE EXCEPTION 'duplicate release request' USING ERRCODE='P5501'; END IF;
 SELECT count(*) INTO n FROM (SELECT r.id FROM public.koinon_chat_tool_results r WHERE r.run_id IN
  (SELECT value->>'run_id' FROM jsonb_array_elements(requests)) LIMIT 2001) bounded;
 IF n>2000 THEN RAISE EXCEPTION 'batch result bound' USING ERRCODE='P5501'; END IF;
 SELECT count(*) INTO n FROM (SELECT e.id FROM public.koinon_chat_events e WHERE e.run_id IN
  (SELECT value->>'run_id' FROM jsonb_array_elements(requests)) LIMIT 10001) bounded;
 IF n>10000 THEN RAISE EXCEPTION 'batch event bound' USING ERRCODE='P5501'; END IF;
 FOR request IN SELECT value FROM jsonb_array_elements(requests) LOOP
  SELECT state_sha256 INTO stored FROM public.koinon_answer_release_proofs p
   WHERE p.release_result_id=request->>'release_result_id' AND p.projection_version=1
   AND request->>'projection_version'='1' AND p.tenant_id=request->>'tenant_id'
   AND p.owner_subject=request->>'owner_subject' AND p.thread_id=request->>'thread_id'
   AND p.run_id=request->>'run_id' AND p.message_id=request->>'message_id';
  IF NOT FOUND THEN CONTINUE; END IF;
  BEGIN
   state:=public.koinon_capture_release_proof(request->>'release_result_id');
  EXCEPTION WHEN SQLSTATE 'P5501' OR SQLSTATE 'P5502' OR SQLSTATE 'P5503' THEN CONTINUE; END;
  IF state IS NULL OR state->>'state_sha256' IS DISTINCT FROM encode(stored,'hex') THEN CONTINUE; END IF;
  requested_source:=NULL;
  IF request->>'source_reference_id' IS NOT NULL THEN
   SELECT value INTO requested_source FROM jsonb_array_elements(state->'sources') WHERE
  value->>'source_reference_id'=request->>'source_reference_id';
   IF NOT FOUND THEN CONTINUE; END IF;
  END IF;
  RETURN NEXT
  jsonb_build_object('header',state->'header','state_sha256',encode(stored,'hex'),'source',requested_source);
 END LOOP;
END $$
"""

CLAIM_SQL = r"""
CREATE OR REPLACE FUNCTION public.koinon_claim_release_projection(job text,claim text,tenant text)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER
SET search_path=pg_catalog,public AS $$
DECLARE j public.koinon_answer_release_projection_jobs%ROWTYPE; high record;
BEGIN
 IF length(job) NOT BETWEEN 1 AND 64 OR length(claim) NOT BETWEEN 1 AND 64
   OR job IS NULL OR claim IS NULL THEN RAISE EXCEPTION 'bounded claim identity required' USING
  ERRCODE='P5504'; END IF;
 SELECT r.created_at,r.id INTO high FROM public.koinon_chat_tool_results r JOIN public.koinon_chat_runs u
  ON u.id=r.run_id
  WHERE r.kind='answer_release' AND (tenant IS NULL OR u.tenant_id=tenant) ORDER BY r.created_at
  DESC,r.id DESC LIMIT 1;
 INSERT INTO
  public.koinon_answer_release_projection_jobs(job_id,projection_version,tenant_id,state,revision,
  high_water_created_at,high_water_release_id,scanned,projected,already_present,invalid,blocked,
  error_sample,created_at,updated_at)
 VALUES(job,1,tenant,'ready',1,high.created_at,high.id,0,0,0,0,0,'[]',clock_timestamp(),clock_timestamp())
 ON CONFLICT DO NOTHING;
 SELECT * INTO j FROM public.koinon_answer_release_projection_jobs WHERE job_id=job AND
  projection_version=1 FOR UPDATE;
 IF j.tenant_id IS DISTINCT FROM tenant OR j.state='complete' OR j.claim_until>clock_timestamp() THEN
  RAISE EXCEPTION 'job scope conflict or existing live claim' USING ERRCODE='P5504'; END IF;
 UPDATE public.koinon_answer_release_projection_jobs SET
  claim_token=claim,claim_until=clock_timestamp()+interval '30 seconds',
   revision=revision+1,state=CASE WHEN high_water_release_id IS NULL THEN 'complete' ELSE 'running' END,
   updated_at=clock_timestamp() WHERE job_id=job AND projection_version=1 RETURNING * INTO j;
 RETURN jsonb_build_object('job_id',j.job_id,'projection_version',1,'claim_token',j.claim_token,
   'revision',j.revision,'claim_until',j.claim_until,'tenant_id',j.tenant_id,'state',j.state);
END $$
"""

CANDIDATES_SQL = r"""
CREATE OR REPLACE FUNCTION public.koinon_release_projection_candidates(job text,claim text,job_revision
  integer,batch_limit integer)
RETURNS SETOF jsonb LANGUAGE plpgsql STABLE SECURITY DEFINER
SET search_path=pg_catalog,public AS $$
DECLARE j public.koinon_answer_release_projection_jobs%ROWTYPE;
BEGIN
 SELECT * INTO j FROM public.koinon_answer_release_projection_jobs WHERE job_id=job AND
  projection_version=1;
 IF j.claim_token IS DISTINCT FROM claim OR j.revision IS DISTINCT FROM job_revision
  OR j.claim_until IS NULL OR j.claim_until<=clock_timestamp() OR j.state NOT IN ('running','complete')
  THEN
  RAISE EXCEPTION 'live exact maintenance claim required' USING ERRCODE='P5504'; END IF;
 IF batch_limit IS NULL OR batch_limit NOT BETWEEN 1 AND 25 THEN RAISE EXCEPTION
  'maintenance batch bound' USING ERRCODE='P5501'; END IF;
 RETURN QUERY SELECT jsonb_build_object('created_at',r.created_at,'release_result_id',r.id)
 FROM public.koinon_chat_tool_results r JOIN public.koinon_chat_runs u ON u.id=r.run_id
 WHERE r.kind='answer_release' AND (j.tenant_id IS NULL OR u.tenant_id=j.tenant_id)
  AND (r.created_at,r.id)<=(j.high_water_created_at,j.high_water_release_id)
  AND (j.cursor_created_at IS NULL OR (r.created_at,r.id)>(j.cursor_created_at,j.cursor_release_id))
 ORDER BY r.created_at,r.id LIMIT batch_limit;
END $$
"""

JOURNAL_GUARD_SQL = r"""
CREATE OR REPLACE FUNCTION public.koinon_release_projection_journal_guard()
RETURNS trigger LANGUAGE plpgsql SECURITY INVOKER
SET search_path=pg_catalog,public AS $$
BEGIN
 IF current_user<>'koinon_release_proof_owner' OR TG_OP IN ('DELETE','TRUNCATE') THEN
  RAISE EXCEPTION 'maintenance journal requires its restricted entrypoint' USING ERRCODE='42501'; END IF;
 IF TG_OP='UPDATE' AND (
  (NEW.job_id,NEW.projection_version,NEW.tenant_id,NEW.high_water_created_at,NEW.high_water_release_id)
   IS DISTINCT FROM
  (OLD.job_id,OLD.projection_version,OLD.tenant_id,OLD.high_water_created_at,OLD.high_water_release_id)
  OR NEW.revision<OLD.revision OR NEW.revision>OLD.revision+1
 ) THEN RAISE EXCEPTION 'maintenance identity and revision are fenced' USING ERRCODE='23514'; END IF;
 RETURN NEW;
END $$
"""

CHECKPOINT_SQL = r"""
CREATE OR REPLACE FUNCTION public.koinon_checkpoint_release_projection(job text,claim text,job_revision
  integer,
 release_id text,release_created_at timestamptz,outcome text)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER
SET search_path=pg_catalog,public AS $$
DECLARE j public.koinon_answer_release_projection_jobs%ROWTYPE; candidate jsonb; remaining boolean;
BEGIN
 SELECT * INTO j FROM public.koinon_answer_release_projection_jobs WHERE job_id=job AND
  projection_version=1 FOR UPDATE;
 SELECT value INTO candidate FROM public.koinon_release_projection_candidates(job,claim,job_revision,1)
  value;
 IF candidate IS NULL OR candidate->>'release_result_id' IS DISTINCT FROM release_id
  OR (candidate->>'created_at')::timestamptz IS DISTINCT FROM release_created_at
  OR outcome IS NULL OR outcome NOT IN ('projected','already_present','invalid','blocked') THEN
  RAISE EXCEPTION 'checkpoint must classify the first unresolved candidate' USING ERRCODE='P5504'; END
  IF;
 IF outcome IN ('projected','already_present') AND NOT EXISTS(
  SELECT FROM public.koinon_answer_release_proofs WHERE release_result_id=release_id AND
  projection_version=1)
 THEN RAISE EXCEPTION 'successful checkpoint requires retained proof' USING ERRCODE='P5504'; END IF;
 UPDATE public.koinon_answer_release_projection_jobs SET
  cursor_created_at=CASE WHEN outcome='blocked' THEN cursor_created_at ELSE release_created_at END,
  cursor_release_id=CASE WHEN outcome='blocked' THEN cursor_release_id ELSE release_id END,
  scanned=scanned+1,projected=projected+(outcome='projected')::int,
  already_present=already_present+(outcome='already_present')::int,
  invalid=invalid+(outcome='invalid')::int,blocked=blocked+(outcome='blocked')::int,
  error_sample=CASE WHEN outcome IN ('invalid','blocked') AND jsonb_array_length(error_sample::jsonb)<25
    THEN
  (error_sample::jsonb||jsonb_build_array(jsonb_build_object('release_result_id',release_id,'reason',outcome)))::json
    ELSE error_sample END,
  state=CASE WHEN outcome='blocked' THEN 'blocked' ELSE 'running' END,
  claim_until=CASE WHEN outcome='blocked' THEN clock_timestamp() ELSE claim_until END,
  revision=revision+1,updated_at=clock_timestamp() WHERE job_id=job AND projection_version=1 RETURNING *
  INTO j;
 IF outcome<>'blocked' THEN
  SELECT EXISTS(SELECT FROM public.koinon_release_projection_candidates(job,claim,j.revision,1)) INTO
  remaining;
  IF NOT remaining THEN UPDATE public.koinon_answer_release_projection_jobs SET state='complete'
    WHERE job_id=job AND projection_version=1 RETURNING * INTO j; END IF;
 END IF;
 RETURN jsonb_build_object('job_id',j.job_id,'projection_version',1,'claim_token',j.claim_token,
   'revision',j.revision,'claim_until',j.claim_until,'tenant_id',j.tenant_id,'state',j.state);
END $$
"""

FUNCTIONS = (
    ("koinon_release_native_hash(text,jsonb)", HASH_SQL),
    ("koinon_release_source_identity(jsonb)", SOURCE_SQL),
    ("koinon_capture_release_proof(text)", CAPTURE_SQL),
    ("koinon_release_proof_immutable()", INSERT_GUARD_SQL),
    ("koinon_release_proof_exact_set()", EXACT_SET_SQL),
    ("koinon_store_release_proof(text,text,text,text,integer,text)", STORE_SQL),
    ("koinon_lock_release_proof(text)", LOCK_SQL),
    ("koinon_publish_release_proof(text,text,text,integer)", PUBLISH_SQL),
    ("koinon_check_release_projection_claim(text,text,text,integer,boolean)", CLAIM_CHECK_SQL),
    ("koinon_prepare_release_backfill(text,text,text,integer)", PREPARE_BACKFILL_SQL),
    ("koinon_backfill_release_proof(text,text,text,text,integer)", BACKFILL_SQL),
    ("koinon_compare_release_proofs(jsonb)", COMPARE_SQL),
    ("koinon_claim_release_projection(text,text,text)", CLAIM_SQL),
    ("koinon_release_projection_journal_guard()", JOURNAL_GUARD_SQL),
    ("koinon_release_projection_candidates(text,text,integer,integer)", CANDIDATES_SQL),
    ("koinon_checkpoint_release_projection(text,text,integer,text,timestamptz,text)", CHECKPOINT_SQL),
)


def guard_statements():
    """The same installation sequence is used by migrations and fresh metadata."""
    yield f"""DO $$ BEGIN
      IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname='{OWNER}') THEN
        CREATE ROLE {OWNER} NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;
      END IF;
      IF EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname='{OWNER}' AND
        (rolcanlogin OR rolsuper OR rolcreatedb OR rolcreaterole OR rolreplication OR rolbypassrls))
      OR EXISTS (SELECT FROM pg_catalog.pg_auth_members
        WHERE roleid=(SELECT oid FROM pg_catalog.pg_roles WHERE rolname='{OWNER}'))
      THEN RAISE EXCEPTION 'proof function owner must be an isolated nonlogin role'; END IF;
    END $$"""
    yield f"GRANT USAGE ON SCHEMA public TO {OWNER}"
    for table in (
        "koinon_chat_tool_results",
        "koinon_chat_runs",
        "koinon_chat_threads",
        "koinon_chat_messages",
    ):
        yield f"GRANT SELECT, UPDATE ON TABLE public.{table} TO {OWNER}"
    yield f"GRANT SELECT ON TABLE public.koinon_chat_events TO {OWNER}"
    for table in TABLE_NAMES:
        yield f"REVOKE ALL ON TABLE public.{table} FROM PUBLIC"
        rights = "SELECT, INSERT, UPDATE" if table.endswith("jobs") else "SELECT, INSERT"
        yield f"GRANT {rights} ON TABLE public.{table} TO {OWNER}"
    for signature, statement in FUNCTIONS:
        yield statement.replace(
            "SET search_path=pg_catalog,public", "SET search_path=pg_catalog,public SET TimeZone='UTC'"
        )
        yield f"ALTER FUNCTION public.{signature} OWNER TO {OWNER}"
        yield f"REVOKE ALL ON FUNCTION public.{signature} FROM PUBLIC"
    for table in TABLE_NAMES[:3]:
        yield (
            f"CREATE TRIGGER release_proof_row_guard BEFORE INSERT OR UPDATE OR DELETE ON public.{table} "
            "FOR EACH ROW EXECUTE FUNCTION public.koinon_release_proof_immutable()"
        )
        yield (
            f"CREATE TRIGGER release_proof_truncate_guard BEFORE TRUNCATE ON public.{table} "
            "FOR EACH STATEMENT EXECUTE FUNCTION public.koinon_release_proof_immutable()"
        )
    yield """CREATE CONSTRAINT TRIGGER release_proof_exact_children
      AFTER INSERT ON public.koinon_answer_release_proofs
      DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION
  public.koinon_release_proof_exact_set()"""
    yield """CREATE TRIGGER release_projection_journal_row_guard BEFORE INSERT OR UPDATE OR DELETE
      ON public.koinon_answer_release_projection_jobs FOR EACH ROW
      EXECUTE FUNCTION public.koinon_release_projection_journal_guard()"""
    yield """CREATE TRIGGER release_projection_journal_truncate_guard BEFORE TRUNCATE
      ON public.koinon_answer_release_projection_jobs FOR EACH STATEMENT
      EXECUTE FUNCTION public.koinon_release_projection_journal_guard()"""
