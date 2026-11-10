# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from importlib import import_module
from types import SimpleNamespace
from unittest.mock import AsyncMock

from pyfly.data.transaction import current_unit_of_work
from test_mode_preflight import setup

from koinon.knowledge.connections.service import embedding_fingerprint

pytest_plugins = ("test_organization_knowledge_service",)


async def preparation(knowledge, *, active=True):
    provider = SimpleNamespace(id="provider", kind="ollama", base_url="http://127.0.0.1:11434/v1")
    fingerprint = embedding_fingerprint(provider, "embedding", 768, 768)
    pins = {
        "documents.embedding": {
            "provider_id": "provider",
            "model_id": "embedding",
            "dimensions": 768,
            "storage_dimensions": 768,
            "space_id": "active" if active else None,
            "embedding_fingerprint": fingerprint,
            "assignment_revision": 1,
        },
        "documents.answer": {"provider_revision": 1},
    }
    roles = SimpleNamespace(check=AsyncMock(return_value=pins))
    service, queue, targets, request, preflight = await setup(knowledge, roles)
    await preflight.step("north", request.id, "worker")
    await queue.claim("worker")
    await preflight.step("north", request.id, "worker")
    await queue.claim("worker")
    reader = SimpleNamespace(
        plan_state=AsyncMock(
            return_value=(
                provider,
                {"active_index_id": "active-id" if active else None, "expected_connection_revision": 1},
            )
        ),
        adapter=SimpleNamespace(
            get_native=AsyncMock(
                return_value={
                    "id": "active-id",
                    "space_id": "active",
                    "model_id": "embedding",
                    "dimensions": 768,
                    "storage_dimensions": 768,
                    "active": True,
                    "indexed": True,
                    "chunk_count": 3,
                    "vector_count": 3,
                }
            )
        ),
    )
    lifecycle = SimpleNamespace(
        reader=reader,
        records=SimpleNamespace(
            mode_ready_candidates=AsyncMock(return_value=[]), find_all=AsyncMock(return_value=[])
        ),
        create=AsyncMock(
            return_value={"index": {"id": "new-index", "status": "queued"}, "job_id": "index-job"}
        ),
    )
    activation = SimpleNamespace(activate=AsyncMock())
    recovery = SimpleNamespace(inspect=AsyncMock())
    module = import_module("koinon.organization_knowledge.transitions.index_preparation")
    instance = module.ModeIndexPreparation(
        queue, targets, preflight.authority, roles, preflight.progress, lifecycle, activation, recovery
    )
    return service, queue, targets, request, instance


async def test_qualified_active_index_is_reused_without_embedding_probe_or_rebuild(knowledge):
    service, _, targets, request, instance = await preparation(knowledge)
    await instance.step("north", request.id, "worker")
    workspace = (await targets.page("north", request.id, kind="workspace"))[0]
    assert workspace.status == "ready" and workspace.result["index_id"] == "active-id"
    instance.lifecycle.create.assert_not_awaited()
    instance.activation.activate.assert_not_awaited()
    assert (await service.get("admin", "north", request.id)).active_mode == "rlm"


async def test_new_index_intent_is_durable_before_detached_qualification_and_linked_to_parent(knowledge):
    service, _, targets, request, instance = await preparation(knowledge, active=False)

    async def create(subject, tenant_id, fields, key, *, parent_mode_transition_id):
        assert current_unit_of_work("primary") is None
        assert (subject, tenant_id, parent_mode_transition_id) == ("admin", "north", request.id)
        target = (await targets.page("north", request.id, kind="workspace"))[0]
        assert target.result["index_create"] == fields
        assert target.result["index_create_dispatched"] == 0
        return {"index": {"id": "new-index", "status": "queued"}, "job_id": "index-job"}

    instance.lifecycle.create.side_effect = create
    await instance.step("north", request.id, "worker")
    workspace = (await targets.page("north", request.id, kind="workspace"))[0]
    assert workspace.status == "waiting"
    assert workspace.result["index_id"] == "new-index" and workspace.result["job_id"] == "index-job"
    assert (await service.get("admin", "north", request.id)).status == "queued"


async def test_restarted_worker_does_not_repeat_uncertain_qualification_without_explicit_retry(knowledge):
    service, _, targets, request, instance = await preparation(knowledge, active=False)
    target = (await targets.page("north", request.id, kind="workspace"))[0]
    target.result = {
        **target.result,
        "index_create": {
            "workspace_id": target.workspace_id,
            "domain": "documents",
            "provider_id": "provider",
            "model_id": "embedding",
            "expected_dimensions": 768,
            "expected_active_id": None,
            "expected_connection_revision": 1,
        },
        "index_create_dispatched": 0,
    }
    await targets.save(target)
    await instance.step("north", request.id, "worker")
    instance.lifecycle.create.assert_not_awaited()
    failed = await service.get("admin", "north", request.id)
    assert failed.status == "failed" and failed.error_code == "INDEX_QUALIFICATION_OUTCOME_UNKNOWN"
    assert failed.active_mode == "rlm"


async def test_failed_index_is_resumed_only_after_explicit_mode_retry(knowledge):
    service, queue, targets, request, instance = await preparation(knowledge, active=False)
    target = (await targets.page("north", request.id, kind="workspace"))[0]
    target.result = {**target.result, "index_id": "failed-index", "job_id": "failed-job"}
    await targets.save(target)
    instance.lifecycle.get = AsyncMock(
        return_value={"id": "failed-index", "status": "failed", "revision": 3, "job_id": "failed-job"}
    )
    instance.lifecycle.resume = AsyncMock(
        return_value={"index": {"id": "failed-index"}, "job_id": "resumed-job"}
    )
    await instance.step("north", request.id, "worker")
    instance.lifecycle.resume.assert_not_awaited()
    failed = await service.get("admin", "north", request.id)
    assert failed.error_code == "INDEX_PREPARATION_REVIEW_REQUIRED"
    await service.retry("admin", "north", request.id, expected_revision=failed.revision)
    row = await service.records.find_by_id(request.id)
    row.stage = "prepare_indexes"
    await service.records.save(row)
    await queue.claim("worker")
    await instance.step("north", request.id, "worker")
    assert instance.lifecycle.resume.await_count == 1
    assert instance.lifecycle.resume.call_args.kwargs == {"parent_mode_transition_id": request.id}
    saved = await targets.find_by_id(target.id)
    assert saved.result["index_id"] == "failed-index" and saved.result["job_id"] == "resumed-job"


async def test_content_growth_replaces_only_the_now_stale_active_index_without_replaying_old_intent(
    knowledge,
):
    service, _, targets, request, instance = await preparation(knowledge)
    target = (await targets.page("north", request.id, kind="workspace"))[0]
    target.result = {
        **target.result,
        "index_id": "active-id",
        "index_create": {"old": "intent"},
        "index_create_dispatched": 0,
    }
    await targets.save(target)
    instance.lifecycle.get = AsyncMock(
        return_value={"id": "active-id", "status": "active", "revision": 2, "job_id": "completed"}
    )
    instance.lifecycle.reader.adapter.get_native.return_value["vector_count"] = 2
    await instance.step("north", request.id, "worker")
    saved = await targets.find_by_id(target.id)
    assert saved.status == "prepared" and saved.result["index_id"] is None
    assert saved.result["index_create"] is None and saved.result["index_generation"] == 1
    instance.lifecycle.create.assert_not_awaited()
    assert (await service.get("admin", "north", request.id)).active_mode == "rlm"


async def test_unqualified_candidate_advances_only_candidate_cursor_then_reuses_next_version(knowledge):
    service, queue, targets, request, instance = await preparation(knowledge, active=False)
    role = instance.roles.check.return_value["documents.embedding"]
    candidates = {
        key: SimpleNamespace(
            id=key,
            job_id="job-" + key,
            model_id="embedding",
            dimensions=768,
            storage_dimensions=768,
            embedding_fingerprint=role["embedding_fingerprint"],
        )
        for key in ("a", "b")
    }

    async def page(*args, after=None, **kwargs):
        return [candidates["a" if after is None else "b"]] if after != "b" else []

    activated = False

    async def native(**kwargs):
        key = kwargs["identifier"]
        return {
            "id": key,
            "space_id": key,
            "model_id": "embedding",
            "dimensions": 768,
            "storage_dimensions": 768,
            "indexed": True,
            "active": activated,
            "chunk_count": 3,
            "vector_count": 2 if key == "a" else 3,
        }

    async def activate(subject, tenant, identifier, values, *, parent_mode_transition_id):
        nonlocal activated
        assert identifier == "b" and parent_mode_transition_id == request.id
        activated = True
        role["space_id"], role["assignment_revision"] = "b", 2
        return {"status": "active"}

    instance.lifecycle.records.mode_ready_candidates.side_effect = page
    instance.lifecycle.reader.adapter.get_native.side_effect = native
    instance.lifecycle.get = AsyncMock(
        return_value={"id": "b", "job_id": "job-b", "status": "ready", "revision": 1}
    )
    instance.activation.activate.side_effect = activate
    await instance.step("north", request.id, "worker")
    target = (await targets.page("north", request.id, kind="workspace"))[0]
    assert target.status == "prepared" and target.result["candidate_after"] == "a"
    assert (await service.records.find_by_id(request.id)).cursor.get("indexes_after") is None
    await queue.claim("worker")
    await instance.step("north", request.id, "worker")
    target = await targets.find_by_id(target.id)
    assert target.status == "ready" and target.result["index_id"] == "b"
    assert (await service.records.find_by_id(request.id)).cursor["indexes_after"] == target.id
    assert instance.lifecycle.records.mode_ready_candidates.await_args.kwargs["after"] == "a"
    instance.lifecycle.create.assert_not_awaited()
    instance.activation.activate.assert_awaited_once()
