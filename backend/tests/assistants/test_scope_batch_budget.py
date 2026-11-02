# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import pytest
from pyfly.data.relational.datasource_registry import DataSourceRegistry
from sqlalchemy import event
from test_scope_read_budget import scoped_tree
from test_service import assistants as assistants

from koinon.catalog.errors import AccessDenied


@pytest.mark.parametrize("assets", [1, 40])
async def test_scope_reads_catalog_and_memberships_in_batches(assistants, assets):
    service, context = assistants
    scope = await scoped_tree(service)
    first = await service.catalog.get("issuer|admin", "north", scope["asset_ids"][0])
    for index in range(assets - 1):
        row = await service.catalog.create(
            "issuer|admin", "north", kind="dataset", name=f"Dataset {index}", parent_id=first.parent_id
        )
        scope["asset_ids"].append(row.id)
    engine = context.get_bean(DataSourceRegistry).primary.engine.sync_engine
    statements = []

    def capture(connection, cursor, statement, parameters, execution, many):
        statements.append(statement)

    event.listen(engine, "before_cursor_execute", capture)
    try:
        assert await service.validate_scope("issuer|viewer", "north", scope) == scope
    finally:
        event.remove(engine, "before_cursor_execute", capture)
    assert len(statements) <= 3, f"Scope of {assets} assets issued {len(statements)} SQL statements"


async def test_batched_ancestry_does_not_admit_a_foreign_parent(assistants):
    service, _ = assistants
    scope = await scoped_tree(service)
    row = await service.catalog.catalog_repository.find_by_id(scope["asset_ids"][0])
    foreign = await service.catalog.create("issuer|outsider", "south", kind="workspace", name="Private")
    row.parent_id = foreign.id
    await service.catalog.catalog_repository.save(row)
    with pytest.raises(AccessDenied):
        await service.validate_scope("issuer|viewer", "north", scope)


async def test_batched_ancestry_does_not_admit_a_missing_entry(assistants):
    service, _ = assistants
    scope = await scoped_tree(service)
    scope["asset_ids"].append("absent-entry")
    with pytest.raises(AccessDenied):
        await service.validate_scope("issuer|viewer", "north", scope)


async def test_batched_ancestry_is_bounded_and_still_rejects_cycles(assistants):
    from pyfly.kernel import InvalidRequestException

    service, _ = assistants
    scope = await scoped_tree(service)
    root = await service.catalog.catalog_repository.find_by_id(scope["workspace_id"])
    root.parent_id = scope["asset_ids"][0]
    await service.catalog.catalog_repository.save(root)
    with pytest.raises(InvalidRequestException, match="ancestry"):
        await service.validate_scope("issuer|viewer", "north", scope)
