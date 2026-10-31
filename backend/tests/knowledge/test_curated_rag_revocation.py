# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Post-query revocation must precede body release and evidence capture."""

from types import SimpleNamespace

import pytest
from pyfly.kernel import ForbiddenException
from test_curated_intents import curated as curated
from test_curated_intents import input_for
from test_curated_native_commit import transaction_fixture
from test_curated_native_events import native_lifecycle as native_lifecycle


@pytest.mark.parametrize("change", ["membership", "serving"])
async def test_revocation_during_native_ranked_query_prevents_body_and_receipt(
    curated, native_lifecycle, change
):
    from pyfly.data.relational.datasource_registry import DataSourceRegistry
    from pyfly.data.transaction import infrastructure_unit

    from koinon.knowledge.curated.acknowledgement import CatalogAcknowledgement
    from koinon.knowledge.curated.corpus import CuratedBodyCorpus
    from koinon.knowledge.curated.ports import NativeCatalogProjection, NativeKnowledgeOperation
    from koinon.knowledge.curated.reads import CuratedKnowledgeReads
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
    from koinon.knowledge.curated.whole_repository import CuratedWholePartRepository

    context.get_bean(CuratedWholePartRepository).datasources = source.registry
    from sqlalchemy import delete, update

    from koinon.catalog.entities import Membership
    from koinon.knowledge.capture_receipt import NativeEvidenceReceipt
    from koinon.knowledge.curated.entities import CuratedCatalogState

    corpus = context.get_bean(CuratedBodyCorpus)
    selected = await corpus.admit("issuer|reader", "north", [first.item_id])
    original_ranked = corpus.ranked

    async def ranked_then_revoke(*args, **kwargs):
        result = await original_ranked(*args, **kwargs)
        assert result, "The test must observe a real matching native body before revocation"
        async with primary.engine.begin() as connection:
            if change == "membership":
                await connection.execute(delete(Membership).where(Membership.id == "reader"))
            else:
                await connection.execute(
                    update(CuratedCatalogState)
                    .where(CuratedCatalogState.item_id == first.item_id)
                    .values(serving_version=None, serving_version_id=None)
                )
        return result

    corpus.ranked = ranked_then_revoke
    capture = NativeEvidenceReceipt("issuer|reader", "north")
    with pytest.raises(ForbiddenException):
        await corpus.search(
            "issuer|reader", "north", "owned", selected, query="threshold47", limit=10, _capture=capture
        )
    assert capture.knowledge_sources == {} and capture.native_reads == []
