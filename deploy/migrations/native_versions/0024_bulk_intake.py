# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Durable private intake manifests, originals, and fenced native job receipts."""

import sqlalchemy as sa
from alembic import op
from pyfly.data.relational.sqlalchemy import UtcDateTime

revision = "koinon_0024_bulk"
down_revision = "koinon_0023_ciam_profiles"
branch_labels = None
depends_on = None


# Only these fields may change after the original identity is admitted.
MUTABLE = {
    "koinon_bulk_batches": ("actions_json", "revision", "submitted", "cancelled"),
    "koinon_bulk_items": (
        "native_workspace_id",
        "native_id",
        "job_id",
        "status",
        "winning_upload_id",
        "receipt_json",
        "error_code",
        "connection_json",
    ),
    "koinon_bulk_uploads": ("status", "permit_held"),
    "koinon_bulk_quotas": ("reserved_bytes", "active_uploads"),
}
FROZEN = {
    "koinon_bulk_batches": (
        "id",
        "tenant_id",
        "subject",
        "token_id",
        "workspace_id",
        "project_id",
        "parent_id",
        "key_hash",
        "request_hash",
        "request_json",
        "total_bytes",
        "created_at",
        "expires_at",
    ),
    "koinon_bulk_items": (
        "id",
        "batch_id",
        "ordinal",
        "client_item_id",
        "filename",
        "mode",
        "size_bytes",
        "sha256",
        "source_id",
        "asset_id",
    ),
    "koinon_bulk_uploads": ("id", "item_id", "key_hash", "object_key", "created_at"),
    "koinon_bulk_quotas": ("id",),
}


def upgrade():
    op.create_table(
        "koinon_bulk_batches",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("tenant_id", sa.String(64), sa.ForeignKey("lattice_tenants.id"), nullable=False),
        sa.Column("subject", sa.String(512), nullable=False),
        sa.Column("token_id", sa.String(64), nullable=True),
        sa.Column("workspace_id", sa.String(64), sa.ForeignKey("lattice_catalog.id"), nullable=False),
        sa.Column("project_id", sa.String(64), sa.ForeignKey("lattice_catalog.id"), nullable=False),
        sa.Column("parent_id", sa.String(64), sa.ForeignKey("lattice_catalog.id"), nullable=False),
        sa.Column("key_hash", sa.String(64), nullable=False),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("request_json", sa.JSON(), nullable=False),
        sa.Column("actions_json", sa.JSON(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("submitted", sa.Boolean(), nullable=False),
        sa.Column("cancelled", sa.Boolean(), nullable=False),
        sa.Column("total_bytes", sa.BigInteger(), nullable=False),
        sa.Column("created_at", UtcDateTime(), nullable=False),
        sa.Column("expires_at", UtcDateTime(), nullable=False),
        sa.UniqueConstraint("tenant_id", "key_hash", name="uq_bulk_batch_key"),
        sa.CheckConstraint(
            "revision BETWEEN 1 AND 2147483647 AND total_bytes BETWEEN 1 AND 268435456",
            name="ck_bulk_batch_bounds",
        ),
    )
    op.create_index("ix_bulk_owner_page", "koinon_bulk_batches", ["tenant_id", "subject", "created_at", "id"])
    op.create_table(
        "koinon_bulk_items",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("batch_id", sa.String(64), sa.ForeignKey("koinon_bulk_batches.id"), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("client_item_id", sa.String(64), nullable=False),
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("mode", sa.String(16), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column(
            "source_id", sa.String(64), sa.ForeignKey("lattice_catalog.id"), nullable=False, unique=True
        ),
        sa.Column(
            "asset_id", sa.String(64), sa.ForeignKey("lattice_catalog.id"), nullable=False, unique=True
        ),
        sa.Column("native_workspace_id", sa.String(64), nullable=True),
        sa.Column("native_id", sa.String(64), nullable=True),
        sa.Column("job_id", sa.String(64), sa.ForeignKey("lattice_jobs.id"), nullable=True, unique=True),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("winning_upload_id", sa.String(64), nullable=True),
        sa.Column("receipt_json", sa.JSON(none_as_null=True), nullable=True),
        sa.Column("error_code", sa.String(64), nullable=True),
        sa.Column("connection_json", sa.JSON(), nullable=False),
        sa.UniqueConstraint("batch_id", "client_item_id", name="uq_bulk_item_client"),
        sa.UniqueConstraint("batch_id", "ordinal", name="uq_bulk_item_order"),
        sa.CheckConstraint(
            "status IN ('awaiting_upload','staged','queued','running','succeeded','failed','cancelled','reconciling')",
            name="ck_bulk_item_status",
        ),
        sa.CheckConstraint(
            "mode IN ('document','dataset') AND ordinal BETWEEN 0 AND 99 AND size_bytes BETWEEN 1 AND 33554432",
            name="ck_bulk_item_bounds",
        ),
        sa.CheckConstraint(
            "status != 'succeeded' OR (receipt_json IS NOT NULL AND native_id IS NOT NULL AND native_workspace_id IS NOT NULL)",
            name="ck_bulk_success_receipt",
        ),
    )
    op.create_index("ix_bulk_item_page", "koinon_bulk_items", ["batch_id", "ordinal", "id"])
    op.create_table(
        "koinon_bulk_uploads",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("item_id", sa.String(64), sa.ForeignKey("koinon_bulk_items.id"), nullable=False),
        sa.Column("key_hash", sa.String(64), nullable=False),
        sa.Column("object_key", sa.String(1024), nullable=False, unique=True),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("permit_held", sa.Boolean(), nullable=False),
        sa.Column("created_at", UtcDateTime(), nullable=False),
        sa.UniqueConstraint("item_id", "key_hash", name="uq_bulk_upload_key"),
        sa.CheckConstraint("status IN ('uploading','verified','uncertain')", name="ck_bulk_upload_status"),
    )
    op.create_table(
        "koinon_bulk_quotas",
        sa.Column("id", sa.String(96), primary_key=True),
        sa.Column("reserved_bytes", sa.BigInteger(), nullable=False),
        sa.Column("active_uploads", sa.Integer(), nullable=False),
        sa.CheckConstraint("reserved_bytes >= 0 AND active_uploads >= 0", name="ck_bulk_quota_nonnegative"),
    )
    if op.get_bind().dialect.name == "postgresql":
        _postgres_guards()
    elif op.get_bind().dialect.name == "sqlite":
        _sqlite_guards()
    else:
        raise RuntimeError("Bulk guards require PostgreSQL or SQLite")


def _sqlite_guards():
    extra = {
        "koinon_bulk_batches": "NEW.revision < OLD.revision OR (OLD.submitted AND NOT NEW.submitted) OR (OLD.cancelled AND NOT NEW.cancelled)",
        "koinon_bulk_items": "(OLD.winning_upload_id IS NOT NULL AND NEW.winning_upload_id IS NOT OLD.winning_upload_id) OR (OLD.native_workspace_id IS NOT NULL AND NEW.native_workspace_id IS NOT OLD.native_workspace_id) OR (OLD.native_id IS NOT NULL AND NEW.native_id IS NOT OLD.native_id) OR (OLD.job_id IS NOT NULL AND (NEW.job_id IS NOT OLD.job_id OR NEW.connection_json IS NOT OLD.connection_json)) OR (OLD.receipt_json IS NOT NULL AND NEW.receipt_json IS NOT OLD.receipt_json) OR (OLD.status = 'succeeded' AND NEW.status != 'succeeded')",
        "koinon_bulk_uploads": "(NOT OLD.permit_held AND NEW.permit_held) OR (OLD.status = 'verified' AND NEW.status != 'verified')",
        "koinon_bulk_quotas": "NEW.reserved_bytes < OLD.reserved_bytes",
    }
    for table, columns in FROZEN.items():
        changed = " OR ".join(f"NEW.{column} IS NOT OLD.{column}" for column in columns)
        op.execute(
            f"CREATE TRIGGER {table}_identity BEFORE UPDATE ON {table} WHEN {changed} OR {extra[table]} BEGIN SELECT RAISE(ABORT,'Immutable bulk identity or receipt'); END"
        )
        op.execute(
            f"CREATE TRIGGER {table}_retain BEFORE DELETE ON {table} BEGIN SELECT RAISE(ABORT,'Retain bulk originals and receipts'); END"
        )


def _postgres_guards():
    extra = {
        "koinon_bulk_batches": "NEW.revision < OLD.revision OR (OLD.submitted AND NOT NEW.submitted) OR (OLD.cancelled AND NOT NEW.cancelled)",
        "koinon_bulk_items": "(OLD.winning_upload_id IS NOT NULL AND NEW.winning_upload_id IS DISTINCT FROM OLD.winning_upload_id) OR (OLD.native_workspace_id IS NOT NULL AND NEW.native_workspace_id IS DISTINCT FROM OLD.native_workspace_id) OR (OLD.native_id IS NOT NULL AND NEW.native_id IS DISTINCT FROM OLD.native_id) OR (OLD.job_id IS NOT NULL AND (NEW.job_id IS DISTINCT FROM OLD.job_id OR NEW.connection_json::jsonb IS DISTINCT FROM OLD.connection_json::jsonb)) OR (OLD.receipt_json IS NOT NULL AND NEW.receipt_json::jsonb IS DISTINCT FROM OLD.receipt_json::jsonb) OR (OLD.status = 'succeeded' AND NEW.status != 'succeeded')",
        "koinon_bulk_uploads": "(NOT OLD.permit_held AND NEW.permit_held) OR (OLD.status = 'verified' AND NEW.status != 'verified')",
        "koinon_bulk_quotas": "NEW.reserved_bytes < OLD.reserved_bytes",
    }
    for table, mutable in MUTABLE.items():
        fields = "ARRAY[" + ",".join("'" + field + "'" for field in mutable) + "]::text[]"
        op.execute(f"""CREATE FUNCTION {table}_guard() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            IF TG_OP = 'DELETE' THEN RAISE EXCEPTION 'Retain bulk originals and receipts'; END IF;
            IF (to_jsonb(NEW) - {fields}) IS DISTINCT FROM (to_jsonb(OLD) - {fields}) OR {extra[table]} THEN
                RAISE EXCEPTION 'Immutable bulk identity or receipt';
            END IF;
            RETURN NEW;
        END $$""")
        op.execute(
            f"CREATE TRIGGER {table}_retain BEFORE UPDATE OR DELETE ON {table} FOR EACH ROW EXECUTE FUNCTION {table}_guard()"
        )


def downgrade():
    raise RuntimeError("Use a reviewed backup/restore recovery plan for durable bulk intake")
