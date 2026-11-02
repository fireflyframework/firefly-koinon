# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Concurrent scoped navigation must not hold the whole pool while authorizing."""

import asyncio

import pytest
from pyfly.data.relational.datasource_registry import DataSourceRegistry
from test_memory_authority_postgres import pg_assistants as pg_assistants
from test_service import configured

from koinon.assistants.history.service import ChatHistoryService
from koinon.assistants.scope import KnowledgeScopePolicy
from koinon.catalog.errors import AccessDenied
from koinon.catalog.repositories import MembershipRepository

pytestmark = pytest.mark.integration


@pytest.mark.parametrize(
    "pg_assistants",
    [{"pool": {"size": size, "max-overflow": 0, "timeout": 0.5}} for size in (1, 5)],
    indirect=True,
)
async def test_scoped_navigation_shares_authority_connection_and_observes_revocation(
    pg_assistants, monkeypatch
):
    assistant, context, _ = pg_assistants
    await configured(assistant)
    history = context.get_bean(ChatHistoryService)
    workspace = await assistant.catalog.create(
        "issuer|admin", "north", kind="workspace", name="Scoped navigation"
    )
    project = await assistant.catalog.create(
        "issuer|admin", "north", kind="project", name="Evidence", parent_id=workspace.id
    )
    scope = {"workspace_id": workspace.id, "project_id": project.id}
    folder = await history.create_folder("issuer|admin", "north", {"name": "Private chats", "scope": scope})
    thread = await history.create_thread(
        "issuer|admin", "north", {"title": "Scoped chat", "scope": scope, "folder_id": folder["id"]}
    )
    policy = context.get_bean(KnowledgeScopePolicy)
    validate = policy.validate_scope
    pool = context.get_bean(DataSourceRegistry).primary.engine.pool
    assert pool.size() in {1, 5}
    barrier = asyncio.Barrier(pool.size())
    entered = set()

    async def synchronized_validation(*args, **kwargs):
        task = asyncio.current_task()
        if task not in entered:
            entered.add(task)
            await asyncio.wait_for(barrier.wait(), timeout=5)
        return await validate(*args, **kwargs)

    monkeypatch.setattr(policy, "validate_scope", synchronized_validation)
    async with asyncio.timeout(15):
        results = await asyncio.gather(
            assistant.configuration_service.agent_page("issuer|admin", "north", **scope),
            history.folder_page("issuer|admin", "north", workspace_id=workspace.id),
            history.thread_page("issuer|admin", "north", **scope),
            history.get_folder("issuer|admin", "north", folder["id"]),
            history.get_thread("issuer|admin", "north", thread["id"]),
            return_exceptions=True,
        )
    assert not [result for result in results if isinstance(result, BaseException)], results
    assert [result["total"] for result in results[:3]] == [1, 1, 1]
    assert results[3]["id"] == folder["id"] and results[4]["id"] == thread["id"]
    assert pool.checkedout() == 0

    monkeypatch.setattr(policy, "validate_scope", validate)
    memberships = context.get_bean(MembershipRepository)
    member = await memberships.find_by_id("admin")
    member.active = False
    await memberships.save(member)
    for read in (
        lambda: assistant.configuration_service.agent_page("issuer|admin", "north", **scope),
        lambda: history.folder_page("issuer|admin", "north", workspace_id=workspace.id),
        lambda: history.thread_page("issuer|admin", "north", **scope),
        lambda: history.get_folder("issuer|admin", "north", folder["id"]),
        lambda: history.get_thread("issuer|admin", "north", thread["id"]),
    ):
        with pytest.raises(AccessDenied):
            await read()
    assert pool.checkedout() == 0
