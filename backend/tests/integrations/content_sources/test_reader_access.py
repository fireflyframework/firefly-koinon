# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import asyncio
from contextlib import asynccontextmanager
from dataclasses import replace

import pytest
from koinon.catalog.errors import AccessDenied
from koinon.integrations.content_sources.dtos import RemoteItem
from koinon.integrations.content_sources.errors import SourceError
from test_connection_lifecycle import begin, complete
from test_connection_lifecycle import lifecycle as lifecycle


async def setup(lifecycle, monkeypatch, respond):
    from koinon.integrations.content_sources.browse import PersonalSourceBrowser
    from koinon.integrations.content_sources.reader_access import PersonalSourceAccess

    connections, _, _, context = lifecycle
    start, state = await begin(connections)
    connection = await complete(connections, start, state)
    browser = context.get_bean(PersonalSourceBrowser)

    @asynccontextmanager
    async def source(scope, tokens):
        class Adapter:
            async def check_access(self, identifier):
                assert await tokens.access_token(scope.account) == "access-one"
                item = RemoteItem(scope, identifier, "Private filename", "file", "v1", 10, "text/plain", ())
                return await respond(item)

        yield Adapter()

    monkeypatch.setattr(browser, "_source", source)
    return PersonalSourceAccess(browser, connections), start, connection


def target(identifier="file", **values):
    from koinon.integrations.content_sources.reader_access import RemoteReadTarget

    return RemoteReadTarget("google_drive", "drive", identifier, "v1", **values)


async def test_only_requested_files_checked_with_bounded_concurrency_and_fresh_rechecks(
    lifecycle, monkeypatch
):
    active, maximum, seen = 0, 0, []

    async def respond(item):
        nonlocal active, maximum
        active += 1
        maximum = max(active, maximum)
        seen.append(item.item_id)
        await asyncio.sleep(0)
        active -= 1
        return item

    access, start, _ = await setup(lifecycle, monkeypatch, respond)
    targets = tuple(target(str(index)) for index in range(19))
    observations = await access.check("issuer|alice", "tenant", start.connection_id, targets)
    assert tuple(row.target for row in observations) == targets
    assert set(seen) == {str(index) for index in range(19)}
    assert 1 < maximum <= 4
    assert all(row.checked_at is not None for row in observations)
    await access.check("issuer|alice", "tenant", start.connection_id, targets[:1])
    assert seen.count("0") == 2


@pytest.mark.parametrize("change", ["version", "folder", "wrong_item", "wrong_scope", "denied"])
async def test_no_partial_receipt_for_changed_or_unreadable_candidates(lifecycle, monkeypatch, change):
    async def respond(item):
        if change == "denied":
            raise SourceError("access_denied")
        return replace(
            item,
            **{
                "version": {"version": "v2"},
                "folder": {"kind": "folder"},
                "wrong_item": {"item_id": "other"},
                "wrong_scope": {"scope": replace(item.scope, drive_id="other")},
            }[change],
        )

    access, start, _ = await setup(lifecycle, monkeypatch, respond)
    with pytest.raises(SourceError):
        await access.check("issuer|alice", "tenant", start.connection_id, (target(),))


async def test_reader_connection_cannot_be_borrowed_or_changed_during_check(lifecycle, monkeypatch):
    calls = []

    async def respond(item):
        calls.append(item.item_id)
        await lifecycle[0].disconnect("issuer|alice", "tenant", start.connection_id, connected.revision)
        return item

    access, start, connected = await setup(lifecycle, monkeypatch, respond)
    with pytest.raises(SourceError):
        await access.check("issuer|bob", "tenant", start.connection_id, (target(),))
    with pytest.raises(AccessDenied):
        await access.check("issuer|alice", "other", start.connection_id, (target(),))
    assert not calls
    with pytest.raises(SourceError):
        await access.check("issuer|alice", "tenant", start.connection_id, (target(),))
    assert calls == ["file"]


async def test_batch_bounds_and_provider_binding_rejected_before_remote_io(lifecycle, monkeypatch):
    from koinon.integrations.content_sources.reader_access import RemoteReadTarget

    async def respond(item):
        pytest.fail("No provider request expected")

    access, start, _ = await setup(lifecycle, monkeypatch, respond)
    for targets in (
        tuple(target(str(index)) for index in range(101)),
        (RemoteReadTarget("onedrive", "drive", "file", "v1"),),
        (target(external_tenant="different"),),
    ):
        with pytest.raises(SourceError):
            await access.check("issuer|alice", "tenant", start.connection_id, targets)
    assert await access.check("issuer|alice", "tenant", start.connection_id, ()) == ()


async def test_cancellation_drains_candidate_checks_and_returns_no_observation(lifecycle, monkeypatch):
    entered, release = asyncio.Event(), asyncio.Event()
    active = 0

    async def respond(item):
        nonlocal active
        active += 1
        entered.set()
        try:
            await release.wait()
        finally:
            active -= 1
        return item

    access, start, _ = await setup(lifecycle, monkeypatch, respond)
    task = asyncio.create_task(
        access.check("issuer|alice", "tenant", start.connection_id, tuple(target(str(i)) for i in range(10)))
    )
    await entered.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert active == 0


async def test_remote_check_rejects_an_open_primary_unit(lifecycle, monkeypatch):
    from koinon.security.authority import primary_authority

    async def respond(item):
        pytest.fail("Provider I/O must not hold a primary unit")

    access, start, _ = await setup(lifecycle, monkeypatch, respond)
    async with primary_authority():
        with pytest.raises(SourceError, match="unavailable"):
            await access.check("issuer|alice", "tenant", start.connection_id, (target(),))


async def test_simultaneous_calls_share_capacity(lifecycle, monkeypatch):
    active, maximum = 0, 0

    async def respond(item):
        nonlocal active, maximum
        active += 1
        maximum = max(maximum, active)
        try:
            await asyncio.sleep(0.01)
        finally:
            active -= 1
        return item

    access, start, _ = await setup(lifecycle, monkeypatch, respond)
    values = await asyncio.gather(
        *(
            access.check(
                "issuer|alice", "tenant", start.connection_id, tuple(target(str(i)) for i in range(8))
            )
            for _ in range(3)
        )
    )
    assert [len(rows) for rows in values] == [8, 8, 8]
    assert maximum == 4 and active == 0


@pytest.mark.parametrize("unexpected", [False, True])
async def test_failure_drains_other_checks_without_exposing_exception_groups(
    lifecycle, monkeypatch, unexpected
):
    entered = asyncio.Event()
    active = 0

    async def respond(item):
        nonlocal active
        active += 1
        if active == 4:
            entered.set()
        try:
            await entered.wait()
            if item.item_id == "0":
                if unexpected:
                    raise RuntimeError("private provider payload")
                raise SourceError("throttled", retry_after=12)
            await asyncio.sleep(0)
            return item
        finally:
            active -= 1

    access, start, _ = await setup(lifecycle, monkeypatch, respond)
    with pytest.raises(SourceError) as failure:
        await access.check(
            "issuer|alice", "tenant", start.connection_id, tuple(target(str(i)) for i in range(9))
        )
    assert failure.value.code == ("unavailable" if unexpected else "throttled")
    assert failure.value.retry_after == (None if unexpected else 12)
    assert "private" not in str(failure.value) and active == 0


@pytest.mark.parametrize("change", ["scopes", "reconnect", "client", "rotation"])
async def test_authority_changed_during_check_invalidates_observations(lifecycle, monkeypatch, change):
    from koinon.integrations.content_sources.repositories import SourceConnectionRepository
    from koinon.security.authority import primary_authority

    async def respond(item):
        if change == "client":
            lifecycle[1].providers["google_drive"]["client_id"] = "replacement-client"
        else:
            async with primary_authority(read_only=False):
                repository = lifecycle[3].get_bean(SourceConnectionRepository)
                row = await repository.owned("tenant", "issuer|alice", start.connection_id)
                row.revision += 2 if change == "reconnect" else 1
                if change == "scopes":
                    row.scopes = [scope for scope in row.scopes if scope != "profile"]
                await repository.save(row)
        return item

    access, start, _ = await setup(lifecycle, monkeypatch, respond)
    with pytest.raises(SourceError):
        await access.check("issuer|alice", "tenant", start.connection_id, (target(),))
