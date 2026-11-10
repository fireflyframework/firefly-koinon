# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from importlib import import_module

import pytest
from pyfly.kernel import ConflictException
from test_mode_discovery import discovery, tree
from test_organization_knowledge_service import update_input

from koinon.catalog.errors import AccessDenied
from koinon.knowledge.repositories import DomainBindingRepository
from koinon.security.authority import primary_authority

pytest_plugins = ("test_organization_knowledge_service",)


async def preparing(knowledge):
    entries = await tree(knowledge, 1)
    service, queue, targets, scanner = discovery(knowledge)
    request = await service.request("admin", "north", update_input(), "authority")
    await queue.claim("worker")
    await scanner.step("north", request.id, "worker")
    target = next(row for row in await targets.page("north", request.id) if row.kind == "document")
    authority = import_module("koinon.organization_knowledge.transitions.authority").ModeTargetAuthority(
        queue, scanner.knowledge, targets
    )
    return service, authority, request, target, entries


async def test_target_authority_rechecks_binding_and_exact_transition(knowledge):
    _, authority, request, target, _ = await preparing(knowledge)
    checked = await authority.check("north", request.id, "worker", target.id)
    assert checked.native_id == target.native_id
    with pytest.raises(AccessDenied):
        await authority.check("south", request.id, "worker", target.id)
    binding = (await DomainBindingRepository().find_all(catalog_id=target.catalog_id))[0]
    binding.native_id = "replacement-source"
    await DomainBindingRepository().save(binding)
    with pytest.raises(ConflictException) as error:
        await authority.check("north", request.id, "worker", target.id)
    assert error.value.code == "KNOWLEDGE_MODE_SOURCE_CHANGED"


async def test_cancelled_worker_cannot_enter_publication_guard(knowledge):
    service, authority, request, target, _ = await preparing(knowledge)
    current = await service.get("admin", "north", request.id)
    await service.cancel("admin", "north", request.id, expected_revision=current.revision)
    with pytest.raises(ConflictException):
        async with authority.publication("north", request.id, "worker", target.id):
            pytest.fail("Cancelled preparation entered publication")


async def test_publication_refuses_ambient_primary_unit(knowledge):
    _, authority, request, target, _ = await preparing(knowledge)
    async with primary_authority():
        with pytest.raises(RuntimeError, match="outside"):
            async with authority.publication("north", request.id, "worker", target.id):
                pytest.fail("Publication reused an ambient read snapshot")


async def test_archive_and_authority_revocation_are_checked_again(knowledge):
    _, authority, request, target, entries = await preparing(knowledge)
    await knowledge.catalog.archive("admin", "north", entries[-1].id)
    with pytest.raises(AccessDenied):
        await authority.check("north", request.id, "worker", target.id)


async def test_revoked_submitter_is_denied_before_native_publication(knowledge):
    _, authority, request, target, _ = await preparing(knowledge)
    membership = await knowledge.catalog.membership_repository.find_by_id("admin")
    membership.role = "viewer"
    await knowledge.catalog.membership_repository.save(membership)
    with pytest.raises(AccessDenied):
        async with authority.publication("north", request.id, "worker", target.id):
            pytest.fail("Revoked submitter reached native publication")
