# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from types import SimpleNamespace
from unittest.mock import AsyncMock

from pyfly.data.transaction import current_unit_of_work
from test_mode_discovery import discovery, tree
from test_organization_knowledge_service import update_input

from koinon.organization_knowledge.transitions.verification import ModeVerification

pytest_plugins = ("test_organization_knowledge_service",)


async def test_verification_checks_one_page_and_releases_primary_before_native_reads(knowledge):
    entries = await tree(knowledge, 5)
    service, queue, targets, scanner = discovery(knowledge)
    request = await service.request("admin", "north", update_input(), "verify-pages")
    await queue.claim("worker")
    await scanner.step("north", request.id, "worker")
    roles = {"documents.embedding": {"space_id": "set-one"}}
    for target in await targets.page("north", request.id):
        target.status = "ready"
        if target.kind == "workspace":
            target.result = {"roles": roles, "has_documents": True, "index_id": "index-one"}
        await targets.save(target)
    seen = []

    async def sources(**arguments):
        assert current_unit_of_work("primary") is None
        assert len(arguments["source_ids"]) <= 2
        seen.extend(arguments["source_ids"])

    async def index(**arguments):
        assert current_unit_of_work("primary") is None
        return {"active": True, "indexed": True, "chunk_count": 5, "vector_count": 5, "space_id": "set-one"}

    checker = ModeVerification(
        scanner,
        targets,
        SimpleNamespace(check=AsyncMock(return_value=roles)),
        SimpleNamespace(verify_sources=sources, verify_pins=AsyncMock()),
        SimpleNamespace(get_native=index),
    )
    row = await service.records.find_by_id(request.id)
    first = await checker.page(row, page_size=2)
    assert first.scanned == 2 and not first.complete
    assert len(seen) < 5
    after = first.after
    total = first.scanned
    while not first.complete:
        first = await checker.page(row, after=after, page_size=2)
        total += first.scanned
        after = first.after
    assert total == len(entries)
    assert len(seen) == len(set(seen)) == 5


async def test_discovery_dirty_workspace_selectors_never_broaden_on_missing_scope(knowledge):
    entries = await tree(knowledge, 2)
    service, queue, _, scanner = discovery(knowledge)
    request = await service.request("admin", "north", update_input(), "dirty-scopes")
    await queue.claim("worker")
    row = await service.records.find_by_id(request.id)
    found, _ = await scanner.page(row, workspace_id=knowledge.workspace.id)
    assert {entry.id for entry in found} == {entry.id for entry in entries}
    assert await scanner.page(row, workspace_id="unavailable") == ([], [])
    assert await scanner.page(row, native_workspace_id="unavailable") == ([], [])
    found, _ = await scanner.page(row, native_workspace_id="native-workspace")
    assert {entry.id for entry in found} == {entry.id for entry in entries}
