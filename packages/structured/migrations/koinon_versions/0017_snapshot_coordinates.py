# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Reader-observed immutable input coordinates; existing snapshots remain unrecorded."""

from alembic import op

revision = "0017_snapshot_coordinates"
down_revision = "0016_immutable_file_lineage"


def upgrade():
    op.execute("""ALTER TABLE flyquery_snapshot_lineage ADD CONSTRAINT uq_snapshot_lineage_coordinates
        UNIQUE(snapshot_id,tenant_id,workspace_id,dataset_id,table_id,run_id)""")
    op.execute("""ALTER TABLE flyquery_lineage_runs ADD CONSTRAINT uq_lineage_run_artifact
        UNIQUE(id,artifact_id,tenant_id,workspace_id,dataset_id)""")
    op.execute("""CREATE TABLE flyquery_coordinate_manifests (
        snapshot_id uuid PRIMARY KEY,recorded_xid xid8 NOT NULL,
        tenant_id varchar(512) NOT NULL,workspace_id uuid NOT NULL,
        dataset_id uuid NOT NULL,actor varchar(512) NOT NULL,recorded_at timestamptz NOT NULL DEFAULT now(),
        table_id uuid NOT NULL,run_id uuid NOT NULL,artifact_id uuid NOT NULL,
        input_sha256 varchar(64) NOT NULL CHECK(input_sha256 ~ '^[0-9a-f]{64}$'),
        mapping_sha256 varchar(64) NOT NULL CHECK(mapping_sha256 ~ '^[0-9a-f]{64}$'),
        row_count bigint NOT NULL CHECK(row_count>=0),
        column_count integer NOT NULL CHECK(column_count BETWEEN 0 AND 16384),
        complete boolean NOT NULL,reason_code varchar(128),descriptor json NOT NULL,
        CHECK((complete AND reason_code IS NULL) OR (NOT complete AND reason_code IS NOT NULL)),
        UNIQUE(snapshot_id,tenant_id,workspace_id,dataset_id),
        FOREIGN KEY(snapshot_id,tenant_id,workspace_id,dataset_id,table_id,run_id)
            REFERENCES flyquery_snapshot_lineage(
                snapshot_id,tenant_id,workspace_id,dataset_id,table_id,run_id),
        FOREIGN KEY(run_id,artifact_id,tenant_id,workspace_id,dataset_id)
            REFERENCES flyquery_lineage_runs(id,artifact_id,tenant_id,workspace_id,dataset_id)
    )""")
    op.execute("""CREATE TABLE flyquery_coordinate_ranges (
        snapshot_id uuid NOT NULL,tenant_id varchar(512) NOT NULL,workspace_id uuid NOT NULL,
        dataset_id uuid NOT NULL,actor varchar(512) NOT NULL,recorded_at timestamptz NOT NULL DEFAULT now(),
        output_start bigint NOT NULL CHECK(output_start>=0),count bigint NOT NULL CHECK(count>0),
        source_start bigint NOT NULL CHECK(source_start>=0),
        source_stride bigint NOT NULL CHECK(source_stride>0),
        PRIMARY KEY(snapshot_id,output_start),
        FOREIGN KEY(snapshot_id,tenant_id,workspace_id,dataset_id)
            REFERENCES flyquery_coordinate_manifests(snapshot_id,tenant_id,workspace_id,dataset_id)
    )""")
    op.execute("""CREATE TABLE flyquery_coordinate_columns (
        snapshot_id uuid NOT NULL,tenant_id varchar(512) NOT NULL,workspace_id uuid NOT NULL,
        dataset_id uuid NOT NULL,actor varchar(512) NOT NULL,recorded_at timestamptz NOT NULL DEFAULT now(),
        output_position integer NOT NULL CHECK(output_position BETWEEN 0 AND 16383),
        source_field_index integer CHECK(source_field_index>=0),source_path json NOT NULL,
        source_type varchar(4096),header_cells json NOT NULL,PRIMARY KEY(snapshot_id,output_position),
        FOREIGN KEY(snapshot_id,tenant_id,workspace_id,dataset_id)
            REFERENCES flyquery_coordinate_manifests(snapshot_id,tenant_id,workspace_id,dataset_id)
    )""")
    op.execute("""
        CREATE FUNCTION public.koinon_coordinate_stamp_xid() RETURNS trigger
        LANGUAGE plpgsql SET search_path=pg_catalog AS $$
        BEGIN
            NEW.recorded_xid := pg_current_xact_id();
            RETURN NEW;
        END;
        $$
    """)
    op.execute("REVOKE ALL ON FUNCTION public.koinon_coordinate_stamp_xid() FROM PUBLIC")
    op.execute("""CREATE TRIGGER tr_coordinate_manifest_stamp BEFORE INSERT ON flyquery_coordinate_manifests
        FOR EACH ROW EXECUTE FUNCTION public.koinon_coordinate_stamp_xid()""")
    op.execute("""
        CREATE FUNCTION public.koinon_coordinate_child_xid() RETURNS trigger
        LANGUAGE plpgsql SET search_path=pg_catalog AS $$
        DECLARE creation_xid xid8;
        BEGIN
            SELECT recorded_xid INTO creation_xid FROM public.flyquery_coordinate_manifests
            WHERE snapshot_id=NEW.snapshot_id AND tenant_id=NEW.tenant_id
                AND workspace_id=NEW.workspace_id AND dataset_id=NEW.dataset_id;
            IF NOT FOUND THEN
                RAISE EXCEPTION 'Coordinate manifest unavailable in this scope' USING ERRCODE='23503';
            END IF;
            IF creation_xid <> pg_current_xact_id() THEN
                RAISE EXCEPTION 'Coordinate mapping creation transaction has ended' USING ERRCODE='55000';
            END IF;
            RETURN NEW;
        END;
        $$
    """)
    op.execute("REVOKE ALL ON FUNCTION public.koinon_coordinate_child_xid() FROM PUBLIC")
    for table in ("flyquery_coordinate_ranges", "flyquery_coordinate_columns"):
        op.execute(f"""CREATE TRIGGER tr_{table}_creation BEFORE INSERT ON {table}
            FOR EACH ROW EXECUTE FUNCTION public.koinon_coordinate_child_xid()""")
    for table in (
        "flyquery_coordinate_manifests",
        "flyquery_coordinate_ranges",
        "flyquery_coordinate_columns",
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
        op.execute(f"CREATE INDEX ix_{table}_scope ON {table}(tenant_id,workspace_id,dataset_id,snapshot_id)")


def downgrade():
    raise RuntimeError("Immutable source coordinates require a reviewed restore plan")
