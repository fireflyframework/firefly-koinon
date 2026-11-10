# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from contextlib import asynccontextmanager
from importlib import import_module
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from flycanon.models.repositories.readiness_generation_repository import ReadinessGenerationChangedError
from pyfly.data.transaction import current_unit_of_work
from pyfly.kernel import ConflictException
from test_mode_discovery import discovery, tree
from test_organization_knowledge_service import update_input

from koinon.organization_knowledge.transitions.generations import ModeGenerationRepository
from koinon.organization_knowledge.transitions.readiness_fence import ModeReadinessFence

pytest_plugins = ("test_organization_knowledge_service",)


async def setup(knowledge, *, verified=True):
    await tree(knowledge, 1)
    service, queue, targets, scanner = discovery(knowledge)
    request = await service.request("admin", "north", update_input(), "activate")
    await queue.claim("worker")
    await scanner.step("north", request.id, "worker")
    roles = {"documents.embedding": {"space_id": "set-one"}}
    for target in await targets.page("north", request.id):
        if target.kind == "workspace":
            target.status = "ready"
            target.result = {"roles": roles, "has_documents": True, "index_id": "index-one"}
            await targets.save(target)
    row = await service.records.find_by_id(request.id)
    row.stage = "activate"
    await service.records.save(row)
    native = SimpleNamespace(verify_sources=AsyncMock(), verify_pins=AsyncMock())
    indexes = SimpleNamespace(
        generation=1,
        get_native=AsyncMock(
            return_value={
                "active": True,
                "indexed": True,
                "chunk_count": 4,
                "vector_count": 4,
                "space_id": "set-one",
            }
        ),
    )
    checker = import_module("koinon.organization_knowledge.transitions.verification").ModeVerification(
        scanner, targets, SimpleNamespace(check=AsyncMock(return_value=roles)), native, indexes
    )
    fence = ModeReadinessFence(ModeGenerationRepository(), None)

    @asynccontextmanager
    async def native_hold(tenant_id, expected):
        if expected.tenant_generation != indexes.generation:
            raise ReadinessGenerationChangedError("Controlled native mutation")
        assert current_unit_of_work("primary") is not None
        yield
        assert current_unit_of_work("primary") is None

    fence.native = lambda: SimpleNamespace(hold=native_hold)
    if verified:
        page = await checker.page(row)
        assert page.complete
        snapshot = {"primary": await fence.primary.current("north"), "canon": indexes.generation}
        row.cursor = {
            "verified_generations": snapshot,
            "verification": {"phase": "settle", "watermark": snapshot},
        }
        row.counters = page.counts
        await service.records.save(row)
    activation = import_module("koinon.organization_knowledge.transitions.activation").ModeActivation(
        queue, fence
    )
    return service, queue, request, activation, native, indexes


async def test_activation_changes_settings_only_after_current_metadata_verification(knowledge):
    service, _, request, activation, native, indexes = await setup(knowledge)
    await activation.activate("north", request.id, "worker")
    assert (await knowledge.service.get("admin", "north")).documents.answer_mode == "rag"
    current = await service.get("admin", "north", request.id)
    assert current.status == "succeeded"
    assert current.active_mode == "rag"
    assert (await service.jobs.repository.find_by_id(request.job_id)).status == "succeeded"
    native.verify_sources.assert_awaited_once()
    indexes.get_native.assert_awaited_once()
    with pytest.raises(ConflictException):
        await activation.activate("north", request.id, "worker")
    assert (await knowledge.service.get("admin", "north")).revision == 1


async def test_newly_added_document_cannot_be_silently_omitted_at_activation(knowledge):
    _, _, request, activation, _, _ = await setup(knowledge)
    await tree(knowledge, 1)
    with pytest.raises(ConflictException) as error:
        await activation.activate("north", request.id, "worker")
    assert error.value.code == "KNOWLEDGE_MODE_GENERATION_CHANGED"
    assert (await knowledge.service.get("admin", "north")).documents.answer_mode == "rlm"


async def test_changed_index_coverage_and_newer_settings_prevent_activation(knowledge):
    _, _, request, activation, _, indexes = await setup(knowledge)
    indexes.get_native.return_value["vector_count"] = 3
    indexes.generation += 1
    with pytest.raises(ConflictException) as error:
        await activation.activate("north", request.id, "worker")
    assert error.value.code == "KNOWLEDGE_MODE_GENERATION_CHANGED"
    values = update_input()
    values = values.model_copy(
        update={"documents": values.documents.model_copy(update={"answer_mode": "rlm", "answer_top_k": 12})}
    )
    await knowledge.service.update("admin", "north", values)
    indexes.get_native.return_value["vector_count"] = 4
    with pytest.raises(ConflictException) as error:
        await activation.activate("north", request.id, "worker")
    assert error.value.code == "KNOWLEDGE_MODE_SUPERSEDED"
    assert (await knowledge.service.get("admin", "north")).documents.answer_top_k == 12


async def test_activation_requires_a_durable_completed_verification_checkpoint(knowledge):
    _, _, request, activation, _, _ = await setup(knowledge, verified=False)
    with pytest.raises(ConflictException) as error:
        await activation.activate("north", request.id, "worker")
    assert error.value.code == "KNOWLEDGE_MODE_VERIFICATION_REQUIRED"
    assert (await knowledge.service.get("admin", "north")).documents.answer_mode == "rlm"
