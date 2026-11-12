# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Catalog service mutations cannot bypass source policy through a non-HTTP caller."""

from contextlib import asynccontextmanager

import pytest
from pyfly.data.transaction import current_unit_of_work
from test_catalog import catalog as catalog

from koinon.integrations.content_sources.errors import SourceError


async def test_direct_catalog_update_checks_source_before_entering_transaction(catalog):
    service, _, _ = catalog
    workspace = await service.create("issuer|alice", "north", kind="workspace", name="Before")

    class Policy:
        @asynccontextmanager
        async def mutation(self, actor, tenant, identifiers, *, action, target):
            unit = current_unit_of_work("primary")
            assert unit is None or unit.completed, "Source provider check entered a write unit"
            assert (actor, tenant, action, target) == ("issuer|alice", "north", "update", workspace.id)
            raise SourceError("access_denied")
            yield

    class PolicyProvider:
        def get(self):
            return Policy()

    service.source_policy = PolicyProvider()
    with pytest.raises(SourceError, match="access_denied"):
        await service.update(
            "issuer|alice", "north", workspace.id, {"name": "After"}, expected_updated_at=workspace.updated_at
        )
    assert (await service.get("issuer|alice", "north", workspace.id)).name == "Before"


async def test_catalog_page_scope_uses_identity_without_parent_metadata(catalog, monkeypatch):
    service, _, _ = catalog
    workspace = await service.create("issuer|alice", "north", kind="workspace", name="Private parent")

    async def hydrate(*args, **kwargs):
        pytest.fail("Listing hydrated its parent before source classification")

    monkeypatch.setattr(service, "get", hydrate)
    result = await service.page("issuer|alice", "north", parent_id=workspace.id)
    assert result["items"] == [] and result["total"] == 0
