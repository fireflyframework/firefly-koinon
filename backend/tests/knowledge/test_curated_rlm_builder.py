# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""The managed builder must never interpret curated-only scope as unrestricted documents."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from flycanon.core.services.query import provenance
from flycanon.core.services.query.rlm.corpus import CanonCorpusBuilder, CanonDocStore, Filters
from flycanon.core.services.retrieval import curated_corpus
from test_curated_rlm_corpus import Observer, Reader, _retrieve
from test_curated_whole_views import _inputs


def _fixture():
    mapper, _, value, _, meta, parts = _inputs()
    reader = Reader(meta, mapper.whole_view(meta, value.selected_version.content.body, parts))
    sources = SimpleNamespace(
        list_sources=AsyncMock(side_effect=AssertionError("Unrestricted document lookup"))
    )
    knowledge = SimpleNamespace(
        resolve_source_ids_for_items=AsyncMock(
            side_effect=AssertionError("Curated knowledge is not its upstream document")
        )
    )
    objects = SimpleNamespace(get_sync=Mock(side_effect=AssertionError("No original file read")))
    return (
        CanonCorpusBuilder(source_repository=sources, knowledge_repository=knowledge, object_store=objects),
        sources,
        knowledge,
        objects,
        reader,
    )


async def test_curated_only_build_skips_all_document_queries_and_upstream_substitution():
    builder, sources, knowledge, objects, reader = _fixture()
    observer = Observer()
    with (
        provenance.observe(
            observer, tenant_id="north", workspace_id="native-workspace", actor="reader", source_ids=[]
        ),
        curated_corpus.bind(
            tenant_id="north",
            workspace_id="native-workspace",
            actor="reader",
            retrieve=_retrieve,
            documents=False,
            rlm=reader,
        ),
    ):
        store = await builder.build(
            tenant_id="north",
            workspace_id="native-workspace",
            filters=Filters(source_ids=[], knowledge_item_ids=["native-item"]),
        )
        assert store.keys() == ["knowledge:item@version-one"]
        assert len(store) == 1 and reader.pins == 1 and reader.reads == 0
    sources.list_sources.assert_not_awaited()
    knowledge.resolve_source_ids_for_items.assert_not_awaited()
    objects.get_sync.assert_not_called()


async def test_standalone_empty_source_filter_retains_the_existing_document_behavior():
    builder, sources, knowledge, objects, _ = _fixture()
    sources.list_sources.side_effect = None
    sources.list_sources.return_value = ([], 0)
    store = await builder.build(
        tenant_id="north", workspace_id="native-workspace", filters=Filters(source_ids=[])
    )
    assert isinstance(store, CanonDocStore) and len(store) == 0
    sources.list_sources.assert_awaited_once()
    knowledge.resolve_source_ids_for_items.assert_not_awaited()
    objects.get_sync.assert_not_called()


@pytest.mark.parametrize(
    "filters",
    [
        Filters(knowledge_item_ids=["different-item"]),
        Filters(domains=["security"]),
        Filters(tags=["unrecorded-tag"]),
        Filters(statuses=["draft"]),
        Filters(jurisdictions=["EU"]),
    ],
)
async def test_curated_version_filters_never_expand_to_nonmatching_or_unknown_metadata(filters):
    builder, _, _, _, reader = _fixture()
    with (
        provenance.observe(
            Observer(), tenant_id="north", workspace_id="native-workspace", actor="reader", source_ids=[]
        ),
        curated_corpus.bind(
            tenant_id="north",
            workspace_id="native-workspace",
            actor="reader",
            retrieve=_retrieve,
            documents=False,
            rlm=reader,
        ),
    ):
        store = await builder.build(tenant_id="north", workspace_id="native-workspace", filters=filters)
        assert len(store) == 0 and store.keys() == [] and reader.reads == 0
