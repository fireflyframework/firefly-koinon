# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Enrollment identity is immutable; activation is a single monotonic transition."""

from datetime import datetime

from pyfly.data.relational.sqlalchemy import Base, UtcDateTime
from sqlalchemy import DDL, CheckConstraint, ForeignKey, Index, String, UniqueConstraint, event, func
from sqlalchemy.orm import Mapped, mapped_column

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


class BootstrapIdentityGrant(Base):
    __tablename__ = "koinon_bootstrap_identity_grants"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "canonical_issuer",
            "native_client_id",
            "entra_tenant_id",
            "object_id",
            name="uq_bootstrap_identity_scope",
        ),
        CheckConstraint("role = 'admin'", name="ck_bootstrap_admin_role"),
        CheckConstraint("expires_at > created_at", name="ck_bootstrap_expiry"),
        CheckConstraint(
            "(consumed_at IS NULL AND consumed_subject IS NULL AND membership_id IS NULL) OR "
            "(consumed_at IS NOT NULL AND consumed_subject IS NOT NULL AND membership_id IS NOT NULL)",
            name="ck_bootstrap_activation_complete",
        ),
        Index(
            "ix_bootstrap_pending_identity",
            "canonical_issuer",
            "native_client_id",
            "entra_tenant_id",
            "object_id",
            "consumed_at",
        ),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("lattice_tenants.id"))
    canonical_issuer: Mapped[str] = mapped_column(String(512))
    native_client_id: Mapped[str] = mapped_column(String(255))
    entra_tenant_id: Mapped[str] = mapped_column(String(36))
    object_id: Mapped[str] = mapped_column(String(36))
    role: Mapped[str] = mapped_column(String(32))
    expires_at: Mapped[datetime] = mapped_column(UtcDateTime())
    created_at: Mapped[datetime] = mapped_column(UtcDateTime(), server_default=func.current_timestamp())
    consumed_at: Mapped[datetime | None] = mapped_column(UtcDateTime(), nullable=True)
    consumed_subject: Mapped[str | None] = mapped_column(String(512), nullable=True)
    # Historical receipt, retained even if the corresponding membership is later removed.
    membership_id: Mapped[str | None] = mapped_column(String(64), nullable=True)


def guard_statements(dialect: str) -> tuple[str, ...]:
    table = BootstrapIdentityGrant.__tablename__
    member_table = "main.lattice_memberships" if dialect == "sqlite" else "public.lattice_memberships"
    member = (
        f"EXISTS (SELECT 1 FROM {member_table} m WHERE m.id=NEW.membership_id "
        "AND m.tenant_id=OLD.tenant_id AND m.subject=NEW.consumed_subject "
        "AND m.workspace_id IS NULL AND m.role=OLD.role AND m.active)"
    )
    if dialect not in {"sqlite", "postgresql"}:
        raise RuntimeError("Bootstrap grants require PostgreSQL or SQLite")
    comparison = "IS NOT" if dialect == "sqlite" else "IS DISTINCT FROM"
    changed = " OR ".join(f"NEW.{name} {comparison} OLD.{name}" for name in IMMUTABLE_COLUMNS)
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


for dialect in ("sqlite", "postgresql"):
    for statement in guard_statements(dialect):
        event.listen(
            BootstrapIdentityGrant.__table__, "after_create", DDL(statement).execute_if(dialect=dialect)
        )
