# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Add database publication fences without altering published original guards."""

import sqlalchemy as sa
from alembic import op
from pyfly.data.relational.sqlalchemy import UtcDateTime

revision = "koinon_0029_bulk_staging"
down_revision = "koinon_0028_bulk_queries"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "koinon_bulk_upload_states",
        sa.Column("upload_id", sa.String(64), sa.ForeignKey("koinon_bulk_uploads.id"), primary_key=True),
        sa.Column("generation", sa.Integer(), nullable=False),
        sa.Column("owner_hash", sa.String(64), nullable=False),
        sa.Column("operation", sa.String(16), nullable=False),
        sa.Column("lease_until", UtcDateTime(), nullable=False),
        sa.Column("storage_identity", sa.String(64), nullable=False),
        sa.Column("recovery_id", sa.String(64), nullable=True),
        sa.CheckConstraint("generation BETWEEN 1 AND 2147483647", name="ck_bulk_writer_generation"),
        sa.CheckConstraint("operation IN ('writing','verifying','closed')", name="ck_bulk_writer_operation"),
    )
    op.create_index(
        "ix_bulk_writer_expiry", "koinon_bulk_upload_states", ["operation", "lease_until", "upload_id"]
    )
    op.create_table(
        "koinon_bulk_recoveries",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("batch_id", sa.String(64), sa.ForeignKey("koinon_bulk_batches.id"), nullable=False),
        sa.Column("upload_id", sa.String(64), sa.ForeignKey("koinon_bulk_uploads.id"), nullable=False),
        sa.Column("key_hash", sa.String(64), nullable=False),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("fenced_revision", sa.Integer(), nullable=False),
        sa.Column("generation", sa.Integer(), nullable=False),
        sa.Column("owner_hash", sa.String(64), nullable=False),
        sa.Column("lease_until", UtcDateTime(), nullable=False),
        sa.Column("permit_held", sa.Boolean(), nullable=False),
        sa.Column("completed", sa.Boolean(), nullable=False),
        sa.UniqueConstraint("batch_id", "key_hash", name="uq_bulk_recovery_key"),
        sa.CheckConstraint("generation BETWEEN 1 AND 2147483647", name="ck_bulk_recovery_generation"),
    )
    install_guards()


def install_guards():
    dialect = op.get_bind().dialect.name
    if dialect not in {"sqlite", "postgresql"}:
        raise RuntimeError("Bulk staging fences require PostgreSQL or SQLite")
    guards = {
        "koinon_bulk_upload_states": (
            ("upload_id", "storage_identity"),
            "NEW.generation < OLD.generation OR NEW.generation > OLD.generation + 1 "
            "OR NEW.operation = 'writing' AND OLD.operation != 'writing' "
            "OR NEW.operation = 'writing' AND NEW.generation != OLD.generation "
            "OR NEW.generation = OLD.generation AND (NEW.owner_hash != OLD.owner_hash "
            "OR NEW.lease_until > OLD.lease_until OR NEW.recovery_id {different} OLD.recovery_id "
            "OR NEW.operation != OLD.operation AND NEW.operation != 'closed')",
        ),
        "koinon_bulk_recoveries": (
            ("id", "batch_id", "upload_id", "key_hash", "request_hash", "fenced_revision"),
            "NEW.generation < OLD.generation "
            "OR OLD.completed AND ({row_changed}) "
            "OR NEW.generation = OLD.generation AND (NEW.owner_hash != OLD.owner_hash "
            "OR NEW.lease_until > OLD.lease_until OR NOT OLD.permit_held AND NEW.permit_held)",
        ),
    }
    for table, (frozen, condition) in guards.items():
        if dialect == "sqlite":
            columns = [column["name"] for column in sa.inspect(op.get_bind()).get_columns(table)]
            changed = " OR ".join(f"NEW.{name} IS NOT OLD.{name}" for name in columns)
            immutable = " OR ".join(f"NEW.{name} IS NOT OLD.{name}" for name in frozen)
            checks = condition.format(different="IS NOT", row_changed=changed)
            op.execute(
                f"CREATE TRIGGER {table}_update BEFORE UPDATE ON {table} "
                f"WHEN {immutable} OR {checks} "
                "BEGIN SELECT RAISE(ABORT,'Retain bulk writer fences and recovery receipts'); END"
            )
            op.execute(
                f"CREATE TRIGGER {table}_delete BEFORE DELETE ON {table} "
                "BEGIN SELECT RAISE(ABORT,'Retain bulk writer fences and recovery receipts'); END"
            )
        else:
            immutable = " OR ".join(f"NEW.{name} IS DISTINCT FROM OLD.{name}" for name in frozen)
            checks = condition.format(different="IS DISTINCT FROM", row_changed="NEW IS DISTINCT FROM OLD")
            op.execute(f"REVOKE ALL ON TABLE public.{table} FROM PUBLIC")
            op.execute(f"""CREATE FUNCTION public.{table}_guard() RETURNS trigger
                LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog AS $$
                BEGIN
                    IF TG_OP = 'DELETE' THEN RAISE EXCEPTION 'Retain bulk writer fences'; END IF;
                    IF {immutable} OR {checks} THEN
                        RAISE EXCEPTION 'Retain bulk writer fences and recovery receipts';
                    END IF;
                    RETURN NEW;
                END $$""")
            op.execute(f"REVOKE ALL ON FUNCTION public.{table}_guard() FROM PUBLIC")
            op.execute(
                f"CREATE TRIGGER {table}_retain BEFORE UPDATE OR DELETE ON public.{table} "
                f"FOR EACH ROW EXECUTE FUNCTION public.{table}_guard()"
            )


def downgrade():
    raise RuntimeError("Use a reviewed retained-data backup/restore recovery plan")
