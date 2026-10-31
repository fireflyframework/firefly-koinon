# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Complete native bulk dataset operation receipts; preserve standalone history."""

import sqlalchemy as sa
from alembic import op
from pyfly.data.relational.sqlalchemy import UtcDateTime

revision = "0018_bulk_operations"
down_revision = "0017_snapshot_coordinates"

FROZEN = (
    "id",
    "tenant_id",
    "workspace_id",
    "dataset_id",
    "file_id",
    "actor",
    "catalog_source_id",
    "catalog_dataset_id",
    "catalog_file_version_id",
    "filename",
    "sha256",
    "size_bytes",
    "created_at",
)


def upgrade():
    op.create_table(
        "flyquery_bulk_operations",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("tenant_id", sa.String(512), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column(
            "dataset_id", sa.Uuid(), sa.ForeignKey("flyquery_datasets.id"), nullable=False, unique=True
        ),
        sa.Column("file_id", sa.Uuid(), nullable=False, unique=True),
        sa.Column("actor", sa.String(512), nullable=False),
        sa.Column("catalog_source_id", sa.String(64), nullable=False),
        sa.Column("catalog_dataset_id", sa.String(64), nullable=False),
        sa.Column("catalog_file_version_id", sa.String(64), nullable=False),
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("plan_json", sa.JSON(none_as_null=True), nullable=True),
        sa.Column("prepared_json", sa.JSON(none_as_null=True), nullable=True),
        sa.Column("receipt_json", sa.JSON(none_as_null=True), nullable=True),
        sa.Column("created_at", UtcDateTime(), nullable=False),
        sa.CheckConstraint("status IN ('admitted','prepared','committed')", name="ck_structured_bulk_status"),
        sa.CheckConstraint(
            "status = 'admitted' OR (plan_json IS NOT NULL AND prepared_json IS NOT NULL)",
            name="ck_structured_bulk_complete",
        ),
        sa.CheckConstraint(
            "receipt_json IS NULL OR status = 'committed'", name="ck_structured_bulk_receipt_state"
        ),
        sa.CheckConstraint(
            "status != 'prepared' OR prepared_json IS NOT NULL", name="ck_structured_bulk_prepared"
        ),
        sa.CheckConstraint(
            "status != 'committed' OR receipt_json IS NOT NULL", name="ck_structured_bulk_receipt"
        ),
    )
    dialect = op.get_bind().dialect.name
    if dialect == "sqlite":
        op.execute(
            "CREATE TRIGGER structured_bulk_admit BEFORE INSERT ON flyquery_bulk_operations "
            "WHEN NEW.status != 'admitted' OR NEW.plan_json IS NOT NULL "
            "OR NEW.prepared_json IS NOT NULL OR NEW.receipt_json IS NOT NULL "
            "BEGIN SELECT RAISE(ABORT,'Start with an admitted operation'); END"
        )
        frozen = " OR ".join(f"NEW.{field} IS NOT OLD.{field}" for field in FROZEN)
        monotonic = " OR ".join(
            f"(OLD.{field} IS NOT NULL AND NEW.{field} IS NOT OLD.{field})"
            for field in ["plan_json", "prepared_json", "receipt_json"]
        )
        transition = (
            "(OLD.status='admitted' AND NEW.status NOT IN ('admitted','prepared')) OR "
            "(OLD.status='prepared' AND NEW.status NOT IN ('prepared','committed')) OR "
            "(OLD.status='committed' AND NEW.status!='committed')"
        )
        op.execute(
            f"CREATE TRIGGER structured_bulk_identity BEFORE UPDATE ON flyquery_bulk_operations "
            f"WHEN {frozen} OR {monotonic} OR {transition} "
            "BEGIN SELECT RAISE(ABORT,'Immutable structured bulk operation'); END"
        )
        op.execute(
            "CREATE TRIGGER structured_bulk_retain BEFORE DELETE ON flyquery_bulk_operations "
            "BEGIN SELECT RAISE(ABORT,'Retain structured bulk receipts'); END"
        )
    elif dialect == "postgresql":
        op.execute("""CREATE FUNCTION public.koinon_structured_bulk_guard() RETURNS trigger
            LANGUAGE plpgsql SET search_path=pg_catalog AS $$
            BEGIN
                IF TG_OP='INSERT' THEN
                    IF NEW.status != 'admitted' OR NEW.plan_json IS NOT NULL OR NEW.prepared_json IS NOT NULL
                        OR NEW.receipt_json IS NOT NULL THEN
                        RAISE EXCEPTION 'Start with an admitted operation';
                    END IF;
                    RETURN NEW;
                END IF;
                IF TG_OP='DELETE' THEN
                    RAISE EXCEPTION 'Retain structured bulk receipts' USING ERRCODE='55000';
                END IF;
                IF (to_jsonb(NEW)-ARRAY['status','plan_json','prepared_json','receipt_json'])
                    IS DISTINCT FROM
                    (to_jsonb(OLD)-ARRAY['status','plan_json','prepared_json','receipt_json'])
                    OR (OLD.plan_json IS NOT NULL
                        AND NEW.plan_json::jsonb IS DISTINCT FROM OLD.plan_json::jsonb)
                    OR (OLD.prepared_json IS NOT NULL
                        AND NEW.prepared_json::jsonb IS DISTINCT FROM OLD.prepared_json::jsonb)
                    OR (OLD.receipt_json IS NOT NULL
                        AND NEW.receipt_json::jsonb IS DISTINCT FROM OLD.receipt_json::jsonb)
                    OR (OLD.status='admitted' AND NEW.status NOT IN ('admitted','prepared'))
                    OR (OLD.status='prepared' AND NEW.status NOT IN ('prepared','committed'))
                    OR (OLD.status='committed' AND NEW.status!='committed')
                THEN RAISE EXCEPTION 'Immutable structured bulk operation' USING ERRCODE='55000'; END IF;
                RETURN NEW;
            END $$""")
        op.execute("REVOKE ALL ON FUNCTION public.koinon_structured_bulk_guard() FROM PUBLIC")
        op.execute(
            "CREATE TRIGGER structured_bulk_identity BEFORE INSERT OR UPDATE OR DELETE "
            "ON flyquery_bulk_operations "
            "FOR EACH ROW EXECUTE FUNCTION public.koinon_structured_bulk_guard()"
        )
        op.execute("ALTER TABLE flyquery_bulk_operations ENABLE ROW LEVEL SECURITY")
        op.execute("ALTER TABLE flyquery_bulk_operations FORCE ROW LEVEL SECURITY")
        op.execute("""CREATE POLICY pol_flyquery_bulk_operations ON flyquery_bulk_operations
            USING(tenant_id=current_setting('app.tenant_id',true)
                AND workspace_id::text=current_setting('app.workspace_id',true))
            WITH CHECK(tenant_id=current_setting('app.tenant_id',true)
                AND workspace_id::text=current_setting('app.workspace_id',true))""")
        op.execute("REVOKE ALL ON flyquery_bulk_operations FROM PUBLIC")
    else:
        raise RuntimeError("Structured bulk operations require PostgreSQL or SQLite")


def downgrade():
    raise RuntimeError("Use a reviewed backup/restore recovery plan for structured bulk receipts")
