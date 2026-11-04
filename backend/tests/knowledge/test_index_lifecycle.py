# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from pyfly.kernel import ConflictException
from test_index_persistence import index_rows as index_rows

from koinon.knowledge.indexes.lifecycle import IndexLifecycleService


def service(rows):
    provider = SimpleNamespace(
        id="provider", kind="ollama", revision=1, base_url="http://127.0.0.1:11434", model_ids=["embedding"]
    )
    planner = SimpleNamespace(provider=AsyncMock(return_value=provider))
    adapter = SimpleNamespace(create=AsyncMock(return_value="native-fingerprint"))
    workspace = SimpleNamespace(id="workspace", kind="workspace")
    reader = SimpleNamespace(
        authority=AsyncMock(return_value=workspace),
        native_binding=AsyncMock(return_value=SimpleNamespace(native_workspace_id="workspace")),
        connections=SimpleNamespace(authority=AsyncMock()),
        planner=planner,
        adapter=adapter,
        plan=AsyncMock(
            return_value={
                "active_index_id": None,
                "expected_connection_revision": None,
                "dimensions": 768,
                "storage_dimensions": 768,
                "chunk_count": 0,
            }
        ),
        facade=SimpleNamespace(catalog=SimpleNamespace(_audit=AsyncMock(), _lock_tenant=AsyncMock())),
        plan_state=AsyncMock(return_value=(provider, {})),
        validate_plan=lambda before, current: None,
    )
    from koinon.jobs.repository import JobRepository
    from koinon.jobs.service import JobService

    jobs = JobService(JobRepository())
    return IndexLifecycleService(reader, rows, jobs), reader, adapter


def values(**changes):
    return {
        "workspace_id": "workspace",
        "domain": "documents",
        "provider_id": "provider",
        "model_id": "embedding",
        "expected_active_id": None,
        "expected_connection_revision": None,
        **changes,
    }


async def test_create_records_durable_native_target_and_replay_does_not_allocate_or_probe_again(index_rows):
    lifecycle, reader, adapter = service(index_rows)
    first = await lifecycle.create("issuer|actor", "tenant", values(), "request")
    second = await lifecycle.create("issuer|actor", "tenant", values(), "request")
    assert first["index"]["id"] == second["index"]["id"] and first["job_id"] == second["job_id"]
    assert first["index"]["status"] == "queued" and not first["index"]["active"]
    assert first["index"]["native_id"].startswith("es-")
    reader.plan.assert_awaited_once()
    adapter.create.assert_awaited_once()


async def test_stale_active_revision_is_rejected_before_any_native_target_creation(index_rows):
    lifecycle, reader, adapter = service(index_rows)
    reader.plan.return_value["active_index_id"] = "new-active"
    with pytest.raises(ConflictException):
        await lifecycle.create("issuer|actor", "tenant", values(), "request")
    adapter.create.assert_not_awaited()
    assert await index_rows.find_all() == []


@pytest.mark.parametrize("initial_state", ["cancelled", "retired"])
async def test_resume_replay_retains_job_and_revision_without_repeating_native_write(
    index_rows, initial_state
):
    from koinon.jobs.repository import JobRepository
    from koinon.jobs.service import JobService

    lifecycle, reader, adapter = service(index_rows)
    lifecycle.jobs = JobService(JobRepository())
    created = await lifecycle.create("issuer|actor", "tenant", values(), "create")
    row = await index_rows.find_by_id(created["index"]["id"])
    row.status, row.build_slot = initial_state, None
    await index_rows.save(row)
    adapter.overview = AsyncMock(return_value={"active_native_id": None})
    adapter.project_state = AsyncMock()
    revision = row.revision
    first = await lifecycle.resume("issuer|actor", "tenant", row.id, revision, "resume")
    replay = await lifecycle.resume("issuer|actor", "tenant", row.id, revision, "resume")
    assert replay["job_id"] == first["job_id"]
    assert replay["index"]["revision"] == first["index"]["revision"] == revision + 1
    adapter.project_state.assert_awaited_once()


async def test_creation_qualifies_provider_without_holding_a_primary_transaction(index_rows):
    from pyfly.data.transaction import current_unit_of_work

    lifecycle, reader, _ = service(index_rows)
    result = reader.plan.return_value

    async def plan(*args, **kwargs):
        assert current_unit_of_work("primary") is None, "Provider work must release the database first"
        return result

    reader.plan.side_effect = plan
    created = await lifecycle.create("issuer|actor", "tenant", values(), "outside-transaction")
    assert created["index"]["status"] == "queued"


async def test_reviewed_resume_can_link_an_existing_target_without_rewriting_old_job(index_rows):
    lifecycle, _, adapter = service(index_rows)
    initial = await lifecycle.create("issuer|actor", "tenant", values(), "initial")
    row = await index_rows.find_by_id(initial["index"]["id"])
    row.status, row.build_slot = "failed", None
    row.transition = {"parent_mode_transition_id": "historical"}
    await index_rows.save(row)
    guard = AsyncMock()
    lifecycle.parent_authority = SimpleNamespace(get=lambda: SimpleNamespace(check=guard))
    adapter.overview = AsyncMock(return_value={"active_native_id": None, "chunk_count": 0})
    adapter.project_state = AsyncMock()
    resumed = await lifecycle.resume(
        "issuer|actor", "tenant", row.id, row.revision, "reviewed", parent_mode_transition_id="current"
    )
    assert resumed["job_id"] != initial["job_id"]
    old = await lifecycle.jobs.repository.find_by_id(initial["job_id"])
    new = await lifecycle.jobs.repository.find_by_id(resumed["job_id"])
    assert "parent_mode_transition_id" not in old.payload
    assert new.payload["parent_mode_transition_id"] == "current"
    assert "parent_mode_transition_id" not in (await index_rows.find_by_id(row.id)).transition
    assert [value.id for value in await index_rows.mode_children("tenant", "current")] == [row.id]
    assert guard.await_count >= 1
