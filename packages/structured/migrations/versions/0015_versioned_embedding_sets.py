# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Add side-by-side scoped embedding versions; preserve original inline vectors."""

from alembic import op

revision = "0015_versioned_embedding_sets"
down_revision = "0014_semantic_meta_dimtype"


def upgrade():
    op.execute("""
        CREATE TABLE flyquery_embedding_sets (
            id varchar(64) PRIMARY KEY, tenant_id text NOT NULL, workspace_id uuid NOT NULL,
            provider varchar(32) NOT NULL, model varchar(255) NOT NULL,
            dimensions integer NOT NULL CONSTRAINT ck_structured_set_width
              CHECK(dimensions BETWEEN 64 AND 1536),
            config_fingerprint varchar(64) NOT NULL, status varchar(24) NOT NULL DEFAULT 'building',
            created_at timestamptz NOT NULL DEFAULT now(), ready_at timestamptz,
            activated_at timestamptz, retired_at timestamptz, created_by varchar(512) NOT NULL
        )
    """)
    op.execute("CREATE INDEX ix_structured_set_scope ON flyquery_embedding_sets(tenant_id,workspace_id)")
    op.execute(
        "CREATE UNIQUE INDEX uq_structured_active_set "
        "ON flyquery_embedding_sets(tenant_id,workspace_id) WHERE status='active'"
    )
    op.execute("""
        CREATE TABLE flyquery_embedding_vectors (
            set_id varchar(64) NOT NULL REFERENCES flyquery_embedding_sets(id),
            kind varchar(16) NOT NULL CONSTRAINT ck_structured_vector_kind
              CHECK(kind IN ('schema','example')),
            object_id uuid NOT NULL,
            tenant_id text NOT NULL, workspace_id uuid NOT NULL, content_hash varchar(64) NOT NULL,
            embedding vector(1536) NOT NULL, model varchar(255) NOT NULL, text text NOT NULL DEFAULT '',
            created_at timestamptz NOT NULL DEFAULT now(), PRIMARY KEY(set_id,kind,object_id)
        )
    """)
    op.execute(
        "CREATE INDEX ix_structured_vector_scope ON flyquery_embedding_vectors(tenant_id,workspace_id,set_id)"
    )
    op.execute(
        "CREATE INDEX ix_structured_vector_hnsw ON flyquery_embedding_vectors "
        "USING hnsw(embedding vector_cosine_ops) WITH(m=16,ef_construction=64)"
    )
    for table in ("flyquery_embedding_sets", "flyquery_embedding_vectors"):
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(f"""CREATE POLICY pol_{table} ON {table}
            USING(tenant_id=current_setting('app.tenant_id',true)
              AND workspace_id::text=current_setting('app.workspace_id',true))
            WITH CHECK(tenant_id=current_setting('app.tenant_id',true)
              AND workspace_id::text=current_setting('app.workspace_id',true))""")


def downgrade():
    raise RuntimeError("Use a reviewed restore plan; preserved native embedding versions must not be dropped")
