# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Caller-transaction scoped FIFO admission and exact account checkpoint fencing."""

import math
from datetime import UTC, datetime, timedelta
from typing import Literal
from uuid import uuid4

from pyfly.container import repository
from pyfly.data.relational.sqlalchemy import Repository
from pyfly.kernel.exceptions import ConflictException
from sqlalchemy import delete, exists, func, or_, select, text

from koinon.catalog.entities import Tenant
from koinon.integrations.content_sources.account_operation_dtos import (
    AccountOperationBusy,
    AccountOperationIdentity,
    AccountOperationLease,
    AccountOperationRequest,
)
from koinon.integrations.content_sources.account_operation_entities import (
    FENCE_SEQUENCE,
    TICKET_SEQUENCE,
)
from koinon.integrations.content_sources.account_operation_entities import (
    SourceAccountOperation as Header,
)
from koinon.integrations.content_sources.account_operation_entities import (
    SourceAccountWaiter as Waiter,
)

ACTIVE_FIELDS = (
    "token",
    "operation_kind",
    "operation_id",
    "continuation_revision",
    "generation",
    "connection_id",
    "connection_revision",
    "owner",
    "process_instance_id",
    "fence",
    "ticket",
    "started_at",
    "expires_at",
)


@repository(name="content_sources.account_operations")
class SourceAccountOperationRepository(Repository[Header, str]):
    """Never commits, performs remote work or replaces source authorization."""

    async def _now(self) -> datetime:
        return (await self._require_session().scalar(select(func.clock_timestamp()))).astimezone(UTC)

    async def _tenant(self, tenant_id: str) -> None:
        if (
            await self._require_session().scalar(
                select(Tenant.id).where(Tenant.id == tenant_id).with_for_update()
            )
            is None
        ):
            raise ConflictException("Account operation tenant unavailable", code="SOURCE_ACCOUNT_BUSY")

    @staticmethod
    def _scope(identity):
        return Header.tenant_id == identity.tenant_id, Header.account_key == identity.account_key

    async def _header(self, identity):
        return await self._require_session().scalar(
            select(Header)
            .where(*self._scope(identity))
            .with_for_update()
            .execution_options(populate_existing=True)
        )

    @staticmethod
    def _waiter_key(identity, operation):
        return (
            identity.tenant_id,
            identity.account_key,
            operation.kind,
            operation.operation_id,
            operation.revision,
            operation.generation,
        )

    @staticmethod
    def _same_operation(header, operation):
        return (
            header.operation_kind,
            header.operation_id,
            header.continuation_revision,
            header.generation,
        ) == (operation.kind, operation.operation_id, operation.revision, operation.generation)

    @staticmethod
    def _waiter_matches(waiter, operation):
        return (waiter.connection_id, waiter.connection_revision, waiter.owner) == (
            operation.connection_id,
            operation.connection_revision,
            operation.owner,
        )

    @staticmethod
    def _clear(header):
        for field in ACTIVE_FIELDS:
            setattr(header, field, None)

    async def _expire_holder(self, header, now):
        if header.token is None or header.expires_at > now:
            return False
        deadline = header.expires_at + timedelta(seconds=30)
        header.quarantine_until = max(header.quarantine_until or deadline, deadline)
        await self._require_session().execute(
            delete(Waiter).where(
                Waiter.tenant_id == header.tenant_id,
                Waiter.account_key == header.account_key,
                Waiter.ticket == header.ticket,
            )
        )
        self._clear(header)
        header.last_used_at = now
        await self._require_session().flush()
        return True

    async def _prune_waiters(self, tenant_id, now, *, limit, account_key=None):
        held = exists(
            select(Header.tenant_id).where(
                Header.tenant_id == Waiter.tenant_id,
                Header.account_key == Waiter.account_key,
                Header.ticket == Waiter.ticket,
            )
        )
        statement = select(Waiter.ticket).where(
            Waiter.tenant_id == tenant_id, Waiter.idle_expires_at <= now, ~held
        )
        if account_key is not None:
            statement = statement.where(Waiter.account_key == account_key)
        tickets = list(
            (
                await self._require_session().scalars(
                    statement.order_by(Waiter.idle_expires_at, Waiter.ticket)
                    .limit(limit)
                    .with_for_update(skip_locked=True)
                )
            ).all()
        )
        if tickets:
            await self._require_session().execute(delete(Waiter).where(Waiter.ticket.in_(tickets)))
        return len(tickets)

    async def _evict_idle(self, tenant_id, now, limit):
        empty = ~exists(
            select(Waiter.ticket).where(
                Waiter.tenant_id == Header.tenant_id, Waiter.account_key == Header.account_key
            )
        )
        rows = (
            await self._require_session().scalars(
                select(Header)
                .where(
                    Header.tenant_id == tenant_id,
                    Header.token.is_(None),
                    or_(Header.quarantine_until.is_(None), Header.quarantine_until <= now),
                    empty,
                )
                .order_by(Header.last_used_at, Header.account_key)
                .limit(limit)
                .with_for_update(skip_locked=True)
            )
        ).all()
        for row in rows:
            await self._require_session().delete(row)
        await self._require_session().flush()
        return len(rows)

    async def _count(self, entity, tenant_id, *, account_key=None, limit=1001):
        statement = select(entity.tenant_id).where(entity.tenant_id == tenant_id)
        if account_key is not None:
            statement = statement.where(entity.account_key == account_key)
        return await self._require_session().scalar(
            select(func.count()).select_from(statement.limit(limit).subquery())
        )

    @staticmethod
    def _busy(header, now):
        deadline = header.quarantine_until
        if header.expires_at is not None:
            deadline = max(deadline or header.expires_at, header.expires_at)
        if deadline is None:
            return AccountOperationBusy()
        return AccountOperationBusy(
            retry_after_seconds=max(1, min(30, math.ceil((deadline - now).total_seconds())))
        )

    async def try_acquire(
        self, identity: AccountOperationIdentity, operation: AccountOperationRequest
    ) -> AccountOperationLease | AccountOperationBusy:
        session = self._require_session()
        # Claims serialize capacity first and never acquire domain rows afterward.
        await self._tenant(identity.tenant_id)
        header = await self._header(identity)
        now = await self._now()
        if header is None:
            if await self._count(Header, identity.tenant_id) >= 1000:
                await self._evict_idle(identity.tenant_id, now, 1)
                if await self._count(Header, identity.tenant_id) >= 1000:
                    return AccountOperationBusy()
            header = Header(tenant_id=identity.tenant_id, account_key=identity.account_key, last_used_at=now)
            session.add(header)
            await session.flush()
        await self._expire_holder(header, now)
        await self._prune_waiters(identity.tenant_id, now, limit=64, account_key=identity.account_key)
        if header.token is not None and self._same_operation(header, operation):
            return self._busy(header, now)
        waiter = await session.get(Waiter, self._waiter_key(identity, operation), populate_existing=True)
        if waiter is None:
            if (
                await self._count(Waiter, identity.tenant_id, account_key=identity.account_key, limit=65)
                >= 64
                or await self._count(Waiter, identity.tenant_id) >= 1000
            ):
                return AccountOperationBusy()
            waiter = Waiter(
                tenant_id=identity.tenant_id,
                account_key=identity.account_key,
                operation_kind=operation.kind,
                operation_id=operation.operation_id,
                continuation_revision=operation.revision,
                generation=operation.generation,
                ticket=await session.scalar(select(TICKET_SEQUENCE.next_value())),
                connection_id=operation.connection_id,
                connection_revision=operation.connection_revision,
                owner=operation.owner,
                last_requested_at=now,
                idle_expires_at=now + timedelta(seconds=120),
            )
            session.add(waiter)
        elif not self._waiter_matches(waiter, operation):
            return AccountOperationBusy()
        else:
            waiter.last_requested_at = now
            waiter.idle_expires_at = now + timedelta(seconds=120)
        header.last_used_at = now
        await session.flush()
        oldest = await session.scalar(
            select(Waiter.ticket)
            .where(Waiter.tenant_id == identity.tenant_id, Waiter.account_key == identity.account_key)
            .order_by(Waiter.ticket)
            .limit(1)
        )
        if (
            header.token is not None
            or (header.quarantine_until is not None and header.quarantine_until > now)
            or oldest != waiter.ticket
        ):
            return self._busy(header, now)
        header.token, header.fence, header.ticket = (
            uuid4(),
            await session.scalar(select(FENCE_SEQUENCE.next_value())),
            waiter.ticket,
        )
        header.operation_kind, header.operation_id = operation.kind, operation.operation_id
        header.continuation_revision, header.generation = operation.revision, operation.generation
        header.connection_id, header.connection_revision = (
            operation.connection_id,
            operation.connection_revision,
        )
        header.owner, header.process_instance_id = operation.owner, operation.process_instance_id
        header.started_at, header.expires_at, header.quarantine_until = (
            now,
            now + timedelta(seconds=150),
            None,
        )
        await session.flush()
        return AccountOperationLease(
            identity=identity,
            operation=operation,
            token=header.token,
            fence=header.fence,
            ticket=header.ticket,
            started_at=header.started_at,
            expires_at=header.expires_at,
        )

    @classmethod
    def _matches(cls, header, lease, now):
        return (
            header is not None
            and header.expires_at is not None
            and header.expires_at > now
            and (header.quarantine_until is None or header.quarantine_until <= now)
            and cls._same_operation(header, lease.operation)
            and (
                header.token,
                header.fence,
                header.ticket,
                header.connection_id,
                header.connection_revision,
                header.owner,
                header.process_instance_id,
                header.started_at,
                header.expires_at,
            )
            == (
                lease.token,
                lease.fence,
                lease.ticket,
                lease.operation.connection_id,
                lease.operation.connection_revision,
                lease.operation.owner,
                lease.operation.process_instance_id,
                lease.started_at,
                lease.expires_at,
            )
        )

    async def assert_current(self, lease: AccountOperationLease) -> None:
        header = await self._header(lease.identity)
        if not self._matches(header, lease, await self._now()):
            raise ConflictException(
                "Account operation lease is no longer current", code="SOURCE_ACCOUNT_LEASE_LOST"
            )

    async def finish(self, lease: AccountOperationLease, *, outcome: Literal["clean", "uncertain"]) -> bool:
        if outcome not in {"clean", "uncertain"}:
            raise ValueError("unknown account completion outcome")
        header = await self._header(lease.identity)
        now = await self._now()
        if not self._matches(header, lease, now):
            return False
        if outcome == "uncertain":
            header.quarantine_until = header.expires_at + timedelta(seconds=30)
        else:
            header.quarantine_until = None
        await self._require_session().execute(
            delete(Waiter).where(
                Waiter.tenant_id == lease.identity.tenant_id,
                Waiter.account_key == lease.identity.account_key,
                Waiter.ticket == lease.ticket,
            )
        )
        self._clear(header)
        header.last_used_at = now
        await self._require_session().flush()
        return True

    async def cancel_waiter(
        self, identity: AccountOperationIdentity, operation: AccountOperationRequest
    ) -> bool:
        header = await self._header(identity)
        if header is None:
            return False
        waiter = await self._require_session().get(
            Waiter, self._waiter_key(identity, operation), populate_existing=True
        )
        if waiter is None or waiter.ticket == header.ticket or not self._waiter_matches(waiter, operation):
            return False
        await self._require_session().delete(waiter)
        await self._require_session().flush()
        return True

    async def prune_expired(self, tenant_id: str, *, limit: int = 1000) -> int:
        if isinstance(limit, bool) or not 1 <= limit <= 1000:
            raise ValueError("cleanup limit must be between1 and1000")
        await self._tenant(tenant_id)
        session, now, changed = self._require_session(), await self._now(), 0
        if limit >= 2:
            expired = (
                await session.scalars(
                    select(Header)
                    .where(Header.tenant_id == tenant_id, Header.expires_at <= now)
                    .order_by(Header.expires_at, Header.account_key)
                    .limit(limit // 2)
                    .with_for_update(skip_locked=True)
                )
            ).all()
            for header in expired:
                if await self._expire_holder(header, now):
                    changed += 2
        if changed < limit:
            changed += await self._prune_waiters(tenant_id, now, limit=limit - changed)
        if changed < limit:
            changed += await self._evict_idle(tenant_id, now, limit - changed)
        return changed

    async def next_cleanup_tenant(self, after: str | None) -> str | None:
        """Seek the next account tenant, independently of validation lifetime."""
        session = self._require_session()
        await session.execute(text("SET LOCAL statement_timeout = '1s'"))
        statement = select(Header.tenant_id).order_by(Header.tenant_id).limit(1)
        if after is not None:
            statement = statement.where(Header.tenant_id > after)
        return await session.scalar(statement)

    async def cleanup_tenant(self, tenant_id: str) -> int:
        """One caller-owned transaction; preserve the existing account expiry fences."""
        session = self._require_session()
        await session.execute(text("SET LOCAL lock_timeout = '500ms'"))
        await session.execute(text("SET LOCAL statement_timeout = '1s'"))
        return await self.prune_expired(tenant_id, limit=1000)
