# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Ordinary retrieval binds actual emitted chunks to retained immutable inputs."""

from dataclasses import replace
from hashlib import sha256
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from pyfly.kernel import ResourceNotFoundException, ServiceUnavailableException
from sqlalchemy import delete, insert, select, update
from test_source_lineage_admission import intake_fixture, submit
from test_source_lineage_admission import lineage as lineage

from flycanon.core.services.ingestion.loaders import LoadedDocument, Section
from flycanon.core.services.query import provenance
from flycanon.core.services.retrieval.corpus_factory import CorpusContext
from flycanon.core.services.retrieval.retrieval_service import Hit, RetrievalService
from flycanon.core.services.sources.lineage.dtos import DocumentScope
from flycanon.core.services.sources.lineage.whole_read import WholeDocumentReader
from flycanon.interfaces.enums import SourceKind
from flycanon.models.entities.source_lineage import source_artifacts, source_events, source_parts

SCOPE = DocumentScope("t", "w", "actor")


async def selected(lineage, repositories, *, recorded_page=7):
    intake = intake_fixture(lineage, repositories)
    intake._loaders.register(
        SimpleNamespace(
            kind=SourceKind.text,
            load=lambda *args, **kwargs: LoadedDocument(
                [
                    Section(["Repeated"], "first passage", page=3),
                    Section(["Repeated"], "selected passage", page=recorded_page),
                ]
            ),
        )
    )
    source = await submit(intake)
    head = dict(await lineage.head(SCOPE, source.id))
    chunks = await repositories["chunk"].list_for_source(source.id)
    part = (await lineage.parts(SCOPE, source.id, head["extraction_id"], kind="chunk")).items[1]
    hit = Hit(
        chunks[1].id,
        source.id,
        None,
        None,
        "selected passage",
        0.7,
        None,
        None,
        {
            "source_version_id": "forged",
            "source_part_id": "forged",
            "source_part_kind": "page",
            "projection_chunk_id": "forged",
            "source_filename": "forged.txt",
            "source_kind": "forged",
            "raw_sha256": "forged",
            "normalized_sha256": "forged",
            "recorded_page": "999",
            "page_basis": "forged",
        },
    )
    return intake, source, head, part, hit


async def bind(lineage, hits, scope=SCOPE):
    from flycanon.core.services.sources.lineage.retrieval import bind_retrieval_parts

    return await bind_retrieval_parts(lineage, scope, hits)


async def test_selected_chunk_keeps_projection_identity_and_overwrites_candidate_claims(
    lineage, repositories
):
    _, source, head, part, hit = await selected(lineage, repositories)
    (bound,) = await bind(lineage, [hit])
    assert bound.chunk_id == hit.chunk_id and bound.chunk_id != part["id"]
    assert bound.content == "selected passage" and bound.source_id == source.id
    assert bound.metadata["source_version_id"] == head["version_id"]
    assert bound.metadata["extraction_id"] == head["extraction_id"]
    assert bound.metadata["source_part_id"] == part["id"]
    assert bound.metadata["source_part_sha256"] == sha256(b"selected passage").hexdigest()
    assert bound.metadata["source_part_kind"] == "chunk"
    assert bound.metadata["projection_chunk_id"] == hit.chunk_id
    assert bound.metadata["source_filename"] == "one.txt" and bound.metadata["source_kind"] == "text"
    assert bound.metadata["_observed_source_filename"] == "one.txt"
    assert bound.metadata["recorded_page"] == "7" and bound.metadata["page_basis"] == "recorded_loader"
    assert bound.metadata["raw_sha256"] == sha256(b"raw original").hexdigest()
    assert bound.metadata["normalized_sha256"] == sha256(b"normalized text").hexdigest()
    assert bound.metadata["raw_artifact_id"] != bound.metadata["normalized_artifact_id"]
    assert hit.metadata["source_part_id"] == "forged"


async def test_unrecorded_chunk_strips_forged_immutable_identity(lineage, repositories):
    _, _, _, _, hit = await selected(lineage, repositories)
    hit = replace(
        hit,
        source_id="legacy-source",
        chunk_id="legacy-chunk",
        metadata={**hit.metadata, "extraction_id": "forged"},
    )
    (bound,) = await bind(lineage, [hit])
    assert bound.chunk_id == "legacy-chunk" and bound.content == "selected passage"
    for key in (
        "source_version_id",
        "extraction_id",
        "source_part_id",
        "source_part_kind",
        "projection_chunk_id",
        "raw_sha256",
        "normalized_sha256",
        "recorded_page",
        "page_basis",
    ):
        assert key not in bound.metadata


async def test_unpaginated_chunk_retains_recorded_basis_without_inventing_page(lineage, repositories):
    _, source, head, part, hit = await selected(lineage, repositories, recorded_page=None)
    (bound,) = await bind(lineage, [hit])
    assert bound.metadata["page_basis"] == "recorded_loader"
    assert "recorded_page" not in bound.metadata and "page" not in bound.metadata
    (read,) = await WholeDocumentReader(lineage).resolve_parts(
        SCOPE, source_id=source.id, source_version_id=head["version_id"],
        extraction_id=head["extraction_id"], part_ids=(part["id"],),
    )
    assert read.page is None and read.page_basis == "recorded_loader"


async def test_versioned_source_with_missing_projection_never_downgrades_to_legacy(lineage, repositories):
    _, _, _, _, hit = await selected(lineage, repositories)
    with pytest.raises(ServiceUnavailableException):
        await bind(lineage, [replace(hit, chunk_id="missing-projection")])


async def test_uncommitted_mapping_cannot_claim_recorded_ingestion(lineage, repositories):
    _, _, head, _, hit = await selected(lineage, repositories)
    async with lineage.sources.session() as session:
        await session.execute(
            delete(source_events).where(source_events.c.extraction_id == head["extraction_id"])
        )
    with pytest.raises(ServiceUnavailableException):
        await bind(lineage, [hit])


async def test_pending_admission_does_not_invent_lineage_for_legacy_projection(lineage, repositories):
    _, _, _, _, hit = await selected(lineage, repositories)
    admission = await lineage.admit(
        SCOPE,
        logical_key="pending",
        operation_id="pending",
        content=b"pending",
        filename="pending.txt",
        media_type="text/plain",
    )
    (bound,) = await bind(lineage, [replace(hit, source_id=admission.source_id, chunk_id="old-legacy")])
    assert "source_version_id" not in bound.metadata and "source_part_id" not in bound.metadata


async def test_versioned_chunk_cannot_borrow_unrecorded_current_title_or_uri(lineage, repositories):
    _, _, _, _, hit = await selected(lineage, repositories)
    hit = replace(
        hit, metadata={**hit.metadata, "source_title": "Replacement title", "source_uri": "replacement://uri"}
    )
    (bound,) = await bind(lineage, [hit])
    assert "source_title" not in bound.metadata and "source_uri" not in bound.metadata


async def test_ingestion_read_honors_reader_part_limit_before_blob_reads(lineage, repositories):
    _, source, head, part, _ = await selected(lineage, repositories)
    from pyfly.kernel import InvalidRequestException

    async def forbidden(*args, **kwargs):
        raise AssertionError("Part limit must be checked before retained bytes")

    lineage.store.get_bounded = forbidden
    with pytest.raises(InvalidRequestException):
        await WholeDocumentReader(lineage, max_parts=0).resolve_parts(
            SCOPE,
            source_id=source.id,
            source_version_id=head["version_id"],
            extraction_id=head["extraction_id"],
            part_ids=(part["id"],),
        )


@pytest.mark.parametrize("damage", ["content", "digest", "duplicate", "artifact"])
async def test_ambiguous_or_mismatched_projection_fails_closed(lineage, repositories, damage):
    _, _, _, part, hit = await selected(lineage, repositories)
    if damage == "content":
        hit = replace(hit, content="different model input")
    else:
        async with lineage.sources.session() as session:
            if damage == "duplicate":
                await session.execute(insert(source_parts).values(**{**part, "id": str(uuid4())}))
            else:
                values = {"sha256": "0" * 64} if damage == "digest" else {"artifact_id": None}
                await session.execute(
                    update(source_parts).where(source_parts.c.id == part["id"]).values(**values)
                )
    with pytest.raises(ServiceUnavailableException):
        await bind(lineage, [hit])


async def test_ingestion_chunk_read_survives_replacement_without_current_projection(lineage, repositories):
    intake, source, head, part, hit = await selected(lineage, repositories)
    (bound,) = await bind(lineage, [hit])
    from flycanon.interfaces.dtos.source import SubmitSourceRequest

    await intake.replace(
        request=SubmitSourceRequest(),
        content=b"replacement",
        tenant_id="t",
        workspace_id="w",
        actor="actor",
        filename="replacement.txt",
        logical_source_key="doc1",
        operation_id="replace1",
        source_id=source.id,
        expected_source_version_id=head["version_id"],
        expected_extraction_id=head["extraction_id"],
    )
    assert not await repositories["chunk"].get_many([hit.chunk_id])
    (read,) = await WholeDocumentReader(lineage).resolve_parts(
        SCOPE,
        source_id=source.id,
        source_version_id=head["version_id"],
        extraction_id=head["extraction_id"],
        part_ids=(part["id"],),
    )
    assert read.text == "selected passage" and read.part_id == part["id"]
    assert read.source_version_id == head["version_id"]
    assert read.extraction_id == read.ingestion_extraction_id == head["extraction_id"]
    assert read.raw_sha256 == bound.metadata["raw_sha256"]
    assert read.normalized_sha256 == read.input_sha256 == bound.metadata["normalized_sha256"]
    assert read.page == 7 and read.source_sections == (
        (part["parent_id"], sha256(b"selected passage").hexdigest()),
    )
    assert (await bind(lineage, [hit]))[0].metadata == bound.metadata


async def test_same_bytes_reextraction_keeps_each_selected_chunk_identity(lineage, repositories):
    intake, source, head, _, hit = await selected(lineage, repositories)
    (old,) = await bind(lineage, [hit])
    from flycanon.interfaces.dtos.source import SubmitSourceRequest

    await intake.replace(
        source_id=source.id,
        request=SubmitSourceRequest(),
        content=b"raw original",
        tenant_id="t",
        workspace_id="w",
        actor="actor",
        logical_source_key="doc1",
        operation_id="same-bytes",
        expected_source_version_id=head["version_id"],
        expected_extraction_id=head["extraction_id"],
    )
    chunks = await repositories["chunk"].list_for_source(source.id)
    (new,) = await bind(lineage, [replace(hit, chunk_id=chunks[1].id)])
    assert old.metadata["raw_sha256"] == new.metadata["raw_sha256"]
    assert old.metadata["source_part_sha256"] == new.metadata["source_part_sha256"]
    assert old.metadata["source_version_id"] != new.metadata["source_version_id"]
    assert old.metadata["extraction_id"] != new.metadata["extraction_id"]
    assert old.metadata["source_part_id"] != new.metadata["source_part_id"]
    assert (await bind(lineage, [hit]))[0].metadata == old.metadata


@pytest.mark.parametrize("damage", ["wrong_version", "section", "mixed", "empty", "duplicate"])
async def test_ingestion_exact_read_rejects_wrong_or_mixed_identity_before_bytes(
    lineage, repositories, damage
):
    _, source, head, part, _ = await selected(lineage, repositories)
    identifiers = (part["id"],)
    if damage == "section":
        identifiers = (part["parent_id"],)
    elif damage == "mixed":
        identifiers += (part["parent_id"],)
    elif damage == "empty":
        identifiers = ()
    elif damage == "duplicate":
        identifiers *= 2
    reads = []

    async def forbidden(*args, **kwargs):
        reads.append(args)
        raise AssertionError("Invalid identity reached retained bytes")

    from pyfly.kernel import InvalidRequestException

    lineage.store.get_bounded = forbidden
    with pytest.raises((ResourceNotFoundException, InvalidRequestException)):
        await WholeDocumentReader(lineage).resolve_parts(
            SCOPE,
            source_id=source.id,
            source_version_id="wrong" if damage == "wrong_version" else head["version_id"],
            extraction_id=head["extraction_id"],
            part_ids=identifiers,
        )
    assert reads == []


@pytest.mark.parametrize(
    "scope", [DocumentScope("foreign", "w", "actor"), DocumentScope("t", "foreign", "actor")]
)
async def test_foreign_ingestion_part_is_denied_before_blob_read(lineage, repositories, scope):
    _, source, head, part, _ = await selected(lineage, repositories)
    reads = []
    original = lineage.store.get_bounded

    async def tracked(*args, **kwargs):
        reads.append(args)
        return await original(*args, **kwargs)

    lineage.store.get_bounded = tracked
    with pytest.raises(ResourceNotFoundException):
        await WholeDocumentReader(lineage).resolve_parts(
            scope,
            source_id=source.id,
            source_version_id=head["version_id"],
            extraction_id=head["extraction_id"],
            part_ids=(part["id"],),
        )
    assert reads == []


@pytest.mark.parametrize("role", ["raw", "normalized"])
async def test_ingestion_chunk_rechecks_retained_bytes_on_each_read(lineage, repositories, role):
    _, source, head, part, _ = await selected(lineage, repositories)
    reader = WholeDocumentReader(lineage)
    kwargs = dict(
        source_id=source.id,
        source_version_id=head["version_id"],
        extraction_id=head["extraction_id"],
        part_ids=(part["id"],),
    )
    await reader.resolve_parts(SCOPE, **kwargs)
    async with lineage.sources.session() as session:
        artifact = (
            (
                await session.execute(
                    select(source_artifacts).where(
                        source_artifacts.c.source_id == source.id, source_artifacts.c.role == role
                    )
                )
            )
            .mappings()
            .one()
        )
    await lineage.store.put(artifact["object_key"], b"corrupt", artifact["media_type"])
    with pytest.raises(ServiceUnavailableException):
        await reader.resolve_parts(SCOPE, **kwargs)


async def test_retrieval_binding_precedes_trusted_hit_capture(lineage, repositories):
    _, _, _, part, hit = await selected(lineage, repositories)
    observed = []

    async def bind_hits(hits, scope):
        return await bind(lineage, hits)

    observer = SimpleNamespace(
        authorize=AsyncMock(),
        document_database=lambda *args: None,
        document_retrieval_parts=bind_hits,
        document_read_hits=lambda hits, scope: observed.extend(hits),
    )
    service = RetrievalService(
        context=CorpusContext(corpus=object(), vector_store=object(), backend="test"),
        embeddings=object(),
        source_repository=repositories["source"],
        chunk_repository=repositories["chunk"],
        knowledge_repository=repositories["knowledge"],
        default_top_k=5,
        default_per_query_k=20,
        rrf_k=60,
    )
    with provenance.observe(observer, tenant_id="t", workspace_id="w", actor="actor"):
        (result,) = await service._hydrate([hit])
    assert result.metadata["source_part_id"] == part["id"]
    assert observed[0].metadata["source_part_id"] == part["id"]
