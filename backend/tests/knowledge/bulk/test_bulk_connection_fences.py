# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from types import SimpleNamespace
from unittest.mock import AsyncMock

from test_bulk_native import bulk as bulk


async def test_role_create_delete_and_index_bind_lock_tenant_before_selecting_effective_rows(bulk):
    from koinon.assistants.repositories import ProviderRepository
    from koinon.catalog.entities import Membership
    from koinon.knowledge.connections.repositories import KnowledgeConnectionRepository
    from koinon.knowledge.connections.service import KnowledgeConnectionService
    from koinon.knowledge.indexes.assignments import IndexAssignments

    await bulk.members.save(Membership(id="admin", subject="issuer|admin", tenant_id="north", role="admin"))
    records = bulk.context.get_bean(KnowledgeConnectionRepository)
    events = []

    async def lock(tenant):
        assert tenant == "north"
        events.append("tenant")

    records.lock_tenant = AsyncMock(side_effect=lock)
    roles = KnowledgeConnectionService(
        bulk.catalog, records, bulk.context.get_bean(ProviderRepository), SimpleNamespace()
    )
    original = roles.authority

    async def authority(*args, **kwargs):
        events.append("authority")
        await original(*args, **kwargs)

    roles.authority = authority
    created = await roles.save(
        "issuer|admin",
        "north",
        {
            "domain": "documents",
            "role": "documents.embedding",
            "provider_id": "embedding-provider",
            "model_id": "embedding",
            "dimensions": 768,
            "storage_dimensions": 768,
            "space_id": "reviewed-space",
        },
    )
    assert events[:2] == ["tenant", "authority"]
    events.clear()
    await roles.delete("issuer|admin", "north", created["id"], expected_revision=created["revision"])
    assert events[:2] == ["tenant", "authority"]
    events.clear()
    assignments = IndexAssignments(roles)

    async def snapshot(*args):
        events.append("snapshot")
        return {}

    assignments.snapshot = AsyncMock(side_effect=snapshot)
    await assignments.bind("issuer|admin", SimpleNamespace(tenant_id="north", domain="documents"), {})
    assert events == ["tenant", "snapshot"]


async def test_tenant_selection_fence_is_a_bound_postgresql_row_lock():
    from sqlalchemy.dialects import postgresql

    from koinon.knowledge.connections.repositories import KnowledgeConnectionRepository

    statements = []

    async def scalar(statement):
        statements.append(statement)

    records = KnowledgeConnectionRepository(session=SimpleNamespace(scalar=scalar))
    await records.lock_tenant("north")
    assert len(statements) == 1
    rendered = statements[0].compile(dialect=postgresql.dialect())
    assert "FROM lattice_tenants" in str(rendered) and "FOR UPDATE" in str(rendered)
    assert rendered.params == {"id_1": "north"}
