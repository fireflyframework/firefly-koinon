# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Attempt fences join each native transaction before any pipeline mutation."""

from collections.abc import Awaitable, Callable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from datetime import UTC, datetime
from threading import Event

import sqlalchemy as sa
from pyfly.data.transaction import TransactionSynchronizationAdapter
from pyfly.kernel import ConflictException

JOBS = sa.table(
    "canon_ingest_jobs",
    sa.column("id", sa.String),
    sa.column("tenant_id", sa.String),
    sa.column("workspace_id", sa.String),
    sa.column("status", sa.String),
    sa.column("attempts", sa.Integer),
    sa.column("started_at", sa.DateTime(timezone=True)),
    sa.column("finished_at", sa.DateTime(timezone=True)),
    sa.column("error_code", sa.String),
)


class IngestLeaseLost(ConflictException):
    def __init__(self):
        super().__init__("The ingestion attempt no longer owns this work", code="INGEST_LEASE_LOST")


@dataclass(frozen=True, slots=True)
class IngestLease:
    id: str
    tenant_id: str
    workspace_id: str
    attempts: int
    started_at: datetime
    expires_at: datetime

    def predicate(self):
        return sa.and_(
            JOBS.c.id == self.id,
            JOBS.c.tenant_id == self.tenant_id,
            JOBS.c.workspace_id == self.workspace_id,
            JOBS.c.attempts == self.attempts,
            JOBS.c.started_at == self.started_at,
        )


@dataclass(frozen=True, slots=True)
class _Scope:
    lease: IngestLease
    closed: Event
    authorize: Callable[[], Awaitable[None]] | None


_current: ContextVar[_Scope | None] = ContextVar("canon_ingest_lease", default=None)


@contextmanager
def bind_ingest_lease(
    lease: IngestLease, authorize: Callable[[], Awaitable[None]] | None = None
) -> Iterator[None]:
    scope = _Scope(lease, Event(), authorize)
    token = _current.set(scope)
    try:
        yield
    finally:
        scope.closed.set()
        _current.reset(token)


def current_ingest_lease() -> IngestLease | None:
    scope = _current.get()
    if scope is None:
        return None
    if scope.closed.is_set() or scope.lease.expires_at <= datetime.now(UTC):
        raise IngestLeaseLost()
    return scope.lease


async def authorize_ingest_output(*, required: bool = False) -> IngestLease | None:
    lease = current_ingest_lease()
    scope = _current.get()
    if required and (lease is None or scope is None or scope.authorize is None):
        raise IngestLeaseLost()
    if scope is not None and scope.authorize is not None:
        await scope.authorize()
    return lease


class _Fence(TransactionSynchronizationAdapter):
    def __init__(self, connection):
        self.connection = connection

    async def before_commit(self, read_only):
        await _check(self.connection, write=not read_only)


async def _check(connection, *, write=True):
    lease = current_ingest_lease()
    if lease is None:
        return False
    scope = _current.get()
    if scope is not None and scope.authorize is not None:
        await scope.authorize()
    statement = sa.select(JOBS.c.id).where(
        lease.predicate(), JOBS.c.status.in_(("running", "succeeded", "failed"))
    )
    if write:
        statement = statement.with_for_update()
    found = await connection.scalar(statement)
    if found is None:
        raise IngestLeaseLost()
    return True


async def fence_ingest_transaction(connection):
    return (
        _Fence(connection)
        if await _check(connection, write=not connection.info.get("read_only", False))
        else None
    )
