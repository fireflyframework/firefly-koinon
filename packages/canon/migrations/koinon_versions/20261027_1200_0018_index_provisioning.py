# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Narrow owner-installed ANN provisioning; no runtime owner or DDL grants."""

from alembic import op

revision = "0018_index_provisioning"
down_revision = "0017_embedding_sets"

PROVISION_FUNCTION = r"""
CREATE FUNCTION public.koinon_provision_document_index(p_tenant text,p_workspace text,p_set text)
RETURNS text LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $body$
DECLARE
 target public.canon_embedding_sets%ROWTYPE;
 approval public.canon_index_provisions%ROWTYPE;
 index_name text; cast_type text; op_class text; actual record;
BEGIN
 IF p_tenant IS NULL OR p_workspace IS NULL OR p_set IS NULL
    OR p_tenant='' OR p_workspace='' OR p_set !~ '^es-[0-9a-f]{32}$'
    OR current_setting('app.tenant_id',true) IS DISTINCT FROM p_tenant
    OR current_setting('app.workspace_id',true) IS DISTINCT FROM p_workspace THEN
   RAISE EXCEPTION 'Matching registered native scope required' USING ERRCODE='42501';
 END IF;
 SELECT * INTO target FROM public.canon_embedding_sets
   WHERE tenant_id=p_tenant AND workspace_id=p_workspace AND id=p_set FOR SHARE;
 SELECT * INTO approval FROM public.canon_index_provisions
   WHERE tenant_id=p_tenant AND workspace_id=p_workspace AND set_id=p_set FOR SHARE;
 IF target.id IS NULL OR approval.set_id IS NULL OR target.dimensions<>approval.dimensions
    OR target.provider IS DISTINCT FROM approval.provider
    OR target.model IS DISTINCT FROM approval.model
    OR target.config_fingerprint IS DISTINCT FROM approval.native_fingerprint
    OR target.dimensions NOT BETWEEN 64 AND 4000
    OR target.status NOT IN ('building','ready','active','retired')
    OR NOT EXISTS(SELECT 1 FROM public.canon_workspaces w
                  WHERE w.tenant_id=p_tenant AND w.id=p_workspace) THEN
   RAISE EXCEPTION 'Registered embedding target unavailable or incompatible' USING ERRCODE='42501';
 END IF;
 index_name := 'canon_chunk_vectors_hnsw_' || replace(p_set,'-','_');
 cast_type := CASE WHEN target.dimensions>2000 THEN 'halfvec' ELSE 'vector' END;
 op_class := cast_type || '_cosine_ops';
 IF NOT EXISTS(SELECT 1 FROM pg_catalog.pg_class c JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace
               WHERE n.nspname='public' AND c.relname=index_name) THEN
   EXECUTE pg_catalog.format(
     'CREATE INDEX %I ON public.canon_chunk_vectors USING hnsw
      ((embedding::public.%I(%s)) public.%I) WITH(m=16,ef_construction=64) WHERE set_id=%L',
     index_name,cast_type,target.dimensions,op_class,p_set);
 END IF;
 SELECT i.indisvalid,i.indisready,i.indnkeyatts,i.indnatts,am.amname,opc.opcname,
        opn.nspname AS opschema,t.relname AS tablename,tn.nspname AS tableschema,
        pg_catalog.pg_get_expr(i.indexprs,i.indrelid) AS expression,
        pg_catalog.pg_get_expr(i.indpred,i.indrelid) AS predicate INTO actual
 FROM pg_catalog.pg_class c JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace
 JOIN pg_catalog.pg_index i ON i.indexrelid=c.oid
 JOIN pg_catalog.pg_class t ON t.oid=i.indrelid
 JOIN pg_catalog.pg_namespace tn ON tn.oid=t.relnamespace
 JOIN pg_catalog.pg_am am ON am.oid=c.relam
 JOIN pg_catalog.pg_opclass opc ON opc.oid=i.indclass[0]
 JOIN pg_catalog.pg_namespace opn ON opn.oid=opc.opcnamespace
 WHERE n.nspname='public' AND c.relname=index_name;
 IF actual IS NULL OR NOT actual.indisvalid OR NOT actual.indisready
    OR actual.indnkeyatts<>1 OR actual.indnatts<>1 OR actual.amname<>'hnsw'
    OR actual.opcname<>op_class OR actual.opschema<>'public'
    OR actual.tablename<>'canon_chunk_vectors' OR actual.tableschema<>'public'
    OR actual.expression IS DISTINCT FROM
       pg_catalog.format('(embedding)::public.%I(%s)',cast_type,target.dimensions)
    OR actual.predicate IS DISTINCT FROM pg_catalog.format('(set_id = %L::text)',p_set) THEN
   RAISE EXCEPTION 'Existing index differs from registered target' USING ERRCODE='55000';
 END IF;
 RETURN index_name;
END;
$body$;
"""


def upgrade():
    op.execute("""
      CREATE TABLE public.canon_index_provisions (
        set_id varchar(64) PRIMARY KEY REFERENCES public.canon_embedding_sets(id),
        tenant_id text NOT NULL,workspace_id text NOT NULL,index_id varchar(64) NOT NULL UNIQUE,
        dimensions integer NOT NULL CHECK(dimensions BETWEEN 64 AND 4000),
        embedding_fingerprint varchar(64) NOT NULL,provider varchar(64) NOT NULL,
        model varchar(256) NOT NULL,native_fingerprint varchar(64) NOT NULL,actor varchar(512) NOT NULL,
        created_at timestamptz NOT NULL DEFAULT now()
      )
    """)
    op.execute("ALTER TABLE public.canon_index_provisions ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE public.canon_index_provisions FORCE ROW LEVEL SECURITY")
    op.execute("""CREATE POLICY canon_index_provisions_scope ON public.canon_index_provisions
      USING(tenant_id=current_setting('app.tenant_id',true)
        AND workspace_id=current_setting('app.workspace_id',true))
      WITH CHECK(tenant_id=current_setting('app.tenant_id',true)
        AND workspace_id=current_setting('app.workspace_id',true))""")
    op.execute("REVOKE ALL ON public.canon_index_provisions FROM PUBLIC")
    op.execute(PROVISION_FUNCTION)
    op.execute("REVOKE ALL ON FUNCTION public.koinon_provision_document_index(text,text,text) FROM PUBLIC")


def downgrade():
    raise RuntimeError("Use a reviewed recovery plan; preserved indexes must not be dropped")
