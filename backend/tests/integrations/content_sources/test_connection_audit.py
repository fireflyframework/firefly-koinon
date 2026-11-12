# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Lifecycle audit is committed with state and never carries delegated secrets."""

import json

import pytest
from sqlalchemy import select
from test_connection_lifecycle import begin, complete
from test_connection_lifecycle import lifecycle as lifecycle
from test_source_migration_postgres import source_database as source_database

from koinon.catalog.entities import AuditEvent
from koinon.integrations.content_sources.errors import SourceError
from koinon.integrations.content_sources.repositories import SourceConnectionRepository
from koinon.security.authority import primary_authority

pytestmark = pytest.mark.parametrize("lifecycle", ["postgres"], indirect=True)


async def events(service):
    async with primary_authority():
        return list(await service.connections._require_session().scalars(select(AuditEvent)))


async def test_successful_lifecycle_audits_exact_state_without_secrets(lifecycle):
    service, _, _, _ = lifecycle
    start, state = await begin(service)
    connected = await complete(service, start, state)
    await service.disconnect("issuer|alice", "tenant", start.connection_id, connected.revision)
    rows = await events(service)
    assert {row.action for row in rows} == {
        "source.authorization_requested",
        "source.connected",
        "source.disconnected",
    }
    assert len(rows) == 3
    assert all(row.subject == "issuer|alice" and row.tenant_id == "tenant" for row in rows)
    assert all(row.resource_id == start.connection_id for row in rows)
    assert {row.details["revision"] for row in rows} == {1, 2, 3}
    assert all(
        row.details["provider"] == "google_drive" and row.details["outcome"] == "success" for row in rows
    )
    serialized = json.dumps([row.details for row in rows])
    assert all(
        secret not in serialized
        for secret in (state, "access-one", "refresh-one", "one-use-code", "verified-alice")
    )
    with pytest.raises(SourceError):
        await complete(service, start, state)
    assert len(await events(service)) == 3


async def test_audit_failure_rolls_back_connection_state(lifecycle, monkeypatch):
    service, _, _, context = lifecycle
    start, state = await begin(service)
    connected = await complete(service, start, state)

    async def unavailable(*args, **kwargs):
        raise RuntimeError("audit storage unavailable")

    monkeypatch.setattr(service.catalog.audit_repository, "save", unavailable)
    with pytest.raises(RuntimeError, match="audit storage unavailable"):
        await service.disconnect("issuer|alice", "tenant", start.connection_id, connected.revision)
    async with primary_authority():
        row = await context.get_bean(SourceConnectionRepository).owned(
            "tenant", "issuer|alice", start.connection_id
        )
        assert row.status == "connected" and row.revision == connected.revision
    assert len(await events(service)) == 2


async def test_connection_listing_is_owner_scoped_and_bounded(lifecycle):
    service, _, _, _ = lifecycle
    starts = [await begin(service) for _ in range(3)]
    first = await service.list("issuer|alice", "tenant", limit=2)
    second = await service.list("issuer|alice", "tenant", cursor=first.next_cursor, limit=2)
    assert len(first.items) == 2 and first.next_cursor
    assert len(second.items) == 1 and second.next_cursor is None
    assert {item.id for item in (*first.items, *second.items)} == {start.connection_id for start, _ in starts}
    assert not (await service.list("issuer|bob", "tenant")).items
    for limit in (0, 101):
        with pytest.raises(ValueError):
            await service.list("issuer|alice", "tenant", limit=limit)


async def test_refresh_audit_records_only_successful_rotation_once(lifecycle):
    service, _, _, _ = lifecycle
    start, state = await begin(service)
    connected = await complete(service, start, state)
    async with primary_authority(read_only=False):
        row = await service.connections.owned("tenant", "issuer|alice", start.connection_id)
        payload = service.vault.decrypt("tenant", "issuer|alice", row.id, "grant", row.secret_ciphertext)
        payload["expires_at"] = 0
        row.secret_ciphertext = service.vault.encrypt("tenant", "issuer|alice", row.id, "grant", payload)
        await service.connections.save(row)
    for _ in range(2):
        assert (
            await service.access_token("issuer|alice", "tenant", start.connection_id, connected.account)
            == "access-two"
        )
    rotations = [row for row in await events(service) if row.action == "source.refresh_completed"]
    assert len(rotations) == 1
    assert rotations[0].details == {"provider": "google_drive", "revision": 3, "outcome": "success"}
