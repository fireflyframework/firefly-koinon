# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from datetime import UTC, datetime

from pyfly.data.relational.sqlalchemy import Base, UtcDateTime
from sqlalchemy import (
    JSON,
    CheckConstraint,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    LargeBinary,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column


def now():
    return datetime.now(UTC)


class CorporateProfileSnapshot(Base):
    __tablename__ = "koinon_corporate_profile_snapshots"
    __table_args__ = (
        CheckConstraint(
            "(provider_id IS NOT NULL AND external_subject IS NOT NULL) OR "
            "(provider_id IS NULL AND external_subject IS NULL AND status = 'conflict')",
            name="ck_corporate_profile_binding",
        ),
        UniqueConstraint("tenant_id", "subject", name="uq_corporate_profile_owner"),
        UniqueConstraint(
            "tenant_id", "provider_id", "external_subject", name="uq_corporate_profile_external"
        ),
        ForeignKeyConstraint(
            ["tenant_id", "provider_id"],
            ["koinon_identity_providers.tenant_id", "koinon_identity_providers.id"],
        ),
        Index("ix_corporate_profile_due", "next_due_at", "lease_until"),
    )
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("lattice_tenants.id"))
    subject: Mapped[str] = mapped_column(String(512))
    provider_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    external_subject: Mapped[str | None] = mapped_column(String(512), nullable=True)
    source_fingerprint: Mapped[str] = mapped_column(String(64))
    verified_domain: Mapped[str | None] = mapped_column(String(253), nullable=True)
    verified_external_tenant: Mapped[str | None] = mapped_column(String(64), nullable=True)
    binding_revision: Mapped[int] = mapped_column(default=1)
    provider_revision: Mapped[int] = mapped_column(default=0)
    mapping_revision: Mapped[int] = mapped_column(default=0)
    revision: Mapped[int] = mapped_column(default=1)
    display_name: Mapped[str | None] = mapped_column(String(256), nullable=True)
    name_available: Mapped[bool] = mapped_column(default=False)
    department: Mapped[str | None] = mapped_column(String(160), nullable=True)
    avatar_bytes: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    avatar_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    avatar_available: Mapped[bool] = mapped_column(default=False)
    fields_json: Mapped[list] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(String(24), default="queued")
    last_attempt_at: Mapped[datetime | None] = mapped_column(UtcDateTime(), nullable=True)
    last_success_at: Mapped[datetime | None] = mapped_column(UtcDateTime(), nullable=True)
    next_due_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=now)
    worker_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    lease_until: Mapped[datetime | None] = mapped_column(UtcDateTime(), nullable=True)
    lease_generation: Mapped[int] = mapped_column(default=0)
    claims_observed_at: Mapped[datetime | None] = mapped_column(UtcDateTime(), nullable=True)
    verified_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=now)
    updated_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=now)


class OrganizationPresentationPreference(Base):
    __tablename__ = "koinon_organization_presentation_preferences"
    tenant_id: Mapped[str] = mapped_column(ForeignKey("lattice_tenants.id"), primary_key=True)
    subject: Mapped[str] = mapped_column(String(512), primary_key=True)
    name_mode: Mapped[str] = mapped_column(String(24), default="organization")
    avatar_mode: Mapped[str] = mapped_column(String(24), default="organization")
    revision: Mapped[int] = mapped_column(default=1)
    updated_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=now)
