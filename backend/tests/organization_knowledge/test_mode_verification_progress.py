# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from importlib import import_module
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from pyfly.kernel import ConflictException
from test_mode_discovery import discovery, tree
from test_organization_knowledge_service import update_input

from koinon.organization_knowledge.transitions.generations import ReadinessChange
from koinon.organization_knowledge.transitions.progress import ModeProgress
from koinon.organization_knowledge.transitions.readiness_fence import ModeReadinessSnapshot
from koinon.organization_knowledge.transitions.verification import VerificationPage

pytest_plugins = ("test_organization_knowledge_service",)


async def prepared(knowledge):
    await tree(knowledge, 0)
    service, queue, targets, _ = discovery(knowledge)
    request = await service.request("admin", "north", update_input(), "verification-progress")
    row = await service.records.find_by_id(request.id)
    row.stage = "verify"
    await service.records.save(row)
    progress = ModeProgress(queue, targets)
    targets.counts = AsyncMock(side_effect=AssertionError("No full target count in a verification tick"))
    checker = SimpleNamespace(page=AsyncMock(return_value=VerificationPage(None, 0, True, {})))
    fence = SimpleNamespace(
        snapshot=AsyncMock(return_value=ModeReadinessSnapshot(1, 2)), changes=AsyncMock(return_value=[])
    )
    module = import_module("koinon.organization_knowledge.transitions.verification_progress")
    runner = module.ModeVerificationProgress(queue, checker, fence, progress)
    return service, queue, request, checker, fence, runner


async def advance(service, queue, request, runner):
    assert await queue.claim("worker") == request.id
    await runner.step("north", request.id, "worker")
    return await service.records.find_by_id(request.id)


async def test_verification_resumes_pages_and_activates_only_after_both_journals(knowledge):
    service, queue, request, checker, fence, runner = await prepared(knowledge)
    checker.page.side_effect = [
        VerificationPage("a", 100, False, {"verified_documents": 99}),
        VerificationPage("z", 2, True, {"verified_documents": 2}),
    ]
    row = await advance(service, queue, request, runner)
    assert row.stage == "verify" and checker.page.await_count == 0
    row = await advance(service, queue, request, runner)
    assert row.stage == "verify" and checker.page.await_count == 1
    # A replacement worker reads its continuation from durable state.
    runner = type(runner)(queue, checker, fence, runner.progress)
    row = await advance(service, queue, request, runner)
    assert checker.page.await_args.kwargs["after"] == "a" and row.stage == "verify"
    for _ in range(4):
        row = await advance(service, queue, request, runner)
    assert row.stage == "activate"
    assert row.cursor["verified_generations"] == {"primary": 1, "canon": 2}
    assert row.counters["verified_documents"] == 101
    assert [call.args[1] for call in fence.changes.await_args_list] == ["primary", "canon"]
    assert (await knowledge.service.get("admin", "north")).documents.answer_mode == "rlm"


async def test_primary_journal_rechecks_only_its_dirty_workspace(knowledge):
    service, queue, request, checker, fence, runner = await prepared(knowledge)
    fence.snapshot.side_effect = [
        ModeReadinessSnapshot(1, 2),
        ModeReadinessSnapshot(3, 2),
        ModeReadinessSnapshot(3, 2),
    ]
    fence.changes.side_effect = [[ReadinessChange(3, knowledge.workspace.id)], [], []]
    for _ in range(7):
        row = await advance(service, queue, request, runner)
    assert row.stage == "activate"
    assert checker.page.await_count == 2
    assert checker.page.await_args.kwargs["workspace_id"] == knowledge.workspace.id
    assert checker.page.await_args.kwargs["native_workspace_id"] is None
    assert row.counters["verification_dirty_scopes"] == 1


async def test_new_document_queues_preparation_only_for_its_workspace_and_retains_checkpoint(knowledge):
    from test_mode_activation import setup

    from koinon.organization_knowledge.transitions.verification import ModeVerification

    service, queue, request, _, native, indexes = await setup(knowledge)
    _, _, targets, scanner = discovery(knowledge)
    await tree(knowledge, 1)
    row = await service.records.find_by_id(request.id)
    state = {
        "phase": "primary",
        "watermark": {"primary": 20, "canon": 1},
        "primary_cursor": [0, None],
        "canon_cursor": [1, None],
        "scope": {"generation": 20, "workspace": knowledge.workspace.id, "after": None},
    }
    row.stage, row.cursor = "verify", {"verification": state}
    await service.records.save(row)
    checker = ModeVerification(
        scanner,
        targets,
        SimpleNamespace(check=AsyncMock(return_value={"documents.embedding": {"space_id": "set-one"}})),
        native,
        indexes,
    )
    runner = import_module(
        "koinon.organization_knowledge.transitions.verification_progress"
    ).ModeVerificationProgress(queue, checker, SimpleNamespace(), ModeProgress(queue, targets))
    await runner.step("north", request.id, "worker")
    row = await service.records.find_by_id(request.id)
    assert row.stage == "discovery" and row.status == "queued"
    assert row.cursor["preparation_workspace"] == knowledge.workspace.id
    assert row.cursor["verification"] == state
    assert row.counters["verification_workspace_repreparations"] == 1
    assert (await knowledge.service.get("admin", "north")).documents.answer_mode == "rlm"
    await knowledge.catalog.create("admin", "north", kind="workspace", name="Unrelated workspace")
    assert await queue.claim("worker") == request.id
    await scanner.step("north", request.id, "worker")
    refreshed = await targets.page("north", request.id)
    assert len(refreshed) == 3
    assert {target.workspace_id for target in refreshed} == {knowledge.workspace.id}


async def test_coalesced_change_beyond_watermark_is_verified_in_the_next_round(knowledge):
    service, queue, request, checker, fence, runner = await prepared(knowledge)
    fence.snapshot.side_effect = [
        ModeReadinessSnapshot(1, 2),
        ModeReadinessSnapshot(3, 2),
        ModeReadinessSnapshot(5, 2),
        ModeReadinessSnapshot(5, 2),
    ]
    fence.changes.side_effect = [[ReadinessChange(5, "dirty")], [], [ReadinessChange(5, "dirty")], [], []]
    for _ in range(11):
        row = await advance(service, queue, request, runner)
    assert row.stage == "activate"
    assert row.cursor["verified_generations"] == {"primary": 5, "canon": 2}
    assert row.counters["verification_change_rounds"] == 1
    assert checker.page.await_count == 2
    assert checker.page.await_args.kwargs["workspace_id"] == "dirty"
    assert (await service.get("admin", "north", request.id)).progress_reason == "knowledge_changed"


async def test_cancellation_during_page_cannot_publish_its_checkpoint(knowledge):
    service, queue, request, checker, _, runner = await prepared(knowledge)
    await advance(service, queue, request, runner)

    async def page(*args, **kwargs):
        current = await service.get("admin", "north", request.id)
        await service.cancel("admin", "north", request.id, expected_revision=current.revision)
        return VerificationPage("last", 1, True, {})

    checker.page.side_effect = page
    assert await queue.claim("worker") == request.id
    with pytest.raises(ConflictException) as error:
        await runner.step("north", request.id, "worker")
    assert error.value.code == "KNOWLEDGE_MODE_LEASE_LOST"
    current = await service.get("admin", "north", request.id)
    assert current.status == "cancelled" and current.active_mode == "rlm"
    assert "verified_generations" not in (await service.records.find_by_id(request.id)).cursor


@pytest.mark.parametrize(
    "status,code,action,count",
    [
        ("activating", "MODE_INDEX_RECOVERY_REQUIRED", "reconcile_index", 1),
        ("activating", "MODE_INDEX_RECOVERY_REQUIRED", "reconcile_index", 101),
        ("building", "INDEX_PREPARATION_REVIEW_REQUIRED", "inspect_index_job", 1),
    ],
)
async def test_excluded_workspace_keeps_unresolved_child_out_of_activation(
    knowledge, status, code, action, count
):
    from koinon.assistants.entities import Provider
    from koinon.assistants.repositories import ProviderRepository
    from koinon.knowledge.indexes.entities import KnowledgeIndex

    service, queue, request, checker, fence, runner = await prepared(knowledge)
    _, _, targets, scanner = discovery(knowledge)
    row = await service.records.find_by_id(request.id)
    row.stage = "discovery"
    await service.records.save(row)
    assert await queue.claim("worker") == request.id
    await scanner.step("north", request.id, "worker")
    target = (await targets.page("north", request.id, kind="workspace"))[0]
    target.status = "excluded"
    await targets.save(target)
    await ProviderRepository().save(
        Provider(
            id="child-provider",
            tenant_id="north",
            name="Fixture",
            kind="ollama",
            base_url="http://127.0.0.1:11434/v1",
            model_ids=["embedding"],
        )
    )
    child = await service.jobs.submit(
        "north",
        knowledge.workspace.id,
        "knowledge.index",
        {"parent_mode_transition_id": request.id},
        "unresolved-child",
    )
    await service.indexes.save(
        KnowledgeIndex(
            id="child-index",
            tenant_id="north",
            workspace_id=knowledge.workspace.id,
            native_workspace_id="native-workspace",
            domain="documents",
            native_id="set",
            provider_id="child-provider",
            provider_kind="ollama",
            provider_revision=1,
            model_id="embedding",
            dimensions=768,
            storage_dimensions=768,
            embedding_fingerprint="fingerprint",
            status=status,
            job_id=child.id,
            created_by="admin",
            updated_by="admin",
        )
    )
    for number in range(count - 1):
        await service.indexes.save(
            KnowledgeIndex(
                id=f"a-{number:04}",
                tenant_id="north",
                workspace_id=knowledge.workspace.id,
                native_workspace_id="native-workspace",
                domain="documents",
                native_id=f"set-{number}",
                provider_id="child-provider",
                provider_kind="ollama",
                provider_revision=1,
                model_id="embedding",
                dimensions=768,
                storage_dimensions=768,
                embedding_fingerprint="fingerprint",
                status="retired",
                job_id=child.id,
                created_by="admin",
                updated_by="admin",
            )
        )
    from koinon.organization_knowledge.transitions.generations import ModeGenerationRepository

    generations = ModeGenerationRepository()
    before = await generations.current("north")
    pending = await service.indexes.find_by_id("child-index")
    pending.transition = {"parent_mode_transition_id": request.id}
    await service.indexes.save(pending)
    assert await generations.current("north") > before
    row = await service.records.find_by_id(request.id)
    row.stage, row.cursor = (
        "verify",
        {
            "verification": {
                "phase": "children",
                "watermark": {"primary": 1, "canon": 2},
                "children_after": None,
            }
        },
    )
    await service.records.save(row)
    await runner.step("north", request.id, "worker")
    if count > 100:
        row = await service.records.find_by_id(request.id)
        assert row.stage == "verify" and row.counters["verification_indexes_scanned"] == 100
        assert "verified_generations" not in row.cursor
        assert await queue.claim("worker") == request.id
        await runner.step("north", request.id, "worker")
    current = await service.get("admin", "north", request.id)
    assert current.status == "failed" and current.error_code == code
    assert current.active_mode == "rlm"
    target = await targets.find_by_id(target.id)
    assert target.result["index_id"] == "child-index" and target.result["job_id"] == child.id
    assert target.result["action"] == action
    assert "verified_generations" not in (await service.records.find_by_id(request.id)).cursor
