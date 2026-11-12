# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Reader-owned source checks precede consumption and local revocation wins races."""

from contextlib import asynccontextmanager
from types import SimpleNamespace

import pytest

from koinon.integrations.content_sources.errors import SourceError


def test_saved_result_requires_exact_authorized_snapshot_manifest():
    from koinon.integrations.content_sources.read_dtos import LocalSourcePin, ReaderSelectionSnapshot
    from koinon.integrations.content_sources.read_service import SourceReadOperation

    operation = SourceReadOperation(
        "reader", "tenant", ReaderSelectionSnapshot((), 0), None, _owner_task=None
    )
    operation.used.add(LocalSourcePin("dataset", "structured", "space", "native", "snapshot"))
    result = SimpleNamespace(asset_id="dataset", snapshot_ids=("snapshot",), snapshot_manifest_complete=True)
    operation.validate_result(result)
    for pins, complete in (((), True), (("other",), True), (("snapshot",), False)):
        with pytest.raises(SourceError, match="version_changed"):
            operation.validate_result(
                SimpleNamespace(asset_id="dataset", snapshot_ids=pins, snapshot_manifest_complete=complete)
            )
    operation.validate_result(
        SimpleNamespace(asset_id="local", snapshot_ids=(), snapshot_manifest_complete=False)
    )


@pytest.mark.asyncio
async def test_importer_connection_never_substitutes_for_reader_selection(monkeypatch):
    from koinon.integrations.content_sources.read_authority import SourceReadAuthority
    from koinon.integrations.content_sources.read_dtos import LocalSourcePin, ResolvedSourceOrigin
    from koinon.integrations.content_sources.reader_access import RemoteReadTarget

    pin = LocalSourcePin("asset", "canon", "workspace", "native", "version", "extraction")
    origin = ResolvedSourceOrigin(
        pin, "attempt", "mapping", 1, "object", 1, RemoteReadTarget("google_drive", "drive", "file", "remote")
    )

    class Records:
        async def resolve(self, tenant, pins):
            return (origin,)

    class Local:
        async def get_identity(self, actor, tenant, asset):
            return SimpleNamespace(id=asset, status="ready", parent_id=None)

        async def get(self, *args):
            pytest.fail("Source authority hydrated a title before the reader check")

        async def _refresh_managed_memberships(self, actor):
            return None

    class Remote:
        calls = []

        async def check(self, *args):
            self.calls.append(args)

    @asynccontextmanager
    async def unit(**kwargs):
        yield

    monkeypatch.setattr("koinon.integrations.content_sources.read_authority.primary_authority", unit)
    authority = SourceReadAuthority(Records(), Remote(), Local())
    with pytest.raises(SourceError, match="reconnect_required"):
        await authority.check("reader", "tenant", (pin,), ())
    assert authority.remote.calls == []


@pytest.mark.asyncio
async def test_disconnect_after_remote_check_prevents_local_commit(monkeypatch):
    from koinon.integrations.content_sources.read_dtos import LocalSourcePin, ReaderSelectionSnapshot
    from koinon.integrations.content_sources.read_service import SourceReadOperation

    pin = LocalSourcePin("asset", "canon", "workspace", "native", "version", "extraction")
    connected = True
    committed = []

    class Authority:
        @property
        def catalog(self):
            return self

        async def _lock_tenant(self, tenant):
            pass

        async def check(self, *args):
            pass

        async def _check(self, *args):
            return "private-comparison"

        async def _lock_comparisons(self, actor, tenant, comparisons):
            assert comparisons == ("private-comparison",)
            if not connected:
                raise SourceError("authority_changed")

    class Selections:
        async def confirm(self, *args):
            pass

        async def lock_confirm(self, *args):
            pass

    @asynccontextmanager
    async def transaction(**kwargs):
        yield

    monkeypatch.setattr("koinon.integrations.content_sources.read_service.primary_authority", transaction)
    reader = SimpleNamespace(authority=Authority(), selections=Selections())
    operation = SourceReadOperation("reader", "tenant", ReaderSelectionSnapshot((), 0), reader)
    await operation.check((pin,))
    connected = False
    with pytest.raises(SourceError, match="authority_changed"):
        async with operation.local_fence():
            committed.append("must never commit")
    assert committed == []


@pytest.mark.asyncio
async def test_failed_fresh_check_cannot_reuse_an_earlier_commit_comparison(monkeypatch):
    from koinon.integrations.content_sources.read_dtos import LocalSourcePin, ReaderSelectionSnapshot
    from koinon.integrations.content_sources.read_service import SourceReadOperation

    denied = False

    class Authority:
        catalog = None

        async def _check(self, *args):
            if denied:
                raise SourceError("access_denied")
            return "old-comparison"

        async def _lock_comparisons(self, *args):
            pytest.fail("An earlier check survived a failed fresh check")

    class Selections:
        async def confirm(self, *args):
            pass

        async def lock_confirm(self, *args):
            pass

    @asynccontextmanager
    async def transaction(**kwargs):
        yield

    monkeypatch.setattr("koinon.integrations.content_sources.read_service.primary_authority", transaction)
    authority = Authority()

    async def lock(*args):
        pass

    authority.catalog = SimpleNamespace(_lock_tenant=lock)
    operation = SourceReadOperation(
        "reader",
        "tenant",
        ReaderSelectionSnapshot((), 0),
        SimpleNamespace(authority=authority, selections=Selections()),
    )
    pin = LocalSourcePin("asset", "canon", "workspace", "native", "version", "extraction")
    await operation.check((pin,))
    denied = True
    with pytest.raises(SourceError, match="access_denied"):
        await operation.check((pin,))
    with pytest.raises(SourceError, match="authority_changed"):
        async with operation.local_fence():
            pytest.fail("A revoked operation committed")


@pytest.mark.asyncio
async def test_connection_refresh_between_chunks_invalidates_entire_execution(monkeypatch):
    from unittest.mock import AsyncMock

    from koinon.integrations.content_sources.read_authority import SourceReadAuthority
    from koinon.integrations.content_sources.read_dtos import (
        LocalSourcePin,
        ReaderSourceSelection,
        ResolvedSourceOrigin,
    )
    from koinon.integrations.content_sources.reader_access import RemoteReadTarget

    pins = tuple(
        LocalSourcePin(str(index), "canon", "workspace", str(index), "version", "extraction")
        for index in range(101)
    )
    origins = tuple(
        ResolvedSourceOrigin(
            pin,
            "attempt",
            "mapping",
            1,
            str(index),
            1,
            RemoteReadTarget("google_drive", "drive", str(index), "remote"),
        )
        for index, pin in enumerate(pins)
    )

    class Remote:
        calls = 0

        async def check(self, actor, tenant, identifier, targets):
            self.calls += 1
            return tuple(SimpleNamespace(connection_revision=self.calls) for _ in targets)

    @asynccontextmanager
    async def transaction(**kwargs):
        yield

    monkeypatch.setattr("koinon.integrations.content_sources.read_authority.primary_authority", transaction)
    authority = SourceReadAuthority(
        SimpleNamespace(check_connections=AsyncMock(return_value=())), Remote(), None
    )
    authority._snapshot = AsyncMock(return_value=origins)
    with pytest.raises(SourceError, match="authority_changed"):
        await authority._check(
            "reader",
            "tenant",
            pins,
            (ReaderSourceSelection(provider="google_drive", connection_id="reader"),),
        )
    assert authority.remote.calls == 2


@pytest.mark.asyncio
async def test_local_write_comparison_cannot_be_used_by_a_child_task(monkeypatch):
    import asyncio
    from unittest.mock import AsyncMock

    from koinon.integrations.content_sources.read_dtos import ReaderSelectionSnapshot
    from koinon.integrations.content_sources.read_service import SourceReadOperation

    @asynccontextmanager
    async def transaction(**kwargs):
        yield

    monkeypatch.setattr("koinon.integrations.content_sources.read_service.primary_authority", transaction)
    reader = SimpleNamespace(
        authority=SimpleNamespace(
            catalog=SimpleNamespace(_lock_tenant=AsyncMock()), _lock_comparisons=AsyncMock()
        ),
        selections=SimpleNamespace(lock_confirm=AsyncMock()),
    )
    operation = SourceReadOperation("reader", "tenant", ReaderSelectionSnapshot((), 0), reader)

    async def child():
        with pytest.raises(SourceError, match="authority_changed"):
            async with operation.local_fence():
                pass

    await asyncio.create_task(child())
