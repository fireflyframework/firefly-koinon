# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from importlib import import_module
from types import SimpleNamespace
from unittest.mock import AsyncMock

from pyfly.kernel import ServiceUnavailableException
from test_mode_discovery import discovery, tree
from test_organization_knowledge_service import update_input

pytest_plugins = ("test_organization_knowledge_service",)


async def setup(knowledge, roles):
    await tree(knowledge, 1)
    service, queue, targets, scanner = discovery(knowledge)
    request = await service.request("admin", "north", update_input(), "preflight")
    await queue.claim("worker")
    await scanner.step("north", request.id, "worker")
    progress = import_module("koinon.organization_knowledge.transitions.progress").ModeProgress(
        queue, targets
    )
    authority = import_module("koinon.organization_knowledge.transitions.authority").ModeTargetAuthority(
        queue, scanner.knowledge, targets
    )
    checker = import_module("koinon.organization_knowledge.transitions.preflight").ModePreflight(
        queue, targets, authority, roles, progress
    )
    return service, queue, targets, request, checker


async def test_provider_failure_leaves_active_mode_and_exact_workspace_action(knowledge):
    roles = SimpleNamespace(
        check=AsyncMock(
            side_effect=ServiceUnavailableException(
                "provider disabled", code="KNOWLEDGE_PROVIDER_UNAVAILABLE"
            )
        )
    )
    service, _, targets, request, checker = await setup(knowledge, roles)
    await checker.step("north", request.id, "worker")
    failed = await service.get("admin", "north", request.id)
    assert failed.status == "failed"
    assert failed.error_code == "KNOWLEDGE_PROVIDER_UNAVAILABLE"
    workspace = (await targets.page("north", request.id, kind="workspace"))[0]
    assert workspace.result["action"] == "configure_models"
    assert (await knowledge.service.get("admin", "north")).documents.answer_mode == "rlm"


async def test_workspace_preflight_persists_current_role_pins_before_preparation(knowledge):
    roles = SimpleNamespace(check=AsyncMock(return_value={"documents.answer": {"provider_revision": 3}}))
    service, queue, targets, request, checker = await setup(knowledge, roles)
    await checker.step("north", request.id, "worker")
    workspace = (await targets.page("north", request.id, kind="workspace"))[0]
    assert workspace.result["roles"]["documents.answer"]["provider_revision"] == 3
    roles.check.assert_awaited_once_with("admin", "north", knowledge.workspace.id, "rag", has_documents=True)
    await queue.claim("worker")
    await checker.step("north", request.id, "worker")
    assert (await service.get("admin", "north", request.id)).stage == "prepare_indexes"
