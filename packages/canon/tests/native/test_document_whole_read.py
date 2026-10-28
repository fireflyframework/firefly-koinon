# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Pinned whole-document reads preserve the actual admitted transformation chain."""

from hashlib import sha256
from unittest.mock import AsyncMock

import pytest
from pyfly.kernel import ResourceNotFoundException, ServiceUnavailableException
from sqlalchemy import select
from test_source_lineage_admission import intake_fixture, submit
from test_source_lineage_admission import lineage as lineage

from flycanon.core.services.sources.lineage.dtos import DocumentScope
from flycanon.models.entities.source_lineage import source_artifacts, source_extractions


async def test_whole_read_persists_exact_normalized_sections_with_separate_raw_identity(
    lineage, repositories, session_factory
):
    from flycanon.core.services.sources.lineage.whole_read import WholeDocumentReader

    intake = intake_fixture(lineage, repositories, normalized=b"redacted full text")
    source = await submit(intake, content=b"private raw original")
    scope = DocumentScope("t", "w", "actor")
    head = dict(await lineage.head(scope, source.id))
    read = await WholeDocumentReader(lineage).read(
        scope,
        source_id=source.id,
        source_version_id=head["version_id"],
        ingestion_extraction_id=head["extraction_id"],
    )
    assert read.source_version_id == head["version_id"]
    assert read.ingestion_extraction_id == head["extraction_id"]
    assert read.extraction_id != head["extraction_id"]
    assert tuple(page.text for page in read.pages) == ("redacted full text",)
    assert read.raw_sha256 == sha256(b"private raw original").hexdigest()
    assert read.input_sha256 == sha256(b"redacted full text").hexdigest()
    assert read.raw_sha256 != read.input_sha256
    assert read.pages[0].page is None
    assert read.pages[0].page_basis == "recorded_loader"
    assert read.pages[0].source_sections
    async with session_factory() as session:
        persisted = (
            (
                await session.execute(
                    select(source_extractions).where(source_extractions.c.id == read.extraction_id)
                )
            )
            .mappings()
            .one()
        )
    assert persisted["purpose"] == "whole_document_read"
    assert dict(await lineage.head(scope, source.id)) == head


async def test_foreign_whole_read_is_denied_before_object_store_use(lineage, repositories):
    from flycanon.core.services.sources.lineage.whole_read import WholeDocumentReader

    source = await submit(intake_fixture(lineage, repositories))
    head = await lineage.head(DocumentScope("t", "w", "actor"), source.id)
    original = lineage.store.get_bounded
    lineage.store.get_bounded = AsyncMock(side_effect=original)
    with pytest.raises(ResourceNotFoundException):
        await WholeDocumentReader(lineage).read(
            DocumentScope("foreign", "w", "actor"),
            source_id=source.id,
            source_version_id=head["version_id"],
            ingestion_extraction_id=head["extraction_id"],
        )
    lineage.store.get_bounded.assert_not_awaited()


@pytest.mark.parametrize("role", ["raw", "normalized", "whole_document_view"])
async def test_actual_bound_bytes_are_verified_even_on_reused_extraction(lineage, repositories, role):
    from flycanon.core.services.sources.lineage.whole_read import WholeDocumentReader

    source = await submit(intake_fixture(lineage, repositories))
    scope = DocumentScope("t", "w", "actor")
    head = await lineage.head(scope, source.id)
    reader = WholeDocumentReader(lineage)
    await reader.read(
        scope,
        source_id=source.id,
        source_version_id=head["version_id"],
        ingestion_extraction_id=head["extraction_id"],
    )
    async with lineage.sources.session() as session:
        key = (
            await session.execute(
                select(source_artifacts.c.object_key).where(
                    source_artifacts.c.source_id == source.id, source_artifacts.c.role == role
                )
            )
        ).scalar_one()
    await lineage.store.put(key, b"corrupt")
    with pytest.raises(ServiceUnavailableException, match="integrity"):
        await reader.read(
            scope,
            source_id=source.id,
            source_version_id=head["version_id"],
            ingestion_extraction_id=head["extraction_id"],
        )


async def test_rlm_hook_observes_committed_exact_view_before_model_and_not_metadata(
    lineage, repositories, session_factory
):
    import asyncio
    from dataclasses import FrozenInstanceError

    from flycanon.core.services.ingestion.loaders import default_registry
    from flycanon.core.services.query import provenance
    from flycanon.core.services.query.rlm.corpus import CanonCorpusBuilder

    source = await submit(intake_fixture(lineage, repositories, normalized=b"safe complete text"))
    events = []
    loop = asyncio.get_running_loop()

    async def committed(identifier):
        async with session_factory() as session:
            return (
                await session.execute(
                    select(source_extractions.c.id).where(source_extractions.c.id == identifier)
                )
            ).scalar_one()

    class Observer:
        async def authorize(self):
            pass

        def document_origin(self, *args):
            pass

        def document_sync(self, stage, *args):
            events.append(("sync", stage))

        def document_extraction(self, source_id, version_id, extraction_id, scope):
            assert scope.active and scope.observer is self
            assert source_id == source.id
            assert (
                asyncio.run_coroutine_threadsafe(committed(extraction_id), loop).result(timeout=5)
                == extraction_id
            )
            events.append(("extraction", version_id, extraction_id))

    observer = Observer()
    with provenance.observe(observer, tenant_id="t", workspace_id="w", actor="actor", source_ids={source.id}):
        docs = await CanonCorpusBuilder(
            source_repository=repositories["source"],
            knowledge_repository=repositories["knowledge"],
            object_store=lineage.store,
            registry=default_registry(),
        ).build(tenant_id="t", workspace_id="w")
        await provenance.corpus(docs)
        assert events == [("sync", "rlm.corpus")]
        key = docs.keys()[0]

        @provenance.worker
        def model():
            text = docs[key]
            provenance.model("rlm.root", text)
            return text

        assert await asyncio.to_thread(model) == "safe complete text"
        with pytest.raises(FrozenInstanceError):
            docs.resolve(key).source_id = "foreign"
        with pytest.raises(TypeError):
            docs._sources[key] = docs.resolve(key)
    assert [event[0] for event in events] == ["sync", "extraction", "sync", "sync"]
    assert events[-2:] == [("sync", "rlm.read"), ("sync", "rlm.root")]


async def test_recorded_loader_pages_and_parent_digests_are_not_physical_page_claims(lineage, repositories):
    from types import SimpleNamespace

    from flycanon.core.services.ingestion.loaders import LoadedDocument, Section
    from flycanon.core.services.sources.lineage.whole_read import WholeDocumentReader
    from flycanon.interfaces.enums import SourceKind

    intake = intake_fixture(lineage, repositories)
    intake._loaders.register(
        SimpleNamespace(
            kind=SourceKind.text,
            load=lambda *args, **kwargs: LoadedDocument(
                [Section(["Repeated"], "first", page=7), Section(["Repeated"], "second", page=7)]
            ),
        )
    )
    source = await submit(intake)
    scope = DocumentScope("t", "w", "actor")
    head = await lineage.head(scope, source.id)
    read = await WholeDocumentReader(lineage).read(
        scope,
        source_id=source.id,
        source_version_id=head["version_id"],
        ingestion_extraction_id=head["extraction_id"],
    )
    assert len(read.pages) == 1 and read.pages[0].text == "first\nsecond"
    assert read.pages[0].page == 7 and read.pages[0].page_basis == "recorded_loader"
    assert {digest for _, digest in read.pages[0].source_sections} == {
        sha256(b"first").hexdigest(),
        sha256(b"second").hexdigest(),
    }
    assert read.input_sha256 == sha256(b"first\nsecond").hexdigest()
    assert read.normalized_sha256 == sha256(b"normalized text").hexdigest()


async def test_regroup_reuse_keeps_exact_version_after_current_source_replacement(lineage, repositories):
    from pyfly.agentic.content.binary import BinaryArtifact

    from flycanon.core.services.sources.lineage.whole_read import WholeDocumentReader
    from flycanon.interfaces.dtos.source import SubmitSourceRequest

    intake = intake_fixture(lineage, repositories)
    source = await submit(intake)
    scope = DocumentScope("t", "w", "actor")
    old = dict(await lineage.head(scope, source.id))
    reader = WholeDocumentReader(lineage)
    first = await reader.read(
        scope,
        source_id=source.id,
        source_version_id=old["version_id"],
        ingestion_extraction_id=old["extraction_id"],
    )
    intake._binary_normalizer.normalise.return_value = [
        BinaryArtifact(bytes=b"new normalized", media_type="text/plain", kind="text", filename="one.txt")
    ]
    await intake.replace(
        source_id=source.id,
        request=SubmitSourceRequest(),
        content=b"new raw",
        tenant_id="t",
        workspace_id="w",
        actor="actor",
        logical_source_key="doc1",
        operation_id="replace",
        expected_source_version_id=old["version_id"],
        expected_extraction_id=old["extraction_id"],
    )
    again = await reader.read(
        scope,
        source_id=source.id,
        source_version_id=old["version_id"],
        ingestion_extraction_id=old["extraction_id"],
    )
    assert again == first
    assert again.pages[0].text == "normalized text"
    assert (await lineage.head(scope, source.id))["extraction_id"] != old["extraction_id"]


async def test_real_zip_normalization_is_retained_without_reopening_raw_zip_as_text(lineage, repositories):
    from io import BytesIO
    from zipfile import ZipFile

    from pyfly.agentic.content.binary import BinaryNormalizer

    from flycanon.core.services.sources.lineage.whole_read import WholeDocumentReader
    from flycanon.interfaces.dtos.source import SubmitSourceRequest

    body = BytesIO()
    with ZipFile(body, "w") as archive:
        archive.writestr("alpha.txt", "alpha full text")
        archive.writestr("beta.txt", "beta full text")
    intake = intake_fixture(lineage, repositories)
    intake._binary_normalizer = BinaryNormalizer()
    source = await intake.submit(
        request=SubmitSourceRequest(),
        content=body.getvalue(),
        tenant_id="t",
        workspace_id="w",
        actor="actor",
        filename="bundle.zip",
        logical_source_key="zip",
        operation_id="zip-intake",
    )
    scope = DocumentScope("t", "w", "actor")
    head = await lineage.head(scope, source.id)
    intake._binary_normalizer.normalise = AsyncMock(side_effect=AssertionError("No current normalizer rerun"))
    read = await WholeDocumentReader(lineage).read(
        scope,
        source_id=source.id,
        source_version_id=head["version_id"],
        ingestion_extraction_id=head["extraction_id"],
    )
    text = "\n".join(page.text for page in read.pages)
    assert "alpha full text" in text and "beta full text" in text
    assert read.raw_sha256 == sha256(body.getvalue()).hexdigest()
    assert read.input_sha256 == sha256(text.encode()).hexdigest()
    intake._binary_normalizer.normalise.assert_not_awaited()


async def test_native_pii_redaction_is_not_bypassed_by_whole_document_read(lineage, repositories):
    from flycanon.core.services.pii.scanner import PiiPolicy, RegexPiiScanner
    from flycanon.core.services.sources.lineage.whole_read import WholeDocumentReader

    intake = intake_fixture(lineage, repositories, normalized=b"Email owner@example.org for details.")
    intake._pii_policy, intake._pii_scanner = PiiPolicy.redact, RegexPiiScanner()
    source = await submit(intake, content=b"Email owner@example.org for details.")
    scope = DocumentScope("t", "w", "actor")
    head = await lineage.head(scope, source.id)
    read = await WholeDocumentReader(lineage).read(
        scope,
        source_id=source.id,
        source_version_id=head["version_id"],
        ingestion_extraction_id=head["extraction_id"],
    )
    assert "owner@example.org" not in read.pages[0].text
    assert "[REDACTED:EMAIL]" in read.pages[0].text
    assert read.raw_sha256 != read.normalized_sha256


async def test_mixed_foreign_ingestion_identity_is_rejected_before_bytes(lineage, repositories):
    from flycanon.core.services.sources.lineage.whole_read import WholeDocumentReader

    intake = intake_fixture(lineage, repositories)
    first = await submit(intake)
    second = await submit(intake, logical="other", operation="other-upload")
    scope = DocumentScope("t", "w", "actor")
    first_head, second_head = await lineage.head(scope, first.id), await lineage.head(scope, second.id)
    original = lineage.store.get_bounded
    lineage.store.get_bounded = AsyncMock(side_effect=original)
    with pytest.raises(ResourceNotFoundException):
        await WholeDocumentReader(lineage).read(
            scope,
            source_id=first.id,
            source_version_id=first_head["version_id"],
            ingestion_extraction_id=second_head["extraction_id"],
        )
    lineage.store.get_bounded.assert_not_awaited()


async def test_whole_read_limit_never_returns_a_partial_confirmed_view(lineage, repositories):
    from flycanon.core.services.sources.lineage.whole_read import WholeDocumentReader

    source = await submit(intake_fixture(lineage, repositories))
    scope = DocumentScope("t", "w", "actor")
    head = await lineage.head(scope, source.id)
    with pytest.raises(ServiceUnavailableException, match="limit"):
        await WholeDocumentReader(lineage, max_bytes=4).read(
            scope,
            source_id=source.id,
            source_version_id=head["version_id"],
            ingestion_extraction_id=head["extraction_id"],
        )
    assert (await lineage.extractions(scope, source.id, head["version_id"])).total == 1


async def test_metadata_cannot_override_verified_ledger_pin(lineage, repositories):
    from types import SimpleNamespace

    from flycanon.core.services.query import provenance
    from flycanon.core.services.query.rlm.corpus import CanonCorpusBuilder

    source = await submit(intake_fixture(lineage, repositories))
    scope = DocumentScope("t", "w", "actor")
    head = dict(await lineage.head(scope, source.id))
    row = await repositories["source"].get(source.id, tenant_id="t", workspace_id="w")
    row.metadata_json = {
        **row.metadata_json,
        "_source_lineage": {"version_id": "untrusted", "extraction_id": "untrusted"},
    }
    row.content_sha256 = "not-the-immutable-input"
    await repositories["source"].update(row)
    with provenance.observe(
        SimpleNamespace(authorize=AsyncMock()), tenant_id="t", workspace_id="w", actor="actor"
    ):
        docs = await CanonCorpusBuilder(
            source_repository=repositories["source"],
            knowledge_repository=repositories["knowledge"],
            object_store=lineage.store,
        ).build(tenant_id="t", workspace_id="w")
    meta = docs.resolve(docs.keys()[0])
    assert meta.source_version_id == head["version_id"]
    assert meta.ingestion_extraction_id == head["extraction_id"]
    assert meta.content_sha256 == sha256(b"normalized text").hexdigest()
    with pytest.raises(ServiceUnavailableException, match="observer"):
        docs.pages(docs.keys()[0])


async def test_required_legacy_whole_source_needs_explicit_versioned_intake(
    lineage, repositories, monkeypatch
):
    from types import SimpleNamespace

    from flycanon.core.agents import model_bindings
    from flycanon.core.services.query import provenance
    from flycanon.core.services.query.rlm.corpus import CanonCorpusBuilder
    from flycanon.models.entities.source import SourceRow

    await repositories["source"].add(
        SourceRow(
            id="legacy",
            tenant_id="t",
            workspace_id="w",
            kind="text",
            status="ingested",
            content_sha256=sha256(b"legacy").hexdigest(),
            content_bytes=6,
            object_store_key="old-key",
            metadata_json={},
        )
    )
    monkeypatch.setattr(model_bindings, "current_scope", lambda: SimpleNamespace(required=True))
    with (
        provenance.observe(
            SimpleNamespace(authorize=AsyncMock()), tenant_id="t", workspace_id="w", actor="actor"
        ),
        pytest.raises(ServiceUnavailableException, match="explicitly authorized versioned intake"),
    ):
        await CanonCorpusBuilder(
            source_repository=repositories["source"],
            knowledge_repository=repositories["knowledge"],
            object_store=lineage.store,
        ).build(tenant_id="t", workspace_id="w")


async def test_reused_view_reauthorizes_before_returning_verified_content(lineage, repositories):
    from pyfly.kernel import ForbiddenException

    from flycanon.core.services.sources.lineage.whole_read import WholeDocumentReader

    source = await submit(intake_fixture(lineage, repositories))
    scope = DocumentScope("t", "w", "actor")
    head = await lineage.head(scope, source.id)
    reader = WholeDocumentReader(lineage)
    options = dict(
        source_id=source.id,
        source_version_id=head["version_id"],
        ingestion_extraction_id=head["extraction_id"],
    )
    await reader.read(scope, **options)
    authorize = AsyncMock(side_effect=[None, None, ForbiddenException("Revoked during verified read")])
    with pytest.raises(ForbiddenException):
        await reader.read(scope, authorize=authorize, **options)
    assert authorize.await_count == 3


async def test_versioned_content_requires_the_exact_observer_before_creating_a_view(lineage, repositories):
    import asyncio
    from types import SimpleNamespace

    from flycanon.core.services.query import provenance
    from flycanon.core.services.query.rlm.corpus import CanonCorpusBuilder

    source = await submit(intake_fixture(lineage, repositories))
    scope = DocumentScope("t", "w", "actor")
    head = await lineage.head(scope, source.id)
    observer = SimpleNamespace(authorize=AsyncMock())
    with provenance.observe(observer, tenant_id="t", workspace_id="w", actor="actor"):
        docs = await CanonCorpusBuilder(
            source_repository=repositories["source"],
            knowledge_repository=repositories["knowledge"],
            object_store=lineage.store,
        ).build(tenant_id="t", workspace_id="w")
        with pytest.raises(ServiceUnavailableException, match="extraction observer"):
            await asyncio.to_thread(provenance.worker(lambda: docs[docs.keys()[0]]))
    assert (await lineage.extractions(scope, source.id, head["version_id"])).total == 1


async def test_exact_used_part_resolves_from_immutable_view_without_regrouping(
    lineage, repositories, monkeypatch
):
    from flycanon.core.services.sources.lineage import whole_read

    source = await submit(intake_fixture(lineage, repositories))
    scope = DocumentScope("t", "w", "actor")
    head = await lineage.head(scope, source.id)
    reader = whole_read.WholeDocumentReader(lineage)
    view = await reader.read(
        scope,
        source_id=source.id,
        source_version_id=head["version_id"],
        ingestion_extraction_id=head["extraction_id"],
    )
    monkeypatch.setattr(
        whole_read,
        "grouped_sections",
        lambda _: pytest.fail("Historical proof cannot rerun current grouping"),
    )
    (part,) = await reader.resolve_parts(
        scope,
        source_id=source.id,
        source_version_id=view.source_version_id,
        extraction_id=view.extraction_id,
        part_ids=(view.pages[0].part_id,),
    )
    assert part.text == "normalized text"
    assert part.sha256 == sha256(part.text.encode()).hexdigest()
    assert part.source_version_id == view.source_version_id and part.extraction_id == view.extraction_id
    assert part.raw_sha256 == view.raw_sha256
    assert part.input_sha256 == view.input_sha256 and part.normalized_sha256 == view.normalized_sha256
    assert part.source_sections == view.pages[0].source_sections
    lineage.store.get_bounded = AsyncMock(side_effect=AssertionError("No bytes for a foreign part"))
    with pytest.raises(ResourceNotFoundException):
        await reader.resolve_parts(
            scope,
            source_id=source.id,
            source_version_id=view.source_version_id,
            extraction_id=view.extraction_id,
            part_ids=("foreign-part",),
        )


async def test_versioned_citation_index_one_uses_real_part_for_recorded_page_seven(lineage, repositories):
    import asyncio
    from types import SimpleNamespace

    from flycanon.core.services.ingestion.loaders import LoadedDocument, Section
    from flycanon.core.services.query import provenance
    from flycanon.core.services.query.rlm.corpus import CanonCorpusBuilder
    from flycanon.core.services.query.rlm_answer_service import _map_citations
    from flycanon.interfaces.enums import SourceKind
    from flycanon.models.entities.source_lineage import source_parts

    intake = intake_fixture(lineage, repositories)
    intake._loaders.register(
        SimpleNamespace(
            kind=SourceKind.text,
            load=lambda *args, **kwargs: LoadedDocument(
                [Section(["First"], "first passage", page=3), Section(["Second"], "second passage", page=7)]
            ),
        )
    )
    source = await submit(intake)
    observer = SimpleNamespace(
        authorize=AsyncMock(), document_extraction=lambda *args: None, document_sync=lambda *args: None
    )
    with provenance.observe(observer, tenant_id="t", workspace_id="w", actor="actor"):
        docs = await CanonCorpusBuilder(
            source_repository=repositories["source"],
            knowledge_repository=repositories["knowledge"],
            object_store=lineage.store,
        ).build(tenant_id="t", workspace_id="w")
        key = docs.keys()[0]
        await asyncio.to_thread(provenance.worker(lambda: docs.pages(key)))
        (hit,) = _map_citations([{"filing": key, "page": 1, "content": "second passage"}], docs)
        assert hit.source_id == source.id
        assert hit.page is None
        assert hit.metadata["recorded_page"] == "7" and hit.metadata["page_basis"] == "recorded_loader"
        async with lineage.sources.session() as session:
            part = (
                (await session.execute(select(source_parts).where(source_parts.c.id == hit.chunk_id)))
                .mappings()
                .one()
            )
        assert part["kind"] == "page" and part["ordinal"] == 1
        assert hit.metadata["source_part_id"] == part["id"]
        assert hit.metadata["source_part_sha256"] == part["sha256"]
        assert hit.metadata["extraction_id"] == part["extraction_id"]
        assert not _map_citations([{"filing": key, "page": 1, "content": "not the selected text"}], docs)
