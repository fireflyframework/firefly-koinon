# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Canonical mutations follow durable bulk's tenant-before-resource lock order."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from pyfly.data.relational.sqlalchemy import LockMode
from test_service import assistants as assistants
from test_service import configured


@pytest.mark.parametrize("action", ["update", "archive", "restore", "delete"])
async def test_catalog_mutations_lock_tenant_before_reserved_resource(assistants, monkeypatch, action):
    service, _ = assistants
    catalog = service.catalog
    node = None
    for kind in ("workspace", "project", "collection", "source", "document"):
        node = await catalog.create(
            "issuer|admin", "north", kind=kind, name=kind, parent_id=node.id if node else None
        )
    if action == "restore":
        await catalog.archive("issuer|admin", "north", node.id)
    events = []
    original_tenant, original_entry = catalog._lock_tenant, catalog._scoped_entry

    async def tenant(identifier):
        events.append("tenant")
        await original_tenant(identifier)

    async def entry(*args, **kwargs):
        if kwargs.get("lock"):
            events.append("entry")
        return await original_entry(*args, **kwargs)

    monkeypatch.setattr(catalog, "_lock_tenant", tenant)
    monkeypatch.setattr(catalog, "_scoped_entry", entry)
    await getattr(catalog, action)(
        "issuer|admin", "north", node.id, *({"name": "Reviewed rename"},) if action == "update" else ()
    )
    assert events[:2] == ["tenant", "entry"]
    retained = await catalog.catalog_repository.find_by_id(node.id)
    assert (retained is None) is (action == "delete")


@pytest.mark.parametrize("action", ["save", "validate"])
async def test_provider_mutations_match_bulk_lock_order_without_locking_probe(
    assistants, monkeypatch, action
):
    service, _ = assistants
    provider, _ = await configured(service)
    events = []
    original_tenant, original_provider = service.catalog._lock_tenant, service.providers.find_by_id

    async def tenant(identifier):
        events.append("tenant")
        await original_tenant(identifier)

    async def provider_row(*args, **kwargs):
        if kwargs.get("lock") == LockMode.PESSIMISTIC_WRITE:
            events.append("provider")
        return await original_provider(*args, **kwargs)

    async def probe(*args, **kwargs):
        assert events == []
        events.append("probe")
        return [{"id": key, "status": "passed"} for key in ("connection", "models")]

    monkeypatch.setattr(service.catalog, "_lock_tenant", tenant)
    monkeypatch.setattr(service.providers, "find_by_id", provider_row)
    monkeypatch.setattr(service.configuration_service.probe, "check", AsyncMock(side_effect=probe))
    if action == "save":
        saved = await service.save_provider(
            "issuer|admin", "north", {"name": "Reviewed name"}, provider["id"]
        )
        assert saved["revision"] == provider["revision"] + 1
        assert events[:2] == ["tenant", "provider"]
    else:
        validated = await service.validate_provider("issuer|admin", "north", provider["id"])
        assert validated["revision"] == provider["revision"]
        assert events[:3] == ["probe", "tenant", "provider"]


async def test_bulk_publication_lock_statements_use_the_same_tenant_first_order():
    from sqlalchemy.dialects import postgresql

    from koinon.knowledge.bulk.repositories import BulkRepository

    statements = []

    async def execute(statement):
        statements.append(str(statement.compile(dialect=postgresql.dialect())))
        return SimpleNamespace(all=lambda: [])

    records = BulkRepository(session=SimpleNamespace(scalar=execute, execute=execute, scalars=execute))
    await records.authority_lock("north", "issuer|admin", "origin-token")
    await records.catalog_locks("north", ("reserved-document",))
    assert "FROM lattice_tenants" in statements[0] and statements[0].endswith("FOR UPDATE")
    assert "FROM lattice_catalog" in statements[-1] and statements[-1].endswith("FOR SHARE")
    assert "FROM lattice_memberships" in statements[1] and statements[1].endswith("FOR SHARE")
    assert "FROM koinon_personal_tokens" in statements[2] and statements[2].endswith("FOR SHARE")
