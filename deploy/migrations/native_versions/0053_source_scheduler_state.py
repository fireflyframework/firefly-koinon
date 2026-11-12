# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Expand durable dispatch and bounded scan state without rewriting old evidence.

Transactional expansion: a lock timeout rolls back the whole upgrade for retry.
Legacy scan bounds remain unknown. Resume them through a fresh explicit scan;
never infer a count from retained unique objects. Repair forward after use.
"""

from alembic import op

revision = "koinon_0053_scheduler_state"
down_revision = "koinon_0052_publication_baseline"


def upgrade():
    if op.get_bind().dialect.name != "postgresql":
        raise RuntimeError("Source dispatch requires PostgreSQL")
    op.execute("SET LOCAL lock_timeout='5s'")
    op.execute("""ALTER TABLE public.koinon_content_sync_states
      ADD COLUMN scheduler_last_attempt_at timestamptz,
      ADD COLUMN scheduler_retry_not_before timestamptz,
      ADD COLUMN scheduler_claim_token uuid,
      ADD COLUMN scheduler_claim_until timestamptz,
      ADD COLUMN scheduler_claim_policy_id varchar(64),
      ADD COLUMN scheduler_claim_control_revision integer,
      ADD COLUMN scheduler_claim_occurrence_at timestamptz,
      ADD COLUMN scheduler_failure_count integer NOT NULL DEFAULT 0,
      ADD COLUMN scan_observed_count bigint NOT NULL DEFAULT 0,
      ADD COLUMN scan_max_items integer,
      ADD CONSTRAINT ck_content_scheduler_failure CHECK(scheduler_failure_count>=0),
      ADD CONSTRAINT ck_content_scan_count CHECK(scan_observed_count>=0),
      ADD CONSTRAINT ck_content_scan_max CHECK(scan_max_items BETWEEN 100 AND 1000000),
      ADD CONSTRAINT ck_content_scheduler_claim CHECK(
        num_nonnulls(scheduler_claim_token,scheduler_claim_until,scheduler_claim_policy_id,
          scheduler_claim_control_revision,scheduler_claim_occurrence_at) IN (0,5)),
      ADD CONSTRAINT fk_content_scheduler_policy FOREIGN KEY(tenant_id,mapping_id,scheduler_claim_policy_id)
        REFERENCES public.koinon_content_policies(tenant_id,mapping_id,id)
    """)
    op.execute("""CREATE INDEX ix_content_scheduler_fair ON public.koinon_content_sync_states
      (scheduler_last_attempt_at NULLS FIRST,next_run_at,tenant_id,mapping_id)
      WHERE enabled AND next_run_at IS NOT NULL""")
    op.execute("""CREATE OR REPLACE FUNCTION public.koinon_content_guard_state()
      RETURNS trigger LANGUAGE plpgsql SET search_path=pg_catalog,public AS $$
      DECLARE mapping public.koinon_content_mappings; policy public.koinon_content_policies;
        maintenance text[] := ARRAY['scheduler_last_attempt_at','scheduler_retry_not_before',
          'scheduler_claim_token','scheduler_claim_until','scheduler_claim_policy_id',
          'scheduler_claim_control_revision','scheduler_claim_occurrence_at','scheduler_failure_count'];
      BEGIN
        IF NEW.scheduler_claim_token IS NOT NULL AND
          (NOT NEW.enabled OR NEW.scheduler_claim_policy_id<>NEW.accepted_policy_id
           OR NEW.scheduler_claim_control_revision<>NEW.revision
           OR NEW.scheduler_claim_occurrence_at IS DISTINCT FROM NEW.next_run_at
           OR NEW.scheduler_claim_until<=NEW.scheduler_last_attempt_at) THEN
          RAISE EXCEPTION 'scheduler claim must bind current occurrence' USING ERRCODE='23514';
        END IF;
        IF TG_OP='UPDATE' THEN
          IF NEW.scan_generation=OLD.scan_generation AND
            (NEW.scan_observed_count<OLD.scan_observed_count OR
             (OLD.scan_max_items IS NOT NULL AND NEW.scan_max_items IS DISTINCT FROM OLD.scan_max_items)) THEN
            RAISE EXCEPTION 'scan accounting is monotonic within generation' USING ERRCODE='23514';
          END IF;
          IF NEW.last_complete_scan_generation>OLD.last_complete_scan_generation AND
            (NEW.scan_max_items IS NULL OR NEW.scan_observed_count>NEW.scan_max_items) THEN
            RAISE EXCEPTION 'complete scan requires captured work bound' USING ERRCODE='23514';
          END IF;
          IF to_jsonb(NEW)-maintenance=to_jsonb(OLD)-maintenance THEN
            RETURN NEW;
          END IF;
          IF NEW.tenant_id<>OLD.tenant_id OR NEW.mapping_id<>OLD.mapping_id
            OR NEW.revision<>OLD.revision+1 OR NEW.scan_generation<OLD.scan_generation
            OR NEW.last_complete_scan_generation<OLD.last_complete_scan_generation THEN
            RAISE EXCEPTION 'sync state revision must advance' USING ERRCODE='23514';
          END IF;
        ELSIF NEW.last_complete_scan_generation>0 AND
          (NEW.scan_max_items IS NULL OR NEW.scan_observed_count>NEW.scan_max_items) THEN
          RAISE EXCEPTION 'complete scan requires captured work bound' USING ERRCODE='23514';
        END IF;
        SELECT * INTO mapping FROM public.koinon_content_mappings
          WHERE tenant_id=NEW.tenant_id AND id=NEW.mapping_id;
        SELECT * INTO policy FROM public.koinon_content_policies
          WHERE tenant_id=NEW.tenant_id AND mapping_id=NEW.mapping_id AND id=NEW.accepted_policy_id;
        IF mapping.id IS NULL OR policy.accepted_at IS NULL THEN
          RAISE EXCEPTION 'accepted policy required' USING ERRCODE='23514';
        END IF;
        PERFORM pg_advisory_xact_lock(hashtextextended(
          jsonb_build_array(mapping.tenant_id,mapping.provider,mapping.external_tenant,mapping.drive_id)::text,0));
        IF NEW.enabled AND (policy.mapping_revision<>mapping.revision OR EXISTS (
          SELECT 1 FROM public.koinon_content_sync_states other
          JOIN public.koinon_content_mappings m ON m.id=other.mapping_id AND m.tenant_id=other.tenant_id
          JOIN public.koinon_content_policies p ON p.id=other.accepted_policy_id AND p.tenant_id=other.tenant_id
          WHERE other.enabled AND other.tenant_id=NEW.tenant_id AND other.mapping_id<>NEW.mapping_id
            AND m.provider=mapping.provider AND m.external_tenant IS NOT DISTINCT FROM mapping.external_tenant
            AND m.drive_id=mapping.drive_id
            AND (p.root_ancestry_json::jsonb @> jsonb_build_array(mapping.root_id)
              OR policy.root_ancestry_json::jsonb @> jsonb_build_array(m.root_id))
        )) THEN RAISE EXCEPTION 'source root overlaps or accepted revision is stale' USING ERRCODE='23514'; END IF;
        RETURN NEW;
      END $$""")


def downgrade():
    raise RuntimeError(
        "Retain dispatch and scan evidence; use a reviewed forward migration"
    )
