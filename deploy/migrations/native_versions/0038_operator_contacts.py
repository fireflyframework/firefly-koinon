# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Independent operator-approved delivery contacts; no identity or role grants."""

import sqlalchemy as sa
from alembic import op
from pyfly.data.relational.sqlalchemy import UtcDateTime

revision = "koinon_0038_operator_contacts"
down_revision = "koinon_0037_system_spaces"
branch_labels = None
depends_on = None

IMMUTABLE_COLUMNS = ("id", "tenant_id", "identity_key", "identity_json", "created_at")

OBSERVATION_COLUMNS = ("contact_ciphertext", "observed_at", "expires_at", "revoked_at")

BINDING_COLUMNS = ("canonical_subject", "binding_ciphertext", "bound_at")


def contact_guards(dialect: str) -> tuple[str, ...]:
    if dialect not in {"sqlite", "postgresql"}:
        raise RuntimeError("Operator contacts require PostgreSQL or SQLite")
    comparison = "IS NOT" if dialect == "sqlite" else "IS DISTINCT FROM"

    def changed(columns):
        return " OR ".join(
            f"NEW.{key}::jsonb {comparison} OLD.{key}::jsonb"
            if dialect == "postgresql" and key == "identity_json"
            else f"NEW.{key} {comparison} OLD.{key}"
            for key in columns
        )

    binding = f"({changed(BINDING_COLUMNS)})"
    invalid = (
        f"({changed(IMMUTABLE_COLUMNS)}) OR OLD.revoked_at IS NOT NULL OR "
        f"({binding} AND (OLD.canonical_subject IS NOT NULL OR NEW.canonical_subject IS NULL "
        "OR NEW.binding_ciphertext IS NULL OR NEW.bound_at IS NULL OR NEW.revision<>OLD.revision "
        f"OR ({changed(OBSERVATION_COLUMNS)}))) OR "
        f"(NOT {binding} AND (NEW.revision<>OLD.revision+1 OR NEW.observed_at<OLD.observed_at))"
    )
    table = "koinon_operator_delivery_contacts"
    if dialect == "sqlite":
        return (
            (
                f"CREATE TRIGGER {table}_update BEFORE UPDATE ON {table} WHEN {invalid} "
                "BEGIN SELECT RAISE(ABORT,'Operator contact transition is prohibited'); END"
            ),
            (
                f"CREATE TRIGGER {table}_delete BEFORE DELETE ON {table} "
                "BEGIN SELECT RAISE(ABORT,'Operator contacts cannot be deleted'); END"
            ),
        )
    return (
        (
            f"CREATE FUNCTION public.{table}_guard() RETURNS trigger LANGUAGE plpgsql "
            "SECURITY INVOKER SET search_path=pg_catalog AS $$ BEGIN "
            "IF TG_OP IN ('DELETE','TRUNCATE') THEN RAISE EXCEPTION 'Operator contacts cannot be deleted' "
            "USING ERRCODE='23000'; END IF; "
            f"IF {invalid} THEN RAISE EXCEPTION 'Operator contact transition is prohibited' "
            "USING ERRCODE='23000'; END IF; RETURN NEW; END; $$"
        ),
        (
            f"CREATE TRIGGER {table}_rows BEFORE UPDATE OR DELETE ON public.{table} "
            f"FOR EACH ROW EXECUTE FUNCTION public.{table}_guard()"
        ),
        (
            f"CREATE TRIGGER {table}_truncate BEFORE TRUNCATE ON public.{table} "
            f"FOR EACH STATEMENT EXECUTE FUNCTION public.{table}_guard()"
        ),
    )


def upgrade():
    op.create_table(
        "koinon_operator_delivery_contacts",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column(
            "tenant_id",
            sa.String(64),
            sa.ForeignKey("lattice_tenants.id"),
            nullable=False,
        ),
        sa.Column("identity_key", sa.String(64), nullable=False),
        sa.Column("identity_json", sa.JSON(), nullable=False),
        sa.Column("contact_ciphertext", sa.Text(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("created_at", UtcDateTime(), nullable=False),
        sa.Column("observed_at", UtcDateTime(), nullable=False),
        sa.Column("expires_at", UtcDateTime(), nullable=False),
        sa.Column("revoked_at", UtcDateTime(), nullable=True),
        sa.Column("canonical_subject", sa.String(512), nullable=True),
        sa.Column("binding_ciphertext", sa.Text(), nullable=True),
        sa.Column("bound_at", UtcDateTime(), nullable=True),
        sa.UniqueConstraint(
            "tenant_id", "identity_key", name="uq_operator_delivery_identity"
        ),
        sa.CheckConstraint(
            "revision>=1 AND expires_at>observed_at",
            name="ck_operator_contact_revision_expiry",
        ),
        sa.CheckConstraint(
            "(canonical_subject IS NULL AND binding_ciphertext IS NULL AND bound_at IS NULL) OR "
            "(canonical_subject IS NOT NULL AND binding_ciphertext IS NOT NULL AND bound_at IS NOT NULL)",
            name="ck_operator_contact_binding",
        ),
    )
    for field in ("tenant_id", "canonical_subject"):
        op.create_index(
            "ix_koinon_operator_delivery_contacts_" + field,
            "koinon_operator_delivery_contacts",
            [field],
        )
    for statement in contact_guards(op.get_bind().dialect.name):
        op.execute(sa.text(statement))


def downgrade():
    raise RuntimeError(
        "Use a reviewed restore to preserve recipient observations and diagnostic outcomes"
    )
