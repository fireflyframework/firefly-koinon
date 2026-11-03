# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from importlib import import_module
from types import SimpleNamespace

import pytest
from pyfly.kernel import ConflictException
from test_mode_discovery import discovery, tree
from test_organization_knowledge_service import update_input

from koinon.jobs.repository import JobRepository
from koinon.security.authority import primary_authority

pytest_plugins = ("test_organization_knowledge_service",)


async def setup(knowledge):
    await tree(knowledge, 1)
    service, queue, targets, scanner = discovery(knowledge)
    request = await service.request("admin", "north", update_input(), "index-parent")
    await queue.claim("parent-worker")
    await scanner.step("north", request.id, "parent-worker")
    row = await service.records.find_by_id(request.id)
    row.stage, row.status = "prepare_indexes", "queued"
    await service.records.save(row)
    job = await service.jobs.repository.find_by_id(request.job_id)
    job.status, job.worker_id, job.lease_until = "queued", None, None
    await service.jobs.repository.save(job)
    guard = import_module("koinon.organization_knowledge.transitions.index_guard").ModeIndexGuard(
        knowledge.service, service.records, targets, JobRepository()
    )
    index = SimpleNamespace(
        tenant_id="north",
        workspace_id=knowledge.workspace.id,
        native_workspace_id="native-workspace",
        updated_by="admin",
        access_token_id=None,
        domain="documents",
        transition={},
    )
    return service, guard, request, index


async def test_linked_index_accepts_waiting_parent_without_temporal_worker_lease(knowledge):
    _, guard, request, index = await setup(knowledge)
    async with primary_authority(read_only=False):
        await guard.check(request.id, "north", index)
    with pytest.raises(RuntimeError, match="primary"):
        await guard.check(request.id, "north", index)


async def test_cancelled_or_changed_parent_denies_index_publication(knowledge):
    service, guard, request, index = await setup(knowledge)
    current = await service.get("admin", "north", request.id)
    await service.cancel("admin", "north", request.id, expected_revision=current.revision)
    async with primary_authority(read_only=False):
        with pytest.raises(ConflictException):
            await guard.check(request.id, "north", index)


async def test_foreign_workspace_and_actor_cannot_borrow_parent_authority(knowledge):
    _, guard, request, index = await setup(knowledge)
    for changes in (
        {"domain": "structured"},
        {"tenant_id": "south"},
        {"workspace_id": "foreign"},
        {"updated_by": "other"},
        {"access_token_id": "different-token"},
    ):
        async with primary_authority(read_only=False):
            with pytest.raises(ConflictException):
                await guard.check(request.id, "north", SimpleNamespace(**(vars(index) | changes)))


async def test_borrowed_activation_binds_current_parent_actor_and_token(knowledge):
    _, guard, request, index = await setup(knowledge)
    index.updated_by, index.access_token_id = "historical-builder", "historical-token"
    index.transition = {
        "parent_mode_transition_id": request.id,
        "activation_actor": "admin",
        "activation_token_id": None,
    }
    async with primary_authority(read_only=False):
        await guard.check(request.id, "north", index)
    index.transition = {**index.transition, "activation_token_id": "other-token"}
    async with primary_authority(read_only=False):
        with pytest.raises(ConflictException):
            await guard.check(request.id, "north", index)
