# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Manual recovery records are independent from automatic welcome admission."""

from datetime import datetime

from pyfly.data.relational.sqlalchemy import Base, UtcDateTime
from sqlalchemy import DDL, CheckConstraint, ForeignKey, String, UniqueConstraint, event
from sqlalchemy.orm import Mapped, mapped_column

from koinon.catalog.entities import Tenant
from koinon.communications.contact_entities import OperatorContactRecord
from koinon.communications.entities import OutboxRecord


class WelcomeRecoveryRecord(Base):
    __tablename__ = "koinon_welcome_recoveries"
    __table_args__ = (
        UniqueConstraint("tenant_id", "request_key", name="uq_welcome_recovery_request"),
        UniqueConstraint("delivery_id", name="uq_welcome_recovery_delivery"),
        CheckConstraint(
            "authority_kind IN ('administrator','operator')", name="ck_welcome_recovery_authority"
        ),
        CheckConstraint(
            "contact_revision>=1 AND original_generation>=0", name="ck_welcome_recovery_versions"
        ),
        CheckConstraint("reason='recipient_reported_not_received'", name="ck_welcome_recovery_reason"),
    )
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey(Tenant.id), index=True)
    original_delivery_id: Mapped[str] = mapped_column(ForeignKey(OutboxRecord.id), index=True)
    original_generation: Mapped[int] = mapped_column()
    delivery_id: Mapped[str] = mapped_column(ForeignKey(OutboxRecord.id))
    contact_id: Mapped[str] = mapped_column(ForeignKey(OperatorContactRecord.id))
    contact_revision: Mapped[int] = mapped_column()
    request_key: Mapped[str] = mapped_column(String(64))
    request_hash: Mapped[str] = mapped_column(String(64))
    authority_kind: Mapped[str] = mapped_column(String(32))
    requested_by: Mapped[str] = mapped_column(String(512))
    origin_token_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    reason: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(UtcDateTime())


def immutable_guards(table, dialect):
    if dialect not in {"sqlite", "postgresql"}:
        raise RuntimeError("Email recovery requires PostgreSQL or SQLite")
    if dialect == "sqlite":
        return tuple(
            f"CREATE TRIGGER {table}_no_{kind} BEFORE {kind.upper()} ON {table} "
            "BEGIN SELECT RAISE(ABORT,'Communication recovery evidence is immutable'); END"
            for kind in ("update", "delete")
        )
    return (
        f"CREATE FUNCTION public.{table}_guard() RETURNS trigger LANGUAGE plpgsql "
        "SECURITY INVOKER SET search_path=pg_catalog AS $$ BEGIN "
        "RAISE EXCEPTION 'Communication recovery evidence is immutable' USING ERRCODE='23000'; END; $$",
        f"CREATE TRIGGER {table}_rows BEFORE UPDATE OR DELETE ON public.{table} "
        f"FOR EACH ROW EXECUTE FUNCTION public.{table}_guard()",
        f"CREATE TRIGGER {table}_truncate BEFORE TRUNCATE ON public.{table} "
        f"FOR EACH STATEMENT EXECUTE FUNCTION public.{table}_guard()",
    )


def operator_insert_guard(table, predicate, dialect):
    if dialect != "postgresql":
        return ()
    return (
        f"CREATE FUNCTION public.{table}_operator_insert() RETURNS trigger LANGUAGE plpgsql "
        "SECURITY INVOKER SET search_path=pg_catalog AS $$ BEGIN "
        f"IF ({predicate}) AND NOT (has_table_privilege(current_user,"
        "'public.koinon_operator_delivery_contacts','INSERT') AND "
        "has_column_privilege(current_user,'public.koinon_operator_delivery_contacts','revision','UPDATE')) "
        "THEN RAISE EXCEPTION 'An operator delivery action requires the operator database capability' "
        "USING ERRCODE='42501'; END IF; RETURN NEW; END; $$",
        f"CREATE TRIGGER {table}_operator_admission BEFORE INSERT ON public.{table} "
        f"FOR EACH ROW EXECUTE FUNCTION public.{table}_operator_insert()",
    )


for dialect in ("sqlite", "postgresql"):
    for statement in (
        *immutable_guards(WelcomeRecoveryRecord.__tablename__, dialect),
        *operator_insert_guard(WelcomeRecoveryRecord.__tablename__, "NEW.authority_kind='operator'", dialect),
    ):
        event.listen(
            WelcomeRecoveryRecord.__table__, "after_create", DDL(statement).execute_if(dialect=dialect)
        )
