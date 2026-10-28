# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import asyncio

import pytest
from flycanon.core.services.retrieval import curated_corpus
from pyfly.kernel import ServiceUnavailableException


async def test_curated_corpus_has_no_standalone_fallback_or_child_task_authority():
    calls = []

    async def retrieve(**values):
        calls.append(values)
        return []

    arguments = dict(tenant_id="north", workspace_id="owned", query="threshold", limit=3)
    assert await curated_corpus.search(**arguments) == []
    with curated_corpus.bind(tenant_id="north", workspace_id="owned", retrieve=retrieve):
        assert await curated_corpus.search(**arguments) == []
        with pytest.raises(ServiceUnavailableException):
            await curated_corpus.search(**{**arguments, "tenant_id": "south"})
        with pytest.raises(ServiceUnavailableException):
            await asyncio.create_task(curated_corpus.search(**arguments))
    assert len(calls) == 1


async def test_existing_native_retrieval_consumes_explicit_version_body_and_knowledge_filters():
    from types import SimpleNamespace
    from unittest.mock import AsyncMock, MagicMock

    from flycanon.core.services.retrieval.corpus_factory import CorpusContext
    from flycanon.core.services.retrieval.retrieval_service import Hit, RetrievalFilters, RetrievalService

    corpus = SimpleNamespace(bm25_search=AsyncMock(return_value=[]), get_chunks=AsyncMock(return_value=[]))
    vectors = SimpleNamespace(search=AsyncMock(return_value=[]))
    embeddings = SimpleNamespace(embed_one=AsyncMock(return_value=[0.1]))
    service = RetrievalService(
        context=CorpusContext(corpus, vectors, "test"),
        embeddings=embeddings,
        source_repository=MagicMock(),
        chunk_repository=MagicMock(),
        knowledge_repository=MagicMock(),
        default_top_k=5,
        default_per_query_k=20,
        rrf_k=60,
    )
    service._hydrate = AsyncMock(return_value=[])
    body = Hit(
        chunk_id="version-chunk",
        source_id="native-item",
        knowledge_item_id="native-item",
        knowledge_version=1,
        content="Newly committed fact47",
        score=0.1,
        bm25_rank=None,
        vector_rank=None,
        metadata={"source_kind": "knowledge_version", "_knowledge_status": "published"},
    )

    async def retrieve(**values):
        return [body]

    with curated_corpus.bind(tenant_id="north", workspace_id="owned", retrieve=retrieve):
        result = await service.search(
            query="fact",
            tenant_id="north",
            workspace_id="owned",
            filters=RetrievalFilters(
                source_ids=["separate-document"], knowledge_item_ids=["native-item"], statuses=["published"]
            ),
        )
        assert [hit.content for hit in result.hits] == ["Newly committed fact47"]
        rejected = await service.search(
            query="fact",
            tenant_id="north",
            workspace_id="owned",
            filters=RetrievalFilters(knowledge_item_ids=["different-item"]),
        )
        assert rejected.hits == []
    corpus.bm25_search.reset_mock()
    embeddings.embed_one.reset_mock()
    vectors.search.reset_mock()
    with curated_corpus.bind(tenant_id="north", workspace_id="owned", retrieve=retrieve, documents=False):
        result = await service.search(
            query="fact", tenant_id="north", workspace_id="owned", filters=RetrievalFilters(source_ids=[])
        )
        assert result.hits[0].content == "Newly committed fact47"
    corpus.bm25_search.assert_not_called()
    embeddings.embed_one.assert_not_called()
    vectors.search.assert_not_called()
