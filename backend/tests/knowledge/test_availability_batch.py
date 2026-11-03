# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from pyfly.data.relational.datasource_registry import DataSourceRegistry
from sqlalchemy import event
from test_facade import context as context
from test_facade import upload

from koinon.catalog.errors import AccessDenied
from koinon.catalog.repositories import MembershipRepository
from koinon.knowledge.availability.dtos import AvailabilityRequest, ProcessingRequest
from koinon.knowledge.availability.repository import AvailabilityRepository
from koinon.knowledge.availability.service import KnowledgeAvailabilityService
from koinon.knowledge.content import ContentUpdates


def observer(context):
    native = SimpleNamespace(observe=AsyncMock(return_value={}))
    return KnowledgeAvailabilityService(context[0], AvailabilityRepository(), native), native


async def test_availability_and_processing_batch_primary_reads(context, record_property):
    facade = context[0]
    identifiers = [(await upload(context))["assets"][0]["id"] for _ in range(25)]
    updates = ContentUpdates(facade)
    for identifier in identifiers:
        source = (await facade._chain("issuer|admin", "north", identifier))[1]
        version = await updates._version(
            "issuer|admin", "north", source.id, "document.replace", "new", b"new"
        )
        await updates._finish_version("issuer|admin", "north", version, {"status": "error"}, "failed")
    service, _ = observer(context)
    engine = context[4].get_bean(DataSourceRegistry).primary.engine.sync_engine
    statements = []

    def count(_connection, _cursor, statement, _parameters, _context, _executemany):
        statements.append(statement)

    event.listen(engine, "before_cursor_execute", count)
    try:
        counts = {"observe": [], "processing": []}
        for size in (1, 25):
            statements.clear()
            result = await service.observe(
                "issuer|admin", "north", AvailabilityRequest(asset_ids=identifiers[:size])
            )
            assert len(result.items) == size
            counts["observe"].append(len(statements))
            statements.clear()
            result = await service.processing("issuer|admin", "north", ProcessingRequest(page_size=size))
            assert len(result.items) == size
            counts["processing"].append(len(statements))
        record_property("primary_sql_counts", str(counts))
        assert counts["observe"][0] == counts["observe"][1] <= 16
        assert counts["processing"][0] == counts["processing"][1]
        return counts
    finally:
        event.remove(engine, "before_cursor_execute", count)


@pytest.mark.parametrize("change", ["membership", "ancestor", "foreign_parent"])
async def test_after_native_read_rechecks_current_authority(context, change):
    facade, catalog, _, tree, app = context
    identifier = (await upload(context))["assets"][0]["id"]
    service, native = observer(context)

    async def changed(*args):
        if native.observe.await_count == 1:
            if change == "membership":
                members = app.get_bean(MembershipRepository)
                member = await members.find_by_id("reader")
                member.active = False
                await members.save(member)
            elif change == "ancestor":
                await catalog.archive("issuer|admin", "north", tree["collection"].id)
            else:
                parent = await catalog.create("issuer|outsider", "south", kind="workspace", name="other")
                entry = await catalog.catalog_repository.find_by_id(tree["collection"].id)
                entry.parent_id = parent.id
                await catalog.catalog_repository.save(entry)
        return {}

    native.observe.side_effect = changed
    with pytest.raises(AccessDenied):
        await service.observe("issuer|reader", "north", AvailabilityRequest(asset_ids=[identifier]))
    assert native.observe.await_count == 2


async def test_batched_lookup_does_not_admit_foreign_identifiers(context):
    service, native = observer(context)
    identifier = (await upload(context))["assets"][0]["id"]
    with pytest.raises(AccessDenied):
        await service.observe("issuer|outsider", "south", AvailabilityRequest(asset_ids=[identifier]))
    native.observe.assert_not_awaited()


async def test_empty_processing_and_unobserved_assets_keep_unknown_semantics(context):
    service, _ = observer(context)
    result = await service.processing("issuer|admin", "north", ProcessingRequest())
    assert result.items == [] and result.next_page is None
    identifier = (await upload(context))["assets"][0]["id"]
    observed = await service.observe("issuer|reader", "north", AvailabilityRequest(asset_ids=[identifier]))
    assert observed.items[identifier].read.state == "unknown"
