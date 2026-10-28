# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Product-only immutable original/extraction ledger; no standalone schema change."""

from alembic import op

revision = "0020_source_lineage"
down_revision = "0019_curated_knowledge"


def upgrade():
    op.execute("""
CREATE TABLE canon_source_artifacts (
	id VARCHAR(36) NOT NULL, 
	tenant_id VARCHAR(64) NOT NULL, 
	workspace_id VARCHAR(64) NOT NULL, 
	source_id VARCHAR(36) NOT NULL, 
	role VARCHAR(32) NOT NULL, 
	sha256 VARCHAR(64) NOT NULL, 
	bytes INTEGER NOT NULL, 
	media_type VARCHAR(128), 
	object_key VARCHAR(1024) NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (id, tenant_id, workspace_id, source_id)
);
CREATE TABLE canon_source_versions (
	id VARCHAR(36) NOT NULL, 
	tenant_id VARCHAR(64) NOT NULL, 
	workspace_id VARCHAR(64) NOT NULL, 
	source_id VARCHAR(36) NOT NULL, 
	artifact_id VARCHAR(36) NOT NULL, 
	logical_key VARCHAR(128) NOT NULL, 
	operation_id VARCHAR(128) NOT NULL, 
	filename VARCHAR(512), 
	media_type VARCHAR(128), 
	actor TEXT, 
	predecessor_id VARCHAR(36), 
	expected_extraction_id VARCHAR(36), 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (tenant_id, workspace_id, operation_id), 
	UNIQUE (id, tenant_id, workspace_id, source_id)
);
CREATE TABLE canon_source_extractions (
	id VARCHAR(36) NOT NULL, 
	tenant_id VARCHAR(64) NOT NULL, 
	workspace_id VARCHAR(64) NOT NULL, 
	source_id VARCHAR(36) NOT NULL, 
	version_id VARCHAR(36) NOT NULL, 
	purpose VARCHAR(32) NOT NULL, 
	normalized_artifact_id VARCHAR(36) NOT NULL, 
	predecessor_id VARCHAR(36), 
	implementation JSON NOT NULL, 
	coverage VARCHAR(32) NOT NULL, 
	projection JSON NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (id, tenant_id, workspace_id, source_id)
);
CREATE TABLE canon_source_parts (
	id VARCHAR(36) NOT NULL, 
	tenant_id VARCHAR(64) NOT NULL, 
	workspace_id VARCHAR(64) NOT NULL, 
	source_id VARCHAR(36) NOT NULL, 
	extraction_id VARCHAR(36) NOT NULL, 
	artifact_id VARCHAR(36), 
	kind VARCHAR(32) NOT NULL, 
	parent_id VARCHAR(36), 
	ordinal INTEGER NOT NULL, 
	text TEXT NOT NULL, 
	sha256 VARCHAR(64) NOT NULL, 
	page INTEGER, 
	section_path JSON, 
	char_start INTEGER, 
	char_end INTEGER, 
	offset_basis VARCHAR(64), 
	projection_chunk_id VARCHAR(36), 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (id, tenant_id, workspace_id, source_id), 
	FOREIGN KEY(extraction_id, tenant_id, workspace_id, source_id) REFERENCES canon_source_extractions (id,
        tenant_id, workspace_id, source_id), 
	FOREIGN KEY(artifact_id, tenant_id, workspace_id, source_id) REFERENCES canon_source_artifacts (id,
        tenant_id, workspace_id, source_id), 
	FOREIGN KEY(parent_id, tenant_id, workspace_id, source_id) REFERENCES canon_source_parts (id,
        tenant_id, workspace_id, source_id)
);
CREATE TABLE canon_source_transform_steps (
	id VARCHAR(36) NOT NULL, 
	tenant_id VARCHAR(64) NOT NULL, 
	workspace_id VARCHAR(64) NOT NULL, 
	source_id VARCHAR(36) NOT NULL, 
	extraction_id VARCHAR(36) NOT NULL, 
	ordinal INTEGER NOT NULL, 
	stage VARCHAR(64) NOT NULL, 
	input_artifact_id VARCHAR(36) NOT NULL, 
	output_artifact_id VARCHAR(36) NOT NULL, 
	implementation JSON NOT NULL, 
	parameters JSON NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (id, tenant_id, workspace_id, source_id), 
	FOREIGN KEY(extraction_id, tenant_id, workspace_id, source_id) REFERENCES canon_source_extractions (id,
        tenant_id, workspace_id, source_id), 
	FOREIGN KEY(input_artifact_id, tenant_id, workspace_id, source_id) REFERENCES canon_source_artifacts
        (id, tenant_id, workspace_id, source_id), 
	FOREIGN KEY(output_artifact_id, tenant_id, workspace_id, source_id) REFERENCES canon_source_artifacts
        (id, tenant_id, workspace_id, source_id)
);
CREATE TABLE canon_source_lineage_events (
	id VARCHAR(36) NOT NULL, 
	tenant_id VARCHAR(64) NOT NULL, 
	workspace_id VARCHAR(64) NOT NULL, 
	source_id VARCHAR(36) NOT NULL, 
	version_id VARCHAR(36) NOT NULL, 
	extraction_id VARCHAR(36), 
	status VARCHAR(32) NOT NULL, 
	reason_code VARCHAR(64), 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (id, tenant_id, workspace_id, source_id), 
	FOREIGN KEY(version_id, tenant_id, workspace_id, source_id) REFERENCES canon_source_versions (id,
        tenant_id, workspace_id, source_id), 
	FOREIGN KEY(extraction_id, tenant_id, workspace_id, source_id) REFERENCES canon_source_extractions (id,
        tenant_id, workspace_id, source_id)
);
CREATE TABLE canon_source_heads (
	tenant_id VARCHAR(64) NOT NULL, 
	workspace_id VARCHAR(64) NOT NULL, 
	source_id VARCHAR(36) NOT NULL, 
	logical_key VARCHAR(128) NOT NULL, 
	version_id VARCHAR(36), 
	extraction_id VARCHAR(36), 
	UNIQUE (tenant_id, workspace_id, source_id), 
	UNIQUE (tenant_id, workspace_id, logical_key), 
	FOREIGN KEY(version_id, tenant_id, workspace_id, source_id) REFERENCES canon_source_versions (id,
        tenant_id, workspace_id, source_id), 
	FOREIGN KEY(extraction_id, tenant_id, workspace_id, source_id) REFERENCES canon_source_extractions (id,
        tenant_id, workspace_id, source_id)
);
ALTER TABLE canon_source_extractions ADD FOREIGN KEY(normalized_artifact_id, tenant_id, workspace_id,
        source_id) REFERENCES canon_source_artifacts (id, tenant_id, workspace_id, source_id);
ALTER TABLE canon_source_extractions ADD FOREIGN KEY(predecessor_id, tenant_id, workspace_id, source_id)
        REFERENCES canon_source_extractions (id, tenant_id, workspace_id, source_id);
ALTER TABLE canon_source_extractions ADD FOREIGN KEY(version_id, tenant_id, workspace_id, source_id)
        REFERENCES canon_source_versions (id, tenant_id, workspace_id, source_id);
ALTER TABLE canon_source_versions ADD FOREIGN KEY(artifact_id, tenant_id, workspace_id, source_id)
        REFERENCES canon_source_artifacts (id, tenant_id, workspace_id, source_id);
ALTER TABLE canon_source_versions ADD FOREIGN KEY(expected_extraction_id, tenant_id, workspace_id,
        source_id) REFERENCES canon_source_extractions (id, tenant_id, workspace_id, source_id);
ALTER TABLE canon_source_versions ADD FOREIGN KEY(predecessor_id, tenant_id, workspace_id, source_id)
        REFERENCES canon_source_versions (id, tenant_id, workspace_id, source_id);
    """)
    # Normalized equality is not logical document identity. Standalone0017
    # retains its original index; only the reviewed product graph evolves it.
    op.execute("DROP INDEX public.uq_canon_sources_tenant_workspace_content_sha256")
    op.execute(
        "CREATE INDEX ix_canon_sources_normalized_lineage "
        "ON public.canon_sources(tenant_id,workspace_id,content_sha256)"
    )
    op.execute("""
      CREATE FUNCTION public.koinon_document_lineage_immutable() RETURNS trigger
      LANGUAGE plpgsql SET search_path=pg_catalog AS $$ BEGIN
        RAISE EXCEPTION 'Document lineage records are immutable' USING ERRCODE='55000';
      END $$;
      CREATE FUNCTION public.koinon_document_head_guard() RETURNS trigger
      LANGUAGE plpgsql SET search_path=pg_catalog AS $$ BEGIN
        IF TG_OP='DELETE' THEN
          RAISE EXCEPTION 'Document identity cannot be deleted' USING ERRCODE='55000';
        END IF;
        IF (TG_OP='UPDATE' AND (NEW.tenant_id,NEW.workspace_id,NEW.source_id,NEW.logical_key)
          IS DISTINCT FROM (OLD.tenant_id,OLD.workspace_id,OLD.source_id,OLD.logical_key))
          OR (NEW.version_id IS NULL) IS DISTINCT FROM (NEW.extraction_id IS NULL) THEN
          RAISE EXCEPTION 'Document identity or head coherence changed' USING ERRCODE='55000';
        END IF;
        IF NEW.extraction_id IS NOT NULL AND NOT EXISTS (
          SELECT 1 FROM public.canon_source_extractions e WHERE e.id=NEW.extraction_id
          AND e.version_id=NEW.version_id AND e.tenant_id=NEW.tenant_id
          AND e.workspace_id=NEW.workspace_id AND e.source_id=NEW.source_id
          AND e.purpose='ingestion') THEN
          RAISE EXCEPTION 'Document head requires its exact committed extraction' USING ERRCODE='55000';
        END IF;
        RETURN NEW;
      END $$;
    """)
    for name in (
        "canon_source_artifacts",
        "canon_source_versions",
        "canon_source_extractions",
        "canon_source_parts",
        "canon_source_transform_steps",
        "canon_source_lineage_events",
        "canon_source_heads",
    ):
        op.execute(f"REVOKE ALL ON public.{name} FROM PUBLIC")
        op.execute(f"ALTER TABLE public.{name} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE public.{name} FORCE ROW LEVEL SECURITY")
        op.execute(f"""CREATE POLICY {name}_scope ON public.{name}
          USING(tenant_id=current_setting('app.tenant_id',true) AND
        workspace_id=current_setting('app.workspace_id',true))
          WITH CHECK(tenant_id=current_setting('app.tenant_id',true) AND
        workspace_id=current_setting('app.workspace_id',true))""")
        function = (
            "koinon_document_head_guard"
            if name == "canon_source_heads"
            else "koinon_document_lineage_immutable"
        )
        operations = "INSERT OR UPDATE OR DELETE" if name == "canon_source_heads" else "UPDATE OR DELETE"
        op.execute(
            f"CREATE TRIGGER {name}_immutable BEFORE {operations} ON public.{name} "
            f"FOR EACH ROW EXECUTE FUNCTION public.{function}()"
        )
        privileges = "SELECT,INSERT,UPDATE" if name == "canon_source_heads" else "SELECT,INSERT"
        # Preserve existing deployment role identities; no new login/grant beyond
        # the source runtime's existing data readers/writers is introduced.
        op.execute(f"""DO $$ DECLARE runtime_role record; BEGIN
          FOR runtime_role IN SELECT DISTINCT r.rolname FROM pg_class c
            CROSS JOIN LATERAL aclexplode(c.relacl) a JOIN pg_roles r ON r.oid=a.grantee
            WHERE c.oid='public.canon_sources'::regclass AND a.grantee<>c.relowner
            AND a.privilege_type='INSERT'
          LOOP
            EXECUTE format('REVOKE ALL ON public.{name} FROM %I',runtime_role.rolname);
            EXECUTE format('GRANT {privileges} ON public.{name} TO %I',runtime_role.rolname);
          END LOOP;
        END $$""")
    for function in ("koinon_document_lineage_immutable", "koinon_document_head_guard"):
        op.execute(f"REVOKE ALL ON FUNCTION public.{function}() FROM PUBLIC")


def downgrade():
    raise RuntimeError("Immutable source history cannot be removed by automatic downgrade")
