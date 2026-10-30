# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from datetime import datetime

from pyfly.data.relational.sqlalchemy import Base, UtcDateTime
from sqlalchemy import CheckConstraint, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column


class OrganizationBrandingSetting(Base):
    __tablename__ = "koinon_organization_branding"
    __table_args__ = (
        CheckConstraint("schema_version = 1", name="ck_org_branding_schema"),
        CheckConstraint("revision >= 1 AND revision <= 2147483647", name="ck_org_branding_revision"),
        CheckConstraint(
            "branding_json IS NULL OR length(branding_json) <= 1572864", name="ck_org_branding_size"
        ),
    )
    tenant_id: Mapped[str] = mapped_column(ForeignKey("lattice_tenants.id"), primary_key=True)
    schema_version: Mapped[int] = mapped_column()
    revision: Mapped[int] = mapped_column()
    branding_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_by: Mapped[str] = mapped_column(String(512))
    updated_at: Mapped[datetime] = mapped_column(UtcDateTime())
