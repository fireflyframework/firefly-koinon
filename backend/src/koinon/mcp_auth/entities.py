# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from datetime import UTC, datetime

from pyfly.data.relational.sqlalchemy import Base, UtcDateTime
from sqlalchemy import JSON, String
from sqlalchemy.orm import Mapped, mapped_column


class McpAuthorization(Base):
    __tablename__ = "koinon_mcp_authorizations"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    subject: Mapped[str] = mapped_column(String(512), index=True)
    client_id: Mapped[str] = mapped_column(String(128))
    status: Mapped[str] = mapped_column(String(16))
    request_json: Mapped[dict] = mapped_column(JSON)
    grant_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    code_hash: Mapped[str | None] = mapped_column(String(64), unique=True, nullable=True)
    expires_at: Mapped[datetime] = mapped_column(UtcDateTime(), index=True)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=lambda: datetime.now(UTC))
