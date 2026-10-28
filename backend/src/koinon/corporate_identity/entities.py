# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from datetime import UTC, datetime

from pyfly.data.relational.sqlalchemy import Base, UtcDateTime
from sqlalchemy import JSON, ForeignKey, LargeBinary, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column


class CorporateProvider(Base):
    __tablename__ = "koinon_identity_providers"
    __table_args__ = (UniqueConstraint("tenant_id", "source_key", name="uq_koinon_identity_source"),)
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("lattice_tenants.id"), index=True)
    kind: Mapped[str] = mapped_column(String(32))
    name: Mapped[str] = mapped_column(String(120))
    canonical_issuer: Mapped[str] = mapped_column(String(2048))
    broker_alias: Mapped[str | None] = mapped_column(String(64), nullable=True)
    source_key: Mapped[str] = mapped_column(String(64))
    settings_json: Mapped[dict] = mapped_column(JSON, default=dict)
    secret_ciphertext: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    credential_reference: Mapped[str | None] = mapped_column(String(120), nullable=True)
    ownership: Mapped[str] = mapped_column(String(24), default="tenant")
    revision: Mapped[int] = mapped_column(default=1)
    policy_revision: Mapped[int] = mapped_column(default=1)
    status: Mapped[str] = mapped_column(String(24), default="draft")
    checks_json: Mapped[list] = mapped_column(JSON, default=list)
    observed_at: Mapped[datetime | None] = mapped_column(UtcDateTime(), nullable=True)
    created_by: Mapped[str] = mapped_column(String(512))
    updated_by: Mapped[str] = mapped_column(String(512))
    created_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=lambda: datetime.now(UTC))


class CorporateMapping(Base):
    __tablename__ = "koinon_identity_mappings"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("lattice_tenants.id"), index=True)
    provider_id: Mapped[str] = mapped_column(ForeignKey("koinon_identity_providers.id"), index=True)
    group_id: Mapped[str] = mapped_column(String(256))
    group_name: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(32))
    workspace_id: Mapped[str | None] = mapped_column(ForeignKey("lattice_catalog.id"), nullable=True)
    enabled: Mapped[bool] = mapped_column(default=True)
    revision: Mapped[int] = mapped_column(default=1)


class CorporateGrant(Base):
    __tablename__ = "koinon_identity_grants"
    __table_args__ = (
        UniqueConstraint("provider_id", "subject", "mapping_id", name="uq_koinon_managed_grant"),
    )
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("lattice_tenants.id"), index=True)
    provider_id: Mapped[str] = mapped_column(ForeignKey("koinon_identity_providers.id"), index=True)
    mapping_id: Mapped[str] = mapped_column(ForeignKey("koinon_identity_mappings.id"))
    subject: Mapped[str] = mapped_column(String(512), index=True)
    external_subject: Mapped[str] = mapped_column(String(512))
    workspace_id: Mapped[str | None] = mapped_column(ForeignKey("lattice_catalog.id"), nullable=True)
    role: Mapped[str] = mapped_column(String(32))
    policy_revision: Mapped[int] = mapped_column()
    mapping_revision: Mapped[int] = mapped_column()
    active: Mapped[bool] = mapped_column(default=True)
    observed_at: Mapped[datetime] = mapped_column(UtcDateTime())
    expires_at: Mapped[datetime] = mapped_column(UtcDateTime(), index=True)


class CorporateValidation(Base):
    __tablename__ = "koinon_identity_validations"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("lattice_tenants.id"), index=True)
    provider_id: Mapped[str] = mapped_column(ForeignKey("koinon_identity_providers.id"), index=True)
    requested_by: Mapped[str] = mapped_column(String(512))
    revision: Mapped[int] = mapped_column()
    policy_revision: Mapped[int] = mapped_column()
    status: Mapped[str] = mapped_column(String(24), default="pending")
    checks_json: Mapped[list] = mapped_column(JSON, default=list)
    issued_at: Mapped[datetime] = mapped_column(UtcDateTime())
    expires_at: Mapped[datetime] = mapped_column(UtcDateTime(), index=True)
    started_at: Mapped[datetime | None] = mapped_column(UtcDateTime(), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(UtcDateTime(), nullable=True)
