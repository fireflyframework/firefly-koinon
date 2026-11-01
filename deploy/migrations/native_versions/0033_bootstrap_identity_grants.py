# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Single-use operator-seeded administrator enrollment, never runtime reseeding."""

import sqlalchemy as sa
from alembic import op
from pyfly.data.relational.sqlalchemy import UtcDateTime

revision = "koinon_0033_bootstrap"
down_revision = "koinon_0032_large_files"
branch_labels = None
depends_on = None


IMMUTABLE_COLUMNS = (
    "id",
    "tenant_id",
    "canonical_issuer",
    "native_client_id",
    "entra_tenant_id",
    "object_id",
    "role",
    "expires_at",
    "created_at",
)
ACTIVATION_COLUMNS = ("consumed_at", "consumed_subject", "membership_id")


def guard_statements(dialect: str) -> tuple[str, ...]:
    table = "koinon_bootstrap_identity_grants"
    member_table = "main.lattice_memberships" if dialect == "sqlite" else "public.lattice_memberships"
    member = (
        f"EXISTS (SELECT 1 FROM {member_table} m WHERE m.id=NEW.membership_id "
        "AND m.tenant_id=OLD.tenant_id AND m.subject=NEW.consumed_subject "
        "AND m.workspace_id IS NULL AND m.role=OLD.role AND m.active)"
    )
    if dialect not in {"sqlite", "postgresql"}:
        raise RuntimeError("Bootstrap grants require PostgreSQL or SQLite")
    comparison = "IS NOT" if dialect == "sqlite" else "IS DISTINCT FROM"
    changed = " OR ".join(
        f"NEW.{name} {comparison} OLD.{name}" for name in IMMUTABLE_COLUMNS
    )
    prefix = (
        "substr(NEW.consumed_subject,1,length(OLD.canonical_issuer)+1)"
        if dialect == "sqlite"
        else "left(NEW.consumed_subject,length(OLD.canonical_issuer)+1)"
    )
    invalid = (
        f"OLD.consumed_at IS NOT NULL OR {changed} OR NEW.consumed_at IS NULL "
        "OR NEW.consumed_subject IS NULL OR NEW.membership_id IS NULL "
        "OR OLD.expires_at <= CURRENT_TIMESTAMP "
        f"OR {prefix} != OLD.canonical_issuer || '|' "
        f"OR length(NEW.consumed_subject) <= length(OLD.canonical_issuer)+1 OR NOT {member}"
    )
    if dialect == "sqlite":
        return (
            f"CREATE TRIGGER {table}_activate BEFORE UPDATE ON {table} WHEN {invalid} "
            "BEGIN SELECT RAISE(ABORT,'Bootstrap grant transition is immutable'); END",
            f"CREATE TRIGGER {table}_no_delete BEFORE DELETE ON {table} "
            "BEGIN SELECT RAISE(ABORT,'Bootstrap grants cannot be deleted'); END",
        )
    return (
        f"CREATE FUNCTION {table}_guard() RETURNS trigger LANGUAGE plpgsql "
        "SET search_path=pg_catalog AS $$ BEGIN "
        "IF TG_OP IN ('DELETE','TRUNCATE') THEN RAISE EXCEPTION 'Bootstrap grants cannot be deleted' "
        "USING ERRCODE='23000'; END IF; "
        f"IF {invalid} THEN RAISE EXCEPTION 'Bootstrap grant transition is immutable' "
        "USING ERRCODE='23000'; END IF; RETURN NEW; END; $$",
        f"CREATE TRIGGER {table}_rows BEFORE UPDATE OR DELETE ON {table} "
        f"FOR EACH ROW EXECUTE FUNCTION {table}_guard()",
        f"CREATE TRIGGER {table}_truncate BEFORE TRUNCATE ON {table} "
        f"FOR EACH STATEMENT EXECUTE FUNCTION {table}_guard()",
    )


def upgrade():
    op.create_table(
        "koinon_bootstrap_identity_grants",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "tenant_id",
            sa.String(64),
            sa.ForeignKey("lattice_tenants.id"),
            nullable=False,
        ),
        sa.Column("canonical_issuer", sa.String(512), nullable=False),
        sa.Column("native_client_id", sa.String(255), nullable=False),
        sa.Column("entra_tenant_id", sa.String(36), nullable=False),
        sa.Column("object_id", sa.String(36), nullable=False),
        sa.Column("role", sa.String(32), nullable=False),
        sa.Column("expires_at", UtcDateTime(), nullable=False),
        sa.Column(
            "created_at",
            UtcDateTime(),
            nullable=False,
            server_default=sa.func.current_timestamp(),
        ),
        sa.Column("consumed_at", UtcDateTime(), nullable=True),
        sa.Column("consumed_subject", sa.String(512), nullable=True),
        sa.Column("membership_id", sa.String(64), nullable=True),
        sa.UniqueConstraint(
            "tenant_id",
            "canonical_issuer",
            "native_client_id",
            "entra_tenant_id",
            "object_id",
            name="uq_bootstrap_identity_scope",
        ),
        sa.CheckConstraint("role = 'admin'", name="ck_bootstrap_admin_role"),
        sa.CheckConstraint("expires_at > created_at", name="ck_bootstrap_expiry"),
        sa.CheckConstraint(
            "(consumed_at IS NULL AND consumed_subject IS NULL AND membership_id IS NULL) OR "
            "(consumed_at IS NOT NULL AND consumed_subject IS NOT NULL AND membership_id IS NOT NULL)",
            name="ck_bootstrap_activation_complete",
        ),
    )
    op.create_index(
        "ix_bootstrap_pending_identity",
        "koinon_bootstrap_identity_grants",
        [
            "canonical_issuer",
            "native_client_id",
            "entra_tenant_id",
            "object_id",
            "consumed_at",
        ],
    )
    for statement in guard_statements(op.get_bind().dialect.name):
        op.execute(sa.text(statement))


def downgrade():
    raise RuntimeError(
        "Use a reviewed restore plan to preserve consumed bootstrap grants"
    )
