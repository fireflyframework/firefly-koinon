# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Bounded private mutable account queue state, never publication authority."""

from datetime import datetime
from uuid import UUID

from pyfly.data.relational.sqlalchemy import Base, UtcDateTime
from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    LargeBinary,
    Sequence,
    String,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

FENCE_SEQUENCE = Sequence("koinon_source_account_fence_seq", metadata=Base.metadata, cycle=False)
TICKET_SEQUENCE = Sequence("koinon_source_account_ticket_seq", metadata=Base.metadata, cycle=False)


class SourceAccountOperation(Base):
    __tablename__ = "koinon_source_account_operations"
    __table_args__ = (
        CheckConstraint("octet_length(account_key)=32", name="ck_account_operation_key").ddl_if(
            dialect="postgresql"
        ),
        CheckConstraint(
            "num_nonnulls(token,operation_kind,operation_id,continuation_revision,generation,"
            "connection_id,connection_revision,owner,process_instance_id,fence,ticket,"
            "started_at,expires_at) IN (0,13)",
            name="ck_account_operation_complete",
        ).ddl_if(dialect="postgresql"),
        CheckConstraint(
            "operation_kind IN ('validation','synchronization') AND "
            "(operation_kind<>'validation' OR generation=0)",
            name="ck_account_operation_kind",
        ),
        CheckConstraint(
            "continuation_revision>=0 AND generation>=0 AND connection_revision>=0 AND fence>0 AND ticket>0",
            name="ck_account_operation_numbers",
        ),
        CheckConstraint(
            "length(operation_id) BETWEEN 1 AND 64 AND length(connection_id) BETWEEN 1 AND 64 "
            "AND length(process_instance_id) BETWEEN 1 AND 64 AND length(owner) BETWEEN 1 AND 512",
            name="ck_account_operation_identifiers",
        ),
        CheckConstraint(
            "expires_at>started_at AND expires_at<=started_at+interval '150 seconds'",
            name="ck_account_operation_deadline",
        ).ddl_if(dialect="postgresql"),
        Index("ix_account_operation_idle", "tenant_id", "last_used_at", "account_key"),
        Index("ix_account_operation_expiry", "tenant_id", "expires_at", "account_key"),
    )
    tenant_id: Mapped[str] = mapped_column(ForeignKey("lattice_tenants.id"), primary_key=True)
    account_key: Mapped[bytes] = mapped_column(LargeBinary(32), primary_key=True)
    token: Mapped[UUID | None] = mapped_column(Uuid)
    operation_kind: Mapped[str | None] = mapped_column(String(24))
    operation_id: Mapped[str | None] = mapped_column(String(64))
    continuation_revision: Mapped[int | None] = mapped_column(BigInteger)
    generation: Mapped[int | None] = mapped_column(BigInteger)
    connection_id: Mapped[str | None] = mapped_column(String(64))
    connection_revision: Mapped[int | None] = mapped_column(BigInteger)
    owner: Mapped[str | None] = mapped_column(String(512))
    process_instance_id: Mapped[str | None] = mapped_column(String(64))
    fence: Mapped[int | None] = mapped_column(BigInteger)
    ticket: Mapped[int | None] = mapped_column(BigInteger)
    started_at: Mapped[datetime | None] = mapped_column(UtcDateTime())
    expires_at: Mapped[datetime | None] = mapped_column(UtcDateTime())
    quarantine_until: Mapped[datetime | None] = mapped_column(UtcDateTime())
    last_used_at: Mapped[datetime] = mapped_column(UtcDateTime())


class SourceAccountWaiter(Base):
    __tablename__ = "koinon_source_account_waiters"
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "account_key"],
            ["koinon_source_account_operations.tenant_id", "koinon_source_account_operations.account_key"],
            ondelete="RESTRICT",
            name="fk_account_waiter_operation",
        ),
        UniqueConstraint("ticket", name="uq_account_waiter_ticket"),
        CheckConstraint("octet_length(account_key)=32 AND ticket>0", name="ck_account_waiter_key").ddl_if(
            dialect="postgresql"
        ),
        CheckConstraint(
            "operation_kind IN ('validation','synchronization') AND "
            "(operation_kind<>'validation' OR generation=0)",
            name="ck_account_waiter_kind",
        ),
        CheckConstraint(
            "continuation_revision>=0 AND generation>=0 AND connection_revision>=0",
            name="ck_account_waiter_revisions",
        ),
        CheckConstraint(
            "length(operation_id) BETWEEN 1 AND 64 AND length(connection_id) BETWEEN 1 AND 64 "
            "AND length(owner) BETWEEN 1 AND 512",
            name="ck_account_waiter_identifiers",
        ),
        CheckConstraint(
            "idle_expires_at>last_requested_at AND idle_expires_at<=last_requested_at+interval '120 seconds'",
            name="ck_account_waiter_idle",
        ).ddl_if(dialect="postgresql"),
        Index("ix_account_waiter_fifo", "tenant_id", "account_key", "ticket"),
        Index("ix_account_waiter_expiry", "tenant_id", "idle_expires_at", "ticket"),
    )
    tenant_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    account_key: Mapped[bytes] = mapped_column(LargeBinary(32), primary_key=True)
    operation_kind: Mapped[str] = mapped_column(String(24), primary_key=True)
    operation_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    continuation_revision: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    generation: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    ticket: Mapped[int] = mapped_column(BigInteger)
    connection_id: Mapped[str] = mapped_column(String(64))
    connection_revision: Mapped[int] = mapped_column(BigInteger)
    owner: Mapped[str] = mapped_column(String(512))
    last_requested_at: Mapped[datetime] = mapped_column(UtcDateTime())
    idle_expires_at: Mapped[datetime] = mapped_column(UtcDateTime())


ACCOUNT_OPERATION_TABLES = (SourceAccountOperation.__table__, SourceAccountWaiter.__table__)
