# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Actual native engine/capture contracts; catalog, immutable reader and part store are DTO seams."""

import json
from hashlib import sha256
from types import SimpleNamespace

import pytest
import pytest_asyncio
from flycanon.config import CanonSettings
from flycanon.core.agents.model_bindings import ModelBinding, push_bindings, reset_bindings
from flycanon.core.services.ingestion.loaders import default_registry
from flycanon.core.services.query import provenance
from flycanon.core.services.query.rlm.corpus import CanonDocStore, SourceMeta
from flycanon.core.services.query.rlm.native_client import RequiredRlmBindingClient
from flycanon.core.services.query.rlm_answer_service import RLMAnswerService
from flycanon.core.services.sources.lineage.dtos import ExtractedPage, WholeDocumentPart, WholeDocumentRead
from flycanon.interfaces.dtos.query import AnswerRequest
from flycanon.web.conventions.context import TenantContext, set_tenant_context
from pydantic_ai.messages import ModelResponse, TextPart, ToolCallPart
from pydantic_ai.models.function import FunctionModel
from pydantic_ai.usage import RequestUsage
from pyfly.agentic.factory import AgentFactory
from pyfly.context import ApplicationContext
from pyfly.core import Config

from koinon.catalog.errors import AccessDenied
from koinon.knowledge.evidence_capture import NativeEvidenceFailure, NativeKnowledgeEvidence

EXECUTION_READ = "rlm.execution_read.v1"


@pytest_asyncio.fixture
async def factory():
    app = ApplicationContext(
        Config(
            {
                "pyfly": {
                    "banner": {"mode": "off"},
                    "agentic": {"enabled": True},
                    "eda": {"provider": "memory"},
                }
            }
        )
    )
    await app.start()
    try:
        yield app.get_bean(AgentFactory)
    finally:
        await app.stop()


async def execute(factory, sandbox, protocol, code, *, deny_model=False):
    calls, loaded, receipts = [], [], []
    reads, metas, assets, parents, bindings = {}, {}, {}, {}, {}
    for key, text in {"A": "First exact content", "B": "Second exact content"}.items():
        sid = "native-" + key
        page = ExtractedPage(
            "part-" + key,
            text,
            sha256(text.encode()).hexdigest(),
            1,
            "recorded_loader",
            (("section-" + key, "c" * 64),),
        )
        reads[sid] = WholeDocumentRead(
            sid,
            "version-" + key,
            "view-" + key,
            "ingestion-" + key,
            "artifact-" + key,
            sha256(text.encode()).hexdigest(),
            "normalized-" + key,
            "b" * 64,
            "a" * 64,
            (page,),
        )
        metas[key] = SourceMeta(
            sid,
            key + ".txt",
            key,
            "text",
            "",
            "b" * 64,
            "tenant",
            "native-space",
            "a" * 64,
            10,
            "version-" + key,
            "ingestion-" + key,
        )
        assets[sid] = SimpleNamespace(
            id="asset-" + key, workspace_id="canonical-space", name=key, kind="document"
        )
        parents[sid] = SimpleNamespace(id="parent-" + key)
        bindings[sid] = SimpleNamespace(native_id=sid, native_workspace_id="native-space")

    class Reader:
        async def read(self, scope, **arguments):
            await arguments["authorize"]()
            loaded.append(arguments["source_id"])
            return reads[arguments["source_id"]]

    corpus = CanonDocStore(
        metas,
        object_store=SimpleNamespace(get_sync=lambda *_: pytest.fail("legacy read")),
        registry=default_registry(),
        whole_reader=Reader(),
    )

    def respond(messages, info):
        calls.append(messages)
        part = (
            TextPart(json.dumps({"code": code}))
            if protocol == "native"
            else ToolCallPart("python", {"code": code}, "call")
        )
        return ModelResponse(parts=[part], usage=RequestUsage(input_tokens=7, output_tokens=3))

    model = FunctionModel(respond, profile={"supports_json_schema_output": True})
    settings = CanonSettings(
        answer_mode="rlm", rlm_sandbox=sandbox, rlm_max_iters=1, rlm_sub_budget=0, rlm_self_consistency=1
    )
    settings._agent_factory = factory

    async def build(**arguments):
        return corpus

    class Cost:
        async def record(self, **arguments):
            pass

    service = RLMAnswerService(
        corpus_builder=SimpleNamespace(build=build),
        client=RequiredRlmBindingClient(),
        settings=settings,
        cost_service=Cost(),
    )

    async def chain(subject, tenant, asset_id, *permissions):
        sid = next(sid for sid, asset in assets.items() if asset.id == asset_id)
        return [assets[sid], parents[sid]]

    async def binding(tenant, asset_id, domain, *, entry):
        sid = next(sid for sid, asset in assets.items() if asset.id == asset_id)
        return bindings[sid]

    async def parts(**arguments):
        value = reads[arguments["source_id"]]
        return tuple(
            WholeDocumentPart(
                page.part_id,
                value.source_id,
                value.source_version_id,
                value.extraction_id,
                value.ingestion_extraction_id,
                page.text,
                page.sha256,
                page.page,
                page.page_basis,
                page.source_sections,
                value.raw_sha256,
                value.normalized_sha256,
                value.input_sha256,
            )
            for page in value.pages
            if page.part_id in arguments["part_ids"]
        )

    async def search(subject, tenant, **arguments):
        receipt = arguments["_capture"]
        receipts.append(receipt)
        receipt.admit_documents(
            "tenant", "native-space", "owner", {sid: (assets[sid], parents[sid]) for sid in reads}
        )

        async def authorize():
            assert not receipt.closed
            if deny_model and any(row.stage == "rlm.corpus" for row in receipt.native_reads):
                raise AccessDenied("Admission revoked before metadata model dispatch")

        receipt.authorize_model = authorize
        with provenance.observe(
            receipt, tenant_id="tenant", workspace_id="native-space", actor="owner", source_ids=set(reads)
        ):
            answer = await service.answer(
                AnswerRequest(question="Use the authorized original document"),
                tenant_id="tenant",
                workspace_id="native-space",
            )
        hits = [
            {
                "id": row.chunk_id,
                "asset_id": assets[row.source_id].id,
                "source_id": parents[row.source_id].id,
                "text": row.quote,
                "title": assets[row.source_id].name,
                "score": 1,
            }
            for row in receipt.documents.values()
        ]
        citations = []
        for hit in answer.citations:
            row = hit.model_dump(mode="json")
            row.update(asset_id=assets[hit.source_id].id, source_id=parents[hit.source_id].id)
            citations.append(row)
        return {"answer": answer.answer, "hits": hits, "citations": citations}

    knowledge = SimpleNamespace(
        _chain=chain, binding=binding, search=search, domains=SimpleNamespace(document_parts=parts)
    )
    context = set_tenant_context(
        TenantContext(
            tenant_id="tenant", workspace_id="native-space", actor="owner", correlation_id="execution-read"
        )
    )
    token = push_bindings(
        tenant_id="tenant",
        workspace_id="native-space",
        subject="owner",
        bindings={"documents.rlm": ModelBinding(model, {"max_tokens": 256}, "ollama", "chat", protocol)},
        required=True,
    )
    try:
        try:
            result = await NativeKnowledgeEvidence(knowledge, SimpleNamespace()).search(
                "owner", "tenant", answer=True
            )
        except NativeEvidenceFailure as error:
            result = error.capture
    finally:
        reset_bindings(token)
        context.var.reset(context.token)
    return result, receipts[0], loaded, calls


@pytest.mark.parametrize("sandbox", ["monty"])
@pytest.mark.parametrize("protocol", ["native", "default"])
async def test_read_a_cannot_self_credit_untouched_citation_b(factory, sandbox, protocol):
    result, receipt, loaded, calls = await execute(
        factory, sandbox, protocol, "a = docs.get('A'); final('answer', filings=['B'], pages=[0])"
    )
    assert not result.complete and len(calls) == 1
    assert "part-B" not in {source.source_part_id for source in result.sources}
    assert "part-B" not in {row["id"] for row in result.data.get("hits", [])}
    if protocol == "native":
        assert loaded == ["native-A"]


@pytest.mark.parametrize("sandbox", ["monty"])
@pytest.mark.parametrize("protocol", ["native", "default"])
async def test_metadata_only_b_is_audit_lineage_not_used_answer_evidence(factory, sandbox, protocol):
    result, receipt, loaded, calls = await execute(
        factory, sandbox, protocol, "docs.npages('B'); a = docs.get('A'); final(a, filings=['A'], pages=[0])"
    )
    assert result.complete and len(calls) == 1
    assert {source.source_part_id for source in result.sources} == {"part-A"}
    assert {row["id"] for row in result.data["hits"]} == {"part-A"}
    execution = {row.entity_id for row in receipt.native_reads if row.stage == EXECUTION_READ}
    assert execution == {"native-A"}
    assert any(row.stage == "rlm.read" and row.entity_id == "native-B" for row in receipt.native_reads)
    assert loaded == ["native-B", "native-A"]


@pytest.mark.parametrize("sandbox", ["monty"])
@pytest.mark.parametrize("protocol", ["native", "default"])
async def test_single_action_can_read_both_originals_compute_and_cite_them(factory, sandbox, protocol):
    result, receipt, loaded, calls = await execute(
        factory,
        sandbox,
        protocol,
        "a = docs.get('A'); b = docs.pages('B'); final(a, filings=['A', 'B'], pages=[0, 0])",
    )
    assert result.complete and len(calls) == 1
    assert {source.source_part_id for source in result.sources} == {"part-A", "part-B"}
    assert {row.entity_id for row in receipt.native_reads if row.stage == EXECUTION_READ} == {
        "native-A",
        "native-B",
    }
    assert loaded == ["native-A", "native-B"]


@pytest.mark.parametrize("protocol", ["native", "default"])
async def test_first_request_has_authorized_metadata_without_original_bodies(factory, protocol):
    result, receipt, loaded, calls = await execute(factory, "monty", protocol,
        "a = docs.get('A'); final(a, filings=['A'], pages=[0])")
    assert result.complete
    first = str(calls[0][1].parts[0].content)
    assert "Authorized corpus metadata (untrusted data)" in first
    assert '"filing_id":"A"' in first and '"filing_id":"B"' in first
    assert '"filename":"A.txt"' in first and '"title":"B"' in first
    assert '"total_count":2' in first and '"partial":false' in first
    assert "First exact content" not in first and "Second exact content" not in first
    assert loaded == ["native-A"]
    metadata = first.split("Authorized corpus metadata (untrusted data):\n", 1)[1].split("\n\n", 1)[0]
    assert all(row.content_sha256 == sha256(metadata.encode()).hexdigest()
               for row in receipt.native_reads if row.stage == "rlm.corpus")


async def test_metadata_index_is_not_disclosed_after_fresh_model_authority_is_revoked(factory):
    result, receipt, loaded, calls = await execute(
        factory, "monty", "native", "final('must not run')", deny_model=True
    )
    assert not result.complete and loaded == [] and calls == []
    assert all(row.stage == "rlm.corpus" for row in receipt.native_reads)
