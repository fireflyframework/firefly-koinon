# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from importlib import import_module
from types import SimpleNamespace
from unittest.mock import AsyncMock

from pyfly.data.transaction import current_unit_of_work
from pyfly.kernel import ServiceUnavailableException
from test_mode_discovery import discovery, tree
from test_organization_knowledge_service import update_input

pytest_plugins = ("test_organization_knowledge_service",)


async def setup(knowledge, views):
    knowledge.documents.answer_mode = "rag"
    await tree(knowledge, 1)
    service, queue, targets, scanner = discovery(knowledge)
    values = update_input()
    values = values.model_copy(
        update={"documents": values.documents.model_copy(update={"answer_mode": "rlm"})}
    )
    request = await service.request("admin", "north", values, "view-preparation")
    await queue.claim("worker")
    await scanner.step("north", request.id, "worker")
    row = await service.records.find_by_id(request.id)
    row.stage = "repair_views"
    await service.records.save(row)
    progress = import_module("koinon.organization_knowledge.transitions.progress").ModeProgress(
        queue, targets
    )
    authority = import_module("koinon.organization_knowledge.transitions.authority").ModeTargetAuthority(
        queue, scanner.knowledge, targets
    )
    preparation = import_module(
        "koinon.organization_knowledge.transitions.view_preparation"
    ).ModeViewPreparation(queue, targets, authority, views, progress)
    return service, queue, targets, request, preparation


async def test_native_view_stage_has_no_primary_transaction_and_records_exact_receipt(knowledge):
    async def prepare(**kwargs):
        assert current_unit_of_work("primary") is None
        assert kwargs["tenant_id"] == "north"
        assert kwargs["workspace_id"] == "native-workspace"
        await kwargs["authorize"]()
        async with kwargs["publication_guard"]():
            unit = current_unit_of_work("primary")
            assert unit is not None and not unit.read_only
        return {"source_version_id": "version-one", "view_extraction_id": "view-one", "parts": 1}

    views = SimpleNamespace(prepare=AsyncMock(side_effect=prepare))
    service, queue, targets, request, preparation = await setup(knowledge, views)
    await preparation.step("north", request.id, "worker")
    target = (await targets.page("north", request.id, kind="document"))[0]
    assert target.status == "ready" and target.result["source_version_id"] == "version-one"
    assert (await service.get("admin", "north", request.id)).active_mode == "rag"
    await queue.claim("worker")
    await preparation.step("north", request.id, "worker")
    assert (await service.get("admin", "north", request.id)).stage == "verify"


async def test_missing_version_is_saved_as_source_prerequisite_without_activation(knowledge):
    views = SimpleNamespace(
        prepare=AsyncMock(
            side_effect=ServiceUnavailableException("legacy", code="SOURCE_VERSION_PREPARATION_REQUIRED")
        )
    )
    service, _, targets, request, preparation = await setup(knowledge, views)
    await preparation.step("north", request.id, "worker")
    target = (await targets.page("north", request.id, kind="document"))[0]
    assert target.result["action"] == "reprocess_document"
    assert (await service.get("admin", "north", request.id)).status == "failed"
    assert (await knowledge.service.get("admin", "north")).documents.answer_mode == "rag"
