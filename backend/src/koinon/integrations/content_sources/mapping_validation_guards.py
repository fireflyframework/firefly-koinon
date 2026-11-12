# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Database fences for bounded transient preparation and exact sealed manifests."""

HEADER_GUARD = """
CREATE FUNCTION public.koinon_guard_mapping_validation() RETURNS trigger
LANGUAGE plpgsql SET search_path=pg_catalog,public AS $$
DECLARE records bigint; active bigint; own_active bigint; reserved bigint;
  identity_keys text[] := ARRAY['id','tenant_id','owner','operation_id','session_hash','request_sha256',
    'connection_id','connection_revision','authority_sha256','mapping_id','expected_revision',
    'root_kind','root_proof_sha256','scan_max_items','max_active_per_tenant','max_active_per_owner',
    'max_records_per_tenant','max_retained_bytes_per_tenant','created_at','expires_at'];
  maintenance_keys text[] := ARRAY['cleanup_claim_token','cleanup_claim_until','cleanup_last_attempt_at'];
  protected_keys text[] := ARRAY['request_ciphertext','root_proof_ciphertext',
    'walk_ciphertext','checkpoint_ciphertext'];
  key text; changed boolean;
BEGIN
  IF TG_OP='DELETE' THEN
    PERFORM 1 FROM public.lattice_tenants WHERE id=OLD.tenant_id FOR UPDATE;
    IF OLD.payload_released_at IS NULL OR OLD.expires_at>clock_timestamp() OR EXISTS (
      SELECT 1 FROM public.koinon_content_mapping_validation_entries
      WHERE tenant_id=OLD.tenant_id AND validation_id=OLD.id) THEN
      RAISE EXCEPTION 'validation recovery is retained until expired and cleaned' USING ERRCODE='23514';
    END IF;
    RETURN OLD;
  END IF;
  PERFORM 1 FROM public.lattice_tenants WHERE id=NEW.tenant_id FOR UPDATE;
  NEW.payload_bytes := octet_length((to_jsonb(NEW)-protected_keys-ARRAY['payload_bytes'])::text)
    +coalesce(octet_length(NEW.request_ciphertext),0)+coalesce(octet_length(NEW.root_proof_ciphertext),0)
    +coalesce(octet_length(NEW.walk_ciphertext),0)+coalesce(octet_length(NEW.checkpoint_ciphertext),0);
  IF coalesce(octet_length(NEW.request_ciphertext),0)>2097152
    OR coalesce(octet_length(NEW.root_proof_ciphertext),0)>1048576
    OR coalesce(octet_length(NEW.checkpoint_ciphertext),0)>1048576
    OR NEW.payload_bytes>8388608 THEN
    RAISE EXCEPTION 'validation parent payload bound exceeded' USING ERRCODE='23514';
  END IF;
  IF TG_OP='INSERT' THEN
    IF NEW.state<>'scanning' OR NEW.revision<>1 OR NEW.manifest_sha256 IS NOT NULL
      OR NEW.payload_released_at IS NOT NULL OR NEW.enumeration_complete
      OR NEW.raw_observed_count<>0 OR NEW.eligible_count<>0 OR NEW.change_count<>0
      OR NEW.verification_position<>0 OR NEW.request_ciphertext IS NULL
      OR NEW.root_proof_ciphertext IS NULL OR NEW.expires_at<=clock_timestamp()
      OR NEW.reserved_bytes<>NEW.scan_max_items::bigint*16384+8388608 THEN
      RAISE EXCEPTION 'invalid initial validation reservation' USING ERRCODE='23514';
    END IF;
    SELECT count(*),count(*) FILTER(WHERE payload_released_at IS NULL),
      count(*) FILTER(WHERE payload_released_at IS NULL AND owner=NEW.owner),coalesce(sum(reserved_bytes),0)
      INTO records,active,own_active,reserved FROM public.koinon_content_mapping_validations
      WHERE tenant_id=NEW.tenant_id;
    IF records>=NEW.max_records_per_tenant OR active>=NEW.max_active_per_tenant
      OR own_active>=NEW.max_active_per_owner
      OR reserved+NEW.reserved_bytes>NEW.max_retained_bytes_per_tenant THEN
      RAISE EXCEPTION 'SOURCE_VALIDATION_CAPACITY' USING ERRCODE='23514';
    END IF;
  ELSE
    FOREACH key IN ARRAY identity_keys LOOP
      IF to_jsonb(NEW)->key IS DISTINCT FROM to_jsonb(OLD)->key THEN
        RAISE EXCEPTION 'validation identity and admission bounds are immutable' USING ERRCODE='23514';
      END IF;
    END LOOP;
    changed := to_jsonb(NEW)-maintenance_keys-ARRAY['payload_bytes'] IS DISTINCT FROM
      to_jsonb(OLD)-maintenance_keys-ARRAY['payload_bytes'];
    IF changed AND NEW.revision<>OLD.revision+1 THEN
      RAISE EXCEPTION 'validation revision must advance exactly once' USING ERRCODE='23514';
    END IF;
    IF NEW.raw_observed_count<OLD.raw_observed_count OR NEW.change_count<OLD.change_count
      OR NEW.verification_position<OLD.verification_position OR NEW.eligible_count<OLD.eligible_count
      OR NEW.cleanup_position<OLD.cleanup_position THEN
      RAISE EXCEPTION 'validation counters cannot regress' USING ERRCODE='23514';
    END IF;
    IF NEW.state<>OLD.state AND NOT (
      (OLD.state='scanning' AND NEW.state IN ('verifying','blocked','stale','cleaning')) OR
      (OLD.state='verifying' AND NEW.state IN ('checking_changes','blocked','stale','cleaning')) OR
      (OLD.state='checking_changes' AND NEW.state IN ('complete','blocked','stale','cleaning')) OR
      (OLD.state='complete' AND NEW.state IN ('blocked','stale','cleaning')) OR
      (OLD.state IN ('blocked','stale') AND NEW.state='cleaning') OR
      (OLD.state='cleaning' AND NEW.state IN ('abandoned','expired'))
    ) THEN RAISE EXCEPTION 'invalid validation state transition' USING ERRCODE='23514'; END IF;
    IF NEW.state NOT IN ('cleaning','abandoned','expired') AND (
      NEW.request_ciphertext IS DISTINCT FROM OLD.request_ciphertext OR
      NEW.root_proof_ciphertext IS DISTINCT FROM OLD.root_proof_ciphertext) THEN
      RAISE EXCEPTION 'validation selection proof is immutable' USING ERRCODE='23514';
    END IF;
    IF OLD.manifest_sha256 IS NOT NULL AND (
      NEW.manifest_sha256 IS DISTINCT FROM OLD.manifest_sha256 OR
      NEW.enumeration_complete<>OLD.enumeration_complete OR
      NEW.raw_observed_count<>OLD.raw_observed_count OR NEW.eligible_count<>OLD.eligible_count OR
      NEW.verification_position<>OLD.verification_position OR NEW.change_count<>OLD.change_count OR
      (NEW.state NOT IN ('cleaning','abandoned','expired') AND (
        NEW.walk_ciphertext IS DISTINCT FROM OLD.walk_ciphertext OR
        NEW.checkpoint_ciphertext IS DISTINCT FROM OLD.checkpoint_ciphertext))) THEN
      RAISE EXCEPTION 'sealed validation manifest is immutable' USING ERRCODE='23514';
    END IF;
    IF OLD.payload_released_at IS NOT NULL AND (
      NEW.payload_released_at IS DISTINCT FROM OLD.payload_released_at OR NEW.state<>OLD.state) THEN
      RAISE EXCEPTION 'cleaned validation cannot be revived' USING ERRCODE='23514';
    END IF;
  END IF;
  IF NEW.state IN ('cleaning','abandoned','expired') AND (
    NEW.request_ciphertext IS NOT NULL OR NEW.root_proof_ciphertext IS NOT NULL OR
    NEW.walk_ciphertext IS NOT NULL OR NEW.checkpoint_ciphertext IS NOT NULL) THEN
    RAISE EXCEPTION 'cleaning must clear parent protected payload' USING ERRCODE='23514';
  END IF;
  IF NEW.payload_released_at IS NOT NULL THEN
    IF NEW.state NOT IN ('abandoned','expired') OR EXISTS (
      SELECT 1 FROM public.koinon_content_mapping_validation_entries
      WHERE tenant_id=NEW.tenant_id AND validation_id=NEW.id) THEN
      RAISE EXCEPTION 'validation reservation cannot release before child cleanup' USING ERRCODE='23514';
    END IF;
    NEW.reserved_bytes := NEW.payload_bytes;
  ELSIF NEW.reserved_bytes<>NEW.scan_max_items::bigint*16384+8388608 THEN
    RAISE EXCEPTION 'validation reservation cannot shrink before cleanup' USING ERRCODE='23514';
  END IF;
  IF NEW.state IN ('abandoned','expired') AND NEW.payload_released_at IS NULL THEN
    RAISE EXCEPTION 'terminal validation requires actual payload release' USING ERRCODE='23514';
  END IF;
  IF NEW.state IN ('verifying','checking_changes','complete') AND (
    NOT NEW.enumeration_complete OR NEW.raw_observed_count>NEW.scan_max_items OR
    NEW.change_count>NEW.scan_max_items) THEN
    RAISE EXCEPTION 'validation cannot complete an unbounded scan' USING ERRCODE='23514';
  END IF;
  IF NEW.state='complete' THEN
    IF NEW.manifest_sha256 IS NULL OR NEW.checkpoint_ciphertext IS NULL
      OR NEW.expires_at<=clock_timestamp() OR NEW.verification_position<>NEW.eligible_count
      OR NEW.eligible_count<>(SELECT count(*) FROM public.koinon_content_mapping_validation_entries
         WHERE tenant_id=NEW.tenant_id AND validation_id=NEW.id)
      OR EXISTS(SELECT 1 FROM public.koinon_content_mapping_validation_entries
         WHERE tenant_id=NEW.tenant_id AND validation_id=NEW.id AND NOT verified) THEN
      RAISE EXCEPTION 'complete validation requires verified exact manifest' USING ERRCODE='23514';
    END IF;
  ELSIF TG_OP='UPDATE' AND OLD.manifest_sha256 IS NULL AND NEW.manifest_sha256 IS NOT NULL THEN
    RAISE EXCEPTION 'manifest is assigned only at complete seal' USING ERRCODE='23514';
  END IF;
  RETURN NEW;
END $$
"""

ENTRY_GUARD = """
CREATE FUNCTION public.koinon_guard_mapping_validation_entry() RETURNS trigger
LANGUAGE plpgsql SET search_path=pg_catalog,public AS $$
DECLARE header public.koinon_content_mapping_validations; scope_tenant text; scope_id uuid;
BEGIN
  IF TG_OP='DELETE' THEN scope_tenant:=OLD.tenant_id; scope_id:=OLD.validation_id;
  ELSE scope_tenant:=NEW.tenant_id; scope_id:=NEW.validation_id; END IF;
  PERFORM 1 FROM public.lattice_tenants WHERE id=scope_tenant FOR UPDATE;
  SELECT * INTO header FROM public.koinon_content_mapping_validations
    WHERE tenant_id=scope_tenant AND id=scope_id FOR UPDATE;
  IF header.id IS NULL THEN RAISE EXCEPTION 'validation scope missing' USING ERRCODE='23503'; END IF;
  IF TG_OP='DELETE' THEN
    IF header.state<>'cleaning' OR header.cleanup_claim_token IS NULL
      OR header.cleanup_claim_until<=clock_timestamp() THEN
      RAISE EXCEPTION 'validation cleanup requires live claim' USING ERRCODE='23514';
    END IF;
    RETURN OLD;
  END IF;
  IF header.payload_released_at IS NOT NULL OR header.expires_at<=clock_timestamp()
    OR header.state NOT IN ('scanning','verifying') OR header.manifest_sha256 IS NOT NULL THEN
    RAISE EXCEPTION 'validation candidates are frozen' USING ERRCODE='23514';
  END IF;
  NEW.payload_bytes := octet_length(NEW.tenant_id)+octet_length(NEW.item_id)
    +coalesce(octet_length(NEW.parent_item_id),0)+octet_length(NEW.fingerprint_sha256)
    +octet_length(NEW.destination_key_sha256)+octet_length(NEW.candidate_ciphertext)+36;
  IF NEW.payload_bytes>16384 THEN
    RAISE EXCEPTION 'validation candidate payload bound exceeded' USING ERRCODE='23514';
  END IF;
  IF TG_OP='INSERT' THEN
    IF header.state<>'scanning' OR NEW.verified OR NEW.sequence>=header.scan_max_items THEN
      RAISE EXCEPTION 'validation candidate exceeds admission or phase' USING ERRCODE='23514';
    END IF;
  ELSIF (to_jsonb(NEW)-ARRAY['verified','payload_bytes']) IS DISTINCT FROM
    (to_jsonb(OLD)-ARRAY['verified','payload_bytes']) OR OLD.verified AND NOT NEW.verified THEN
    RAISE EXCEPTION 'validation candidate identity and fingerprint are immutable' USING ERRCODE='23514';
  END IF;
  RETURN NEW;
END $$
"""


def statements() -> tuple[str, ...]:
    return (
        HEADER_GUARD,
        ENTRY_GUARD,
        "CREATE TRIGGER guard_mapping_validation BEFORE INSERT OR UPDATE OR DELETE ON "
        "public.koinon_content_mapping_validations FOR EACH ROW "
        "EXECUTE FUNCTION public.koinon_guard_mapping_validation()",
        "CREATE TRIGGER guard_mapping_validation_entry BEFORE INSERT OR UPDATE OR DELETE ON "
        "public.koinon_content_mapping_validation_entries FOR EACH ROW "
        "EXECUTE FUNCTION public.koinon_guard_mapping_validation_entry()",
        "CREATE TRIGGER retain_validation_table BEFORE TRUNCATE ON "
        "public.koinon_content_mapping_validations EXECUTE FUNCTION public.koinon_content_retain_row()",
        "CREATE TRIGGER retain_validation_entries BEFORE TRUNCATE ON "
        "public.koinon_content_mapping_validation_entries "
        "EXECUTE FUNCTION public.koinon_content_retain_row()",
    )


def _root_capture_clause(source: str, original: str, replacement: str) -> str:
    """Keep the historical guard frozen and require an exact, reviewable forward delta."""
    if source.count(original) != 1:
        raise ValueError("The historical validation guard changed; review its forward migration")
    return source.replace(original, replacement, 1)


HEADER_GUARD_ROOT_CAPTURE = _root_capture_clause(
    HEADER_GUARD,
    "CREATE FUNCTION public.koinon_guard_mapping_validation()",
    "CREATE OR REPLACE FUNCTION public.koinon_guard_mapping_validation()",
)
HEADER_GUARD_ROOT_CAPTURE = _root_capture_clause(
    HEADER_GUARD_ROOT_CAPTURE,
    "'root_kind','root_proof_sha256','scan_max_items'",
    "'scan_max_items'",
)
HEADER_GUARD_ROOT_CAPTURE = _root_capture_clause(
    HEADER_GUARD_ROOT_CAPTURE,
    "key text; changed boolean;",
    "key text; changed boolean; capturing boolean := false;",
)
HEADER_GUARD_ROOT_CAPTURE = _root_capture_clause(
    HEADER_GUARD_ROOT_CAPTURE,
    "  NEW.payload_bytes :=",
    """  IF TG_OP='UPDATE' THEN
    capturing := NOT OLD.root_captured AND NEW.root_captured;
    IF OLD.root_captured AND (NOT NEW.root_captured
      OR NEW.root_kind IS DISTINCT FROM OLD.root_kind
      OR NEW.root_proof_sha256 IS DISTINCT FROM OLD.root_proof_sha256) THEN
      RAISE EXCEPTION 'captured validation root is immutable' USING ERRCODE='23514';
    END IF;
    IF capturing AND (OLD.state<>'scanning' OR NEW.state<>'scanning'
      OR NEW.expires_at<=clock_timestamp() OR NEW.revision<>OLD.revision+1
      OR NEW.root_kind IS NULL OR NEW.root_kind NOT IN ('file','folder')
      OR NEW.root_proof_sha256 IS NULL OR NEW.root_proof_sha256 !~ '^[a-f0-9]{64}$'
      OR NEW.root_proof_ciphertext IS NULL OR NEW.checkpoint_ciphertext IS NULL
      OR NEW.walk_ciphertext IS NOT NULL OR NEW.enumeration_complete
      OR NEW.raw_observed_count<>0 OR NEW.eligible_count<>0 OR NEW.change_count<>0
      OR NEW.verification_position<>0 OR NEW.manifest_sha256 IS NOT NULL
      OR EXISTS(SELECT 1 FROM public.koinon_content_mapping_validation_entries
        WHERE tenant_id=NEW.tenant_id AND validation_id=NEW.id)) THEN
      RAISE EXCEPTION 'validation root capture requires a live empty reservation' USING ERRCODE='23514';
    END IF;
  END IF;
  IF NOT NEW.root_captured AND (
    NEW.root_kind IS NOT NULL OR NEW.root_proof_sha256 IS NOT NULL
    OR NEW.root_proof_ciphertext IS NOT NULL OR NEW.walk_ciphertext IS NOT NULL
    OR NEW.checkpoint_ciphertext IS NOT NULL OR NEW.enumeration_complete
    OR NEW.raw_observed_count<>0 OR NEW.eligible_count<>0 OR NEW.change_count<>0
    OR NEW.verification_position<>0 OR NEW.manifest_sha256 IS NOT NULL
    OR NEW.state NOT IN ('scanning','blocked','stale','cleaning','abandoned','expired')
    OR EXISTS(SELECT 1 FROM public.koinon_content_mapping_validation_entries
      WHERE tenant_id=NEW.tenant_id AND validation_id=NEW.id)) THEN
    RAISE EXCEPTION 'uncaptured validation cannot enumerate or seal' USING ERRCODE='23514';
  END IF;
  NEW.payload_bytes :=""",
)
HEADER_GUARD_ROOT_CAPTURE = _root_capture_clause(
    HEADER_GUARD_ROOT_CAPTURE,
    "OR NEW.root_proof_ciphertext IS NULL OR NEW.expires_at<=clock_timestamp()",
    "OR NEW.root_captured OR NEW.expires_at<=clock_timestamp()",
)
HEADER_GUARD_ROOT_CAPTURE = _root_capture_clause(
    HEADER_GUARD_ROOT_CAPTURE,
    "NEW.root_proof_ciphertext IS DISTINCT FROM OLD.root_proof_ciphertext) THEN",
    "(NEW.root_proof_ciphertext IS DISTINCT FROM OLD.root_proof_ciphertext AND NOT capturing)) THEN",
)

ENTRY_GUARD_ROOT_CAPTURE = _root_capture_clause(
    ENTRY_GUARD,
    "CREATE FUNCTION public.koinon_guard_mapping_validation_entry()",
    "CREATE OR REPLACE FUNCTION public.koinon_guard_mapping_validation_entry()",
)
ENTRY_GUARD_ROOT_CAPTURE = _root_capture_clause(
    ENTRY_GUARD_ROOT_CAPTURE,
    "IF header.payload_released_at IS NOT NULL OR header.expires_at<=clock_timestamp()",
    "IF NOT header.root_captured OR header.payload_released_at IS NOT NULL "
    "OR header.expires_at<=clock_timestamp()",
)


def root_capture_statements() -> tuple[str, ...]:
    """Install only after the forward root-capture column expansion."""
    return HEADER_GUARD_ROOT_CAPTURE, ENTRY_GUARD_ROOT_CAPTURE
