# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from pyfly.kernel import ConflictException, ServiceUnavailableException
from test_index_lifecycle import service, values
from test_index_persistence import index_rows as index_rows

from koinon.knowledge.indexes.activation import IndexActivation


async def prepared(rows):
    lifecycle, reader, adapter = service(rows)
    result = await lifecycle.create("issuer|actor", "tenant", values(), "request")
    row = await rows.find_by_id(result["index"]["id"])
    row.status, row.build_slot, row.indexed = "ready", None, True
    await rows.save(row)
    pointer = {"value": None}
    adapter.overview = AsyncMock(side_effect=lambda **kw: {"active_native_id": pointer["value"]})

    async def switch(record, *, previous_native_id, restore=False):
        pointer["value"] = previous_native_id if restore else record.native_id

    adapter.activate = AsyncMock(side_effect=switch)
    adapter.get_native = AsyncMock(
        return_value={
            "status": "ready",
            "chunk_count": 0,
            "vector_count": 0,
            "indexed": True,
            "qualification": "coverage_and_ann_passed",
        }
    )
    reader.facade.bindings = SimpleNamespace(find_all=AsyncMock(return_value=[]))
    assignments = SimpleNamespace(snapshot=AsyncMock(return_value={"workspace": None}), bind=AsyncMock())
    activation = IndexActivation(lifecycle, assignments)
    return activation, row, pointer, assignments, adapter, reader


def request(row, **changes):
    return {
        "expected_revision": row.revision,
        "expected_active_id": None,
        "expected_connection_revision": None,
        **changes,
    }


async def test_activation_switches_only_after_qualification_and_exact_role_installation(index_rows):
    activation, row, pointer, assignments, adapter, _ = await prepared(index_rows)
    result = await activation.activate("issuer|actor", "tenant", row.id, request(row))
    assert result["status"] == "active" and pointer["value"] == row.native_id
    assignments.bind.assert_awaited_once()
    stored = await index_rows.find_by_id(row.id)
    assert stored.active_slot and stored.build_slot is None
    assert stored.transition["previous_native_id"] is None
    assert stored.previous_binding == {"workspace": None}


async def test_activation_refreshes_original_build_counts_after_later_native_ingestion(index_rows):
    activation, row, _, _, adapter, _ = await prepared(index_rows)
    adapter.get_native.return_value.update(chunk_count=5, vector_count=5)
    result = await activation.activate("issuer|actor", "tenant", row.id, request(row))
    assert result["chunk_count"] == result["vector_count"] == 5 and result["indexed"]


async def test_stale_native_coverage_keeps_previous_pointer_and_releases_activation_slot(index_rows):
    activation, row, pointer, assignments, adapter, _ = await prepared(index_rows)
    adapter.activate.side_effect = ConflictException("Content changed", code="INDEX_COVERAGE_STALE")
    with pytest.raises(ConflictException):
        await activation.activate("issuer|actor", "tenant", row.id, request(row))
    stored = await index_rows.find_by_id(row.id)
    assert pointer["value"] is None and stored.status == "ready" and stored.build_slot is None
    assignments.bind.assert_not_awaited()


async def test_stale_retired_version_keeps_its_history_state_when_activation_is_aborted(index_rows):
    activation, row, _, _, adapter, _ = await prepared(index_rows)
    row.status = "retired"
    await index_rows.save(row)
    adapter.activate.side_effect = ConflictException("Content changed", code="INDEX_COVERAGE_STALE")
    with pytest.raises(ConflictException):
        await activation.activate("issuer|actor", "tenant", row.id, request(row))
    assert (await index_rows.find_by_id(row.id)).status == "retired"


async def test_primary_finish_conflict_is_recoverable_without_replacing_original_previous_pointer(index_rows):
    activation, row, pointer, assignments, _, _ = await prepared(index_rows)
    assignments.bind.side_effect = [ConflictException("Role changed", code="INDEX_CONNECTION_CONFLICT"), None]
    with pytest.raises(ConflictException):
        await activation.activate("issuer|actor", "tenant", row.id, request(row))
    pending = await index_rows.find_by_id(row.id)
    assert pending.status == "activating" and pointer["value"] == row.native_id
    result = await activation.activate(
        "issuer|actor", "tenant", row.id, request(pending, expected_active_id=row.id, recovery="finish")
    )
    assert result["status"] == "active"
    assert (await index_rows.find_by_id(row.id)).transition["previous_native_id"] is None


async def test_restore_pending_pointer_does_not_require_failed_target_provider_or_mutate_roles(index_rows):
    activation, row, pointer, assignments, adapter, reader = await prepared(index_rows)
    assignments.bind.side_effect = ConflictException("Role changed", code="INDEX_CONNECTION_CONFLICT")
    with pytest.raises(ConflictException):
        await activation.activate("issuer|actor", "tenant", row.id, request(row))
    pending = await index_rows.find_by_id(row.id)
    reader.planner.provider.side_effect = ServiceUnavailableException("Provider disabled")
    result = await activation.activate(
        "issuer|actor",
        "tenant",
        row.id,
        request(pending, expected_active_id=row.id, recovery="restore_previous"),
    )
    assert result["status"] == "ready" and pointer["value"] is None
    assert assignments.bind.await_count == 1
    assert len(await index_rows.find_all()) == 1
