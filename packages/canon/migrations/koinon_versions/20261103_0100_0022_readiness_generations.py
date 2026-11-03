# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Fence document readiness with transactional generations and coalesced changes."""

from alembic import op

revision = "0022_readiness_generations"
down_revision = "0021_pinned_originals"
branch_labels = None
depends_on = None

SCOPED_TABLES = (
    "canon_sources",
    "canon_chunks",
    "canon_embedding_sets",
    "canon_source_heads",
    "canon_source_artifacts",
    "canon_source_versions",
    "canon_source_extractions",
    "canon_source_parts",
    "canon_source_transform_steps",
    "canon_source_lineage_events",
    "canon_knowledge_items",
    "canon_knowledge_versions",
    "canon_curated_heads",
    "canon_knowledge_commits",
    "canon_knowledge_version_evidence",
    "canon_knowledge_version_chunks",
    "canon_citations",
)

FUNCTIONS = r"""
CREATE FUNCTION public.koinon_bump_canon_readiness(p_tenant text,p_workspaces text[])
RETURNS void LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $body$
DECLARE next_generation bigint;
BEGIN
 IF p_tenant IS NULL OR p_tenant='' OR p_workspaces IS NULL OR cardinality(p_workspaces)=0
    OR array_position(p_workspaces,NULL) IS NOT NULL THEN
   RAISE EXCEPTION 'Readiness mutation needs an exact native scope' USING ERRCODE='22023';
 END IF;
 INSERT INTO public.canon_readiness_generations(tenant_id,generation,last_transaction)
 VALUES(p_tenant,1,pg_current_xact_id())
 ON CONFLICT(tenant_id) DO UPDATE SET generation=public.canon_readiness_generations.generation+1,
 last_transaction=EXCLUDED.last_transaction
 RETURNING generation INTO next_generation;
 INSERT INTO public.canon_readiness_changes(tenant_id,workspace_id,generation)
 SELECT p_tenant,workspace,next_generation FROM (SELECT DISTINCT unnest(p_workspaces) AS workspace) s
 ON CONFLICT(tenant_id,workspace_id) DO UPDATE SET generation=EXCLUDED.generation;
END;
$body$;
REVOKE ALL ON FUNCTION public.koinon_bump_canon_readiness(text,text[]) FROM PUBLIC;

CREATE FUNCTION public.koinon_assert_canon_readiness_open()
RETURNS void LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $body$
BEGIN
 IF EXISTS(SELECT 1 FROM public.canon_readiness_generations
           WHERE last_transaction=pg_current_xact_id_if_assigned()) THEN
   RAISE EXCEPTION 'Native readiness was sealed; start a new transaction before further writes'
     USING ERRCODE='25000';
 END IF;
END;
$body$;
REVOKE ALL ON FUNCTION public.koinon_assert_canon_readiness_open() FROM PUBLIC;

CREATE FUNCTION public.koinon_guard_canon_readiness()
RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $body$
BEGIN
 PERFORM public.koinon_assert_canon_readiness_open();
 RETURN NULL;
END;
$body$;
REVOKE ALL ON FUNCTION public.koinon_guard_canon_readiness() FROM PUBLIC;

CREATE FUNCTION public.koinon_queue_canon_readiness(p_tenant text,p_workspaces text[])
RETURNS void LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $body$
BEGIN
 PERFORM public.koinon_assert_canon_readiness_open();
 INSERT INTO public.canon_readiness_pending(transaction_id,tenant_id,workspace_id)
 SELECT pg_current_xact_id(),p_tenant,workspace FROM (SELECT DISTINCT unnest(p_workspaces) AS workspace) s
 ON CONFLICT(transaction_id,tenant_id,workspace_id) DO NOTHING;
END;
$body$;
REVOKE ALL ON FUNCTION public.koinon_queue_canon_readiness(text,text[]) FROM PUBLIC;

CREATE FUNCTION public.koinon_finish_canon_readiness()
RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $body$
DECLARE affected record;
BEGIN
 FOR affected IN SELECT tenant_id,array_agg(workspace_id ORDER BY workspace_id) AS workspaces
     FROM public.canon_readiness_pending WHERE transaction_id=NEW.transaction_id
     GROUP BY tenant_id ORDER BY tenant_id
 LOOP
   PERFORM public.koinon_bump_canon_readiness(affected.tenant_id,affected.workspaces);
 END LOOP;
 DELETE FROM public.canon_readiness_pending WHERE transaction_id=NEW.transaction_id;
 RETURN NULL;
END;
$body$;
REVOKE ALL ON FUNCTION public.koinon_finish_canon_readiness() FROM PUBLIC;
CREATE CONSTRAINT TRIGGER readiness_commit AFTER INSERT ON public.canon_readiness_pending
 DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION public.koinon_finish_canon_readiness();

CREATE FUNCTION public.koinon_ensure_canon_readiness(p_tenant text)
RETURNS void LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $body$
BEGIN
 PERFORM public.koinon_assert_canon_readiness_open();
 IF p_tenant IS NULL OR p_tenant='' OR current_setting('app.tenant_id',true) IS DISTINCT FROM p_tenant THEN
   RAISE EXCEPTION 'Matching native tenant required' USING ERRCODE='42501';
 END IF;
 IF EXISTS(SELECT 1 FROM public.canon_readiness_pending
           WHERE transaction_id=pg_current_xact_id_if_assigned() AND tenant_id=p_tenant) THEN
   RAISE EXCEPTION 'Capture readiness outside a pending native write transaction' USING ERRCODE='25000';
 END IF;
 INSERT INTO public.canon_readiness_generations(tenant_id,generation) VALUES(p_tenant,0)
 ON CONFLICT(tenant_id) DO NOTHING;
END;
$body$;
REVOKE ALL ON FUNCTION public.koinon_ensure_canon_readiness(text) FROM PUBLIC;

CREATE FUNCTION public.koinon_capture_canon_readiness()
RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $body$
DECLARE rows_sql text; scopes_sql text; affected record;
BEGIN
 IF TG_OP='TRUNCATE' THEN
   RAISE EXCEPTION 'Use scoped DELETE to preserve native readiness generations' USING ERRCODE='0A000';
 END IF;
 rows_sql := CASE TG_OP
   WHEN 'INSERT' THEN 'SELECT * FROM readiness_new'
   WHEN 'DELETE' THEN 'SELECT * FROM readiness_old'
   WHEN 'UPDATE' THEN 'SELECT * FROM readiness_old UNION ALL SELECT * FROM readiness_new'
 END;
 IF TG_ARGV[0]='vector' THEN
   EXECUTE 'SELECT EXISTS(SELECT 1 FROM (' || rows_sql ||
     ') r WHERE namespace IS NULL OR namespace !~ ''^t/[^/]+/w/[^/]+$'')' INTO affected;
   IF affected.exists THEN
     RAISE EXCEPTION 'Invalid vector namespace for readiness mutation' USING ERRCODE='22023';
   END IF;
   scopes_sql := 'SELECT split_part(namespace,''/'',2) AS tenant_id,' ||
                 'split_part(namespace,''/'',4) AS workspace_id FROM (' || rows_sql || ') r';
 ELSE
   scopes_sql := 'SELECT tenant_id::text AS tenant_id,' ||
     CASE WHEN TG_ARGV[0]='workspace' THEN 'id' ELSE 'workspace_id' END ||
     '::text AS workspace_id FROM (' || rows_sql || ') r';
 END IF;
 FOR affected IN EXECUTE 'SELECT tenant_id,array_agg(DISTINCT workspace_id) AS workspaces FROM (' ||
     scopes_sql || ') s GROUP BY tenant_id ORDER BY tenant_id'
 LOOP
   PERFORM public.koinon_queue_canon_readiness(affected.tenant_id,affected.workspaces);
 END LOOP;
 RETURN NULL;
END;
$body$;
REVOKE ALL ON FUNCTION public.koinon_capture_canon_readiness() FROM PUBLIC;

CREATE FUNCTION public.koinon_check_vector_readiness_owner()
RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $body$
BEGIN
 IF NOT EXISTS(SELECT 1 FROM public.canon_embedding_sets s WHERE s.id=NEW.set_id
     AND NEW.namespace='t/' || s.tenant_id || '/w/' || s.workspace_id) THEN
   RAISE EXCEPTION 'Vector namespace must match its embedding set owner' USING ERRCODE='42501';
 END IF;
 RETURN NEW;
END;
$body$;
REVOKE ALL ON FUNCTION public.koinon_check_vector_readiness_owner() FROM PUBLIC;
CREATE TRIGGER readiness_vector_owner BEFORE INSERT OR UPDATE ON public.canon_chunk_vectors
 FOR EACH ROW EXECUTE FUNCTION public.koinon_check_vector_readiness_owner();

CREATE FUNCTION public.koinon_fence_document_index(p_tenant text,p_workspace text,p_set text)
RETURNS void LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $body$
BEGIN
 IF p_tenant IS NULL OR p_workspace IS NULL OR p_tenant='' OR p_workspace=''
    OR current_setting('app.tenant_id',true) IS DISTINCT FROM p_tenant
    OR current_setting('app.workspace_id',true) IS DISTINCT FROM p_workspace
    OR NOT EXISTS(SELECT 1 FROM public.canon_embedding_sets
                  WHERE id=p_set AND tenant_id=p_tenant AND workspace_id=p_workspace) THEN
   RAISE EXCEPTION 'Matching native index owner required' USING ERRCODE='42501';
 END IF;
 PERFORM public.koinon_queue_canon_readiness(p_tenant,ARRAY[p_workspace]);
END;
$body$;
REVOKE ALL ON FUNCTION public.koinon_fence_document_index(text,text,text) FROM PUBLIC;
"""


def upgrade():
    op.execute("""
      DO $body$
      BEGIN
        IF EXISTS(SELECT 1 FROM public.canon_chunk_vectors v
          WHERE NOT EXISTS(SELECT 1 FROM public.canon_embedding_sets s
            WHERE s.id=v.set_id AND v.namespace='t/' || s.tenant_id || '/w/' || s.workspace_id)) THEN
          RAISE EXCEPTION 'Review vector ownership before installing readiness generations';
        END IF;
      END;
      $body$;
    """)
    op.execute("""
      CREATE TABLE public.canon_readiness_generations(
        tenant_id text PRIMARY KEY, generation bigint NOT NULL CHECK(generation>=0),
        fence integer NOT NULL DEFAULT 0, last_transaction xid8
      );
      CREATE INDEX ix_canon_readiness_last_transaction
        ON public.canon_readiness_generations(last_transaction);
      CREATE TABLE public.canon_readiness_pending(
        transaction_id xid8 NOT NULL,tenant_id text NOT NULL,workspace_id text NOT NULL,
        PRIMARY KEY(transaction_id,tenant_id,workspace_id)
      );
      REVOKE ALL ON public.canon_readiness_pending FROM PUBLIC;
      CREATE TABLE public.canon_readiness_changes(
        tenant_id text NOT NULL,workspace_id text NOT NULL,generation bigint NOT NULL CHECK(generation>=0),
        PRIMARY KEY(tenant_id,workspace_id)
      );
      CREATE INDEX ix_canon_readiness_changes_cursor
        ON public.canon_readiness_changes(tenant_id,generation,workspace_id);
    """)
    for table in ("canon_readiness_generations", "canon_readiness_changes"):
        # Only these metadata tables allow their owner-installed trigger functions to bypass RLS.
        op.execute(f"ALTER TABLE public.{table} ENABLE ROW LEVEL SECURITY")
        op.execute(
            f"CREATE POLICY tenant_readiness ON public.{table} "
            "USING(tenant_id=current_setting('app.tenant_id',true))"
        )
        op.execute(f"REVOKE ALL ON public.{table} FROM PUBLIC")
    op.execute(FUNCTIONS)
    for table, kind in [
        *((table, "scoped") for table in SCOPED_TABLES),
        ("canon_workspaces", "workspace"),
        ("canon_chunk_vectors", "vector"),
    ]:
        op.execute(
            f"CREATE TRIGGER readiness_open BEFORE INSERT OR UPDATE OR DELETE OR TRUNCATE "
            f"ON public.{table} FOR EACH STATEMENT EXECUTE FUNCTION public.koinon_guard_canon_readiness()"
        )
        for operation, aliases in (
            ("INSERT", "NEW TABLE AS readiness_new"),
            ("UPDATE", "OLD TABLE AS readiness_old NEW TABLE AS readiness_new"),
            ("DELETE", "OLD TABLE AS readiness_old"),
        ):
            op.execute(
                f"CREATE TRIGGER readiness_{operation.lower()} AFTER {operation} ON public.{table} "
                f"REFERENCING {aliases} FOR EACH STATEMENT "
                f"EXECUTE FUNCTION public.koinon_capture_canon_readiness('{kind}')"
            )
        op.execute(
            f"CREATE TRIGGER readiness_truncate BEFORE TRUNCATE ON public.{table} "
            f"FOR EACH STATEMENT EXECUTE FUNCTION public.koinon_capture_canon_readiness('{kind}')"
        )
    op.execute("""
      INSERT INTO public.canon_readiness_generations(tenant_id,generation)
        SELECT DISTINCT tenant_id,1 FROM public.canon_workspaces;
      INSERT INTO public.canon_readiness_changes(tenant_id,workspace_id,generation)
        SELECT tenant_id,id,1 FROM public.canon_workspaces;
    """)
    # Preserve the reviewed narrow provisioning function and its existing ACL/OID.
    op.execute(r"""
      DO $body$
      DECLARE definition text; marker text := 'EXECUTE pg_catalog.format(';
      BEGIN
        SELECT pg_get_functiondef('public.koinon_provision_document_index(text,text,text)'::regprocedure)
          INTO definition;
        IF position(marker IN definition)=0 THEN
          RAISE EXCEPTION 'Document provisioning function requires review before readiness migration';
        END IF;
        definition := replace(definition,E'\nBEGIN\n',
          E'\nBEGIN\n PERFORM public.koinon_assert_canon_readiness_open();\n');
        definition := replace(definition,marker,
          'PERFORM public.koinon_fence_document_index(p_tenant,p_workspace,p_set); ' || marker);
        EXECUTE definition;
      END;
      $body$;
    """)


def downgrade():
    raise RuntimeError("Use a reviewed recovery plan; readiness generations must not be reset")
