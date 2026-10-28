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
        facade=SimpleNamespace(catalog=SimpleNamespace(_audit=AsyncMock())),
    )
    jobs = SimpleNamespace(submit=AsyncMock(return_value=SimpleNamespace(id="job")))
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
    assert first["index"]["id"] == second["index"]["id"] and first["job_id"] == "job"
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
