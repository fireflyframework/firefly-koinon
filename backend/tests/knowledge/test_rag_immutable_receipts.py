# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from dataclasses import replace
from hashlib import sha256
from types import SimpleNamespace

import pytest
from flycanon.core.services.query.provenance import before_model, current, observe
from flycanon.core.services.retrieval.retrieval_service import Hit
from pyfly.kernel import ServiceUnavailableException

from koinon.catalog.errors import AccessDenied
from koinon.knowledge.capture_receipt import NativeEvidenceReceipt
from koinon.knowledge.evidence_capture import NativeKnowledgeEvidence, document_reference


def hit():
    return Hit("projection", "native-source", None, None, "Recorded threshold47", 1.0, None, None, {})


def recorded(value):
    return replace(
        value,
        metadata={
            "source_version_id": "version",
            "extraction_id": "ingestion",
            "source_part_id": "part",
            "source_part_sha256": sha256(value.content.encode()).hexdigest(),
            "source_part_kind": "chunk",
            "projection_chunk_id": value.chunk_id,
            "page_basis": "recorded_loader",
            "recorded_page": "7",
            "_observed_source_filename": "original.pdf",
        },
    )


def receipt():
    value = NativeEvidenceReceipt("owner", "tenant")
    value.canonical_documents[("native-space", "native-source")] = "asset"

    async def authorize():
        return None

    async def resolve(hits, scope):
        return [recorded(value) for value in hits]

    value.authorize_model = authorize
    value.resolve_document_retrieval_parts = resolve
    return value


async def bind(value, hits):
    return await value.document_retrieval_parts(hits, current())


async def test_trusted_retrieval_keeps_projection_id_and_captures_distinct_immutable_part():
    value = receipt()
    with observe(
        value, tenant_id="tenant", workspace_id="native-space", actor="owner", source_ids=["native-source"]
    ):
        (found,) = await bind(value, [hit()])
        await before_model(
            "answer", "Exact model context", [found], tenant_id="tenant", workspace_id="native-space"
        )
    source = document_reference(
        value.documents["projection"], asset_id="asset", source_id="source", title="Recorded title"
    )
    assert source.chunk_id is None and source.source_part_id == "part"
    assert (source.source_version_id, source.extraction_id, source.recorded_page) == (
        "version",
        "ingestion",
        7,
    )
    assert source.quote == "Recorded threshold47"
    read = value.native_reads[-1]
    assert (read.stage, read.read_kind, read.source_version_id, read.extraction_id) == (
        "answer",
        "document_extraction",
        "version",
        "ingestion",
    )
    assert read.content_sha256 == sha256(b"Exact model context").hexdigest()


async def test_untrusted_chunk_metadata_cannot_assert_a_distinct_immutable_part():
    value = receipt()
    with (
        observe(
            value,
            tenant_id="tenant",
            workspace_id="native-space",
            actor="owner",
            source_ids=["native-source"],
        ),
        pytest.raises(ServiceUnavailableException),
    ):
        await before_model(
            "answer", "forged", [recorded(hit())], tenant_id="tenant", workspace_id="native-space"
        )
    assert value.documents == {} and value.native_reads == []


@pytest.mark.parametrize("change", ["text", "extraction"])
async def test_bound_chunk_cannot_change_before_model_or_rebind_to_another_extraction(change):
    value = receipt()
    with observe(
        value, tenant_id="tenant", workspace_id="native-space", actor="owner", source_ids=["native-source"]
    ):
        (found,) = await bind(value, [hit()])
        if change == "text":
            found = replace(found, content="Unrecorded replacement")
            with pytest.raises(ServiceUnavailableException):
                await before_model(
                    "answer", "replacement", [found], tenant_id="tenant", workspace_id="native-space"
                )
        else:

            async def other_extraction(hits, scope):
                return [
                    replace(
                        recorded(hits[0]),
                        metadata={
                            **recorded(hits[0]).metadata,
                            "extraction_id": "another-ingestion",
                        },
                    )
                ]

            value.resolve_document_retrieval_parts = other_extraction
            with pytest.raises(ServiceUnavailableException):
                await bind(value, [hit()])
    assert value.documents == {} and value.native_reads == []


@pytest.mark.parametrize("change", ["content", "part", "scope", "owner", "closed"])
async def test_retrieval_binding_rejects_changed_or_expired_authority(change):
    import asyncio

    value = receipt()

    async def resolve(hits, scope):
        found = recorded(hits[0])
        if change == "content":
            found = replace(found, content="Changed content")
        if change == "part":
            found.metadata["source_part_sha256"] = "a" * 64
        return [found]

    value.resolve_document_retrieval_parts = resolve
    if change == "scope":
        value.canonical_documents.clear()
    if change == "closed":
        value.closed = True
    with (
        observe(
            value,
            tenant_id="tenant",
            workspace_id="native-space",
            actor="owner",
            source_ids=["native-source"],
        ),
        pytest.raises((AccessDenied, ServiceUnavailableException)),
    ):
        if change == "owner":
            await asyncio.create_task(bind(value, [hit()]))
        else:
            await bind(value, [hit()])
    assert value.documents == {} and value.native_reads == []


@pytest.mark.parametrize("answer", [False, True])
async def test_ordinary_search_and_answer_capture_observed_parts_without_model_citations(answer):
    value = receipt()
    asset = SimpleNamespace(id="asset", kind="document", name="Recorded title", workspace_id="space")
    source = SimpleNamespace(id="source")
    binding = SimpleNamespace(native_id="native-source", native_workspace_id="native-space")

    async def chain(*args):
        return [asset, source]

    async def bound(*args, **kwargs):
        return binding

    async def parts(**kwargs):
        assert (
            kwargs["source_id"],
            kwargs["source_version_id"],
            kwargs["extraction_id"],
            kwargs["part_ids"],
        ) == ("native-source", "version", "ingestion", ("part",))
        return (
            SimpleNamespace(
                part_id="part",
                source_id="native-source",
                source_version_id="version",
                extraction_id="ingestion",
                ingestion_extraction_id="ingestion",
                sha256=sha256(b"Recorded threshold47").hexdigest(),
                text="Recorded threshold47",
                page=7,
            ),
        )

    async def search(subject, tenant, **kwargs):
        capture = kwargs["_capture"]
        capture.canonical_documents.update(value.canonical_documents)
        capture.resolve_document_retrieval_parts = value.resolve_document_retrieval_parts
        capture.authorize_model = value.authorize_model
        with observe(
            capture,
            tenant_id=tenant,
            workspace_id="native-space",
            actor=subject,
            source_ids=["native-source"],
        ):
            (found,) = await bind(capture, [hit()])
            capture.document_read_hits([found], current())
            if answer:
                await before_model(
                    "answer",
                    "Recorded model-visible context",
                    [found],
                    tenant_id=tenant,
                    workspace_id="native-space",
                )
        return {
            "hits": [{"id": "projection", "asset_id": "asset", "source_id": "source", "text": found.content}],
            "answer": "threshold47",
            "citations": [],
        }

    knowledge = SimpleNamespace(
        _chain=chain, binding=bound, search=search, domains=SimpleNamespace(document_parts=parts)
    )
    captured = await NativeKnowledgeEvidence(knowledge, None).search("owner", "tenant", answer=answer)
    assert captured.complete and captured.rlm_tools is None
    assert captured.sources[0].source_part_id == "part"
    assert [read.stage for read in captured.native_reads] == (
        ["retrieval", "answer"] if answer else ["retrieval"]
    )


async def test_answer_without_a_host_observed_model_context_never_becomes_complete():
    from test_evidence_capture import prepared

    service, _, _, data = prepared()
    data.update(answer="Model claims an answer", citations=[{"source_part_id": "invented"}])
    captured = await service.search("owner", "tenant", answer=True)
    assert not captured.complete


async def test_native_adapter_keeps_immutable_receipt_after_public_hit_projection(monkeypatch):
    from flycanon.core.services.query import provenance
    from flycanon.core.services.query.search_service import _hit_dto
    from flycanon.core.services.sources.lineage import retrieval
    from flycanon.core.services.sources.lineage.service import DocumentLineage
    from flycanon.core.services.storage.object_store import ObjectStore
    from flycanon.models.repositories import SourceRepository
    from pyfly.cqrs import DefaultQueryBus
    from test_native_knowledge_settings import domains

    adapter, _, _, beans = domains()
    beans[DocumentLineage] = object()
    beans[SourceRepository] = object()
    beans[ObjectStore] = object()

    async def exact(lineage, scope, hits):
        assert lineage is beans[DocumentLineage]
        assert (scope.tenant_id, scope.workspace_id, scope.actor) == ("tenant", "native-space", "owner")
        return [recorded(value) for value in hits]

    async def query(request):
        (found,) = await provenance.bind_retrieval_parts([hit()])
        provenance.hydrated([found])
        return {"hits": [_hit_dto(found).model_dump(mode="json")]}

    monkeypatch.setattr(retrieval, "bind_retrieval_parts", exact)
    beans[DefaultQueryBus] = SimpleNamespace(query=query)
    value = receipt()
    data = await adapter.search(
        tenant_id="tenant",
        workspace_id="native-space",
        source_ids=["native-source"],
        actor="owner",
        question="threshold?",
        limit=5,
        answer=False,
        _capture=value,
    )
    assert data["hits"][0]["chunk_id"] == "projection"
    assert value.documents["projection"].source_part_id == "part"
    assert value.source_origins["native-source"].original_filename == "original.pdf"


async def test_empty_hydration_does_not_require_immutable_document_resources():
    from flycanon.core.services.query import provenance
    from pyfly.cqrs import DefaultQueryBus
    from test_native_knowledge_settings import domains

    adapter, _, _, beans = domains()

    async def query(request):
        assert await provenance.bind_retrieval_parts([]) == []
        return {"hits": []}

    beans[DefaultQueryBus] = SimpleNamespace(query=query)
    data = await adapter.search(
        tenant_id="tenant",
        workspace_id="native-space",
        source_ids=["native-source"],
        actor="owner",
        question="empty?",
        limit=5,
        answer=False,
        _capture=receipt(),
    )
    assert data == {"hits": []}
