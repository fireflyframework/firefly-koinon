# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Owned SQLite proves native DI/query/ACK composition, not PostgreSQL RLS or models."""

from dataclasses import replace
from types import SimpleNamespace

import pytest
from pyfly.kernel import ConflictException
from test_curated_intents import curated as curated
from test_curated_intents import input_for
from test_curated_native_commit import transaction_fixture
from test_curated_native_events import native_lifecycle as native_lifecycle


async def test_managed_whole_reader_uses_native_projection_and_preserves_serving_v1_during_draft_v2(
    curated, native_lifecycle
):
    from pyfly.data.relational.datasource_registry import DataSourceRegistry
    from pyfly.data.transaction import infrastructure_unit

    from koinon.knowledge.curated.acknowledgement import CatalogAcknowledgement
    from koinon.knowledge.curated.corpus import CuratedBodyCorpus
    from koinon.knowledge.curated.ports import NativeCatalogProjection, NativeKnowledgeOperation
    from koinon.knowledge.curated.reads import CuratedKnowledgeReads
    from koinon.knowledge.curated.whole import CuratedWholeVersionReader
    from koinon.knowledge.curated.whole_repository import CuratedWholePartRepository
    from koinon.knowledge.entities import DomainBinding

    service, destination, unit = await transaction_fixture(curated, native_lifecycle)
    context = curated[3]
    source = native_lifecycle[1]
    primary = context.get_bean(DataSourceRegistry).get("primary")
    async with infrastructure_unit(primary) as session:
        session.add(
            DomainBinding(
                id="workspace-alias",
                tenant_id="north",
                catalog_id=destination.workspace_id,
                workspace_id=destination.workspace_id,
                domain="canon",
                entity_kind="workspace",
                native_id="owned",
                native_workspace_id="owned",
                created_by="issuer|owner",
            )
        )
    body = "á🙂" * 2500 + "\nReviewed threshold47"
    preview = await service.preview(
        "issuer|owner",
        "north",
        input_for(destination, action="create_published", content={"title": "Approved rule", "body": body}),
    )
    first = await unit.commit(NativeKnowledgeOperation(preview, ()), native_workspace_id="owned")
    acknowledgement = context.get_bean(CatalogAcknowledgement)
    projection = NativeCatalogProjection(
        native_workspace_id="owned",
        title=preview.after.title,
        serving_version_id=first.native_version_id,
        serving_operation_id=first.operation_id,
    )
    await acknowledgement.apply(preview, first, projection)
    reads = context.get_bean(CuratedKnowledgeReads)
    reads.native = SimpleNamespace(datasource=lambda: source)
    parts = context.get_bean(CuratedWholePartRepository)
    assert source.registry is not None
    parts.datasources = source.registry
    reader = context.get_bean(CuratedWholeVersionReader)
    assert reader.parts is parts and reader.reads is reads
    corpus = context.get_bean(CuratedBodyCorpus)
    selection = (await corpus.admit("issuer|reader", "north", [first.item_id]))[0]
    meta = await reader.pin("issuer|reader", "north", "owned", selection)
    view = await reader.read("issuer|reader", "north", meta)
    assert view.text == body and len(view.parts) == 2 and view.database.engine == "sqlite"
    assert view.meta.evidence_sha256 == first.evidence_sha256
    assert view.meta.operation_id == first.operation_id
    for field, value in (
        ("tenant_id", "south"),
        ("workspace_id", "other"),
        ("item_id", "other"),
        ("native_item_id", "other"),
    ):
        with pytest.raises(Exception) as caught:
            await parts.assert_serving(replace(meta, **{field: value}), subject="issuer|reader")
        assert getattr(caught.value, "code", None) == "KNOWLEDGE_VERSION_CONFLICT"

    class Head:
        async def head(self, subject, tenant, identifier):
            return await unit.head(tenant, "owned", identifier)

    service.native = SimpleNamespace(get=lambda: Head())
    draft = await service.preview(
        "issuer|owner",
        "north",
        input_for(
            destination,
            action="update_draft",
            target_item_id=first.item_id,
            expected_version=1,
            content={"title": "Draft rule", "body": "Unpublished99"},
        ),
    )
    second = await unit.commit(NativeKnowledgeOperation(draft, ()), native_workspace_id="owned")
    await acknowledgement.apply(draft, second, projection)
    assert (await reader.read("issuer|reader", "north", meta)).text == body
    with pytest.raises(ConflictException):
        await reader.pin(
            "issuer|reader",
            "north",
            "owned",
            replace(selection, version_id=second.native_version_id, version=2),
        )

    from pyfly.kernel import ForbiddenException
    from sqlalchemy import delete, update

    from koinon.catalog.entities import Membership
    from koinon.knowledge.capture_receipt import NativeEvidenceReceipt

    async with infrastructure_unit(primary, read_only=True) as session:
        cached = await session.get(Membership, "reader")
        assert cached.role == "viewer"
        async with primary.engine.begin() as connection:
            await connection.execute(
                update(Membership).where(Membership.id == "reader").values(role="revoked")
            )
        with pytest.raises(ForbiddenException):
            await reader.authorize("issuer|reader", "north", (meta,))
    async with primary.engine.begin() as connection:
        await connection.execute(update(Membership).where(Membership.id == "reader").values(role="viewer"))

    original_ranked = corpus.ranked

    async def ranked_then_revoke(*args, **kwargs):
        result = await original_ranked(*args, **kwargs)
        async with primary.engine.begin() as connection:
            await connection.execute(delete(Membership).where(Membership.id == "reader"))
        return result

    corpus.ranked = ranked_then_revoke
    capture = NativeEvidenceReceipt("issuer|reader", "north")
    with pytest.raises(ForbiddenException):
        await corpus.search(
            "issuer|reader", "north", "owned", (selection,), query="threshold47", limit=10, _capture=capture
        )
    assert capture.knowledge_sources == {}
