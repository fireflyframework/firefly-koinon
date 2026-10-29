# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from datetime import datetime

from pyfly.data.relational.sqlalchemy import Base, UtcDateTime
from sqlalchemy import JSON, CheckConstraint, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column


class OrganizationKnowledgeSetting(Base):
    __tablename__ = "koinon_organization_knowledge_settings"
    __table_args__ = (
        CheckConstraint("schema_version = 1", name="ck_org_knowledge_schema"),
        CheckConstraint("revision >= 1 AND revision <= 2147483647", name="ck_org_knowledge_revision"),
    )
    tenant_id: Mapped[str] = mapped_column(ForeignKey("lattice_tenants.id"), primary_key=True)
    schema_version: Mapped[int] = mapped_column()
    revision: Mapped[int] = mapped_column()
    documents: Mapped[dict] = mapped_column(JSON)
    structured: Mapped[dict] = mapped_column(JSON)
    updated_by: Mapped[str] = mapped_column(String(512))
    updated_at: Mapped[datetime] = mapped_column(UtcDateTime())
