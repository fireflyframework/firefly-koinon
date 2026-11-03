# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from importlib import import_module

import pytest
from pyfly.kernel import ConflictException
from test_organization_knowledge_service import update_input

from koinon.catalog.errors import AccessDenied
from koinon.jobs.repository import JobRepository
from koinon.jobs.service import JobService
from koinon.knowledge.indexes.repositories import KnowledgeIndexRepository

pytest_plugins = ("test_organization_knowledge_service",)


def transitions(knowledge):
    module = import_module("koinon.organization_knowledge.transitions.service")
    repository = import_module("koinon.organization_knowledge.transitions.repositories")
    return module.KnowledgeModeTransitions(
        knowledge.service,
        repository.ModeTransitionRepository(),
        JobService(JobRepository()),
        repository.ModeTargetRepository(),
        KnowledgeIndexRepository(),
        attempts=import_module("koinon.organization_knowledge.transitions.index_attempts").ModeIndexAttemptRepository(),
    )


async def test_request_preserves_active_mode_and_replays_same_durable_intent(knowledge):
    service = transitions(knowledge)
    before = await knowledge.service.snapshot("admin", "north")
    first = await service.request("admin", "north", update_input(), "mode-one")
    replay = await service.request("admin", "north", update_input(), "mode-one")
    assert first.id == replay.id
    assert first.status == "queued"
    assert (first.active_mode, first.requested_mode) == ("rlm", "rag")
    assert first.base_revision == before.revision
    assert first.base_digest == before.digest
    assert (await knowledge.service.snapshot("admin", "north")) == before
    assert len(await JobRepository().find_all(kind="knowledge.mode", tenant_id="north")) == 1


async def test_request_authority_and_settings_revision_are_not_inferred(knowledge):
    service = transitions(knowledge)
    for subject in ("viewer", "operator", "scoped", "outside"):
        with pytest.raises(AccessDenied):
            await service.request(subject, "north", update_input(), "forbidden-" + subject)
    with pytest.raises(ConflictException) as error:
        await service.request("admin", "north", update_input(expected_revision=8), "stale")
    assert error.value.code == "ORGANIZATION_KNOWLEDGE_CHANGED"
    assert not await JobRepository().find_all(kind="knowledge.mode")


async def test_cancel_preserves_active_mode_and_requires_transition_revision(knowledge):
    service = transitions(knowledge)
    first = await service.request("admin", "north", update_input(), "cancel")
    with pytest.raises(ConflictException):
        await service.cancel("admin", "north", first.id, expected_revision=first.revision + 1)
    cancelled = await service.cancel("admin", "north", first.id, expected_revision=first.revision)
    assert cancelled.status == "cancelled"
    assert cancelled.revision == first.revision + 1
    assert (await knowledge.service.get("admin", "north")).documents.answer_mode == "rlm"
    assert (await JobRepository().find_by_id(first.job_id)).status == "cancelled"


async def test_new_request_requires_explicit_cancellation_of_current_preparation(knowledge):
    service = transitions(knowledge)
    first = await service.request("admin", "north", update_input(), "first")
    with pytest.raises(ConflictException) as error:
        await service.request("admin", "north", update_input(), "second")
    assert error.value.code == "KNOWLEDGE_MODE_IN_PROGRESS"
    await service.cancel("admin", "north", first.id, expected_revision=first.revision)
    second = await service.request("admin", "north", update_input(), "second")
    assert second.id != first.id


async def test_generic_job_consumer_cannot_claim_mode_preparation(knowledge):
    service = transitions(knowledge)
    await service.request("admin", "north", update_input(), "claim")
    assert await JobService(JobRepository()).claim("ordinary-worker") is None


async def test_failed_readiness_and_retry_never_change_active_settings(knowledge):
    service = transitions(knowledge)
    first = await service.request("admin", "north", update_input(), "failure")
    queue = import_module("koinon.organization_knowledge.transitions.queue").ModeTransitionQueue(service)
    claimed = await queue.claim("mode-worker")
    assert claimed == first.id
    await queue.fail("north", first.id, "mode-worker", code="KNOWLEDGE_PROVIDER_UNAVAILABLE")
    failed = await service.get("admin", "north", first.id)
    assert failed.status == "failed"
    assert (await knowledge.service.get("admin", "north")).documents.answer_mode == "rlm"
    retried = await service.retry("admin", "north", first.id, expected_revision=failed.revision)
    assert retried.id == first.id
    assert retried.status == "queued"
    assert await queue.claim("restarted-worker") == first.id
    assert len(await JobRepository().find_all(kind="knowledge.mode", tenant_id="north")) == 1


async def test_cancelled_lease_cannot_publish_progress(knowledge):
    service = transitions(knowledge)
    first = await service.request("admin", "north", update_input(), "cancel-publication")
    queue = import_module("koinon.organization_knowledge.transitions.queue").ModeTransitionQueue(service)
    await queue.claim("mode-worker")
    current = await service.get("admin", "north", first.id)
    await service.cancel("admin", "north", first.id, expected_revision=current.revision)
    with pytest.raises(ConflictException):
        await queue.fence("north", first.id, "mode-worker")


async def test_settings_change_supersedes_preparation_before_next_stage(knowledge):
    service = transitions(knowledge)
    first = await service.request("admin", "north", update_input(), "stale-lease")
    queue = import_module("koinon.organization_knowledge.transitions.queue").ModeTransitionQueue(service)
    await queue.claim("mode-worker")
    changed = update_input()
    changed = changed.model_copy(
        update={"documents": changed.documents.model_copy(update={"answer_mode": "rlm", "answer_top_k": 11})}
    )
    await knowledge.service.update("admin", "north", changed)
    with pytest.raises(ConflictException) as error:
        await queue.authorize("north", first.id, "mode-worker")
    assert error.value.code == "KNOWLEDGE_MODE_SUPERSEDED"
    assert (await knowledge.service.get("admin", "north")).documents.answer_mode == "rlm"


async def test_preparation_targets_page_without_cross_tenant_or_transition_rows(knowledge):
    service = transitions(knowledge)
    first = await service.request("admin", "north", update_input(), "pages")
    module = import_module("koinon.organization_knowledge.transitions.entities")
    repository = import_module(
        "koinon.organization_knowledge.transitions.repositories"
    ).ModeTargetRepository()
    for number in range(201):
        await repository.save(
            module.KnowledgeModeTarget(
                id=f"target-{number:04}",
                tenant_id="north",
                transition_id=first.id,
                kind="document",
                catalog_id=f"document-{number}",
                workspace_id=knowledge.workspace.id,
            )
        )
    page = await repository.page("north", first.id, limit=200)
    tail = await repository.page("north", first.id, after=page[-1].id, limit=200)
    assert len(page) == 200 and len(tail) == 1
    assert len({row.id for row in page + tail}) == 201
    assert not await repository.page("south", first.id)
    assert not await repository.page("north", "another-transition")
    assert await repository.counts("north", first.id) == {"queued": 201}
    with pytest.raises(ValueError):
        await repository.page("north", first.id, limit=201)


async def test_cancel_stops_only_active_index_children_owned_by_this_transition(knowledge):
    service = transitions(knowledge)
    first = await service.request("admin", "north", update_input(), "cancel-children")
    own = await service.jobs.submit(
        "north",
        knowledge.workspace.id,
        "knowledge.index",
        {"parent_mode_transition_id": first.id},
        "owned-index",
    )
    other = await service.jobs.submit(
        "north",
        knowledge.workspace.id,
        "knowledge.index",
        {"parent_mode_transition_id": "other"},
        "other-index",
    )
    completed = await service.jobs.submit(
        "north",
        knowledge.workspace.id,
        "knowledge.index",
        {"parent_mode_transition_id": first.id},
        "completed-index",
    )
    completed.status = "succeeded"
    await service.jobs.repository.save(completed)
    await service.cancel("admin", "north", first.id, expected_revision=first.revision)
    assert (await service.jobs.repository.find_by_id(own.id)).status == "queued"
    await service.settle_cancelled_children("north", first.id)
    assert (await service.jobs.repository.find_by_id(own.id)).status == "cancelled"
    assert (await service.jobs.repository.find_by_id(other.id)).status == "queued"
    assert (await service.jobs.repository.find_by_id(completed.id)).status == "succeeded"


async def test_generic_job_consumer_cannot_claim_native_index_children(knowledge):
    jobs = JobService(JobRepository())
    await jobs.submit(
        "north",
        knowledge.workspace.id,
        "knowledge.index",
        {"parent_mode_transition_id": "parent"},
        "native-only",
    )
    assert await jobs.claim("ordinary-worker") is None


async def test_generic_job_cancellation_closes_mode_and_children_without_old_actor_authority(knowledge):
    service = transitions(knowledge)
    request = await service.request("admin", "north", update_input(), "generic-cancel")
    child = await service.jobs.submit(
        "north",
        knowledge.workspace.id,
        "knowledge.index",
        {"parent_mode_transition_id": request.id},
        "generic-child",
    )
    await service.jobs.cancel("north", request.job_id)
    queue = import_module("koinon.organization_knowledge.transitions.queue").ModeTransitionQueue(service)
    await queue.synchronize_cancelled()
    row = await service.records.find_by_id(request.id)
    assert row.status == "cancelled" and row.active_slot is None
    assert (await service.jobs.repository.find_by_id(child.id)).status == "cancelled"
    assert await queue.claim("worker") is None
    await queue.synchronize_cancelled()
    assert (await service.records.find_by_id(request.id)).revision == row.revision


async def test_cancelled_child_cleanup_is_bounded_and_resumes_without_reopening_parent(knowledge):
    service = transitions(knowledge)
    first = await service.request("admin", "north", update_input(), "bounded-cleanup")
    for number in range(61):
        await service.jobs.submit(
            "north",
            knowledge.workspace.id,
            "knowledge.index",
            {"parent_mode_transition_id": first.id},
            f"cleanup-{number}",
        )
    await service.cancel("admin", "north", first.id, expected_revision=first.revision)
    assert (
        len(
            await service.jobs.repository.find_all(tenant_id="north", kind="knowledge.index", status="queued")
        )
        == 61
    )
    for remaining in (36, 11, 0):
        await service.settle_cancelled_children("north", first.id)
        assert (
            len(
                await service.jobs.repository.find_all(
                    tenant_id="north", kind="knowledge.index", status="queued"
                )
            )
            == remaining
        )
        assert (await service.records.find_by_id(first.id)).status == "cancelled"
    row = await service.records.find_by_id(first.id)
    assert row.counters["cancelled_index_jobs"] == 61
    assert not await service.records.cancelled_children()
