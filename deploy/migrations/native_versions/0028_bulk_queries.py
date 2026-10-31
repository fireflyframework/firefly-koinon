# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Private independent query manifests and immutable native outcome references."""

import sqlalchemy as sa
from alembic import op
from pyfly.data.relational.sqlalchemy import UtcDateTime

revision = "koinon_0028_bulk_queries"
down_revision = "koinon_0027_bulk_reservations"
branch_labels = None
depends_on = None

MUTABLE = {
    "koinon_query_batches": ("actions_json", "revision", "cancelled"),
    "koinon_query_batch_items": ("status", "result_json", "error_code"),
    "koinon_query_batch_references": (),
}
FROZEN = {
    "koinon_query_batches": (
        "id",
        "tenant_id",
        "workspace_id",
        "subject",
        "token_id",
        "key_hash",
        "request_hash",
        "request_json",
        "created_at",
        "expires_at",
    ),
    "koinon_query_batch_items": (
        "id",
        "batch_id",
        "ordinal",
        "client_item_id",
        "dataset_id",
        "question",
        "native_workspace_id",
        "native_dataset_id",
        "connection_json",
        "policy_json",
        "job_id",
    ),
    "koinon_query_batch_references": (
        "item_id",
        "catalog_id",
        "native_table_id",
        "snapshot_id",
        "qualified_name",
    ),
}


def upgrade():
    op.create_table(
        "koinon_query_batches",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("tenant_id", sa.String(64), sa.ForeignKey("lattice_tenants.id"), nullable=False),
        sa.Column("workspace_id", sa.String(64), sa.ForeignKey("lattice_catalog.id"), nullable=False),
        sa.Column("subject", sa.String(512), nullable=False),
        sa.Column("token_id", sa.String(64), nullable=True),
        sa.Column("key_hash", sa.String(64), nullable=False),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("request_json", sa.JSON(), nullable=False),
        sa.Column("actions_json", sa.JSON(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("cancelled", sa.Boolean(), nullable=False),
        sa.Column("created_at", UtcDateTime(), nullable=False),
        sa.Column("expires_at", UtcDateTime(), nullable=False),
        sa.UniqueConstraint("tenant_id", "key_hash", name="uq_query_batch_key"),
        sa.CheckConstraint("revision BETWEEN 1 AND 2147483647", name="ck_query_batch_revision"),
    )
    op.create_index(
        "ix_query_batch_owner", "koinon_query_batches", ["tenant_id", "subject", "created_at", "id"]
    )
    op.create_table(
        "koinon_query_batch_items",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("batch_id", sa.String(64), sa.ForeignKey("koinon_query_batches.id"), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("client_item_id", sa.String(64), nullable=False),
        sa.Column("dataset_id", sa.String(64), sa.ForeignKey("lattice_catalog.id"), nullable=False),
        sa.Column("question", sa.String(8000), nullable=False),
        sa.Column("native_workspace_id", sa.String(64), nullable=False),
        sa.Column("native_dataset_id", sa.String(64), nullable=False),
        sa.Column("connection_json", sa.JSON(), nullable=False),
        sa.Column("policy_json", sa.JSON(), nullable=False),
        sa.Column("job_id", sa.String(64), sa.ForeignKey("lattice_jobs.id"), unique=True, nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("result_json", sa.JSON(none_as_null=True), nullable=True),
        sa.Column("error_code", sa.String(64), nullable=True),
        sa.UniqueConstraint("batch_id", "ordinal", name="uq_query_item_ordinal"),
        sa.UniqueConstraint("batch_id", "client_item_id", name="uq_query_item_client"),
        sa.CheckConstraint("ordinal BETWEEN 0 AND 19", name="ck_query_item_ordinal"),
        sa.CheckConstraint(
            "status IN ('queued','running','succeeded','failed','cancelled','reconciling')",
            name="ck_query_item_status",
        ),
        sa.CheckConstraint("status != 'succeeded' OR result_json IS NOT NULL", name="ck_query_item_receipt"),
    )
    op.create_index("ix_query_item_page", "koinon_query_batch_items", ["batch_id", "ordinal", "id"])
    op.create_table(
        "koinon_query_batch_references",
        sa.Column("item_id", sa.String(64), sa.ForeignKey("koinon_query_batch_items.id"), primary_key=True),
        sa.Column("catalog_id", sa.String(64), sa.ForeignKey("lattice_catalog.id"), primary_key=True),
        sa.Column("native_table_id", sa.String(64), nullable=False),
        sa.Column("snapshot_id", sa.String(64), nullable=False),
        sa.Column("qualified_name", sa.String(512), nullable=False),
        sa.UniqueConstraint("item_id", "native_table_id", name="uq_query_reference_native"),
    )
    dialect = op.get_bind().dialect.name
    if dialect == "sqlite":
        for table, frozen in FROZEN.items():
            changed = " OR ".join(f"NEW.{name} IS NOT OLD.{name}" for name in frozen)
            extra = (
                "NEW.revision < OLD.revision OR (OLD.cancelled AND NOT NEW.cancelled)"
                if table == "koinon_query_batches"
                else (
                    "(OLD.result_json IS NOT NULL AND NEW.result_json IS NOT OLD.result_json) OR "
                    "(OLD.status = 'succeeded' AND NEW.status != 'succeeded')"
                    if table == "koinon_query_batch_items"
                    else "1=1"
                )
            )
            op.execute(
                f"CREATE TRIGGER {table}_identity BEFORE UPDATE ON {table} WHEN {changed} OR {extra} "
                "BEGIN SELECT RAISE(ABORT,'Immutable query identity or receipt'); END"
            )
            op.execute(
                f"CREATE TRIGGER {table}_retain BEFORE DELETE ON {table} "
                "BEGIN SELECT RAISE(ABORT,'Retain query manifests and receipts'); END"
            )
    elif dialect == "postgresql":
        for table, mutable in MUTABLE.items():
            fields = "ARRAY[" + ",".join("'" + value + "'" for value in mutable) + "]::text[]"
            extra = (
                "NEW.revision < OLD.revision OR (OLD.cancelled AND NOT NEW.cancelled)"
                if table == "koinon_query_batches"
                else (
                    "(OLD.result_json IS NOT NULL AND NEW.result_json::jsonb IS DISTINCT FROM OLD.result_json::jsonb) OR "
                    "(OLD.status = 'succeeded' AND NEW.status != 'succeeded')"
                    if table == "koinon_query_batch_items"
                    else "TRUE"
                )
            )
            op.execute(f"""CREATE FUNCTION public.{table}_guard() RETURNS trigger LANGUAGE plpgsql
                SET search_path=pg_catalog AS $$ BEGIN
                IF TG_OP='DELETE' THEN RAISE EXCEPTION 'Retain query manifests and receipts'; END IF;
                IF (to_jsonb(NEW)-{fields}) IS DISTINCT FROM (to_jsonb(OLD)-{fields}) OR {extra}
                THEN RAISE EXCEPTION 'Immutable query identity or receipt'; END IF;
                RETURN NEW; END $$""")
            op.execute(f"REVOKE ALL ON FUNCTION public.{table}_guard() FROM PUBLIC")
            op.execute(
                f"CREATE TRIGGER {table}_retain BEFORE UPDATE OR DELETE ON {table} "
                f"FOR EACH ROW EXECUTE FUNCTION public.{table}_guard()"
            )
            op.execute(f"REVOKE ALL ON TABLE public.{table} FROM PUBLIC")
    else:
        raise RuntimeError("Durable queries require PostgreSQL or SQLite")


def downgrade():
    raise RuntimeError("Use a reviewed backup/restore recovery plan for durable queries")
