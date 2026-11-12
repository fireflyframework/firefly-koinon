# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Retain the source publication descriptor on the original native version.

Nullable expansion leaves local/legacy originals untouched. Existing whole-row
immutability forbids retrofit. Retry a rolled-back upgrade; fix forward after use.
"""

from alembic import op

revision = "0023_source_publication_baseline"
down_revision = "0022_readiness_generations"


def upgrade():
    if op.get_bind().dialect.name != "postgresql":
        raise RuntimeError("Source publication binding requires PostgreSQL")
    op.execute("SET LOCAL lock_timeout='5s'")
    op.execute("ALTER TABLE public.canon_source_versions ADD COLUMN source_publication_json json")
    op.execute("""CREATE FUNCTION public.koinon_canon_publication_binding_guard() RETURNS trigger
      LANGUAGE plpgsql SET search_path=pg_catalog AS $$
      DECLARE value jsonb;
      BEGIN
        value=NEW.source_publication_json::jsonb;
        IF value IS NULL THEN RETURN NEW; END IF;
        IF jsonb_typeof(value) IS DISTINCT FROM 'object' THEN
          RAISE EXCEPTION 'Invalid source publication binding' USING ERRCODE='23514';
        END IF;
        IF (SELECT array_agg(key ORDER BY key) FROM jsonb_object_keys(value) key)
          IS DISTINCT FROM ARRAY['attempt_id','descriptor_sha256','schema']
          OR value->>'schema' IS DISTINCT FROM 'koinon.source-publication-binding.v1'
          OR jsonb_typeof(value->'attempt_id') IS DISTINCT FROM 'string'
          OR length(value->>'attempt_id') NOT BETWEEN 1 AND 64
          OR jsonb_typeof(value->'descriptor_sha256') IS DISTINCT FROM 'string'
          OR NOT coalesce(value->>'descriptor_sha256' ~ '^[0-9a-f]{64}$',false)
        THEN RAISE EXCEPTION 'Invalid source publication binding' USING ERRCODE='23514'; END IF;
        RETURN NEW;
      END $$""")
    op.execute("REVOKE ALL ON FUNCTION public.koinon_canon_publication_binding_guard() FROM PUBLIC")
    op.execute(
        "CREATE TRIGGER canon_publication_binding BEFORE INSERT ON public.canon_source_versions "
        "FOR EACH ROW EXECUTE FUNCTION public.koinon_canon_publication_binding_guard()"
    )


def downgrade():
    raise RuntimeError("Retain source publication binding; use a reviewed forward migration")
