# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Retain folder origins and detect canonical edits independently of wall clocks.

Concurrent supporting indexes are restart-safe. The constant-default expansion and
guards are one bounded-lock transaction. On failure retry this forward migration;
never remove retained provenance or reset canonical revisions.
"""

import sqlalchemy as sa
from alembic import op

revision = "koinon_0049_source_folders"
down_revision = "koinon_0048_source_recovery"


def upgrade():
    if op.get_bind().dialect.name != "postgresql":
        raise RuntimeError("Source folder publication requires PostgreSQL")
    indexes = {
        "uq_content_observation_publication": (
            "UNIQUE",
            "koinon_content_sync_observations(tenant_id,mapping_id,object_id,work_id,id)",
        ),
        "ix_content_folder_audit": (
            "",
            "lattice_audit(tenant_id,resource_id,subject) WHERE action='source.folder.published'",
        ),
    }
    with op.get_context().autocommit_block():
        op.execute("SET lock_timeout='5s'")
        try:
            for name, (kind, definition) in indexes.items():
                invalid = (
                    op.get_bind()
                    .execute(
                        sa.text("SELECT NOT indisvalid FROM pg_index WHERE indexrelid=to_regclass(:name)"),
                        {"name": "public." + name},
                    )
                    .scalar()
                )
                if invalid:
                    op.execute(f"DROP INDEX CONCURRENTLY public.{name}")
                op.execute(f"CREATE {kind} INDEX CONCURRENTLY IF NOT EXISTS {name} ON {definition}")
        finally:
            op.execute("RESET lock_timeout")
    op.execute("SET LOCAL lock_timeout='5s'")
    op.execute("ALTER TABLE lattice_catalog ADD COLUMN mutation_revision bigint NOT NULL DEFAULT 1")
    op.execute(
        "ALTER TABLE lattice_catalog ADD CONSTRAINT ck_catalog_mutation_revision "
        "CHECK(mutation_revision>0) NOT VALID"
    )
    op.execute("""CREATE FUNCTION public.koinon_catalog_revision_guard() RETURNS trigger
        LANGUAGE plpgsql SET search_path=pg_catalog AS $$
        BEGIN
          IF TG_OP='INSERT' THEN
            IF NEW.mutation_revision IS DISTINCT FROM 1 THEN
              RAISE EXCEPTION 'canonical revision is database owned' USING ERRCODE='23514';
            END IF;
          ELSE
            IF NEW.mutation_revision IS DISTINCT FROM OLD.mutation_revision THEN
              RAISE EXCEPTION 'canonical revision is database owned' USING ERRCODE='23514';
            END IF;
            NEW.mutation_revision=OLD.mutation_revision+1;
          END IF;
          RETURN NEW;
        END $$""")
    op.execute(
        "CREATE TRIGGER guard_catalog_revision BEFORE INSERT OR UPDATE ON lattice_catalog "
        "FOR EACH ROW EXECUTE FUNCTION public.koinon_catalog_revision_guard()"
    )
    op.execute("""CREATE TABLE koinon_content_folder_publications (
        id varchar(64) PRIMARY KEY, tenant_id varchar(64) NOT NULL,
        mapping_id varchar(64) NOT NULL, object_id varchar(64) NOT NULL,
        observation_id varchar(64) NOT NULL, work_id varchar(64) NOT NULL,
        local_folder_id varchar(64) NOT NULL REFERENCES lattice_catalog(id),
        local_parent_id varchar(64) NOT NULL REFERENCES lattice_catalog(id),
        canonical_revision bigint NOT NULL CONSTRAINT ck_content_folder_revision CHECK(canonical_revision>0),
        canonical_sha256 varchar(64) NOT NULL CHECK(canonical_sha256 ~ '^[0-9a-f]{64}$'),
        previous_publication_id varchar(64) REFERENCES koinon_content_folder_publications(id),
        created_at timestamptz NOT NULL,
        FOREIGN KEY(tenant_id,mapping_id,object_id) REFERENCES
          koinon_content_objects(tenant_id,mapping_id,id),
        FOREIGN KEY(tenant_id,mapping_id,object_id,work_id,observation_id) REFERENCES
          koinon_content_sync_observations(tenant_id,mapping_id,object_id,work_id,id),
        CONSTRAINT uq_content_folder_observation UNIQUE(tenant_id,mapping_id,object_id,observation_id),
        CONSTRAINT uq_content_folder_revision UNIQUE(local_folder_id,canonical_revision),
        CONSTRAINT uq_content_folder_successor UNIQUE(previous_publication_id)
    )""")
    for name, definition in {
        "ix_content_folder_publication_history": "(tenant_id,local_folder_id,canonical_revision)",
        "ix_content_folder_publication_parent": "(local_parent_id)",
        "ix_content_folder_publication_observation": "(observation_id)",
        "ix_content_folder_publication_work": "(work_id)",
    }.items():
        op.execute(f"CREATE INDEX {name} ON koinon_content_folder_publications{definition}")
    op.execute(
        "CREATE UNIQUE INDEX uq_content_folder_initial ON "
        "koinon_content_folder_publications(local_folder_id) WHERE previous_publication_id IS NULL"
    )
    op.execute("REVOKE ALL ON koinon_content_folder_publications FROM PUBLIC")
    _publication_guard()
    _completion_guard()
    op.execute(
        "REVOKE ALL ON FUNCTION public.koinon_catalog_revision_guard(),"
        "public.koinon_folder_publication_guard(),public.koinon_folder_publication_complete() FROM PUBLIC"
    )


def _publication_guard():
    op.execute("""CREATE FUNCTION public.koinon_folder_publication_guard() RETURNS trigger
        LANGUAGE plpgsql SET search_path=pg_catalog,public AS $$
        DECLARE c public.lattice_catalog; m public.koinon_content_mappings;
          o public.koinon_content_objects; observation public.koinon_content_sync_observations;
          previous public.koinon_content_folder_publications; inserted_here boolean;
        BEGIN
          IF TG_OP<>'INSERT' THEN
            RAISE EXCEPTION 'folder publications are immutable' USING ERRCODE='23514';
          END IF;
          SELECT * INTO c FROM public.lattice_catalog WHERE id=NEW.local_folder_id FOR UPDATE;
          SELECT * INTO m FROM public.koinon_content_mappings
            WHERE id=NEW.mapping_id AND tenant_id=NEW.tenant_id;
          SELECT * INTO o FROM public.koinon_content_objects
            WHERE id=NEW.object_id AND tenant_id=NEW.tenant_id AND mapping_id=NEW.mapping_id;
          SELECT * INTO observation FROM public.koinon_content_sync_observations WHERE id=NEW.observation_id;
          IF c.id IS NULL OR m.id IS NULL OR o.id IS NULL OR observation.id IS NULL
            OR c.tenant_id IS DISTINCT FROM NEW.tenant_id OR c.parent_id IS DISTINCT FROM NEW.local_parent_id
            OR c.kind NOT IN ('folder','collection','corpus')
            OR c.workspace_id IS DISTINCT FROM m.workspace_id OR c.project_id IS DISTINCT FROM m.project_id
            OR c.mutation_revision IS DISTINCT FROM NEW.canonical_revision
            OR NEW.canonical_sha256 IS DISTINCT FROM encode(sha256(convert_to(
                jsonb_build_array('koinon.folder-fields.v1',c.name,c.parent_id,c.workspace_id,
                  c.project_id,c.kind)::text,'UTF8')),'hex')
            OR o.remote_kind IS DISTINCT FROM 'folder'
            OR (observation.tenant_id,observation.mapping_id,observation.object_id,observation.work_id)
              IS DISTINCT FROM (NEW.tenant_id,NEW.mapping_id,NEW.object_id,NEW.work_id)
            OR o.generation IS DISTINCT FROM observation.generation
            OR o.remote_version IS DISTINCT FROM observation.remote_version
            OR NOT EXISTS(SELECT 1 FROM public.lattice_catalog parent
                WHERE parent.id=NEW.local_parent_id AND parent.tenant_id=NEW.tenant_id)
          THEN RAISE EXCEPTION 'folder publication identity mismatch' USING ERRCODE='23514'; END IF;
          SELECT * INTO previous FROM public.koinon_content_folder_publications
            WHERE local_folder_id=NEW.local_folder_id ORDER BY canonical_revision DESC LIMIT 1;
          IF previous.id IS NULL THEN
            SELECT xmin::text=((pg_current_xact_id()::text::bigint & 4294967295)::text)
              INTO inserted_here FROM public.lattice_catalog WHERE id=NEW.local_folder_id;
            IF NEW.previous_publication_id IS NOT NULL OR NEW.canonical_revision<>1
              OR NOT inserted_here OR c.created_by IS DISTINCT FROM m.owner
            THEN RAISE EXCEPTION 'initial publication requires a newly allocated folder'
              USING ERRCODE='23514'; END IF;
          ELSIF NEW.previous_publication_id IS DISTINCT FROM previous.id
            OR (NEW.tenant_id,NEW.mapping_id,NEW.object_id) IS DISTINCT FROM
              (previous.tenant_id,previous.mapping_id,previous.object_id)
            OR NEW.canonical_revision<=previous.canonical_revision
          THEN RAISE EXCEPTION 'folder publication predecessor mismatch' USING ERRCODE='23514'; END IF;
          IF NOT EXISTS(SELECT 1 FROM public.lattice_audit a
            WHERE a.tenant_id=NEW.tenant_id AND a.resource_id=NEW.local_folder_id AND a.subject=m.owner
              AND a.action='source.folder.published' AND a.details::jsonb=jsonb_build_object(
                'publication_id',NEW.id,'object_id',NEW.object_id,'observation_id',NEW.observation_id,
                'work_id',NEW.work_id,'canonical_revision',NEW.canonical_revision,
                'canonical_sha256',NEW.canonical_sha256))
          THEN RAISE EXCEPTION 'exact folder producer audit required' USING ERRCODE='23514'; END IF;
          RETURN NEW;
        END $$""")
    op.execute(
        "CREATE TRIGGER guard_folder_publication BEFORE INSERT OR UPDATE OR DELETE ON "
        "koinon_content_folder_publications FOR EACH ROW EXECUTE FUNCTION "
        "public.koinon_folder_publication_guard()"
    )
    op.execute(
        "CREATE TRIGGER retain_folder_publication BEFORE TRUNCATE ON koinon_content_folder_publications "
        "EXECUTE FUNCTION public.koinon_folder_publication_guard()"
    )


def _completion_guard():
    op.execute("""CREATE FUNCTION public.koinon_folder_publication_complete() RETURNS trigger
        LANGUAGE plpgsql SET search_path=pg_catalog,public AS $$
        DECLARE latest public.koinon_content_folder_publications;
        BEGIN
          SELECT * INTO latest FROM public.koinon_content_folder_publications
            WHERE local_folder_id=NEW.local_folder_id ORDER BY canonical_revision DESC LIMIT 1;
          IF latest.id IS DISTINCT FROM NEW.id THEN RETURN NULL; END IF;
          IF NOT EXISTS(SELECT 1 FROM public.koinon_content_objects o
            JOIN public.koinon_content_folder_bindings b ON b.tenant_id=o.tenant_id
              AND b.mapping_id=o.mapping_id AND b.remote_folder_id=o.item_id
            JOIN public.lattice_catalog c ON c.id=b.local_folder_id
            WHERE o.tenant_id=NEW.tenant_id AND o.mapping_id=NEW.mapping_id AND o.id=NEW.object_id
              AND b.local_folder_id=NEW.local_folder_id AND b.local_parent_id=NEW.local_parent_id
              AND c.parent_id=NEW.local_parent_id AND c.mutation_revision=NEW.canonical_revision
              AND o.published_local_revision=NEW.canonical_revision::text
              AND o.published_sha256=NEW.canonical_sha256 AND o.published_native_version_id IS NULL)
          THEN RAISE EXCEPTION 'folder publication and baseline must commit together'
            USING ERRCODE='23514'; END IF;
          RETURN NULL;
        END $$""")
    op.execute(
        "CREATE CONSTRAINT TRIGGER complete_folder_publication AFTER INSERT ON "
        "koinon_content_folder_publications DEFERRABLE INITIALLY DEFERRED FOR EACH ROW "
        "EXECUTE FUNCTION public.koinon_folder_publication_complete()"
    )


def downgrade():
    raise RuntimeError(
        "Folder provenance and canonical revisions are retained; use a reviewed forward migration"
    )
