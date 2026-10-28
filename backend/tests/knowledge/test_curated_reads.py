# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from types import SimpleNamespace

import pytest
from test_curated_intents import curated as curated
from test_curated_intents import input_for
from test_curated_native_commit import transaction_fixture
from test_curated_native_events import native_lifecycle as native_lifecycle


async def test_native_body_reads_are_versioned_and_drafts_never_replace_serving_content(
    curated, native_lifecycle
):
    from pyfly.data.relational.datasource_registry import DataSourceRegistry
    from pyfly.data.transaction import infrastructure_unit
    from pyfly.kernel import ServiceUnavailableException

    from koinon.catalog.errors import AccessDenied
    from koinon.knowledge.curated.acknowledgement import CatalogAcknowledgement
    from koinon.knowledge.curated.corpus import CuratedBodyCorpus
    from koinon.knowledge.curated.ports import NativeCatalogProjection, NativeKnowledgeOperation
    from koinon.knowledge.curated.reads import CuratedKnowledgeReads
    from koinon.knowledge.entities import DomainBinding

    service, destination, unit = await transaction_fixture(curated, native_lifecycle)
    context = curated[3]
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
    preview = await service.preview(
        "issuer|owner", "north", input_for(destination, action="create_published")
    )
    first = await unit.commit(NativeKnowledgeOperation(preview, ()), native_workspace_id="owned")
    projection = NativeCatalogProjection(
        native_workspace_id="owned",
        title=preview.after.title,
        serving_version_id=first.native_version_id,
        serving_operation_id=first.operation_id,
    )
    projector = context.get_bean(CatalogAcknowledgement)
    await projector.apply(preview, first, projection)
    reads = context.get_bean(CuratedKnowledgeReads)
    reads.native = SimpleNamespace(datasource=lambda: native_lifecycle[1])
    corpus = context.get_bean(CuratedBodyCorpus)
    admitted = await corpus.admit("issuer|reader", "north", [first.item_id])
    from koinon.knowledge.capture_receipt import NativeEvidenceReceipt

    capture = NativeEvidenceReceipt("issuer|reader", "north")
    matches = await corpus.search(
        "issuer|reader", "north", "owned", admitted, query="threshold", limit=10, _capture=capture
    )
    assert [hit.content for hit in matches] == [preview.after.body]
    assert matches[0].metadata["source_kind"] == "knowledge_version"
    assert matches[0].metadata["knowledge_version_id"] == first.native_version_id
    source = capture.knowledge_sources[matches[0].chunk_id]
    assert source.kind == "knowledge_version" and source.source_id is None
    assert source.knowledge_item_id == source.asset_id == first.item_id
    assert source.used_revision == "knowledge-content-sha256:" + first.content_sha256
    from dataclasses import asdict

    from flycanon.core.services.query import provenance

    from koinon.assistants.audit_dtos import NativeReadReceipt

    async def authorize():
        await reads.scope("issuer|reader", "north", first.item_id)

    capture.authorize_model = authorize
    with provenance.observe(
        capture, tenant_id="north", workspace_id="owned", actor="issuer|reader", source_ids=[]
    ):
        await provenance.before_model(
            "answer", "Exact prompt47", matches, tenant_id="north", workspace_id="owned"
        )
    observed = NativeReadReceipt(result_id="result", **asdict(capture.native_reads[-1]))
    assert observed.domain == "knowledge" and observed.read_kind == "knowledge_version"
    assert (
        observed.workspace_id == destination.workspace_id
        and observed.knowledge_version_id == first.native_version_id
    )
    from unittest.mock import AsyncMock, MagicMock

    from flycanon.core.services.query.handlers import SearchKnowledgeHandler
    from flycanon.core.services.query.search_service import SearchService
    from flycanon.core.services.retrieval.corpus_factory import CorpusContext
    from flycanon.core.services.retrieval.retrieval_service import RetrievalService
    from pyfly.cqrs import DefaultQueryBus, HandlerRegistry

    from koinon.knowledge.adapters import NativeDomains
    from koinon.knowledge.evidence_capture import NativeKnowledgeEvidence
    from koinon.knowledge.repositories import DomainBindingRepository
    from koinon.knowledge.service import KnowledgeFacade, KnowledgeSettings

    channels = MagicMock()
    retrieval = RetrievalService(
        context=CorpusContext(channels, channels, "test"),
        embeddings=channels,
        source_repository=channels,
        chunk_repository=channels,
        knowledge_repository=channels,
        default_top_k=10,
        default_per_query_k=30,
        rrf_k=60,
    )
    retrieval._hydrate = AsyncMock(return_value=[])
    handlers = HandlerRegistry()
    handlers.register_query_handler(SearchKnowledgeHandler(SearchService(retrieval=retrieval)))
    context.container.register_instance(DefaultQueryBus, DefaultQueryBus(handlers, caching_enabled=False))
    facade = KnowledgeFacade(
        curated[1],
        context.get_bean(DomainBindingRepository),
        NativeDomains(context.container),
        KnowledgeSettings(),
        SimpleNamespace(get=lambda: corpus),
    )
    produced = await NativeKnowledgeEvidence(facade, context.get_bean(DataSourceRegistry)).search(
        "issuer|reader", "north", question="threshold", asset_ids=[first.item_id], answer=False
    )
    assert produced.complete and produced.data["hits"][0]["text"] == preview.after.body
    assert produced.sources[0].knowledge_version_id == first.native_version_id
    assert produced.native_reads[0].domain == "knowledge"
    channels.embed_one.assert_not_called()
    found = await reads.version("issuer|reader", "north", first.item_id)
    assert found.selected_version.content.body == preview.after.body
    assert found.selected_version.evidence[0].kind == "user_statement"
    assert (await reads.page("issuer|reader", "north")).total == 1

    class Port:
        async def head(self, subject, tenant_id, item_id):
            return await unit.head(tenant_id, "owned", item_id)

    service.native = SimpleNamespace(get=lambda: Port())
    draft = await service.preview(
        "issuer|owner",
        "north",
        input_for(
            destination,
            action="update_draft",
            target_item_id=first.item_id,
            expected_version=1,
            content={"title": "Unpublished", "body": "Threshold99"},
        ),
    )
    second = await unit.commit(NativeKnowledgeOperation(draft, ()), native_workspace_id="owned")
    await projector.apply(draft, second, projection)
    assert (
        await corpus.search("issuer|reader", "north", "owned", admitted, query="Threshold99", limit=10) == []
    )
    assert (
        await reads.version("issuer|reader", "north", first.item_id)
    ).selected_version.content.body == preview.after.body
    with pytest.raises(AccessDenied):
        await reads.version("issuer|reader", "north", first.item_id, 2)
    assert (
        await reads.version("issuer|owner", "north", first.item_id, 2)
    ).selected_version.content.body == "Threshold99"
    publish = await service.preview(
        "issuer|owner",
        "north",
        input_for(
            destination,
            action="publish_draft",
            target_item_id=first.item_id,
            expected_version=2,
            content=draft.after.model_dump(mode="json"),
        ),
    )
    third = await unit.commit(NativeKnowledgeOperation(publish, ()), native_workspace_id="owned")
    with pytest.raises(ServiceUnavailableException) as error:
        await reads.version("issuer|reader", "north", first.item_id)
    assert error.value.code == "KNOWLEDGE_ACK_PENDING"
    await projector.apply(
        publish,
        third,
        NativeCatalogProjection(
            native_workspace_id="owned",
            title="Unpublished",
            serving_version_id=third.native_version_id,
            serving_operation_id=third.operation_id,
        ),
    )
    with pytest.raises(AccessDenied):
        await corpus.search("issuer|reader", "north", "owned", admitted, query="threshold", limit=10)
    admitted = await corpus.admit("issuer|reader", "north", [first.item_id])
    assert [
        hit.content
        for hit in await corpus.search(
            "issuer|reader", "north", "owned", admitted, query="Threshold99", limit=10
        )
    ] == ["Threshold99"]
    assert (await reads.version("issuer|reader", "north", first.item_id)).selected_version.version == 3
    assert (
        await reads.version("issuer|reader", "north", first.item_id, 1)
    ).selected_version.content.body == preview.after.body
