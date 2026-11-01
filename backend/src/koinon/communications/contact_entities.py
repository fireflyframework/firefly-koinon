# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from datetime import datetime

from pyfly.data.relational.sqlalchemy import Base, UtcDateTime
from sqlalchemy import DDL, JSON, CheckConstraint, ForeignKey, String, Text, UniqueConstraint, event
from sqlalchemy.orm import Mapped, mapped_column

from koinon.catalog.entities import Tenant
from koinon.communications.contact_guards import contact_guards


class OperatorContactRecord(Base):
    __tablename__ = "koinon_operator_delivery_contacts"
    __table_args__ = (
        UniqueConstraint("tenant_id", "identity_key", name="uq_operator_delivery_identity"),
        CheckConstraint("revision>=1 AND expires_at>observed_at", name="ck_operator_contact_revision_expiry"),
        CheckConstraint(
            "(canonical_subject IS NULL AND binding_ciphertext IS NULL AND bound_at IS NULL) OR "
            "(canonical_subject IS NOT NULL AND binding_ciphertext IS NOT NULL AND bound_at IS NOT NULL)",
            name="ck_operator_contact_binding",
        ),
    )
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey(Tenant.id), index=True)
    identity_key: Mapped[str] = mapped_column(String(64))
    identity_json: Mapped[dict] = mapped_column(JSON)
    contact_ciphertext: Mapped[str] = mapped_column(Text)
    revision: Mapped[int] = mapped_column(default=1)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime())
    observed_at: Mapped[datetime] = mapped_column(UtcDateTime())
    expires_at: Mapped[datetime] = mapped_column(UtcDateTime())
    revoked_at: Mapped[datetime | None] = mapped_column(UtcDateTime(), nullable=True)
    canonical_subject: Mapped[str | None] = mapped_column(String(512), nullable=True, index=True)
    binding_ciphertext: Mapped[str | None] = mapped_column(Text, nullable=True)
    bound_at: Mapped[datetime | None] = mapped_column(UtcDateTime(), nullable=True)


for dialect in ("sqlite", "postgresql"):
    for statement in contact_guards(dialect):
        event.listen(
            OperatorContactRecord.__table__, "after_create", DDL(statement).execute_if(dialect=dialect)
        )
