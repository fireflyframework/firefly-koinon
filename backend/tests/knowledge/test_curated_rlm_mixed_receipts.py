# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""A valid document proof never masks a forged curated version, or the reverse."""

from asyncio import to_thread
from dataclasses import replace
from types import SimpleNamespace

import pytest
from flycanon.core.services.ingestion.loaders import default_registry
from flycanon.core.services.query import provenance
from flycanon.core.services.query.rlm.combined_corpus import CombinedCorpus
from flycanon.core.services.query.rlm.corpus import CanonDocStore
from flycanon.core.services.query.rlm.knowledge_corpus import build_knowledge_store
from flycanon.core.services.query.rlm_answer_service import _map_citations
from flycanon.core.services.retrieval import curated_corpus
from pyfly.kernel import ServiceUnavailableException
from test_curated_rlm_corpus import _retrieve
from test_curated_rlm_receipts import prepare
from test_rlm_recorded_provenance import meta, whole_read

from koinon.knowledge.rlm_provenance import verified_rlm_answer


@pytest.mark.parametrize("read_knowledge", [False, True])
async def test_mixed_domains_verify_independently_and_metadata_is_not_content_use(read_knowledge):
    receipt, knowledge, _, view = await prepare()
    document = replace(whole_read("An independently recorded document42"), source_id="document-native")
    source = replace(meta(), tenant_id="north", workspace_id="native-workspace", source_id="document-native")

    class Reader:
        async def read(self, scope, **arguments):
            await arguments["authorize"]()
            return document

    documents = CanonDocStore(
        {"controlled": source},
        object_store=SimpleNamespace(),
        registry=default_registry(),
        whole_reader=Reader(),
    )
    asset = SimpleNamespace(
        id="document-asset", workspace_id="canonical-workspace", name="Recorded document", kind="document"
    )
    parent = SimpleNamespace(id="document-parent")
    binding = SimpleNamespace(native_id="document-native", native_workspace_id="native-workspace")
    receipt.admit_documents("north", "native-workspace", "reader", {"document-native": (asset, parent)})
    with (
        provenance.observe(
            receipt,
            tenant_id="north",
            workspace_id="native-workspace",
            actor="reader",
            source_ids=["document-native"],
        ),
        curated_corpus.bind(
            tenant_id="north",
            workspace_id="native-workspace",
            actor="reader",
            retrieve=_retrieve,
            rlm=knowledge,
        ),
    ):
        corpus = CombinedCorpus(
            documents, await build_knowledge_store(tenant_id="north", workspace_id="native-workspace")
        )
        await provenance.corpus(corpus)

        def execute():
            provenance.model("rlm.root", "The document and published knowledge metadata")
            corpus._execution_read("document:controlled", as_pages=False)
            if read_knowledge:
                corpus._execution_read("knowledge:item@version-one", as_pages=False)

        await to_thread(provenance.worker(execute))
        await provenance.authorize()
        engine_citations = [{"filing": "document:controlled", "page": 0, "content": "document42"}]
        if read_knowledge:
            engine_citations.append(
                {"filing": "knowledge:item@version-one", "page": 1, "content": "Exact tail"}
            )
        hits = _map_citations(engine_citations, corpus)
    citations = []
    for hit in hits:
        row = hit.model_dump()
        if hit.source_kind == "knowledge_version":
            row.update(
                asset_id="item",
                source_id=None,
                knowledge_item_id="item",
                knowledge_version_id="version-one",
                knowledge_version=1,
            )
        else:
            row.update(asset_id="document-asset", source_id="document-parent")
        citations.append(row)
    data = {"answer": "Grounded mixed answer", "citations": citations}
    admitted = {("native-workspace", "document-native"): ([asset, parent], binding)}
    assert verified_rlm_answer(receipt, data, admitted)
    if not read_knowledge:
        assert not receipt.curated_rlm.views and not receipt.knowledge_sources
        assert any(row.domain == "knowledge" and row.stage == "rlm.root" for row in receipt.native_reads)
    else:
        data["citations"][1]["knowledge_version_id"] = "unread-version"
        with pytest.raises(ServiceUnavailableException):
            verified_rlm_answer(receipt, data, admitted)
        data["citations"][1]["knowledge_version_id"] = view.meta.version_id
    data["citations"][0]["metadata"]["source_part_sha256"] = "f" * 64
    with pytest.raises(ServiceUnavailableException):
        verified_rlm_answer(receipt, data, admitted)
