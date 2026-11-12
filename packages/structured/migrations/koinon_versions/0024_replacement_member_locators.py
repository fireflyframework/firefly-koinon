# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Allow reviewed live members to reuse a removed member's historical locator.

Only replace the bounded plan-validation function; retained rows and trigger
bindings are untouched. Historical removal locators remain exact. Recovery is
another reviewed forward function replacement, never rewriting retained plans.
"""

from alembic import op

revision = "0024_replacement_member_locators"
down_revision = "0023_metadata_indexes"


def upgrade():
    if op.get_bind().dialect.name != "postgresql":
        raise RuntimeError("Dataset replacement requires PostgreSQL")
    op.execute("""CREATE OR REPLACE FUNCTION public.koinon_replacement_plan_guard() RETURNS trigger
        LANGUAGE plpgsql SET search_path=pg_catalog AS $$
        DECLARE plan jsonb; member jsonb; prior jsonb; n integer;
        BEGIN
          IF NEW.operation_kind<>'replace' OR NEW.plan_json IS NULL THEN RETURN NEW; END IF;
          plan=NEW.plan_json::jsonb;
          IF jsonb_typeof(plan) IS DISTINCT FROM 'array' OR jsonb_array_length(plan) NOT BETWEEN 1 AND 32
            OR (SELECT count(*) FROM jsonb_array_elements(plan) p WHERE p->>'action' IN ('retain','add'))
            NOT BETWEEN 1 AND 16
          THEN RAISE EXCEPTION 'invalid replacement member plan' USING ERRCODE='23514'; END IF;
          n=jsonb_array_length(plan);
          IF EXISTS(SELECT 1 FROM jsonb_array_elements(plan) p
              GROUP BY p->>'member_key', (p->>'action'='remove') HAVING count(*)>1)
            OR (SELECT count(DISTINCT p->>'table_id') FROM jsonb_array_elements(plan) p)<>n
            OR (SELECT count(DISTINCT p->>'catalog_table_id') FROM jsonb_array_elements(plan) p)<>n
          THEN RAISE EXCEPTION 'replacement plan identities must be unique' USING ERRCODE='23514'; END IF;
          FOR member IN SELECT value FROM jsonb_array_elements(plan) LOOP
            IF member->>'schema' IS DISTINCT FROM 'koinon.dataset-replacement-member.v1'
              OR NOT coalesce(member->>'action' IN ('retain','add','remove'),false)
              OR EXISTS(SELECT 1 FROM
              unnest(ARRAY['member_key','table_id','catalog_table_id','snapshot_id']) key
                WHERE jsonb_typeof(member->key) IS DISTINCT FROM 'string' OR length(member->>key) NOT
                BETWEEN 1 AND 2048)
            THEN RAISE EXCEPTION 'invalid replacement member plan' USING ERRCODE='23514'; END IF;
            SELECT p INTO prior FROM jsonb_array_elements(NEW.baseline_json::jsonb->'members') p
              WHERE p->>'table_id'=member->>'table_id';
            IF (member->>'action'='add' AND prior IS NOT NULL)
              OR (member->>'action' IN ('retain','remove') AND (prior IS NULL
                OR prior->>'catalog_table_id' IS DISTINCT FROM member->>'catalog_table_id'))
              OR (member->>'action'='retain' AND prior->>'snapshot_id'=member->>'snapshot_id')
              OR (member->>'action'='remove' AND (prior->>'snapshot_id' IS DISTINCT FROM
                member->>'snapshot_id' OR prior->>'member_key' IS DISTINCT FROM member->>'member_key'))
            THEN RAISE EXCEPTION 'replacement plan must preserve baseline identities' USING
            ERRCODE='23514'; END IF;
          END LOOP;
          IF EXISTS(SELECT 1 FROM jsonb_array_elements(NEW.baseline_json::jsonb->'members')
          baseline_member
            WHERE NOT EXISTS(SELECT 1 FROM jsonb_array_elements(plan) p
              WHERE p->>'table_id'=baseline_member->>'table_id' AND p->>'action' IN ('retain','remove')))
          THEN RAISE EXCEPTION 'replacement plan must cover the whole baseline' USING ERRCODE='23514';
          END IF;
          RETURN NEW;
        END $$""")


def downgrade():
    raise RuntimeError("Recover replacement member locators through a reviewed forward migration")
