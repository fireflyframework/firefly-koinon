# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Bounded source ownership maintenance outside the heavy-work admission pool."""

import asyncio
import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from pyfly.container import service
from pyfly.context.conditions import conditional_on_property
from pyfly.context.lifecycle import pre_destroy
from pyfly.data.transaction import Propagation, TransactionTemplate
from pyfly.scheduling import scheduled
from sqlalchemy import text

from koinon.integrations.content_sources.settings import ContentSourceSettings
from koinon.integrations.content_sources.sync_runs import SourceRunLease, SourceRunRepository, lost

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class _Registration:
    key: tuple[str, str, str]
    lease: SourceRunLease | None = None
    task: asyncio.Task | None = None


def _same(left: SourceRunLease, right: SourceRunLease) -> bool:
    return (
        left.tenant_id,
        left.owner,
        left.mapping_id,
        left.run_id,
        left.job_id,
        left.worker_id,
        left.attempt,
        left.mapping_revision,
        left.connection_revision,
        left.policy_id,
    ) == (
        right.tenant_id,
        right.owner,
        right.mapping_id,
        right.run_id,
        right.job_id,
        right.worker_id,
        right.attempt,
        right.mapping_revision,
        right.connection_revision,
        right.policy_id,
    )


@service(name="content_sources.heartbeat")
@conditional_on_property("koinon.process.role", having_value="worker")
class SourceSyncHeartbeat:
    def __init__(self, records: SourceRunRepository, settings: ContentSourceSettings):
        settings.synchronization_options()
        self.records, self.settings = records, settings
        self._entries: dict[tuple[str, str, str], _Registration] = {}
        self._busy = asyncio.Lock()
        self._next_tick = 0.0
        self._closing = False

    def reserve(self, tenant: str, owner: str, run_id: str) -> _Registration | None:
        """Reserve before claiming, so a new job can never exceed renewal capacity."""
        self._expire()
        key = (tenant, owner, run_id)
        if self._closing:
            return None
        if key in self._entries:
            return self._entries[key]
        if len(self._entries) >= 64:
            return None
        value = _Registration(key)
        self._entries[key] = value
        return value

    def register(self, slot: _Registration, lease: SourceRunLease) -> None:
        if self._closing or self._entries.get(slot.key) is not slot:
            raise lost()
        if slot.key != (lease.tenant_id, lease.owner, lease.run_id):
            raise lost()
        if slot.lease is not None and not _same(slot.lease, lease):
            raise lost()
        slot.lease = lease

    def attach(self, lease: SourceRunLease) -> None:
        entry = self._entries.get((lease.tenant_id, lease.owner, lease.run_id))
        if entry is None or entry.lease is None or not _same(entry.lease, lease):
            raise lost()
        entry.task = asyncio.current_task()

    def detach(self, lease: SourceRunLease) -> None:
        entry = self._entries.get((lease.tenant_id, lease.owner, lease.run_id))
        if entry and entry.lease and _same(entry.lease, lease):
            entry.task = None

    def release(self, lease: SourceRunLease) -> None:
        entry = self._entries.get((lease.tenant_id, lease.owner, lease.run_id))
        if entry and entry.lease and _same(entry.lease, lease):
            self._entries.pop(entry.key)

    def abandon(self, slot: _Registration) -> None:
        if self._entries.get(slot.key) is slot and slot.lease is None:
            self._entries.pop(slot.key)

    def discard(self, slot: _Registration) -> None:
        """Forget retained ownership when current domain authority failed before claim."""
        self._invalidate(slot)

    def _invalidate(self, entry: _Registration) -> None:
        if self._entries.get(entry.key) is not entry:
            return
        self._entries.pop(entry.key)
        if entry.task is not None and entry.task is not asyncio.current_task() and not entry.task.done():
            entry.task.cancel()

    def _expire(self) -> None:
        now = datetime.now(UTC) + timedelta(seconds=10)
        for entry in tuple(self._entries.values()):
            if entry.lease is not None and entry.lease.expires_at <= now:
                self._invalidate(entry)

    async def renew(self) -> None:
        """At most two independent 32-identity transactions; no heavy-work permit."""
        if self._closing or self._busy.locked():
            return
        async with self._busy:
            self._expire()
            entries = tuple(entry for entry in self._entries.values() if entry.lease is not None)
            for offset in range(0, len(entries), 32):
                batch = entries[offset : offset + 32]
                try:
                    refreshed = []
                    async with (
                        asyncio.timeout(5),
                        TransactionTemplate(
                            "primary",
                            propagation=Propagation.REQUIRES_NEW,
                            read_only=False,
                            read_from_primary=True,
                        ).transaction(),
                    ):
                        session = self.records._require_session()
                        await session.execute(text("SET LOCAL lock_timeout = '1s'"))
                        await session.execute(text("SET LOCAL statement_timeout = '5s'"))
                        for entry in batch:
                            if self._entries.get(entry.key) is entry and entry.lease is not None:
                                current = entry.lease
                                updated = await self.records.renew_owned(
                                    current, lease_seconds=self.settings.sync_lease_seconds
                                )
                                refreshed.append((entry, current, updated))
                    # Publish refreshed deadlines only after the entire batch committed.
                    for entry, current, updated in refreshed:
                        if self._entries.get(entry.key) is entry and entry.lease is current:
                            if updated is None:
                                self._invalidate(entry)
                            else:
                                entry.lease = updated
                except Exception as error:
                    for entry in batch:
                        self._invalidate(entry)
                    logger.warning("source_heartbeat_failed", extra={"error_type": type(error).__name__})

    @scheduled(fixed_delay=timedelta(seconds=1))
    async def tick(self):
        if not self.settings.synchronization_enabled or self._closing:
            return
        now = asyncio.get_running_loop().time()
        if now < self._next_tick:
            return
        self._next_tick = now + self.settings.source_heartbeat_interval
        await self.renew()

    @pre_destroy
    async def close(self) -> None:
        self._closing = True
        tasks = {entry.task for entry in self._entries.values() if entry.task is not None}
        for entry in tuple(self._entries.values()):
            self._invalidate(entry)
        tasks.discard(asyncio.current_task())
        if tasks:
            async with asyncio.timeout(10):
                await asyncio.gather(*tasks, return_exceptions=True)
        async with self._busy:
            return
