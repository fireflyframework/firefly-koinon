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
from koinon.integrations.content_sources.mapping_ancestry import FolderAncestry


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


@dataclass(frozen=True, slots=True, kw_only=True)
class RemoteFolderReadTarget(RemoteReadTarget):
    name: str
    parents: tuple[str, ...]
    mime_type: str
    size_bytes: int | None
    ancestry: tuple[str, ...]
    root_ancestry: tuple[str, ...]

    def __post_init__(self):
        RemoteReadTarget.__post_init__(self)
        bounded(self.name)
        if len(self.parents) != 1:
            raise SourceError("unavailable")
        bounded(self.parents[0])
        if (
            not self.ancestry
            or not self.root_ancestry
            or len(self.ancestry) > 256
            or len(self.root_ancestry) > 256
            or len(set(self.ancestry)) != len(self.ancestry)
            or len(set(self.root_ancestry)) != len(self.root_ancestry)
            or self.ancestry[0] != self.root_ancestry[0]
            or self.ancestry[-1] != self.parents[0]
            or self.item_id in self.ancestry
        ):
            raise SourceError("unavailable")
        for identifier in (*self.ancestry, *self.root_ancestry):
            bounded(identifier)


@dataclass(frozen=True, slots=True)
class RemoteReadObservation:
    target: RemoteReadTarget
    checked_at: datetime
    connection_revision: int


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
                    folder = isinstance(target, RemoteFolderReadTarget)
                    async with self._slots, self.browser._source(scope, tokens) as adapter:
                        item = (
                            await adapter.get_item(target.item_id)
                            if folder
                            else await adapter.check_access(target.item_id)
                        )
                    if (
                        item.scope != scope
                        or item.item_id != target.item_id
                        or item.kind != ("folder" if folder else "file")
                    ):
                        raise SourceError("access_denied")
                    if item.version != target.version:
                        raise SourceError("version_changed")
                    if isinstance(target, RemoteFolderReadTarget) and (
                        item.name != target.name
                        or item.parents != target.parents
                        or item.mime_type != target.mime_type
                        or item.size_bytes != target.size_bytes
                    ):
                        raise SourceError("version_changed")
                    observations[index] = RemoteReadObservation(target, datetime.now(UTC), grant.revision)
                except SourceError as error:
                    failures.append(error)
                except Exception:
                    failures.append(SourceError("unavailable"))

        async with asyncio.TaskGroup() as tasks:
            for _ in range(min(4, len(targets))):
                tasks.create_task(worker())
        if failures:
            raise failures[0]
        await self._folder_ancestry(account, tokens, targets)
        await self.connections.confirm_read_grant(actor, tenant, connection_id, grant)
        return tuple(observations[index] for index in range(len(targets)))

    async def _folder_ancestry(self, account, tokens, targets):
        """Verify retained containment with this reader, bounded across the whole check batch."""
        groups: dict[str, list[RemoteFolderReadTarget]] = {}
        for target in targets:
            if isinstance(target, RemoteFolderReadTarget):
                groups.setdefault(target.drive_id, []).append(target)
        remaining = 512
        for drive, folders in groups.items():
            if remaining <= 0:
                raise SourceError("size_exceeded")
            scope = SourceScope(account, drive)
            roots = tuple(
                dict.fromkeys(
                    identifier
                    for target in folders
                    for identifier in (target.root_ancestry[0], target.parents[0])
                )
            )
            try:
                async with self._slots, self.browser._source(scope, tokens) as adapter:
                    proof = await FolderAncestry(
                        adapter, scope, max_roots=200, max_depth=256, max_nodes=remaining
                    ).capture(roots)
            except SourceError:
                raise
            except Exception as error:
                raise SourceError("unavailable") from error
            remaining -= len(proof.nodes)
            if remaining < 0:
                raise SourceError("size_exceeded")
            for target in folders:
                root = target.root_ancestry[0]
                if (root, *proof.ancestors(root)) != target.root_ancestry:
                    raise SourceError("version_changed")
                reverse = (target.parents[0], *proof.ancestors(target.parents[0]))
                if (
                    root not in reverse
                    or tuple(reversed(reverse[: reverse.index(root) + 1])) != target.ancestry
                ):
                    raise SourceError("version_changed")
