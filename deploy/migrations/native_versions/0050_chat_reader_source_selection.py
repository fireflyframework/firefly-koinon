# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Retain the exact reader selection for each queued assistant run.

The nullable expansion and guards commit together under a bounded lock. Existing
NULL selections remain local-only; no saved defaults are invented. On failure,
retry the forward migration. Roll back application code without dropping retained
selections; any schema correction belongs in another forward migration.
"""

from alembic import op

revision = "koinon_0050_reader_selection"
down_revision = "koinon_0049_source_folders"


def upgrade():
    if op.get_bind().dialect.name != "postgresql":
        raise RuntimeError("Queued reader selections require PostgreSQL")
    op.execute("SET LOCAL lock_timeout='5s'")
    op.execute(
        "ALTER TABLE public.koinon_chat_runs ADD COLUMN reader_source_selection json"
    )
    op.execute("""CREATE FUNCTION public.koinon_chat_reader_selection_guard() RETURNS trigger
        LANGUAGE plpgsql SET search_path=pg_catalog AS $$
        DECLARE
          selection json;
          choice json;
          field_count integer;
          distinct_fields integer;
          choice_count integer;
          selection_mode text;
        BEGIN
          IF TG_OP='UPDATE' THEN
            RAISE EXCEPTION 'retained reader selection is immutable' USING ERRCODE='23514';
          END IF;
          selection := NEW.reader_source_selection;
          IF selection IS NULL THEN
            RETURN NEW;
          END IF;
          IF json_typeof(selection) IS DISTINCT FROM 'object'
             OR octet_length(convert_to(selection::text,'UTF8'))>131072 THEN
            RAISE EXCEPTION 'invalid reader selection object or size' USING ERRCODE='23514';
          END IF;
          SELECT count(*),count(DISTINCT key) INTO field_count,distinct_fields
            FROM json_each(selection);
          IF field_count<>4 OR distinct_fields<>4
             OR EXISTS (SELECT 1 FROM json_each(selection)
                        WHERE key NOT IN ('version','mode','revision','connections'))
             OR json_typeof(selection->'version') IS DISTINCT FROM 'number'
             OR (selection->'version')::text IS DISTINCT FROM '1'
             OR json_typeof(selection->'mode') IS DISTINCT FROM 'string'
             OR json_typeof(selection->'connections') IS DISTINCT FROM 'array' THEN
            RAISE EXCEPTION 'invalid reader selection shape' USING ERRCODE='23514';
          END IF;
          selection_mode := selection->>'mode';
          choice_count := json_array_length(selection->'connections');
          IF choice_count>100 OR selection_mode NOT IN ('saved','explicit','local_only') THEN
            RAISE EXCEPTION 'invalid reader selection mode or count' USING ERRCODE='23514';
          END IF;
          IF selection_mode='saved' THEN
            IF json_typeof(selection->'revision') IS DISTINCT FROM 'number'
               OR (selection->'revision')::text !~ '^(0|[1-9][0-9]*)$' THEN
              RAISE EXCEPTION 'invalid saved reader revision' USING ERRCODE='23514';
            END IF;
          ELSIF json_typeof(selection->'revision') IS DISTINCT FROM 'null'
             OR (selection_mode='explicit' AND choice_count=0)
             OR (selection_mode='local_only' AND choice_count<>0) THEN
            RAISE EXCEPTION 'invalid explicit or local reader selection' USING ERRCODE='23514';
          END IF;
          FOR choice IN SELECT value FROM json_array_elements(selection->'connections') LOOP
            IF json_typeof(choice) IS DISTINCT FROM 'object' THEN
              RAISE EXCEPTION 'invalid reader connection object' USING ERRCODE='23514';
            END IF;
            SELECT count(*),count(DISTINCT key) INTO field_count,distinct_fields
              FROM json_each(choice);
            IF field_count NOT IN (2,3) OR field_count<>distinct_fields
               OR EXISTS (SELECT 1 FROM json_each(choice)
                          WHERE key NOT IN ('provider','external_tenant','connection_id'))
               OR json_typeof(choice->'provider') IS DISTINCT FROM 'string'
               OR choice->>'provider' NOT IN ('sharepoint','onedrive','google_drive')
               OR json_typeof(choice->'connection_id') IS DISTINCT FROM 'string'
               OR length(choice->>'connection_id') NOT BETWEEN 1 AND 64
               OR (choice->'external_tenant' IS NOT NULL
                   AND json_typeof(choice->'external_tenant')<>'null'
                   AND (json_typeof(choice->'external_tenant')<>'string'
                        OR length(choice->>'external_tenant') NOT BETWEEN 1 AND 1024)) THEN
              RAISE EXCEPTION 'invalid reader connection fields' USING ERRCODE='23514';
            END IF;
          END LOOP;
          IF EXISTS (
            SELECT 1 FROM json_array_elements(selection->'connections') AS choices(value)
            GROUP BY value->>'provider',value->>'external_tenant' HAVING count(*)>1
          ) THEN
            RAISE EXCEPTION 'duplicate reader connection provider and tenant' USING ERRCODE='23514';
          END IF;
          RETURN NEW;
        END $$""")
    op.execute(
        "REVOKE ALL ON FUNCTION public.koinon_chat_reader_selection_guard() FROM PUBLIC"
    )
    op.execute("""CREATE TRIGGER koinon_chat_reader_selection_guard
        BEFORE INSERT OR UPDATE OF reader_source_selection ON public.koinon_chat_runs
        FOR EACH ROW EXECUTE FUNCTION public.koinon_chat_reader_selection_guard()""")


def downgrade():
    raise RuntimeError(
        "Retained reader selections require a forward migration; downgrade is unsupported"
    )
