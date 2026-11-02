# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Real PostgreSQL scope reads stay bounded under simultaneous callers."""

import asyncio

import pytest
from pyfly.data.relational.datasource_registry import DataSourceRegistry
from pyfly.data.transaction import Propagation, TransactionTemplate, current_unit_of_work
from sqlalchemy import event, update
from test_memory_authority_postgres import pg_assistants as pg_assistants
from test_scope_read_budget import scoped_tree

from koinon.catalog.entities import Membership
from koinon.catalog.errors import AccessDenied
from koinon.security.authority import primary_authority

pytestmark = pytest.mark.integration


@pytest.mark.parametrize(
    "pg_assistants",
    [{"pool": {"size": size, "max-overflow": 0, "timeout": 2}} for size in (1, 5)],
    indirect=True,
)
@pytest.mark.parametrize("assets", [1, 40])
async def test_scope_sql_budget_with_concurrent_readers(pg_assistants, assets):
    service, context, _ = pg_assistants
    scope = await scoped_tree(service)
    first = await service.catalog.get("issuer|admin", "north", scope["asset_ids"][0])
    for index in range(assets - 1):
        row = await service.catalog.create(
            "issuer|admin", "north", kind="dataset", name=f"Dataset {index}", parent_id=first.parent_id
        )
        scope["asset_ids"].append(row.id)
    engine = context.get_bean(DataSourceRegistry).primary.engine
    statements = []

    def capture(connection, cursor, statement, parameters, execution, many):
        statements.append(statement)

    event.listen(engine.sync_engine, "before_cursor_execute", capture)
    try:
        assert await service.validate_scope("issuer|admin", "north", scope) == scope
    finally:
        event.remove(engine.sync_engine, "before_cursor_execute", capture)
    assert len(statements) <= 3, f"Scope of {assets} assets issued {len(statements)} SQL statements"
    async with asyncio.timeout(10):
        results = await asyncio.gather(
            *(service.validate_scope("issuer|admin", "north", scope) for _ in range(5))
        )
    assert results == [scope] * 5
    assert engine.pool.checkedout() == 0


@pytest.mark.parametrize("pg_assistants", [{"pool": {"size": 5, "max-overflow": 0}}], indirect=True)
async def test_fresh_egress_does_not_reuse_populated_policy_observations(pg_assistants):
    service, _, _ = pg_assistants
    scope = await scoped_tree(service)
    async with primary_authority() as outer:
        assert await service.validate_scope("issuer|admin", "north", scope) == scope
        async with TransactionTemplate(
            "primary", propagation=Propagation.REQUIRES_NEW
        ).transaction() as writer:
            await writer.resource.execute(
                update(Membership).where(Membership.id == "admin").values(active=False)
            )
        with pytest.raises(AccessDenied):
            async with primary_authority(fresh=True):
                await service.validate_scope("issuer|admin", "north", scope)
        assert current_unit_of_work("primary") is outer
    with pytest.raises(AccessDenied):
        await service.validate_scope("issuer|admin", "north", scope)
