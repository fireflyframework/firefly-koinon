# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Immutable provider bindings, inspection admissions and operation-only observations."""

from datetime import datetime

from pyfly.data.relational.sqlalchemy import Base, UtcDateTime
from sqlalchemy import DDL, CheckConstraint, ForeignKey, String, UniqueConstraint, event
from sqlalchemy.orm import Mapped, mapped_column

from koinon.catalog.entities import Tenant
from koinon.communications.entities import OutboxRecord
from koinon.communications.recovery_entities import immutable_guards, operator_insert_guard


class DeliveryBindingRecord(Base):
    __tablename__ = "koinon_email_provider_bindings"
    __table_args__ = (
        CheckConstraint(
            "(source='dispatch' AND evidence_sha256 IS NULL) OR "
            "(source='operator_historical' AND evidence_sha256 IS NOT NULL AND length(evidence_sha256)=64)",
            name="ck_email_binding_source",
        ),
    )
    id: Mapped[str] = mapped_column(ForeignKey(OutboxRecord.id), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey(Tenant.id), index=True)
    provider: Mapped[str] = mapped_column(String(64))
    instance_sha256: Mapped[str] = mapped_column(String(64))
    operation_id: Mapped[str] = mapped_column(String(64))
    source: Mapped[str] = mapped_column(String(32))
    evidence_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime())


class DeliveryInspectionRecord(Base):
    __tablename__ = "koinon_email_operation_inspections"
    __table_args__ = (
        UniqueConstraint("tenant_id", "request_key", name="uq_email_inspection_request"),
        CheckConstraint("generation>=0 AND lease_until>created_at", name="ck_email_inspection_lease"),
        CheckConstraint(
            "authority_kind IN ('administrator','operator')", name="ck_email_inspection_authority"
        ),
    )
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey(Tenant.id), index=True)
    delivery_id: Mapped[str] = mapped_column(ForeignKey(DeliveryBindingRecord.id), index=True)
    generation: Mapped[int] = mapped_column()
    request_key: Mapped[str] = mapped_column(String(64))
    request_hash: Mapped[str] = mapped_column(String(64))
    requested_by: Mapped[str] = mapped_column(String(512))
    authority_kind: Mapped[str] = mapped_column(String(32))
    origin_token_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime())
    lease_until: Mapped[datetime] = mapped_column(UtcDateTime())


class DeliveryObservationRecord(Base):
    __tablename__ = "koinon_email_operation_observations"
    __table_args__ = (
        CheckConstraint(
            "operation_state IN ('pending','accepted','rejected','unknown','unavailable')",
            name="ck_email_operation_state",
        ),
    )
    id: Mapped[str] = mapped_column(ForeignKey(DeliveryInspectionRecord.id), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey(Tenant.id), index=True)
    delivery_id: Mapped[str] = mapped_column(ForeignKey(OutboxRecord.id), index=True)
    operation_state: Mapped[str] = mapped_column(String(32))
    reason_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    checked_at: Mapped[datetime] = mapped_column(UtcDateTime())


for table_name, table, predicate in (
    (
        DeliveryBindingRecord.__tablename__,
        DeliveryBindingRecord.__table__,
        "NEW.source='operator_historical'",
    ),
    (
        DeliveryInspectionRecord.__tablename__,
        DeliveryInspectionRecord.__table__,
        "NEW.authority_kind='operator'",
    ),
    (DeliveryObservationRecord.__tablename__, DeliveryObservationRecord.__table__, None),
):
    for dialect in ("sqlite", "postgresql"):
        statements = (
            *immutable_guards(table_name, dialect),
            *(operator_insert_guard(table_name, predicate, dialect) if predicate else ()),
        )
        for statement in statements:
            event.listen(table, "after_create", DDL(statement).execute_if(dialect=dialect))
