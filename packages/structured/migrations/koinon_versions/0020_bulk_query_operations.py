# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Native query completion marker commits atomically with its query result."""

import sqlalchemy as sa
from alembic import op
from pyfly.data.relational.sqlalchemy import UtcDateTime

revision = "0020_bulk_query_operations"
down_revision = "0019_consumer_context"
FROZEN = (
    "id",
    "tenant_id",
    "subject",
    "workspace_id",
    "dataset_id",
    "catalog_workspace_id",
    "catalog_dataset_id",
    "question",
    "policy_sha256",
    "connections_sha256",
    "created_at",
)


def upgrade():
    table = "flyquery_bulk_query_operations"
    op.create_table(
        table,
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("tenant_id", sa.String(64), nullable=False),
        sa.Column("subject", sa.String(512), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("dataset_id", sa.Uuid(), sa.ForeignKey("flyquery_datasets.id"), nullable=False),
        sa.Column("catalog_workspace_id", sa.String(64), nullable=False),
        sa.Column("catalog_dataset_id", sa.String(64), nullable=False),
        sa.Column("question", sa.String(8000), nullable=False),
        sa.Column("policy_sha256", sa.String(64), nullable=False),
        sa.Column("connections_sha256", sa.String(64), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("query_id", sa.Uuid(), sa.ForeignKey("flyquery_queries.id"), nullable=True, unique=True),
        sa.Column("receipt_json", sa.JSON(none_as_null=True), nullable=True),
        sa.Column("created_at", UtcDateTime(), nullable=False),
        sa.CheckConstraint("status IN ('admitted','committed')", name="ck_bulk_query_operation_status"),
        sa.CheckConstraint(
            "(status = 'admitted' AND receipt_json IS NULL AND query_id IS NULL) OR "
            "(status = 'committed' AND receipt_json IS NOT NULL AND query_id IS NOT NULL)",
            name="ck_bulk_query_operation_receipt",
        ),
    )
    dialect = op.get_bind().dialect.name
    if dialect == "sqlite":
        changed = " OR ".join(f"NEW.{name} IS NOT OLD.{name}" for name in FROZEN)
        op.execute(
            f"CREATE TRIGGER bulk_query_admit BEFORE INSERT ON {table} "
            "WHEN NEW.status != 'admitted' BEGIN SELECT RAISE(ABORT,'Start with an admitted query'); END"
        )
        op.execute(
            f"CREATE TRIGGER bulk_query_identity BEFORE UPDATE ON {table} WHEN {changed} OR "
            "(OLD.status='committed' AND (NEW.status!='committed' OR NEW.query_id IS NOT OLD.query_id "
            "OR NEW.receipt_json IS NOT OLD.receipt_json)) "
            "BEGIN SELECT RAISE(ABORT,'Immutable native query receipt'); END"
        )
        op.execute(
            f"CREATE TRIGGER bulk_query_retain BEFORE DELETE ON {table} "
            "BEGIN SELECT RAISE(ABORT,'Retain native query receipts'); END"
        )
    elif dialect == "postgresql":
        op.execute("""CREATE FUNCTION public.koinon_bulk_query_guard() RETURNS trigger LANGUAGE plpgsql
            SET search_path=pg_catalog AS $$ BEGIN
            IF TG_OP='INSERT' THEN IF NEW.status!='admitted' THEN
                RAISE EXCEPTION 'Start with an admitted query'; END IF; RETURN NEW; END IF;
            IF TG_OP='DELETE' THEN RAISE EXCEPTION 'Retain native query receipts'; END IF;
            IF (to_jsonb(NEW)-ARRAY['status','query_id','receipt_json']) IS DISTINCT FROM
               (to_jsonb(OLD)-ARRAY['status','query_id','receipt_json']) OR
               (OLD.status='committed' AND (NEW.status!='committed'
               OR NEW.query_id IS DISTINCT FROM OLD.query_id
               OR NEW.receipt_json::jsonb IS DISTINCT FROM OLD.receipt_json::jsonb))
            THEN RAISE EXCEPTION 'Immutable native query receipt'; END IF; RETURN NEW; END $$""")
        op.execute("REVOKE ALL ON FUNCTION public.koinon_bulk_query_guard() FROM PUBLIC")
        op.execute(
            f"CREATE TRIGGER bulk_query_identity BEFORE INSERT OR UPDATE OR DELETE ON {table} "
            "FOR EACH ROW EXECUTE FUNCTION public.koinon_bulk_query_guard()"
        )
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"CREATE POLICY pol_{table} ON {table} "
            "USING(tenant_id=current_setting('app.tenant_id',true) "
            "AND workspace_id::text=current_setting('app.workspace_id',true)) "
            "WITH CHECK(tenant_id=current_setting('app.tenant_id',true) "
            "AND workspace_id::text=current_setting('app.workspace_id',true))"
        )
        op.execute(f"REVOKE ALL ON TABLE {table} FROM PUBLIC")
    else:
        raise RuntimeError("Durable native query operations require PostgreSQL or SQLite")


def downgrade():
    raise RuntimeError("Use a reviewed backup/restore recovery plan for native query receipts")
