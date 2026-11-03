# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Fresh remote checks for bounded, locally admitted candidates; not a reusable grant."""

import asyncio
from dataclasses import dataclass, field
from datetime import UTC, datetime

from pyfly.container import service

from koinon.integrations.content_sources.browse import PersonalSourceBrowser
from koinon.integrations.content_sources.dtos import Account, Provider, SourceScope, bounded
from koinon.integrations.content_sources.errors import SourceError
from koinon.integrations.content_sources.lifecycle import SourceConnectionService, _no_remote_unit


@dataclass(frozen=True, slots=True)
class RemoteReadTarget:
    provider: Provider
    drive_id: str
    item_id: str
    version: str
    external_tenant: str | None = None

    def __post_init__(self):
        Account(self.provider, "validation", self.external_tenant)
        for value in (self.drive_id, self.item_id, self.version):
            bounded(value)


@dataclass(frozen=True, slots=True)
class RemoteReadObservation:
    target: RemoteReadTarget
    checked_at: datetime


@dataclass(frozen=True, slots=True)
class _OperationToken:
    account: Account
    token: str = field(repr=False)

    async def access_token(self, account: Account) -> str:
        if account != self.account:
            raise SourceError("access_denied")
        return self.token


@service(name="content_sources.reader_access")
class PersonalSourceAccess:
    def __init__(self, browser: PersonalSourceBrowser, connections: SourceConnectionService):
        self.browser, self.connections = browser, connections
        self._slots = asyncio.Semaphore(4)

    async def check(
        self,
        actor: str,
        tenant: str,
        connection_id: str,
        targets: tuple[RemoteReadTarget, ...],
    ) -> tuple[RemoteReadObservation, ...]:
        """Check one reader's selected candidates without listing any remote corpus.

        Callers must first admit immutable origin bindings under current local policy and recheck
        those bindings afterward. Every consumption/output fence calls this method afresh.
        Observations are evidence of a completed check, never authorization to skip a later check.
        """
        _no_remote_unit()
        if len(targets) > 100:
            raise SourceError("size_exceeded")
        if not targets:
            return ()
        connection = await self.connections.connected(actor, tenant, connection_id)
        account = connection.account
        if account is None:
            raise SourceError("reconnect_required")
        if any(
            target.provider != account.provider or target.external_tenant != account.tenant_id
            for target in targets
        ):
            raise SourceError("access_denied")
        # Rotate at most once before parallel requests; never race a single-use refresh grant.
        grant = await self.connections.read_grant(actor, tenant, connection_id, account)
        tokens = _OperationToken(account, grant.token)
        pending = iter(enumerate(targets))
        observations: dict[int, RemoteReadObservation] = {}
        failures: list[SourceError] = []

        async def worker():
            while not failures:
                selected = next(pending, None)
                if selected is None:
                    return
                index, target = selected
                try:
                    scope = SourceScope(account, target.drive_id)
                    async with self._slots, self.browser._source(scope, tokens) as adapter:
                        item = await adapter.check_access(target.item_id)
                    if item.scope != scope or item.item_id != target.item_id or item.kind != "file":
                        raise SourceError("access_denied")
                    if item.version != target.version:
                        raise SourceError("version_changed")
                    observations[index] = RemoteReadObservation(target, datetime.now(UTC))
                except SourceError as error:
                    failures.append(error)
                except Exception:
                    failures.append(SourceError("unavailable"))

        async with asyncio.TaskGroup() as tasks:
            for _ in range(min(4, len(targets))):
                tasks.create_task(worker())
        if failures:
            raise failures[0]
        await self.connections.confirm_read_grant(actor, tenant, connection_id, grant)
        return tuple(observations[index] for index in range(len(targets)))
