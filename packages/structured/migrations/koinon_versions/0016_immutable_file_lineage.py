# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Immutable file/section materialization receipts; no historical inferred origins."""

from alembic import op

revision = "0016_immutable_file_lineage"
down_revision = "0015_versioned_embedding_sets"


def upgrade():
    op.execute("""
        CREATE TABLE flyquery_lineage_artifacts (
            id uuid PRIMARY KEY, tenant_id varchar(512) NOT NULL, workspace_id uuid NOT NULL,
            dataset_id uuid NOT NULL, actor varchar(512) NOT NULL,
            recorded_at timestamptz NOT NULL DEFAULT now(), original_filename varchar(512) NOT NULL,
            sha256 varchar(64) NOT NULL CHECK(sha256 ~ '^[0-9a-f]{64}$'),
            byte_size bigint NOT NULL CHECK(byte_size>=0), file_format varchar(32) NOT NULL,
            compression varchar(32) NOT NULL,
            UNIQUE(id,tenant_id,workspace_id,dataset_id)
        )
    """)
    op.execute("""
        CREATE TABLE flyquery_lineage_runs (
            id uuid PRIMARY KEY, tenant_id varchar(512) NOT NULL, workspace_id uuid NOT NULL,
            dataset_id uuid NOT NULL, actor varchar(512) NOT NULL,
            recorded_at timestamptz NOT NULL DEFAULT now(), artifact_id uuid NOT NULL,
            operation varchar(16) NOT NULL CHECK(operation IN ('upload','replace','reingest')),
            predecessor_snapshot_id uuid, sheet_or_json_path varchar(2048), table_label varchar(512) NOT NULL,
            implementation varchar(512) NOT NULL, implementation_sha256 varchar(64), parameters json NOT NULL,
            UNIQUE(id,tenant_id,workspace_id,dataset_id),
            FOREIGN KEY(artifact_id,tenant_id,workspace_id,dataset_id)
                REFERENCES flyquery_lineage_artifacts(id,tenant_id,workspace_id,dataset_id),
            CHECK(operation='upload' OR predecessor_snapshot_id IS NOT NULL)
        )
    """)
    op.execute("""
        CREATE TABLE flyquery_lineage_steps (
            id uuid PRIMARY KEY, tenant_id varchar(512) NOT NULL, workspace_id uuid NOT NULL,
            dataset_id uuid NOT NULL, actor varchar(512) NOT NULL,
            recorded_at timestamptz NOT NULL DEFAULT now(), run_id uuid NOT NULL,
            ordinal integer NOT NULL CHECK(ordinal BETWEEN 1 AND 64), kind varchar(32) NOT NULL,
            implementation varchar(512) NOT NULL, implementation_sha256 varchar(64),
            input_sha256 varchar(64), output_sha256 varchar(64),
            parameters json NOT NULL, UNIQUE(run_id,ordinal),
            FOREIGN KEY(run_id,tenant_id,workspace_id,dataset_id)
                REFERENCES flyquery_lineage_runs(id,tenant_id,workspace_id,dataset_id)
        )
    """)
    op.execute("""
        CREATE TABLE flyquery_snapshot_lineage (
            snapshot_id uuid PRIMARY KEY, tenant_id varchar(512) NOT NULL, workspace_id uuid NOT NULL,
            dataset_id uuid NOT NULL, actor varchar(512) NOT NULL,
            recorded_at timestamptz NOT NULL DEFAULT now(), run_id uuid NOT NULL UNIQUE,
            table_id uuid NOT NULL, parquet_sha256 varchar(64) NOT NULL
                CHECK(parquet_sha256 ~ '^[0-9a-f]{64}$'),
            parquet_byte_size bigint NOT NULL CHECK(parquet_byte_size>=0),
            schema_sha256 varchar(64) NOT NULL CHECK(schema_sha256 ~ '^[0-9a-f]{64}$'),
            row_count bigint NOT NULL CHECK(row_count>=0),
            FOREIGN KEY(run_id,tenant_id,workspace_id,dataset_id)
                REFERENCES flyquery_lineage_runs(id,tenant_id,workspace_id,dataset_id)
        )
    """)
    op.execute("""
        CREATE FUNCTION public.koinon_reject_lineage_mutation() RETURNS trigger
        LANGUAGE plpgsql SET search_path=pg_catalog AS $$
        BEGIN RAISE EXCEPTION 'Immutable lineage cannot be updated or deleted' USING ERRCODE='55000'; END;
        $$
    """)
    op.execute("REVOKE ALL ON FUNCTION public.koinon_reject_lineage_mutation() FROM PUBLIC")
    for table in (
        "flyquery_lineage_artifacts",
        "flyquery_lineage_runs",
        "flyquery_lineage_steps",
        "flyquery_snapshot_lineage",
    ):
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(f"""CREATE POLICY pol_{table} ON {table}
            USING(tenant_id=current_setting('app.tenant_id',true)
                AND workspace_id::text=current_setting('app.workspace_id',true))
            WITH CHECK(tenant_id=current_setting('app.tenant_id',true)
                AND workspace_id::text=current_setting('app.workspace_id',true))""")
        op.execute(f"""CREATE TRIGGER tr_{table}_immutable BEFORE UPDATE OR DELETE ON {table}
            FOR EACH ROW EXECUTE FUNCTION public.koinon_reject_lineage_mutation()""")
        op.execute(f"REVOKE ALL ON {table} FROM PUBLIC")
        op.execute(f"CREATE INDEX ix_{table}_scope ON {table}(tenant_id,workspace_id,dataset_id)")
    op.execute(
        "CREATE INDEX ix_snapshot_lineage_table ON flyquery_snapshot_lineage"
        "(tenant_id,workspace_id,dataset_id,table_id,recorded_at,snapshot_id)"
    )


def downgrade():
    raise RuntimeError("Immutable lineage history requires a reviewed restore plan")
