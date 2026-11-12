# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Bounded renewal registrations and shutdown keep exact worker ownership."""

import asyncio
from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest

from koinon.integrations.content_sources.settings import ContentSourceSettings
from koinon.integrations.content_sources.sync_heartbeat import SourceSyncHeartbeat
from koinon.integrations.content_sources.sync_runs import SourceRunLease, SourceRunRepository


def lease(identifier="run"):
    return SourceRunLease(
        "tenant",
        "owner",
        "mapping",
        identifier,
        "job-" + identifier,
        "worker",
        1,
        1,
        1,
        "policy",
        datetime.now(UTC) + timedelta(seconds=360),
        False,
    )


def heartbeat():
    return SourceSyncHeartbeat(SourceRunRepository(), ContentSourceSettings())


def test_registry_reserves_before_claim_and_never_exceeds_capacity():
    control = heartbeat()
    leases = [lease(str(index)) for index in range(64)]
    for current in leases:
        slot = control.reserve(current.tenant_id, current.owner, current.run_id)
        assert slot is not None
        control.register(slot, current)
    assert control.reserve("tenant", "owner", "overflow") is None
    control.release(replace(leases[0], worker_id="foreign"))
    assert control.reserve("tenant", "owner", "overflow") is None
    control.release(leases[0])
    slot = control.reserve("tenant", "owner", "overflow")
    assert slot is not None
    control.abandon(slot)
    assert control.reserve("tenant", "owner", "replacement") is not None


async def test_shutdown_cancels_and_drains_source_slice_and_denies_new_claim():
    control, current = heartbeat(), lease()
    slot = control.reserve(current.tenant_id, current.owner, current.run_id)
    control.register(slot, current)
    ready, blocked, cleaned = asyncio.Event(), asyncio.Event(), asyncio.Event()

    async def source_slice():
        control.attach(current)
        ready.set()
        try:
            await blocked.wait()
        finally:
            cleaned.set()

    task = asyncio.create_task(source_slice())
    await ready.wait()
    await control.close()
    assert task.cancelled() and cleaned.is_set()
    assert control.reserve("tenant", "owner", "next") is None


def test_expired_registration_is_not_adopted_by_another_attempt(monkeypatch):
    import koinon.integrations.content_sources.sync_heartbeat as module

    control, current = heartbeat(), lease()
    slot = control.reserve(current.tenant_id, current.owner, current.run_id)
    control.register(slot, current)

    class Later(datetime):
        @classmethod
        def now(cls, tz=None):
            return current.expires_at + timedelta(seconds=1)

    monkeypatch.setattr(module, "datetime", Later)
    fresh = control.reserve(current.tenant_id, current.owner, current.run_id)
    assert fresh is not None and fresh is not slot
    replacement = replace(
        current, worker_id="new-worker", attempt=2, expires_at=Later.now() + timedelta(seconds=360)
    )
    control.register(fresh, replacement)
    control.release(current)
    assert control.reserve(current.tenant_id, current.owner, current.run_id) is fresh


@pytest.mark.parametrize("seconds", [300, 360, 3600])
def test_heartbeat_budget_fits_supported_lease_with_shutdown_margin(seconds):
    settings = ContentSourceSettings(sync_lease_seconds=seconds)
    settings.synchronization_options()
    assert settings.source_heartbeat_interval + 10 + 30 < seconds
