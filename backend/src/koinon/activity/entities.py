# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Minimal append-only transport facts and installation observation coverage."""

from datetime import datetime

from pyfly.data.relational.sqlalchemy import Base, UtcDateTime
from sqlalchemy import DDL, CheckConstraint, ForeignKey, Index, String, event, func
from sqlalchemy.orm import Mapped, mapped_column


class ActivityEvent(Base):
    __tablename__ = "koinon_activity_events"
    __table_args__ = (
        CheckConstraint("kind IN ('request', 'tool')", name="ck_activity_kind"),
        CheckConstraint(
            "outcome IN ('succeeded', 'failed', 'rejected', 'cancelled')", name="ck_activity_outcome"
        ),
        CheckConstraint("duration_ms >= 0 AND duration_ms <= 86400000", name="ck_activity_duration"),
        Index("ix_activity_tenant_subject_time_kind", "tenant_id", "subject", "created_at", "kind"),
        Index("ix_activity_tenant_time_kind", "tenant_id", "created_at", "kind"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("lattice_tenants.id"))
    subject: Mapped[str] = mapped_column(String(512))
    workspace_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    kind: Mapped[str] = mapped_column(String(16))
    operation: Mapped[str] = mapped_column(String(80))
    outcome: Mapped[str] = mapped_column(String(16))
    duration_ms: Mapped[int] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(UtcDateTime(), server_default=func.current_timestamp())


class ActivityCoverageState(Base):
    __tablename__ = "koinon_activity_coverage"
    __table_args__ = (CheckConstraint("id = 'installation'", name="ck_activity_coverage_singleton"),)
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    coverage_started_at: Mapped[datetime] = mapped_column(
        UtcDateTime(), server_default=func.current_timestamp()
    )


def _append_only(table) -> None:
    name = table.name
    for operation in ("UPDATE", "DELETE"):
        event.listen(
            table,
            "after_create",
            DDL(
                f"CREATE TRIGGER {name}_immutable_{operation.lower()} BEFORE {operation} ON {name} "
                "BEGIN SELECT RAISE(ABORT, 'Activity observations are append-only'); END"
            ).execute_if(dialect="sqlite"),
        )
    function = f"{name}_immutable"
    for statement in (
        f"CREATE FUNCTION {function}() RETURNS trigger LANGUAGE plpgsql AS $$ "
        "BEGIN RAISE EXCEPTION 'Activity observations are append-only' USING ERRCODE = '23000'; END; $$",
        f"CREATE TRIGGER {function}_rows BEFORE UPDATE OR DELETE ON {name} "
        f"FOR EACH ROW EXECUTE FUNCTION {function}()",
        f"CREATE TRIGGER {function}_truncate BEFORE TRUNCATE ON {name} "
        f"FOR EACH STATEMENT EXECUTE FUNCTION {function}()",
    ):
        event.listen(table, "after_create", DDL(statement).execute_if(dialect="postgresql"))


_append_only(ActivityEvent.__table__)
_append_only(ActivityCoverageState.__table__)
