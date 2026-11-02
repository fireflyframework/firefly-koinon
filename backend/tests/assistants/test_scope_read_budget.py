# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""A folder scope must not multiply policy SQL for every repeated ancestor."""

import pytest
from pyfly.data.relational.datasource_registry import DataSourceRegistry
from pyfly.data.transaction import TransactionTemplate
from sqlalchemy import event
from test_service import assistants as assistants

from koinon.catalog.errors import AccessDenied
from koinon.security.authority import primary_authority


async def scoped_tree(service):
    parent = None
    entries = []
    for kind in ("workspace", "project", "collection", "source", "dataset"):
        entry = await service.catalog.create("issuer|admin", "north", kind=kind, name=kind, parent_id=parent)
        entries.append(entry)
        parent = entry.id
    return {
        "workspace_id": entries[0].id,
        "project_id": entries[1].id,
        "collection_id": entries[2].id,
        "asset_ids": [entries[4].id],
    }


async def test_scope_uses_bounded_sql_and_rechecks_membership_next_time(assistants):
    service, context = assistants
    scope = await scoped_tree(service)
    engine = context.get_bean(DataSourceRegistry).primary.engine.sync_engine
    statements = []

    def capture(connection, cursor, statement, parameters, execution, many):
        statements.append(statement)

    event.listen(engine, "before_cursor_execute", capture)
    try:
        assert await service.validate_scope("issuer|viewer", "north", scope) == scope
    finally:
        event.remove(engine, "before_cursor_execute", capture)
    assert len(statements) <= 20, f"Scope issued {len(statements)} SQL statements for five entries"
    member = await service.catalog.membership_repository.find_by_id("viewer")
    member.active = False
    await service.catalog.membership_repository.save(member)
    with pytest.raises(AccessDenied):
        await service.validate_scope("issuer|viewer", "north", scope)


@pytest.mark.parametrize("subject,tenant", [("issuer|outsider", "north"), ("issuer|viewer", "south")])
async def test_policy_reads_do_not_reuse_another_subject_or_tenant(assistants, subject, tenant):
    service, _ = assistants
    scope = await scoped_tree(service)
    with pytest.raises(AccessDenied):
        async with primary_authority():
            assert await service.validate_scope("issuer|viewer", "north", scope) == scope
            await service.validate_scope(subject, tenant, scope)


async def test_rejected_scope_filter_does_not_poison_a_borrowed_writer(assistants):
    service, _ = assistants
    scope = await scoped_tree(service)
    async with TransactionTemplate("primary").transaction():
        with pytest.raises(AccessDenied):
            await service.validate_scope(
                "issuer|admin", "north", scope, {"workspace_id": "incompatible-selection"}
            )
        entry = await service.catalog.create(
            "issuer|admin", "north", kind="collection", name="Still usable", parent_id=scope["project_id"]
        )
    assert (await service.catalog.get("issuer|admin", "north", entry.id)).name == "Still usable"
