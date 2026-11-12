# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Exact document authority runs before model input and cannot widen candidates."""

from types import SimpleNamespace

import pytest
from pyfly.kernel import ServiceUnavailableException

from flycanon.core.services.query import provenance


class Observer:
    def __init__(self):
        self.models = []
        self.checked = []
        self.deny = True

    async def authorize(self):
        return None

    async def authorize_document_pins(self, pins):
        self.checked.append(pins)
        if self.deny:
            raise ServiceUnavailableException("Source access revoked", code="SOURCE_UNAVAILABLE")

    def document_model(self, stage, prompt, hits, scope):
        self.models.append(prompt)


@pytest.mark.asyncio
async def test_revoked_exact_origin_prevents_model_input():
    observer = Observer()
    hit = SimpleNamespace(
        chunk_id="chunk",
        source_id="source",
        score=1.0,
        metadata={"source_version_id": "version", "extraction_id": "extraction"},
    )
    with (
        provenance.observe(observer, tenant_id="tenant", workspace_id="workspace", actor="reader"),
        pytest.raises(ServiceUnavailableException, match="Source access revoked"),
    ):
        await provenance.before_model(
            "answer", "protected text", [hit], tenant_id="tenant", workspace_id="workspace"
        )
    assert observer.models == []


@pytest.mark.asyncio
async def test_candidate_fusion_does_not_load_text_before_admission():
    from flycanon.core.services.retrieval.fusion import ChunkHit, HybridRetriever

    class Corpus:
        hydrated = False

        async def bm25_search(self, query, *, top_k):
            return [ChunkHit("denied", 1, "")]

        async def get_chunks(self, ids):
            self.hydrated = True
            raise AssertionError("Unauthorized text was loaded")

    class Vectors:
        async def search(self, vector, *, top_k):
            return []

    class Embeddings:
        async def embed_one(self, query):
            return [1.0]

    observer = Observer()
    observer.admit_document_candidates = lambda pins: None
    corpus = Corpus()
    retriever = HybridRetriever(corpus=corpus, vector_store=Vectors(), embedder=Embeddings())
    with provenance.observe(observer, tenant_id="tenant", workspace_id="workspace", actor="reader"):
        result = await retriever.retrieve(["query"])
    assert not corpus.hydrated
    assert [(hit.chunk_id, hit.content) for hit in result] == [("denied", "")]


@pytest.mark.asyncio
async def test_candidate_observer_cannot_substitute_a_version():
    from dataclasses import replace

    pin = provenance.DocumentCandidatePin("chunk", "source", "v1", "e1")
    observer = Observer()

    async def widen(pins):
        return (replace(pins[0], source_version_id="v2"),)

    observer.admit_document_candidates = widen
    with (
        provenance.observe(observer, tenant_id="tenant", workspace_id="workspace", actor="reader"),
        pytest.raises(ServiceUnavailableException, match="widened"),
    ):
        await provenance.admit_document_candidates((pin,))


@pytest.mark.asyncio
async def test_only_admitted_exact_pins_reach_chunk_hydration():
    from flycanon.core.services.retrieval.fusion import ChunkHit
    from flycanon.core.services.retrieval.retrieval_service import RetrievalService

    class Chunks:
        loaded = []

        async def get_many(self, identifiers):
            raise AssertionError("Unpinned content read")

        async def candidate_pins(self, identifiers, **scope):
            return tuple(provenance.DocumentCandidatePin(i, i, "v1", "e1") for i in identifiers)

        async def get_pinned_chunks(self, pins, **scope):
            self.loaded.extend(pin.chunk_id for pin in pins)
            return [
                SimpleNamespace(
                    id=pin.chunk_id,
                    source_id=pin.source_id,
                    content="allowed text",
                    section_path=None,
                    page=None,
                )
                for pin in pins
            ]

    class Sources:
        async def get_many(self, identifiers):
            return []

    class Knowledge:
        async def lookup_published_citations_for_chunks(self, identifiers):
            return {}

    observer = Observer()
    observer.deny = False
    observer.document_read_hits = lambda hits, scope: None

    async def admit(pins):
        return tuple(pin for pin in pins if pin.source_id == "allowed")

    observer.admit_document_candidates = admit
    chunks = Chunks()
    service = RetrievalService(
        context=None,
        embeddings=None,
        source_repository=Sources(),
        chunk_repository=chunks,
        knowledge_repository=Knowledge(),
        default_top_k=10,
        default_per_query_k=20,
        rrf_k=60,
    )
    with provenance.observe(observer, tenant_id="tenant", workspace_id="workspace", actor="reader"):
        hits = await service._hydrate([ChunkHit("denied", 2, ""), ChunkHit("allowed", 1, "")])
    assert chunks.loaded == ["allowed"]
    assert [(hit.source_id, hit.content) for hit in hits] == [("allowed", "allowed text")]


@pytest.mark.asyncio
async def test_rlm_does_not_load_denied_source_metadata():
    from flycanon.core.services.query.rlm.corpus import CanonCorpusBuilder
    from flycanon.interfaces.dtos.rlm_corpus import Filters

    class Sources:
        async def candidate_pins(self, ids, **scope):
            return (provenance.DocumentCandidatePin("", "denied", "v1", "e1"),)

        async def get_many_scoped(self, ids, **scope):
            if ids:
                raise AssertionError("Denied title was loaded")
            return []

    observer = Observer()

    async def admit(pins):
        return ()

    observer.admit_document_candidates = admit
    builder = CanonCorpusBuilder(source_repository=Sources(), knowledge_repository=None, object_store=None)
    with provenance.observe(observer, tenant_id="tenant", workspace_id="workspace", actor="reader"):
        rows = await builder._list_in_scope("tenant", "workspace", Filters(source_ids=["denied"]))
    assert rows == []


@pytest.mark.asyncio
async def test_cached_rlm_page_rechecks_source_before_content_read():
    import asyncio

    from flycanon.core.services.query.rlm.corpus import CanonDocStore
    from flycanon.interfaces.dtos.rlm_corpus import SourceMeta

    observer = Observer()
    observer.requires_source_authority = True
    source = SourceMeta(
        "source",
        "private.txt",
        None,
        "file",
        "",
        "hash",
        "tenant",
        "workspace",
        source_version_id="v1",
        ingestion_extraction_id="e1",
    )
    store = CanonDocStore({"private": source}, object_store=None, registry=None)
    store._pages["private"] = ["private cached content"]
    with (
        provenance.observe(observer, tenant_id="tenant", workspace_id="workspace", actor="reader"),
        pytest.raises(ServiceUnavailableException, match="Source access revoked"),
    ):
        await asyncio.to_thread(provenance.worker(store._load), "private")
    assert len(observer.checked) == 1
    assert observer.checked[0][0].source_version_id == "v1"
