# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from datetime import UTC, datetime

from pyfly.data.relational.sqlalchemy import Base, UtcDateTime
from sqlalchemy import JSON, ForeignKey, ForeignKeyConstraint, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column


def now():
    return datetime.now(UTC)


class OrganizationUnitRecord(Base):
    __tablename__ = "koinon_organization_units"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="uq_org_unit_tenant_id"),
        UniqueConstraint("tenant_id", "provider_id", "external_key", name="uq_org_unit_source"),
        ForeignKeyConstraint(
            ["tenant_id", "parent_id"],
            ["koinon_organization_units.tenant_id", "koinon_organization_units.id"],
        ),
        ForeignKeyConstraint(
            ["tenant_id", "provider_id"],
            ["koinon_identity_providers.tenant_id", "koinon_identity_providers.id"],
        ),
        Index("ix_org_unit_parent", "tenant_id", "parent_id"),
    )
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("lattice_tenants.id"))
    parent_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    name: Mapped[str] = mapped_column(String(160))
    kind: Mapped[str] = mapped_column(String(24))
    revision: Mapped[int] = mapped_column(default=1)
    provider_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    external_key: Mapped[str | None] = mapped_column(String(256), nullable=True)
    updated_by: Mapped[str] = mapped_column(String(512))
    updated_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=now)


class OrganizationPersonRecord(Base):
    __tablename__ = "koinon_organization_people"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="uq_org_person_tenant_id"),
        UniqueConstraint("tenant_id", "subject", name="uq_org_person_subject"),
        ForeignKeyConstraint(
            ["tenant_id", "unit_id"], ["koinon_organization_units.tenant_id", "koinon_organization_units.id"]
        ),
        ForeignKeyConstraint(
            ["tenant_id", "manager_id"],
            ["koinon_organization_people.tenant_id", "koinon_organization_people.id"],
        ),
        ForeignKeyConstraint(
            ["tenant_id", "provider_id"],
            ["koinon_identity_providers.tenant_id", "koinon_identity_providers.id"],
        ),
        Index("ix_org_person_unit", "tenant_id", "unit_id"),
        Index("ix_org_person_manager", "tenant_id", "manager_id"),
    )
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("lattice_tenants.id"))
    subject: Mapped[str] = mapped_column(String(512))
    job_title: Mapped[str | None] = mapped_column(String(160), nullable=True)
    unit_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    manager_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    revision: Mapped[int] = mapped_column(default=1)
    provider_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    external_subject: Mapped[str | None] = mapped_column(String(512), nullable=True)
    managed_fields: Mapped[list] = mapped_column(JSON, default=list)
    pending_manager: Mapped[bool] = mapped_column(default=False)
    observed_at: Mapped[datetime | None] = mapped_column(UtcDateTime(), nullable=True)
    observation_status: Mapped[str] = mapped_column(String(24), default="not_observed")
    updated_by: Mapped[str] = mapped_column(String(512))
    updated_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=now)


class OrganizationDirectorySettingRecord(Base):
    __tablename__ = "koinon_organization_directory_settings"
    tenant_id: Mapped[str] = mapped_column(ForeignKey("lattice_tenants.id"), primary_key=True)
    visibility: Mapped[str] = mapped_column(String(32))
    revision: Mapped[int] = mapped_column(default=1)
    updated_by: Mapped[str] = mapped_column(String(512))
    updated_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=now)


class OrganizationProfileMappingRecord(Base):
    __tablename__ = "koinon_organization_profile_mappings"
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "provider_id"],
            ["koinon_identity_providers.tenant_id", "koinon_identity_providers.id"],
        ),
    )
    tenant_id: Mapped[str] = mapped_column(ForeignKey("lattice_tenants.id"), primary_key=True)
    provider_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    revision: Mapped[int] = mapped_column(default=1)
    enabled: Mapped[bool] = mapped_column(default=False)
    fields_json: Mapped[dict] = mapped_column(JSON, default=dict)
    updated_by: Mapped[str] = mapped_column(String(512))
    updated_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=now)
