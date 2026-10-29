# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Actual lazy corpus/receiver guards; provider inference and knowledge writes are absent."""

import asyncio
from contextvars import copy_context
from dataclasses import replace
from hashlib import sha256
from threading import Event, Thread
from types import SimpleNamespace

import pytest
from flycanon.core.services.ingestion.loaders import default_registry
from flycanon.core.services.query import provenance
from flycanon.core.services.query.rlm.corpus import CanonDocStore, SourceMeta
from flycanon.core.services.sources.lineage.dtos import ExtractedPage, WholeDocumentPart, WholeDocumentRead
from pyfly.kernel import ServiceUnavailableException

from koinon.catalog.errors import AccessDenied
from koinon.knowledge.capture_dtos import NativeCaptureLimits
from koinon.knowledge.capture_receipt import NativeEvidenceReceipt
from koinon.knowledge.evidence_capture import NativeEvidenceFailure, NativeKnowledgeEvidence


def whole_read(*texts):
    texts = texts or ("Exact committed view",)
    return WholeDocumentRead(
        "native-source",
        "version",
        "view",
        "ingestion",
        "view-artifact",
        sha256("\n".join(texts).encode()).hexdigest(),
        "normalized-artifact",
        "b" * 64,
        "a" * 64,
        tuple(
            ExtractedPage(
                f"part-{index}",
                text,
                sha256(text.encode()).hexdigest(),
                index + 2,
                "recorded_loader",
                ((f"section-{index}", "c" * 64),),
            )
            for index, text in enumerate(texts)
        ),
    )


def meta():
    return SourceMeta(
        "native-source",
        "controlled.txt",
        "Controlled",
        "text",
        "",
        "b" * 64,
        "tenant",
        "native-space",
        "a" * 64,
        10,
        "version",
        "ingestion",
    )


class Reader:
    def __init__(self, value):
        self.value = value
        self.started = None
        self.release = None

    async def read(self, scope, **values):
        assert (scope.tenant_id, scope.workspace_id, scope.actor) == ("tenant", "native-space", "owner")
        assert (values["source_id"], values["source_version_id"], values["ingestion_extraction_id"]) == (
            "native-source",
            "version",
            "ingestion",
        )
        await values["authorize"]()
        if self.started is not None:
            self.started.set()
            await self.release.wait()
        return self.value


def store(value, *, source=None, reader=None):
    return CanonDocStore(
        {"controlled": source or meta()},
        object_store=SimpleNamespace(
            get_sync=lambda *_: pytest.fail("Recorded product reads must not load a legacy original")
        ),
        registry=default_registry(),
        whole_reader=reader or Reader(value),
    )


def admit(receipt):
    asset = SimpleNamespace(id="asset", workspace_id="space", name="Controlled", kind="document")
    source = SimpleNamespace(id="source")
    receipt.admit_documents("tenant", "native-space", "owner", {"native-source": (asset, source)})

    async def authorize():
        if receipt.closed:
            raise AccessDenied("Closed")

    receipt.authorize_model = authorize
    return asset, source


async def consume(receipt, corpus, *, record_model=True):
    with provenance.observe(
        receipt, tenant_id="tenant", workspace_id="native-space", actor="owner", source_ids={"native-source"}
    ):
        await provenance.corpus(corpus)

        @provenance.worker
        def read():
            if record_model:
                provenance.model("rlm.root", "The admitted corpus metadata")
            pages = corpus.pages("controlled")
            if record_model:
                provenance.model("rlm.forced_final", "Actual model input: " + "\n".join(pages))
            return pages

        return await asyncio.to_thread(read)


async def test_recorded_parts_are_admitted_before_corpus_returns_bytes_with_full_and_quote_hashes():
    value = whole_read("x" * 9000, "Exact second page")
    receipt = NativeEvidenceReceipt("owner", "tenant")
    admit(receipt)
    assert await consume(receipt, store(value)) == [page.text for page in value.pages]
    assert set(receipt.documents) == {"part-0", "part-1"}
    observed = receipt.documents["part-0"]
    assert observed.quote == "x" * 8000 and observed.digest == sha256(("x" * 8000).encode()).hexdigest()
    assert observed.source_part_sha256 == sha256(("x" * 9000).encode()).hexdigest()
    assert (
        observed.source_version_id,
        observed.extraction_id,
        observed.source_part_id,
        observed.recorded_page,
        observed.page,
    ) == ("version", "view", "part-0", 2, None)
    read = next(row for row in receipt.native_reads if row.stage == "rlm.read")
    assert read.content_sha256 == sha256("\n".join(page.text for page in value.pages).encode()).hexdigest()
    assert read.read_kind == "document_extraction" and read.extraction_id == "view"


@pytest.mark.parametrize(
    "change",
    [
        {"source_id": "foreign"},
        {"source_version_id": "other"},
        {"ingestion_extraction_id": "other"},
        {"raw_sha256": "d" * 64},
        {"normalized_sha256": "d" * 64},
        {"input_sha256": "d" * 64},
    ],
)
async def test_pinned_view_identity_or_manifest_tampering_is_denied_before_pages_escape(change):
    receipt = NativeEvidenceReceipt("owner", "tenant")
    admit(receipt)
    with pytest.raises(ServiceUnavailableException):
        await consume(receipt, store(replace(whole_read(), **change)))
    assert receipt.documents == {}


@pytest.mark.parametrize("boundary", ["tenant_id", "workspace_id"])
async def test_other_tenant_or_workspace_corpus_cannot_enter_current_receiver(boundary):
    receipt = NativeEvidenceReceipt("owner", "tenant")
    admit(receipt)
    with pytest.raises(ServiceUnavailableException):
        await consume(receipt, store(whole_read(), source=replace(meta(), **{boundary: "foreign"})))
    assert receipt.documents == {}


async def test_corrupt_part_sha_and_duplicate_part_ids_are_denied_atomically():
    value = whole_read("one", "two")
    for pages in (
        (replace(value.pages[0], sha256="f" * 64),),
        (value.pages[0], replace(value.pages[1], part_id=value.pages[0].part_id)),
    ):
        receipt = NativeEvidenceReceipt("owner", "tenant")
        admit(receipt)
        changed = replace(
            value, pages=pages, input_sha256=sha256("\n".join(p.text for p in pages).encode()).hexdigest()
        )
        with pytest.raises(ServiceUnavailableException):
            await consume(receipt, store(changed))
        assert receipt.documents == {}


async def test_all_parts_are_budgeted_before_any_page_is_exposed_or_recorded():
    receipt = NativeEvidenceReceipt("owner", "tenant", limits=NativeCaptureLimits(sources=1))
    admit(receipt)
    with pytest.raises(ServiceUnavailableException) as error:
        await consume(receipt, store(whole_read("one", "two")))
    assert error.value.code == "EVIDENCE_BUDGET_EXCEEDED"
    assert receipt.documents == {}
    assert not any(row.stage == "rlm.read" for row in receipt.native_reads)


async def test_legacy_original_has_an_explicit_recorded_views_prerequisite_before_access():
    receipt = NativeEvidenceReceipt("owner", "tenant")
    admit(receipt)
    source = replace(meta(), source_version_id=None, ingestion_extraction_id=None)
    with pytest.raises(ServiceUnavailableException) as error:
        await consume(receipt, store(whole_read(), source=source))
    assert error.value.code == "RLM_DOCUMENT_VIEWS_REQUIRED"
    assert receipt.documents == {}


async def test_escaped_thread_cannot_reuse_a_live_worker_scope():
    receipt = NativeEvidenceReceipt("owner", "tenant")
    admit(receipt)
    failures = []
    with provenance.observe(
        receipt, tenant_id="tenant", workspace_id="native-space", actor="owner", source_ids={"native-source"}
    ):
        context, scope = copy_context(), provenance.current()

        def escaped():
            try:
                context.run(receipt.document_view_parts, meta(), whole_read(), scope)
            except BaseException as error:
                failures.append(error)

        thread = Thread(target=escaped)
        thread.start()
        await asyncio.to_thread(thread.join)
    assert len(failures) == 1 and isinstance(failures[0], ServiceUnavailableException)
    assert receipt.documents == {}


async def test_cancelled_parent_closes_scope_before_delayed_pages_can_escape():
    receipt = NativeEvidenceReceipt("owner", "tenant")
    admit(receipt)
    reader = Reader(whole_read())
    reader.started, reader.release = asyncio.Event(), asyncio.Event()
    corpus, finished, exposed = store(reader.value, reader=reader), Event(), []
    with provenance.observe(
        receipt, tenant_id="tenant", workspace_id="native-space", actor="owner", source_ids={"native-source"}
    ):

        @provenance.worker
        def read():
            try:
                exposed.extend(corpus.pages("controlled"))
            except ServiceUnavailableException:
                pass
            finally:
                finished.set()

        task = asyncio.create_task(asyncio.to_thread(read))
        await reader.started.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    reader.release.set()
    assert await asyncio.to_thread(finished.wait, 2)
    assert exposed == [] and receipt.documents == {}


def canonical_result(value):
    page = value.pages[0]
    return {
        "answer": "Exact committed answer",
        "hits": [
            {
                "id": page.part_id,
                "asset_id": "asset",
                "source_id": "source",
                "text": page.text[:8000],
                "title": "Controlled",
                "score": 1,
            }
        ],
        "citations": [
            {
                "source_id": "source",
                "asset_id": "asset",
                "chunk_id": page.part_id,
                "content": page.text[-12:],
                "metadata": {
                    "source_version_id": value.source_version_id,
                    "extraction_id": value.extraction_id,
                    "source_part_id": page.part_id,
                    "source_part_sha256": page.sha256,
                    "page_basis": "recorded_loader",
                    "recorded_page": str(page.page),
                },
            }
        ],
    }


def evidence(value, data, *, source=None, record_model=True):
    asset = SimpleNamespace(id="asset", workspace_id="space", name="Controlled", kind="document")
    parent = SimpleNamespace(id="source")
    binding = SimpleNamespace(native_id="native-source", native_workspace_id="native-space")

    async def chain(subject, tenant, asset_id, *args):
        assert (subject, tenant, asset_id) == ("owner", "tenant", "asset")
        return [asset, parent]

    async def bound(tenant, asset_id, domain, *, entry):
        assert (tenant, asset_id, domain) == ("tenant", "asset", "canon")
        return binding

    async def search(subject, tenant, **kwargs):
        receipt = kwargs["_capture"]
        admit(receipt)
        await consume(receipt, store(value, source=source), record_model=record_model)
        return data

    async def parts(**kwargs):
        assert (
            kwargs["tenant_id"],
            kwargs["workspace_id"],
            kwargs["source_id"],
            kwargs["source_version_id"],
            kwargs["extraction_id"],
            kwargs["actor"],
        ) == ("tenant", "native-space", "native-source", "version", "view", "owner")
        return tuple(
            WholeDocumentPart(
                p.part_id,
                value.source_id,
                value.source_version_id,
                value.extraction_id,
                value.ingestion_extraction_id,
                p.text,
                p.sha256,
                p.page,
                p.page_basis,
                p.source_sections,
                value.raw_sha256,
                value.normalized_sha256,
                value.input_sha256,
            )
            for p in value.pages
            if p.part_id in kwargs["part_ids"]
        )

    knowledge = SimpleNamespace(
        _chain=chain, binding=bound, search=search, domains=SimpleNamespace(document_parts=parts)
    )
    return NativeKnowledgeEvidence(knowledge, SimpleNamespace())


async def test_modern_rlm_answer_is_complete_only_with_exact_read_citation_and_existing_part_verification():
    value = whole_read("x" * 8500 + "Final sentence")
    result = await evidence(value, canonical_result(value)).search("owner", "tenant", answer=True)
    assert result.complete and len(result.sources) == 1
    source = result.sources[0]
    assert source.source_part_id == "part-0" and source.quote == "x" * 8000
    assert source.source_part_sha256 == value.pages[0].sha256 and source.availability == "available"
    assert any(
        row.stage == "rlm.read" and row.content_sha256 == value.input_sha256 for row in result.native_reads
    )


@pytest.mark.parametrize(
    "field",
    [
        "source_version_id",
        "extraction_id",
        "source_part_id",
        "source_part_sha256",
        "page_basis",
        "recorded_page",
    ],
)
async def test_citation_tuple_tampering_never_becomes_complete(field):
    value = whole_read()
    data = canonical_result(value)
    data["citations"][0]["metadata"][field] = "foreign"
    with pytest.raises(NativeEvidenceFailure):
        await evidence(value, data).search("owner", "tenant", answer=True)


async def test_citation_quote_must_have_been_in_the_full_recorded_part():
    value = whole_read()
    data = canonical_result(value)
    data["citations"][0]["content"] = "Invented quotation"
    with pytest.raises(NativeEvidenceFailure):
        await evidence(value, data).search("owner", "tenant", answer=True)


async def test_parts_without_actual_rlm_model_read_stages_remain_unqualified():
    value = whole_read()
    result = await evidence(value, canonical_result(value), record_model=False).search(
        "owner", "tenant", answer=True
    )
    assert not result.complete


async def test_missing_recorded_views_reason_survives_audited_partial_failure():
    value = whole_read()
    with pytest.raises(NativeEvidenceFailure) as error:
        await evidence(
            value,
            canonical_result(value),
            source=replace(meta(), source_version_id=None, ingestion_extraction_id=None),
        ).search("owner", "tenant", answer=True)
    assert error.value.code == "RLM_DOCUMENT_VIEWS_REQUIRED"
    assert not error.value.capture.complete and error.value.capture.data == {}


@pytest.mark.parametrize("tenant,actor", [("foreign", "owner"), ("tenant", "other")])
async def test_receiver_rejects_other_receipt_tenant_or_actor_even_in_a_leased_thread(tenant, actor):
    receipt = NativeEvidenceReceipt("owner", "tenant")
    admit(receipt)
    with provenance.observe(
        receipt, tenant_id=tenant, workspace_id="native-space", actor=actor, source_ids={"native-source"}
    ):

        @provenance.worker
        def foreign():
            receipt.document_view_parts(replace(meta(), tenant_id=tenant), whole_read(), provenance.current())

        with pytest.raises(ServiceUnavailableException):
            await asyncio.to_thread(foreign)
    assert receipt.documents == {}


async def test_fresh_authority_is_required_after_the_reader_returns_before_pages_escape():
    receipt = NativeEvidenceReceipt("owner", "tenant")
    admit(receipt)
    revoked = False

    async def authorize():
        if revoked:
            raise AccessDenied("Controlled revocation")

    receipt.authorize_model = authorize

    class RevokedReader(Reader):
        async def read(self, scope, **values):
            nonlocal revoked
            result = await super().read(scope, **values)
            revoked = True
            return result

    with pytest.raises(AccessDenied):
        await consume(receipt, store(whole_read(), reader=RevokedReader(whole_read())))
    assert receipt.documents == {}


async def test_modern_citation_may_identify_exact_part_without_a_chunk_id():
    value = whole_read()
    data = canonical_result(value)
    data["citations"][0].pop("chunk_id")
    result = await evidence(value, data).search("owner", "tenant", answer=True)
    assert result.complete


async def test_required_product_legacy_pin_reports_recorded_views_before_original_io(tmp_path):
    from flycanon.core.agents.model_bindings import push_bindings, reset_bindings
    from flycanon.core.services.query.rlm.corpus import CanonCorpusBuilder
    from flycanon.models.entities import Base
    from flycanon.models.entities.source import SourceRow
    from flycanon.models.entities.source_lineage import metadata
    from flycanon.models.repositories import SourceRepository
    from flycanon.web.conventions.context import TenantContext, set_tenant_context
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'legacy-pin.db'}")
    try:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
            await connection.run_sync(metadata.create_all)
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        async with sessions.begin() as session:
            session.add(
                SourceRow(
                    id="legacy",
                    tenant_id="tenant",
                    workspace_id="native-space",
                    kind="text",
                    status="ingested",
                    filename="legacy.txt",
                    content_sha256="a" * 64,
                    object_store_key="preserved-original",
                    metadata_json={},
                )
            )
        sources = SourceRepository(sessions)
        builder = CanonCorpusBuilder(
            source_repository=sources,
            knowledge_repository=None,
            object_store=SimpleNamespace(
                get_sync=lambda *_: pytest.fail("Legacy original must not be opened")
            ),
            registry=default_registry(),
        )
        receipt = NativeEvidenceReceipt("owner", "tenant")

        async def authorize():
            return None

        receipt.authorize_model = authorize
        context = set_tenant_context(
            TenantContext(
                tenant_id="tenant", workspace_id="native-space", actor="owner", correlation_id="controlled"
            )
        )
        token = push_bindings(tenant_id="tenant", workspace_id="native-space", subject="owner", bindings={})
        try:
            with (
                provenance.observe(
                    receipt,
                    tenant_id="tenant",
                    workspace_id="native-space",
                    actor="owner",
                    source_ids={"legacy"},
                ),
                pytest.raises(ServiceUnavailableException) as error,
            ):
                await builder.build(tenant_id="tenant", workspace_id="native-space")
            assert error.value.code == "RLM_DOCUMENT_VIEWS_REQUIRED"
            assert error.value.__cause__.code == "DOCUMENT_EXTRACTION_UNAVAILABLE"
            assert receipt.documents == {} and receipt.native_reads == []
        finally:
            reset_bindings(token)
            context.var.reset(context.token)
    finally:
        await engine.dispose()


async def test_selector_or_submodel_stages_cannot_replace_the_actual_rlm_root_stage():
    value = whole_read()
    service = evidence(value, canonical_result(value))
    original = service.knowledge.search

    async def selector_only(subject, tenant, **kwargs):
        result = await original(subject, tenant, **kwargs)
        receipt = kwargs["_capture"]
        receipt.native_reads = [
            replace(row, stage="rlm.selector") if row.stage in {"rlm.root", "rlm.forced_final"} else row
            for row in receipt.native_reads
        ]
        return result

    service.knowledge.search = selector_only
    result = await service.search("owner", "tenant", answer=True)
    assert not result.complete


async def test_model_read_cannot_claim_a_version_without_its_matching_extraction():
    value = whole_read()
    service = evidence(value, canonical_result(value))
    original = service.knowledge.search

    async def mismatched(subject, tenant, **kwargs):
        result = await original(subject, tenant, **kwargs)
        receipt = kwargs["_capture"]
        receipt.native_reads = [
            replace(row, source_version_id="foreign")
            if row.stage == "rlm.root" and row.extraction_id is None
            else row
            for row in receipt.native_reads
        ]
        return result

    service.knowledge.search = mismatched
    with pytest.raises(NativeEvidenceFailure):
        await service.search("owner", "tenant", answer=True)
