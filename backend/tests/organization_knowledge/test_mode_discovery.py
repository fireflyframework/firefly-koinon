# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from importlib import import_module
from uuid import uuid4

import pytest
from test_mode_transitions import transitions
from test_organization_knowledge_service import update_input

from koinon.catalog.errors import AccessDenied
from koinon.knowledge.entities import DomainBinding
from koinon.knowledge.repositories import DomainBindingRepository
from koinon.knowledge.service import KnowledgeFacade, KnowledgeSettings

pytest_plugins = ("test_organization_knowledge_service",)


async def tree(knowledge, count=3):
    catalog = knowledge.catalog
    project = await catalog.create(
        "admin", "north", kind="project", name="Project", parent_id=knowledge.workspace.id
    )
    collection = await catalog.create(
        "admin", "north", kind="collection", name="Documents", parent_id=project.id
    )
    entries = [knowledge.workspace]
    for index in range(count):
        source = await catalog.create(
            "admin", "north", kind="source", name=f"Source {index}", parent_id=collection.id
        )
        entries.append(
            await catalog.create(
                "admin", "north", kind="document", name=f"Document {index}", parent_id=source.id
            )
        )
    for entry in entries:
        if await DomainBindingRepository().find_all(tenant_id="north", catalog_id=entry.id, domain="canon"):
            continue
        await DomainBindingRepository().save(
            DomainBinding(
                id=str(uuid4()),
                tenant_id="north",
                catalog_id=entry.id,
                workspace_id=knowledge.workspace.id,
                domain="canon",
                entity_kind=entry.kind,
                native_id="native-workspace" if entry.kind == "workspace" else "native-" + entry.id,
                native_workspace_id="native-workspace",
                created_by="admin",
            )
        )
    return entries


def discovery(knowledge):
    service = transitions(knowledge)
    queue = import_module("koinon.organization_knowledge.transitions.queue").ModeTransitionQueue(service)
    targets = import_module("koinon.organization_knowledge.transitions.repositories").ModeTargetRepository()
    facade = KnowledgeFacade(knowledge.catalog, DomainBindingRepository(), None, KnowledgeSettings())
    instance = import_module("koinon.organization_knowledge.transitions.discovery").ModeDiscovery(
        facade, targets, queue
    )
    return service, queue, targets, instance


async def test_discovery_pages_exact_canonical_bindings_and_can_resume(knowledge):
    entries = await tree(knowledge)
    service, queue, targets, scanner = discovery(knowledge)
    request = await service.request("admin", "north", update_input(), "discovery")
    await queue.claim("scanner")
    assert await scanner.step("north", request.id, "scanner", page_size=2) is False
    assert await scanner.step("north", request.id, "scanner", page_size=2) is False
    assert await scanner.step("north", request.id, "scanner", page_size=2) is True
    rows = await targets.page("north", request.id)
    assert {row.catalog_id for row in rows} == {entry.id for entry in entries}
    assert all(row.native_workspace_id == "native-workspace" for row in rows)
    assert len(rows) == 4
    assert (await knowledge.service.get("admin", "north")).documents.answer_mode == "rlm"


async def test_rediscovery_updates_changed_native_binding_without_reusing_old_source_receipt(knowledge):
    await tree(knowledge, 1)
    service, queue, targets, scanner = discovery(knowledge)
    request = await service.request("admin", "north", update_input(), "changed-binding")
    await queue.claim("worker")
    await scanner.step("north", request.id, "worker")
    rows = await targets.page("north", request.id)
    for target in rows:
        target.status = "ready"
        target.result = {"original_receipt": target.id}
        await targets.save(target)
    document = next(target for target in rows if target.kind == "document")
    binding = (await DomainBindingRepository().find_all(catalog_id=document.catalog_id, domain="canon"))[0]
    binding.native_id = "replacement-native-source"
    await DomainBindingRepository().save(binding)
    row = await service.records.find_by_id(request.id)
    row.stage, row.cursor, row.counters = (
        "discovery",
        {"preparation_workspace": knowledge.workspace.id},
        {"queued": 0, "ready": 2},
    )
    await service.records.save(row)
    await scanner.step("north", request.id, "worker")
    refreshed = await targets.find_by_id(document.id)
    assert refreshed.native_id == "replacement-native-source"
    assert refreshed.status == "queued" and refreshed.result == {}
    workspace = next(
        target for target in await targets.page("north", request.id) if target.kind == "workspace"
    )
    assert workspace.status == "ready" and workspace.result == {"original_receipt": workspace.id}
    counts = (await service.records.find_by_id(request.id)).counters
    assert counts["queued"] == 1 and counts["ready"] == 1


async def test_scoped_rediscovery_excludes_archived_descendants_in_bounded_pages_and_restores_them(knowledge):
    entries = await tree(knowledge, 3)
    service, queue, targets, scanner = discovery(knowledge)
    request = await service.request("admin", "north", update_input(), "retired-targets")
    await queue.claim("worker")
    await scanner.step("north", request.id, "worker")
    for target in await targets.page("north", request.id):
        target.status, target.result = "ready", {"retained_receipt": target.id}
        await targets.save(target)
    await knowledge.catalog.archive("admin", "north", entries[1].project_id)
    row = await service.records.find_by_id(request.id)
    row.stage, row.cursor, row.counters = (
        "discovery",
        {"preparation_workspace": knowledge.workspace.id},
        {"ready": 4, "queued": 0},
    )
    await service.records.save(row)
    while not await scanner.step("north", request.id, "worker", page_size=2):
        pass
    documents = await targets.page("north", request.id, kind="document")
    assert len(documents) == 3 and all(target.status == "excluded" for target in documents)
    assert all(target.result["retained_receipt"] == target.id for target in documents)
    row = await service.records.find_by_id(request.id)
    assert row.stage == "preflight" and row.counters["excluded"] == 3 and row.counters["ready"] == 1
    await knowledge.catalog.restore("admin", "north", entries[1].project_id)
    row.stage, row.cursor = "discovery", {"preparation_workspace": knowledge.workspace.id}
    await service.records.save(row)
    while not await scanner.step("north", request.id, "worker", page_size=2):
        pass
    assert all(
        target.status == "queued" for target in await targets.page("north", request.id, kind="document")
    )
    row = await service.records.find_by_id(request.id)
    assert row.counters["excluded"] == 0 and row.counters["queued"] == 3


async def test_discovery_refuses_foreign_native_workspace_binding(knowledge):
    entries = await tree(knowledge, 1)
    binding = (await DomainBindingRepository().find_all(catalog_id=entries[-1].id))[0]
    binding.native_workspace_id = "other-native-workspace"
    await DomainBindingRepository().save(binding)
    service, queue, _, scanner = discovery(knowledge)
    request = await service.request("admin", "north", update_input(), "foreign-binding")
    await queue.claim("scanner")
    with pytest.raises(AccessDenied) as error:
        await scanner.step("north", request.id, "scanner")
    assert error.value.code == "BINDING_SCOPE_MISMATCH"
