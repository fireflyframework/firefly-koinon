# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from datetime import datetime

from pyfly.data.relational.sqlalchemy import Base, UtcDateTime
from sqlalchemy import CheckConstraint, ForeignKey, ForeignKeyConstraint, String
from sqlalchemy.orm import Mapped, mapped_column


class OrganizationChatSetting(Base):
    __tablename__ = "koinon_organization_chat_settings"
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "default_agent_id"],
            ["koinon_agents.tenant_id", "koinon_agents.id"],
            name="fk_org_chat_tenant_agent",
        ),
        CheckConstraint("revision >= 1 AND revision <= 2147483647", name="ck_org_chat_revision"),
    )
    tenant_id: Mapped[str] = mapped_column(ForeignKey("lattice_tenants.id"), primary_key=True)
    default_agent_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    revision: Mapped[int] = mapped_column()
    updated_by: Mapped[str] = mapped_column(String(512))
    updated_at: Mapped[datetime] = mapped_column(UtcDateTime())
