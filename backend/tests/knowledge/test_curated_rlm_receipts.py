# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Actual curated code input has a separate, complete immutable receipt domain."""

from asyncio import to_thread
from dataclasses import replace
from types import SimpleNamespace

import pytest
from flycanon.core.services.query import provenance
from flycanon.core.services.retrieval import curated_corpus
from pyfly.kernel import ServiceUnavailableException
from test_curated_rlm_corpus import Reader, _retrieve
from test_curated_whole_views import _inputs

from koinon.knowledge.capture_dtos import NativeCaptureLimits
from koinon.knowledge.capture_receipt import NativeEvidenceReceipt


async def prepare(*, limits=None):
    mapper, _, value, selected, meta, parts = _inputs()
    view = mapper.whole_view(meta, value.selected_version.content.body, parts)
    reader = Reader(meta, view)
    receipt = NativeEvidenceReceipt("reader", "north", limits=limits)

    async def authorized():
        return None

    receipt.authorize_model = authorized
    receipt.admit_knowledge(
        "north",
        "native-workspace",
        "reader",
        {"native-item": (SimpleNamespace(id="item", workspace_id="canonical-workspace"), None)},
        (selected,),
    )
    return receipt, reader, meta, view


async def consume(receipt, reader, *, execute=True):
    from flycanon.core.services.query.rlm.knowledge_corpus import build_knowledge_store

    with (
        provenance.observe(
            receipt, tenant_id="north", workspace_id="native-workspace", actor="reader", source_ids=[]
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
        store = await build_knowledge_store(tenant_id="north", workspace_id="native-workspace")
        await provenance.corpus(store)

        def model_input():
            provenance.model("rlm.root", "Exact metadata and question")
            key = store.keys()[0]
            return store._execution_read(key, as_pages=False) if execute else store[key]

        await to_thread(provenance.worker(model_input))
    return store


async def test_full_knowledge_view_records_parts_manifest_execution_without_document_identity():
    receipt, reader, meta, view = await prepare()
    await consume(receipt, reader)
    assert receipt.documents == {} and receipt.document_extractions == {}
    assert len(receipt.knowledge_sources) == len(view.parts)
    assert "".join(source.quote for source in receipt.knowledge_sources.values()) == view.text
    for source in receipt.knowledge_sources.values():
        assert source.asset_id == source.knowledge_item_id == "item"
        assert source.knowledge_version_id == "version-one" and source.knowledge_version == 1
        assert source.source_id is None and source.page is None
        assert source.source_version_id is source.extraction_id is source.source_part_id is None
    reads = receipt.native_reads
    assert {row.stage for row in reads} == {
        "rlm.corpus",
        "rlm.root",
        "rlm.knowledge_view.v1",
        "rlm.read",
        "rlm.execution_read.v1",
    }
    manifest = next(row for row in reads if row.stage == "rlm.knowledge_view.v1")
    assert manifest.content_sha256 == view.manifest_sha256
    released = next(row for row in reads if row.stage == "rlm.execution_read.v1")
    assert released.content_sha256 == meta.body_sha256
    assert all(
        row.domain == "knowledge"
        and row.workspace_id == "canonical-workspace"
        and row.source_ids == ("item",)
        and row.knowledge_version_id == "version-one"
        for row in reads
    )


async def test_hydration_does_not_claim_execution_or_publish_knowledge():
    receipt, reader, _, _ = await prepare()
    await consume(receipt, reader, execute=False)
    assert not any(row.stage == "rlm.execution_read.v1" for row in receipt.native_reads)
    from koinon.knowledge.curated.rlm_receipts import execution_views

    assert not execution_views(receipt)


@pytest.mark.parametrize(
    "changes",
    [
        {"version_id": "forged-version"},
        {"version": 2},
        {"item_id": "other"},
        {"native_item_id": "foreign-native"},
        {"workspace_id": "other-native-space"},
        {"canonical_workspace_id": "other-space"},
        {"tenant_id": "other"},
    ],
)
async def test_metadata_cannot_replace_admitted_scope_or_ack_version(changes):
    receipt, reader, meta, _ = await prepare()
    reader.meta = replace(meta, **changes)
    with pytest.raises(ServiceUnavailableException):
        await consume(receipt, reader)
    assert not receipt.knowledge_sources and not receipt.documents


async def test_forged_or_incomplete_view_cannot_release_body_or_mutate_receipt():
    receipt, reader, _, view = await prepare()
    reader.view = replace(view, parts=view.parts[:-1])
    with pytest.raises(ServiceUnavailableException):
        await consume(receipt, reader)
    assert not receipt.knowledge_sources
    assert not any(row.stage in {"rlm.read", "rlm.execution_read.v1"} for row in receipt.native_reads)


async def test_budget_reserves_all_parts_and_reads_before_body_is_returned():
    receipt, reader, _, _ = await prepare(limits=NativeCaptureLimits(sources=1))
    with pytest.raises(ServiceUnavailableException) as caught:
        await consume(receipt, reader)
    assert caught.value.code == "EVIDENCE_BUDGET_EXCEEDED"
    assert not receipt.knowledge_sources
    assert {row.stage for row in receipt.native_reads} == {"rlm.corpus", "rlm.root"}


def answer(view):
    source = next(iter(view.parts))
    return {
        "answer": "Approved answer",
        "citations": [
            {
                "asset_id": "item",
                "source_id": None,
                "source_kind": "knowledge_version",
                "kind": "knowledge_version",
                "knowledge_item_id": "item",
                "knowledge_version_id": view.meta.version_id,
                "knowledge_version": view.meta.version,
                "chunk_id": source.part_id,
                "content": source.text[:100],
                "page": None,
                "metadata": {
                    "knowledge_content_sha256": view.meta.content_sha256,
                    "knowledge_part_sha256": source.sha256,
                },
            }
        ],
    }


async def test_final_knowledge_answer_requires_actual_execution_and_exact_citation():
    from koinon.knowledge.rlm_provenance import verified_rlm_answer

    receipt, reader, _, view = await prepare()
    await consume(receipt, reader)
    assert verified_rlm_answer(receipt, answer(view), {})
    for field, value in [
        ("knowledge_version_id", "different"),
        ("knowledge_version", 2),
        ("source_id", "guessed-document"),
        ("page", 1),
        ("content", "Fabricated quote"),
    ]:
        data = answer(view)
        data["citations"][0][field] = value
        with pytest.raises(ServiceUnavailableException):
            verified_rlm_answer(receipt, data, {})


async def test_loaded_or_metadata_only_knowledge_cannot_become_cited_execution():
    from koinon.knowledge.rlm_provenance import verified_rlm_answer

    receipt, reader, _, view = await prepare()
    await consume(receipt, reader, execute=False)
    assert not verified_rlm_answer(receipt, answer(view), {})


async def test_missing_manifest_or_wrong_fingerprint_never_verifies_an_answer():
    from koinon.knowledge.rlm_provenance import verified_rlm_answer

    for mode in ("manifest", "body", "execution", "root"):
        receipt, reader, _, view = await prepare()
        await consume(receipt, reader)
        stages = {
            "manifest": "rlm.knowledge_view.v1",
            "body": "rlm.read",
            "execution": "rlm.execution_read.v1",
            "root": "rlm.root",
        }
        receipt.native_reads = [row for row in receipt.native_reads if row.stage != stages[mode]]
        if mode in {"manifest", "body"}:
            with pytest.raises(ServiceUnavailableException):
                verified_rlm_answer(receipt, answer(view), {})
        else:
            assert not verified_rlm_answer(receipt, answer(view), {})


async def test_curated_only_tools_keep_document_scope_empty_and_canonical_knowledge_scope_explicit():
    from test_rlm_tool_receipts import tool

    receipt, reader, _, _ = await prepare()
    from flycanon.core.services.query.rlm.knowledge_corpus import build_knowledge_store

    with (
        provenance.observe(
            receipt, tenant_id="north", workspace_id="native-workspace", actor="reader", source_ids=[]
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
        store = await build_knowledge_store(tenant_id="north", workspace_id="native-workspace")
        await provenance.corpus(store)

        def execute():
            provenance.before_tool()
            provenance.tool(tool())

        await to_thread(provenance.worker(execute))
    assert len(receipt.rlm_tools) == 1
    assert receipt.rlm_tools[0].source_ids == ()
    assert receipt.rlm_tools[0].knowledge_item_ids == ("item",)


async def test_native_citation_mapper_keeps_curated_parts_separate_from_document_pages():
    from flycanon.core.services.query.rlm.knowledge_corpus import build_knowledge_store
    from flycanon.core.services.query.rlm_answer_service import _map_citations

    receipt, reader, meta, view = await prepare()
    with (
        provenance.observe(
            receipt, tenant_id="north", workspace_id="native-workspace", actor="reader", source_ids=[]
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
        store = await build_knowledge_store(tenant_id="north", workspace_id="native-workspace")
        await provenance.corpus(store)
        await provenance.authorize()
        key = store.keys()[0]
        await to_thread(provenance.worker(lambda: store._execution_read(key, as_pages=True)))
        await provenance.authorize()
        hits = _map_citations([{"filing": key, "page": 1, "content": "Exact tail"}], store)
        assert len(hits) == 1
        hit = hits[0]
        assert hit.source_id == meta.native_item_id
        assert hit.source_kind == "knowledge_version" and hit.page is None
        assert hit.knowledge_item_id == meta.native_item_id and hit.knowledge_version == meta.version
        assert hit.chunk_id == view.parts[1].part_id
        assert hit.metadata["knowledge_content_sha256"] == meta.content_sha256
        assert hit.metadata["knowledge_part_sha256"] == view.parts[1].sha256
        assert not _map_citations([{"filing": key, "page": 1, "content": "Invented quote"}], store)
