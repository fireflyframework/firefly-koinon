# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from pyfly.kernel import ConflictException, ServiceUnavailableException
from test_index_lifecycle import service, values
from test_index_persistence import index_rows as index_rows

from koinon.knowledge.indexes.activation import IndexActivation
from koinon.organization_knowledge.transitions.entities import KnowledgeModeTransition
from koinon.organization_knowledge.transitions.index_attempts import ModeIndexAttemptRepository
from koinon.organization_knowledge.transitions.repositories import ModeTransitionRepository


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


async def inactive_parent(lifecycle, row):
    job = await lifecycle.jobs.repository.find_by_id(row.job_id)
    job.payload = {**job.payload, "parent_mode_transition_id": "cancelled-parent"}
    await lifecycle.jobs.repository.save(job)
    lifecycle.parent_authority = SimpleNamespace(
        get=lambda: SimpleNamespace(
            check=AsyncMock(
                side_effect=ConflictException("Parent cancelled", code="INDEX_MODE_PREPARATION_INACTIVE")
            )
        )
    )


@pytest.mark.parametrize("action", ["finish", "restore_previous"])
async def test_explicit_recovery_of_started_activation_survives_parent_cancellation(index_rows, action):
    activation, row, pointer, assignments, _, _ = await prepared(index_rows)
    assignments.bind.side_effect = ConflictException("Assignment changed", code="INDEX_CONNECTION_CONFLICT")
    with pytest.raises(ConflictException):
        await activation.activate("issuer|actor", "tenant", row.id, request(row))
    pending = await index_rows.find_by_id(row.id)
    assert pending.status == "activating" and pointer["value"] == row.native_id
    await inactive_parent(activation.lifecycle, pending)
    assignments.bind.side_effect = None
    result = await activation.activate(
        "issuer|actor",
        "tenant",
        row.id,
        request(pending, expected_active_id=row.id, recovery=action),
    )
    assert result["status"] == ("active" if action == "finish" else "ready")
    assert pointer["value"] == (row.native_id if action == "finish" else None)


async def test_cancelled_parent_cannot_start_new_activation_even_with_recovery_label(index_rows):
    activation, row, pointer, _, _, _ = await prepared(index_rows)
    await inactive_parent(activation.lifecycle, row)
    for recovery in (None, "finish", "restore_previous"):
        with pytest.raises(ConflictException):
            await activation.activate("issuer|actor", "tenant", row.id, request(row, recovery=recovery))
    assert pointer["value"] is None


async def test_cancel_before_native_switch_cannot_be_recovered_by_starting_new_switch(index_rows):
    activation, row, pointer, assignments, adapter, _ = await prepared(index_rows)
    from koinon.knowledge.indexes.dtos import IndexActivateInput

    initial = IndexActivateInput.model_validate(request(row)).model_dump()
    pending = await activation.begin("issuer|actor", "tenant", row.id, initial)
    await inactive_parent(activation.lifecycle, pending)
    with pytest.raises(ConflictException) as error:
        await activation.activate("issuer|actor", "tenant", row.id, request(pending, recovery="finish"))
    assert error.value.code == "INDEX_RECOVERY_SWITCH_NOT_APPLIED"
    adapter.activate.assert_not_awaited()
    assignments.bind.assert_not_awaited()
    assert pointer["value"] is None
    pending = await index_rows.find_by_id(row.id)
    result = await activation.activate(
        "issuer|actor", "tenant", row.id, request(pending, recovery="restore_previous")
    )
    assert result["status"] == "ready" and pointer["value"] is None


@pytest.mark.parametrize("cancel_after_switch", [False, True])
async def test_borrowed_ready_activation_is_fenced_without_rewriting_build_job(
    index_rows, cancel_after_switch
):
    from koinon.knowledge.indexes.dtos import IndexActivateInput

    activation, row, pointer, _, adapter, _ = await prepared(index_rows)
    build_job = await activation.lifecycle.jobs.repository.find_by_id(row.job_id)
    payload = dict(build_job.payload)
    parent = {"active": True}

    async def guard(parent_id, tenant_id, index_record=None):
        assert (parent_id, tenant_id) == ("mode-parent", "tenant")
        if not parent["active"]:
            raise ConflictException("Parent cancelled", code="INDEX_MODE_PREPARATION_INACTIVE")

    mode_job = await activation.lifecycle.jobs.submit("tenant", "tenant", "knowledge.mode", {}, "mode-parent")
    await ModeTransitionRepository().save(
        KnowledgeModeTransition(
            id="mode-parent",
            tenant_id="tenant",
            job_id=mode_job.id,
            actor="issuer|actor",
            base_revision=0,
            base_digest="a" * 64,
            active_mode="rlm",
            requested_settings={},
        )
    )
    evidence = ModeIndexAttemptRepository()

    async def admitted(parent_id, tenant_id, record):
        return await evidence.capture(tenant_id, parent_id, record)

    async def resolved(parent_id, tenant_id, record, outcome):
        await evidence.resolve(
            tenant_id,
            parent_id,
            record.transition["mode_activation_attempt_id"],
            record,
            outcome,
            expected_revision=1,
        )

    activation.lifecycle.parent_authority = SimpleNamespace(
        get=lambda: SimpleNamespace(
            check=guard,
            admitted=admitted,
            resolved=resolved,
        )
    )
    initial = IndexActivateInput.model_validate(request(row)).model_dump()
    pending = await activation.begin(
        "issuer|actor", "tenant", row.id, initial, parent_mode_transition_id="mode-parent"
    )
    if cancel_after_switch:
        await activation.switch("issuer|actor", "tenant", row.id, initial)
    parent["active"] = False
    with pytest.raises(ConflictException, match="Parent cancelled"):
        if cancel_after_switch:
            await activation.finish("issuer|actor", "tenant", row.id, initial)
        else:
            await activation.switch("issuer|actor", "tenant", row.id, initial)
    assert pointer["value"] == (row.native_id if cancel_after_switch else None)
    assert (await activation.lifecycle.jobs.repository.find_by_id(build_job.id)).payload == payload
    assert await index_rows.count_mode_recoveries("tenant", "mode-parent") == 1
    assert [value.id for value in await index_rows.mode_children("tenant", "mode-parent")] == [row.id]
    result = await activation.activate(
        "issuer|actor",
        "tenant",
        row.id,
        request(
            pending,
            expected_active_id=row.id if cancel_after_switch else None,
            recovery="finish" if cancel_after_switch else "restore_previous",
        ),
    )
    assert result["status"] == ("active" if cancel_after_switch else "ready")
    assert await index_rows.count_mode_recoveries("tenant", "mode-parent") == 0
    assert adapter.activate.await_count == int(cancel_after_switch)
    attempts = await evidence.page("tenant", "mode-parent")
    assert len(attempts) == 1 and attempts[0].index_id == row.id
    assert attempts[0].native_workspace_id == row.native_workspace_id
    resolutions = await evidence.resolutions("tenant", [attempts[0].id])
    assert resolutions[attempts[0].id].status == ("finished" if cancel_after_switch else "restored")
    assert resolutions[attempts[0].id].revision == 2
