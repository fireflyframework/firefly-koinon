# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import pytest
from pyfly.kernel import ConflictException, InvalidRequestException
from test_mode_discovery import discovery, tree
from test_organization_knowledge_service import update_input

from koinon.assistants.entities import Provider
from koinon.assistants.repositories import ProviderRepository
from koinon.knowledge.indexes.entities import KnowledgeIndex
from koinon.knowledge.indexes.repositories import KnowledgeIndexRepository
from koinon.security.authority import primary_authority

pytest_plugins = ("test_organization_knowledge_service",)


async def test_cancelled_mode_keeps_exact_index_recovery_until_reconciled(knowledge):
    await tree(knowledge, 1)
    service, queue, targets, scanner = discovery(knowledge)
    request = await service.request("admin", "north", update_input(), "recover-index")
    await queue.claim("worker")
    await scanner.step("north", request.id, "worker")
    await ProviderRepository().save(
        Provider(
            id="provider",
            tenant_id="north",
            name="Fixture",
            kind="ollama",
            base_url="http://127.0.0.1:11434/v1",
            model_ids=["embedding"],
        )
    )
    job = await service.jobs.submit(
        "north",
        knowledge.workspace.id,
        "knowledge.index",
        {
            "parent_mode_transition_id": request.id,
        },
        "recovery-child",
    )
    job.status = "succeeded"
    await service.jobs.repository.save(job)
    index = await KnowledgeIndexRepository().save(
        KnowledgeIndex(
            id="index",
            tenant_id="north",
            workspace_id=knowledge.workspace.id,
            native_workspace_id="native-workspace",
            domain="documents",
            native_id="set",
            provider_id="provider",
            provider_kind="ollama",
            provider_revision=1,
            model_id="embedding",
            dimensions=768,
            storage_dimensions=768,
            embedding_fingerprint="fingerprint",
            status="activating",
            job_id=job.id,
            created_by="admin",
            updated_by="admin",
            transition={"previous_native_id": "previous", "request": {}},
        )
    )
    async with primary_authority(read_only=False):
        attempt = await service.attempts.capture("north", request.id, index)
        index.transition = {
            **index.transition,
            "mode_activation_attempt_id": attempt,
            "mode_activation_attempt_revision": index.revision,
        }
        await KnowledgeIndexRepository().save(index)
    current = await service.get("admin", "north", request.id)
    cancelled = await service.cancel("admin", "north", request.id, expected_revision=current.revision)
    assert cancelled.status == "cancelled" and cancelled.pending_index_recoveries == 1
    page = await service.recovery_page("admin", "north", request.id)
    receipt = page.items[0]
    assert receipt.index_id == index.id
    assert receipt.state == "required"
    assert receipt.actions == []
    assert receipt.native_pointer_state == "unavailable"
    assert (await KnowledgeIndexRepository().find_by_id(index.id)).status == "activating"
    assert (await knowledge.service.get("admin", "north")).documents.answer_mode == "rlm"
    with pytest.raises(ConflictException) as error:
        await service.request("admin", "north", update_input(), "next-before-recovery")
    assert error.value.code == "MODE_INDEX_RECOVERY_REQUIRED"
    async with primary_authority(read_only=False):
        index.status = "active"
        index.revision += 1
        await KnowledgeIndexRepository().save(index)
        await service.attempts.resolve("north", request.id, attempt, index, "finished", expected_revision=1)
    assert (await service.get("admin", "north", request.id)).pending_index_recoveries == 0
    receipt = (await service.recovery_page("admin", "north", request.id)).items[0]
    assert receipt.state == "resolved" and receipt.actions == []
    assert (await service.get("admin", "north", request.id)).status == "cancelled"


async def test_recovery_pages_preserve_historical_bindings_and_current_authority(knowledge):
    from koinon.catalog.errors import AccessDenied
    from koinon.knowledge.repositories import DomainBindingRepository

    await tree(knowledge, 1)
    service, queue, targets, scanner = discovery(knowledge)
    request = await service.request("admin", "north", update_input(), "recovery-pages")
    await queue.claim("worker")
    await scanner.step("north", request.id, "worker")
    await ProviderRepository().save(
        Provider(
            id="provider",
            tenant_id="north",
            name="Fixture",
            kind="ollama",
            base_url="http://127.0.0.1:11434/v1",
            model_ids=["embedding"],
        )
    )
    for number in range(103):
        index = await KnowledgeIndexRepository().save(
            KnowledgeIndex(
                id=f"index-{number:03}",
                tenant_id="north",
                workspace_id=knowledge.workspace.id,
                native_workspace_id=f"historical-workspace-{number}",
                domain="documents",
                native_id=f"set-{number}",
                provider_id="provider",
                provider_kind="ollama",
                provider_revision=1,
                model_id="embedding",
                dimensions=768,
                storage_dimensions=768,
                embedding_fingerprint="fingerprint",
                status="activating",
                created_by="admin",
                updated_by="admin",
                transition={
                    "parent_mode_transition_id": request.id,
                    "previous_native_id": "previous",
                    "request": {},
                },
            )
        )
        async with primary_authority(read_only=False):
            attempt = await service.attempts.capture("north", request.id, index)
            index.transition = {
                **index.transition,
                "mode_activation_attempt_id": attempt,
                "mode_activation_attempt_revision": index.revision,
            }
            await KnowledgeIndexRepository().save(index)
    current = await service.get("admin", "north", request.id)
    await service.cancel("admin", "north", request.id, expected_revision=current.revision)
    binding = (await DomainBindingRepository().find_all(catalog_id=knowledge.workspace.id, domain="canon"))[0]
    binding.native_workspace_id = binding.native_id = "replacement-workspace"
    await DomainBindingRepository().save(binding)
    first = await service.recovery_page("admin", "north", request.id, limit=100)
    second = await service.recovery_page("admin", "north", request.id, after=first.next_cursor, limit=100)
    assert len(first.items) == 100 and len(second.items) == 3 and second.next_cursor is None
    assert {item.index_id for item in first.items + second.items} == {f"index-{n:03}" for n in range(103)}
    assert {item.native_workspace_id for item in first.items + second.items} == {
        f"historical-workspace-{n}" for n in range(103)
    }
    from types import SimpleNamespace
    from unittest.mock import AsyncMock

    inspector = SimpleNamespace(
        inspect=AsyncMock(side_effect=ConflictException("Changed", code="INDEX_WORKSPACE_CHANGED"))
    )
    service.recovery = SimpleNamespace(get=lambda: inspector)
    changed = await service.recovery_page("admin", "north", request.id, limit=1)
    assert changed.items[0].actions == [] and "previous workspace binding" in changed.items[0].message
    inspector.inspect.reset_mock()
    knowledge.workspace.status = "archived"
    await knowledge.catalog.catalog_repository.save(knowledge.workspace)
    archived = await service.recovery_page("admin", "north", request.id, limit=1)
    assert archived.items[0].actions == []
    assert "archived" in archived.items[0].message
    inspector.inspect.assert_not_awaited()
    for actor, tenant, parent in (
        ("viewer", "north", request.id),
        ("admin", "south", request.id),
        ("admin", "north", "other-parent"),
    ):
        with pytest.raises(AccessDenied):
            await service.recovery_page(actor, tenant, parent)
    with pytest.raises(InvalidRequestException):
        await service.recovery_page("admin", "north", request.id, limit=101)
    from koinon.catalog.repositories import MembershipRepository

    member = await MembershipRepository().find_by_id("admin")
    member.active = False
    await MembershipRepository().save(member)
    with pytest.raises(AccessDenied):
        await service.recovery_page("admin", "north", request.id)
    inspector.inspect.assert_not_awaited()


async def test_cancel_never_enumerates_or_bulk_updates_child_work(knowledge, monkeypatch):
    from unittest.mock import AsyncMock

    from test_mode_transitions import transitions

    service = transitions(knowledge)
    request = await service.request("admin", "north", update_input(), "bounded-cancel")
    monkeypatch.setattr(service.indexes, "mode_children", AsyncMock(side_effect=AssertionError("child scan")))
    monkeypatch.setattr(
        service.jobs.repository, "cancel_mode_children", AsyncMock(side_effect=AssertionError("bulk cancel"))
    )
    cancelled = await service.cancel("admin", "north", request.id, expected_revision=request.revision)
    assert cancelled.status == "cancelled"
