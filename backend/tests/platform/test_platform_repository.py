# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from platform_fixture import authority as authority
from pyfly.data.relational.datasource_registry import DataSourceRegistry
from sqlalchemy import event

from koinon.catalog.entities import CatalogEntry, Tenant
from koinon.catalog.repositories import CatalogRepository, TenantRepository
from koinon.platform.repositories import PlatformRepository


async def test_status_projection_is_tenant_scoped_bounded_and_never_loads_private_metadata(authority):
    context, _ = authority
    catalog = context.get_bean(CatalogRepository)
    await catalog.save(
        CatalogEntry(
            id="project",
            tenant_id="north",
            parent_id="workspace",
            workspace_id="workspace",
            project_id="project",
            kind="project",
            name="Project",
            created_by="issuer|admin",
        )
    )
    for number, status in enumerate(("ready", "error", "pending", "ready")):
        await catalog.save(
            CatalogEntry(
                id=f"doc{number}",
                tenant_id="north",
                parent_id="project",
                workspace_id="workspace",
                project_id="project",
                kind="document",
                name="Secret document",
                status=status,
                metadata_json={"sentinel": "private instructions and DSN" * 1000},
                created_by="issuer|admin",
            )
        )
    await context.get_bean(TenantRepository).save(Tenant(id="other", name="Other"))
    await catalog.save(
        CatalogEntry(
            id="foreign",
            tenant_id="other",
            workspace_id="foreign",
            kind="workspace",
            name="Foreign",
            created_by="issuer|other",
        )
    )
    statements = []
    engine = context.get_bean(DataSourceRegistry).primary.engine.sync_engine

    def capture(conn, cursor, statement, parameters, callcontext, many):
        statements.append(statement)

    event.listen(engine, "before_cursor_execute", capture)
    try:
        result = await context.get_bean(PlatformRepository).catalog_states("north", "document", limit=3)
        assert len(result.states) == 3 and not result.complete
        assert set(result.states) == {"ready", "error", "pending"}
        assert "metadata_json" not in " ".join(statements)
        assert "instructions" not in repr(result) and "Secret document" not in repr(result)
        empty = await context.get_bean(PlatformRepository).catalog_states("other", "document", limit=3)
        assert empty.states == () and empty.complete
    finally:
        event.remove(engine, "before_cursor_execute", capture)
