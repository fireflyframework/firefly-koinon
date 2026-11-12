# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Versioned whole-set reader choices; snapshots are not permission grants."""

from datetime import UTC, datetime

from pyfly.data.relational.sqlalchemy import Base, UtcDateTime
from sqlalchemy import CheckConstraint, ForeignKey, ForeignKeyConstraint, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column


class SourceReaderSelectionSet(Base):
    __tablename__ = "koinon_content_reader_sets"
    __table_args__ = (CheckConstraint("revision >= 0", name="ck_content_reader_revision"),)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("lattice_tenants.id"), primary_key=True)
    owner: Mapped[str] = mapped_column(String(512), primary_key=True)
    revision: Mapped[int] = mapped_column(default=0)
    updated_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=lambda: datetime.now(UTC))


class SourceReaderSelection(Base):
    __tablename__ = "koinon_content_reader_selections"
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "owner"],
            ["koinon_content_reader_sets.tenant_id", "koinon_content_reader_sets.owner"],
        ),
        ForeignKeyConstraint(
            ["tenant_id", "owner", "connection_id"],
            [
                "koinon_content_connections.tenant_id",
                "koinon_content_connections.owner",
                "koinon_content_connections.id",
            ],
        ),
        CheckConstraint("set_revision > 0", name="ck_content_reader_snapshot_revision"),
        CheckConstraint(
            (
                "external_tenant_key = CASE WHEN external_tenant IS NULL THEN 'none:' ELSE "
                "'value:' || external_tenant END"
            ),
            name="ck_content_reader_external_key",
        ),
    )
    tenant_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    owner: Mapped[str] = mapped_column(String(512), primary_key=True)
    set_revision: Mapped[int] = mapped_column(primary_key=True)
    provider: Mapped[str] = mapped_column(String(32), primary_key=True)
    external_tenant_key: Mapped[str] = mapped_column(String(1030), primary_key=True)
    external_tenant: Mapped[str | None] = mapped_column(String(1024))
    connection_id: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=lambda: datetime.now(UTC))


class SourceReaderSelectionOperation(Base):
    __tablename__ = "koinon_content_reader_operations"
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "owner"],
            ["koinon_content_reader_sets.tenant_id", "koinon_content_reader_sets.owner"],
        ),
        UniqueConstraint(
            "tenant_id", "owner", "result_revision", name="uq_content_reader_operation_revision"
        ),
        CheckConstraint("result_revision > 0", name="ck_content_reader_operation_revision"),
    )
    tenant_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    owner: Mapped[str] = mapped_column(String(512), primary_key=True)
    operation_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    payload_sha256: Mapped[str] = mapped_column(String(64))
    result_revision: Mapped[int]
    created_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=lambda: datetime.now(UTC))
