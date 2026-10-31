# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""The native RLM corpus releases only exact, current, request-owned curated views."""

import asyncio
from importlib import import_module, util

import pytest
from flycanon.core.services.query import provenance
from flycanon.core.services.retrieval import curated_corpus
from pyfly.kernel import ServiceUnavailableException
from test_curated_whole_views import _inputs


def _components():
    assert util.find_spec("flycanon.core.services.query.rlm.knowledge_corpus") is not None, (
        "Curated versions need a scoped whole-body corpus, not substituted source documents"
    )
    return import_module("flycanon.core.services.query.rlm.knowledge_corpus")


class Reader:
    def __init__(self, meta, view):
        self.meta, self.view = meta, view
        self.allowed = True
        self.pins = self.reads = self.checks = 0

    async def authorize(self):
        self.checks += 1
        if not self.allowed:
            raise ServiceUnavailableException("Source permission revoked", code="EVIDENCE_UNAVAILABLE")

    async def pin(self):
        self.pins += 1
        await self.authorize()
        return (self.meta,)

    async def read(self, meta):
        self.reads += 1
        await self.authorize()
        assert meta == self.meta
        return self.view


class Observer:
    def __init__(self):
        self.events = []
        self.reject = False

    async def authorize(self):
        return None

    def knowledge_corpus_meta(self, meta, scope):
        self.events.append(("metadata", meta))

    def knowledge_sync(self, stage, content, identifiers, scope):
        self.events.append((stage, identifiers))

    def document_sync(self, *values):
        self.events.append(("document", values))

    def document_origin(self, *values):
        return None

    def knowledge_view_parts(self, meta, read, scope):
        if self.reject:
            raise ServiceUnavailableException("No receipt budget", code="EVIDENCE_BUDGET_EXCEEDED")
        self.events.append(("view", read))

    def knowledge_execution_read(self, meta, read, scope):
        self.events.append(("execution", read))


async def _prepare(observer=None, reader=None):
    module = _components()
    mapper, _, value, _, meta, parts = _inputs()
    reader = reader or Reader(meta, mapper.whole_view(meta, value.selected_version.content.body, parts))
    observer = observer or Observer()
    return module, observer, reader, value


async def _retrieve(**values):
    pytest.fail("RLM must not call lexical retrieval")


async def test_curated_only_metadata_does_not_release_body_and_code_input_has_exact_part_proof():
    module, observer, reader, value = await _prepare()
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
        store = await module.build_knowledge_store(tenant_id="north", workspace_id="native-workspace")
        context = await provenance.corpus(store)
        assert reader.reads == 0
        assert "knowledge:item@version-one" in context

        def consume():
            keys = store.keys()
            assert keys == ["knowledge:item@version-one"]
            assert store.npages(keys[0]) == 2
            assert reader.reads == 0
            text = store._execution_read(keys[0], as_pages=False)
            assert text == value.selected_version.content.body
            return store.pages(keys[0])

        pages = await asyncio.to_thread(provenance.worker(consume))
        assert "".join(pages) == value.selected_version.content.body
        assert reader.reads == 1
        assert any(stage == "execution" for stage, *_ in observer.events)
        assert not any(stage == "document" for stage, *_ in observer.events)


async def test_cached_text_rechecks_reader_authority_before_every_return():
    module, observer, reader, _ = await _prepare()
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
        store = await module.build_knowledge_store(tenant_id="north", workspace_id="native-workspace")
        await provenance.corpus(store)
        key = "knowledge:item@version-one"
        await asyncio.to_thread(provenance.worker(lambda: store[key]))
        reader.allowed = False
        with pytest.raises(ServiceUnavailableException):
            await asyncio.to_thread(provenance.worker(lambda: store[key]))
        assert reader.reads == 1


async def test_budget_denial_prevents_any_body_or_execution_release():
    module, observer, reader, _ = await _prepare()
    observer.reject = True
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
        store = await module.build_knowledge_store(tenant_id="north", workspace_id="native-workspace")
        await provenance.corpus(store)
        with pytest.raises(ServiceUnavailableException) as caught:
            await asyncio.to_thread(
                provenance.worker(lambda: store._execution_read("knowledge:item@version-one", as_pages=False))
            )
        assert caught.value.code == "EVIDENCE_BUDGET_EXCEEDED"
        assert not any(stage == "execution" for stage, *_ in observer.events)
        assert store.accessed == []


async def test_child_task_unleased_worker_and_closed_lease_cannot_borrow_a_corpus():
    module, observer, reader, _ = await _prepare()
    with provenance.observe(
        observer, tenant_id="north", workspace_id="native-workspace", actor="reader", source_ids=[]
    ):
        with curated_corpus.bind(
            tenant_id="north",
            workspace_id="native-workspace",
            actor="reader",
            retrieve=_retrieve,
            documents=False,
            rlm=reader,
        ):
            with pytest.raises(ServiceUnavailableException):
                await asyncio.create_task(
                    module.build_knowledge_store(tenant_id="north", workspace_id="native-workspace")
                )
            store = await module.build_knowledge_store(tenant_id="north", workspace_id="native-workspace")
            await provenance.corpus(store)
            with pytest.raises(ServiceUnavailableException):
                await asyncio.to_thread(lambda: store["knowledge:item@version-one"])
        with pytest.raises(ServiceUnavailableException):
            await asyncio.to_thread(provenance.worker(lambda: store["knowledge:item@version-one"]))
        assert reader.reads == 0


async def test_citations_only_resolve_loaded_exact_parts_with_no_document_page_identity():
    module, observer, reader, _ = await _prepare()
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
        store = await module.build_knowledge_store(tenant_id="north", workspace_id="native-workspace")
        await provenance.corpus(store)
        await provenance.authorize()
        assert store.citation_ref("knowledge:item@version-one", 0, "á") is None
        await asyncio.to_thread(
            provenance.worker(lambda: store._execution_read("knowledge:item@version-one", as_pages=True))
        )
        await provenance.authorize()
        result = store.citation_ref("knowledge:item@version-one", 1, "Exact tail")
        assert result.meta == reader.meta
        assert result.part_id == reader.view.parts[1].part_id
        assert not hasattr(result, "page") and not hasattr(result, "extraction_id")
        assert store.citation_ref("knowledge:item@version-one", 1, "Fabricated quote") is None
        assert store.citation_ref("knowledge:item@version-one", True, "Exact tail") is None


async def test_combined_corpus_keeps_identical_document_and_knowledge_names_distinct():
    module, observer, reader, _ = await _prepare()
    from flycanon.core.services.query.rlm.corpus import SourceMeta

    class Documents:
        accessed = []

        def keys(self):
            return ["knowledge:item@version-one"]

        def resolve(self, key):
            return SourceMeta(
                "doc",
                key,
                "Approved operating threshold",
                "text",
                "unused",
                "0" * 64,
                tenant_id="north",
                workspace_id="native-workspace",
            )

    with (
        provenance.observe(
            observer, tenant_id="north", workspace_id="native-workspace", actor="reader", source_ids=["doc"]
        ),
        curated_corpus.bind(
            tenant_id="north", workspace_id="native-workspace", actor="reader", retrieve=_retrieve, rlm=reader
        ),
    ):
        knowledge = await module.build_knowledge_store(tenant_id="north", workspace_id="native-workspace")
        store = module.CombinedCorpus(Documents(), knowledge)
        context = await provenance.corpus(store)
        assert "document:knowledge:item@version-one" in context
        assert "knowledge:item@version-one" in context
        await provenance.authorize()
        assert store.resolve("document:knowledge:item@version-one").source_id == "doc"
        assert store.resolve("knowledge:item@version-one").native_item_id == "native-item"
        assert reader.reads == 0


async def test_lease_expiration_while_body_is_pending_rejects_late_bytes_and_execution():
    module, observer, reader, _ = await _prepare()
    started, released = asyncio.Event(), asyncio.Event()
    original = reader.read

    async def pending(meta):
        started.set()
        await released.wait()
        return await original(meta)

    reader.read = pending
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
        store = await module.build_knowledge_store(tenant_id="north", workspace_id="native-workspace")
        await provenance.corpus(store)
        lease = curated_corpus.current_lease()

        async def expire():
            await started.wait()
            lease.active = False
            released.set()

        invalidation = asyncio.create_task(expire())
        with pytest.raises(ServiceUnavailableException):
            await asyncio.to_thread(
                provenance.worker(lambda: store._execution_read("knowledge:item@version-one", as_pages=False))
            )
        await invalidation
        assert store.accessed == []
    assert not any(stage in {"view", "execution"} for stage, *_ in observer.events)


async def test_owner_cancellation_does_not_turn_a_late_body_into_used_evidence():
    module, observer, reader, _ = await _prepare()
    started, released = asyncio.Event(), asyncio.Event()
    original = reader.read

    async def pending(meta):
        started.set()
        await released.wait()
        return await original(meta)

    reader.read = pending

    async def owner():
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
            store = await module.build_knowledge_store(tenant_id="north", workspace_id="native-workspace")
            await provenance.corpus(store)
            await asyncio.to_thread(
                provenance.worker(lambda: store._execution_read("knowledge:item@version-one", as_pages=False))
            )

    task = asyncio.create_task(owner())
    await started.wait()
    task.cancel()
    released.set()
    result = await asyncio.gather(task, return_exceptions=True)
    assert isinstance(result[0], asyncio.CancelledError)
    await asyncio.to_thread(lambda: None)
    assert not any(stage in {"view", "execution"} for stage, *_ in observer.events)
