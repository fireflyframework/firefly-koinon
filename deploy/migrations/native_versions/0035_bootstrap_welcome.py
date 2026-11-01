# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Operator-pinned bootstrap welcome receipts, without creating a canonical principal."""

import sqlalchemy as sa
from alembic import op
from pyfly.data.relational.sqlalchemy import UtcDateTime

revision = "koinon_0035_bootstrap_welcome"
down_revision = "koinon_0034_postgres_cache"
branch_labels = None
depends_on = None

IMMUTABLE_CONTACT_COLUMNS = (
    "id",
    "installation_id",
    "grant_id",
    "identity_sha256",
    "event_id",
    "contact_ciphertext",
    "observed_at",
    "expires_at",
)


def contact_guards(dialect: str) -> tuple[str, ...]:
    if dialect not in {"sqlite", "postgresql"}:
        raise RuntimeError("Bootstrap contacts require PostgreSQL or SQLite")
    prefix = "main" if dialect == "sqlite" else "public"
    comparison = "IS NOT" if dialect == "sqlite" else "IS DISTINCT FROM"
    changed = " OR ".join(
        f"NEW.{key} {comparison} OLD.{key}" for key in IMMUTABLE_CONTACT_COLUMNS
    )
    binding = (
        f"EXISTS (SELECT 1 FROM {prefix}.koinon_bootstrap_identity_grants g "
        f"JOIN {prefix}.lattice_memberships m ON m.id=g.membership_id "
        "WHERE g.id=OLD.grant_id AND g.consumed_at IS NOT NULL "
        "AND g.consumed_subject=NEW.canonical_subject AND m.subject=NEW.canonical_subject "
        "AND m.tenant_id=g.tenant_id AND m.workspace_id IS NULL AND m.role='admin' AND m.active)"
    )
    invalid = f"({changed}) OR OLD.canonical_subject IS NOT NULL OR NEW.canonical_subject IS NULL OR NOT {binding}"
    if dialect == "sqlite":
        update = (
            "CREATE TRIGGER koinon_bootstrap_contacts_update BEFORE UPDATE ON koinon_bootstrap_contacts "
            f"WHEN {invalid} BEGIN SELECT RAISE(ABORT,'Bootstrap contact is immutable'); END"
        )
        delete = (
            "CREATE TRIGGER koinon_bootstrap_contacts_delete BEFORE DELETE ON koinon_bootstrap_contacts "
            "BEGIN SELECT RAISE(ABORT,'Bootstrap contacts cannot be deleted'); END"
        )
        return update, delete
    function = (
        "CREATE FUNCTION public.koinon_bootstrap_contacts_guard() RETURNS trigger LANGUAGE plpgsql "
        "SECURITY INVOKER SET search_path=pg_catalog AS $$ BEGIN "
        "IF TG_OP IN ('DELETE','TRUNCATE') THEN RAISE EXCEPTION 'Bootstrap contacts cannot be deleted' "
        "USING ERRCODE='23000'; END IF; "
        f"IF {invalid} THEN RAISE EXCEPTION 'Bootstrap contact is immutable' USING ERRCODE='23000'; "
        "END IF; RETURN NEW; END; $$"
    )
    rows = (
        "CREATE TRIGGER koinon_bootstrap_contacts_rows BEFORE UPDATE OR DELETE ON "
        "public.koinon_bootstrap_contacts FOR EACH ROW "
        "EXECUTE FUNCTION public.koinon_bootstrap_contacts_guard()"
    )
    truncate = (
        "CREATE TRIGGER koinon_bootstrap_contacts_truncate BEFORE TRUNCATE ON "
        "public.koinon_bootstrap_contacts FOR EACH STATEMENT "
        "EXECUTE FUNCTION public.koinon_bootstrap_contacts_guard()"
    )
    return function, rows, truncate


def upgrade():
    op.create_table(
        "koinon_bootstrap_contacts",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column(
            "installation_id",
            sa.String(64),
            sa.ForeignKey("koinon_installation_identity.installation_id"),
            nullable=False,
        ),
        sa.Column(
            "grant_id",
            sa.String(36),
            sa.ForeignKey("koinon_bootstrap_identity_grants.id"),
            nullable=False,
        ),
        sa.Column("identity_sha256", sa.String(64), nullable=False),
        sa.Column(
            "event_id",
            sa.String(64),
            sa.ForeignKey("koinon_communication_outbox.id"),
            nullable=False,
        ),
        sa.Column("contact_ciphertext", sa.Text(), nullable=False),
        sa.Column("observed_at", UtcDateTime(), nullable=False),
        sa.Column("expires_at", UtcDateTime(), nullable=False),
        sa.Column("canonical_subject", sa.String(512), nullable=True),
        sa.UniqueConstraint(
            "installation_id", "identity_sha256", name="uq_bootstrap_contact_identity"
        ),
        sa.UniqueConstraint("grant_id", name="uq_bootstrap_contact_grant"),
        sa.UniqueConstraint("event_id", name="uq_bootstrap_contact_event"),
        sa.CheckConstraint(
            "expires_at > observed_at", name="ck_bootstrap_contact_expiry"
        ),
    )
    op.create_index(
        "ix_koinon_bootstrap_contacts_canonical_subject",
        "koinon_bootstrap_contacts",
        ["canonical_subject"],
    )
    for statement in contact_guards(op.get_bind().dialect.name):
        op.execute(sa.text(statement))


def downgrade():
    raise RuntimeError(
        "Use a reviewed restore to preserve bootstrap welcome admission and unknown outcomes"
    )
