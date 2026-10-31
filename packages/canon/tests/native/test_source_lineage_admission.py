# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Durability before transformations without changing the standalone source schema."""

from hashlib import sha256

import pytest
from sqlalchemy import inspect, select, text


@pytest.fixture
async def lineage(repositories, engine, tmp_path):
    from flycanon.core.services.sources.lineage.service import DocumentLineage
    from flycanon.core.services.storage.local_fs import LocalFsObjectStore
    from flycanon.models.entities.source_lineage import metadata

    async with engine.begin() as connection:
        await connection.run_sync(metadata.create_all)
        await connection.execute(text("DROP INDEX uq_canon_sources_tenant_workspace_content_sha256"))
    return DocumentLineage(repositories["source"], LocalFsObjectStore(str(tmp_path)))


async def test_admitted_raw_original_is_committed_and_verified_in_a_fresh_session(lineage, session_factory):
    from flycanon.core.services.sources.lineage.dtos import DocumentScope
    from flycanon.models.entities.source_lineage import source_versions

    scope = DocumentScope("t", "w", "actor")
    admitted = await lineage.admit(
        scope,
        logical_key="doc1",
        operation_id="upload1",
        content=b"raw",
        filename="one.txt",
        media_type="text/plain",
    )
    async with session_factory() as session:
        version = (await session.execute(select(source_versions))).mappings().one()
    assert version["id"] == admitted.version_id
    assert admitted.sha256 == sha256(b"raw").hexdigest()
    assert (
        await lineage.original(scope, admitted.source_id, admitted.version_id, max_bytes=3)
    ).content == b"raw"


async def test_equal_raw_originals_with_different_logical_keys_never_alias(lineage):
    from flycanon.core.services.sources.lineage.dtos import DocumentScope

    scope = DocumentScope("t", "w", "actor")
    first = await lineage.admit(
        scope,
        logical_key="doc1",
        operation_id="upload1",
        content=b"same",
        filename="one.txt",
        media_type="text/plain",
    )
    second = await lineage.admit(
        scope,
        logical_key="doc2",
        operation_id="upload2",
        content=b"same",
        filename="two.txt",
        media_type="text/plain",
    )
    assert first.source_id != second.source_id
    assert first.version_id != second.version_id


async def test_operation_retry_is_idempotent_but_changed_payload_conflicts(lineage):
    from pyfly.kernel import ConflictException

    from flycanon.core.services.sources.lineage.dtos import DocumentScope

    scope = DocumentScope("t", "w", "actor")
    kwargs = dict(logical_key="doc", operation_id="upload", filename="one.txt", media_type="text/plain")
    first = await lineage.admit(scope, content=b"raw", **kwargs)
    assert (await lineage.admit(scope, content=b"raw", **kwargs)).version_id == first.version_id
    with pytest.raises(ConflictException):
        await lineage.admit(scope, content=b"different", **kwargs)


async def test_foreign_scope_cannot_read_admitted_original(lineage):
    from pyfly.kernel import ResourceNotFoundException

    from flycanon.core.services.sources.lineage.dtos import DocumentScope

    first = await lineage.admit(
        DocumentScope("t", "w", "actor"),
        logical_key="doc",
        operation_id="upload",
        content=b"raw",
        filename="one.txt",
        media_type="text/plain",
    )
    with pytest.raises(ResourceNotFoundException):
        await lineage.original(
            DocumentScope("other", "w", "actor"), first.source_id, first.version_id, max_bytes=3
        )


async def test_original_schema_source_crud_has_no_unconditional_sidecar_dependency(repositories, engine):
    from flycanon.models.entities.source import SourceRow

    async with engine.connect() as connection:
        columns = await connection.run_sync(
            lambda sync: {item["name"] for item in inspect(sync).get_columns("canon_sources")}
        )
    assert "current_source_version_id" not in columns
    row = SourceRow(
        id="standalone",
        tenant_id="t",
        workspace_id="w",
        kind="text",
        status="pending",
        content_sha256="legacy",
        content_bytes=3,
        metadata_json={},
    )
    await repositories["source"].add(row)
    found = await repositories["source"].get(row.id, tenant_id="t", workspace_id="w")
    assert found.content_sha256 == "legacy"
    found.filename = "changed.txt"
    await repositories["source"].update(found)
    await repositories["source"].delete(found)
    assert await repositories["source"].get(row.id, tenant_id="t", workspace_id="w") is None


def intake_fixture(lineage, repositories, normalized=b"normalized text", *, normalizer=None, settings=None):
    from types import SimpleNamespace
    from unittest.mock import AsyncMock, Mock

    from pyfly.agentic.content.binary import BinaryArtifact

    from flycanon.config import CanonSettings
    from flycanon.core.services.ingestion.chunker import ParagraphChunker
    from flycanon.core.services.ingestion.ingestion_service import IngestionService
    from flycanon.core.services.ingestion.loaders import default_registry

    registry = default_registry()
    normalizer = normalizer or SimpleNamespace(
        normalise=AsyncMock(
            return_value=[
                BinaryArtifact(bytes=normalized, media_type="text/plain", kind="text", filename="one.txt")
            ]
        )
    )
    service = _versioned_intake(
        dict(
            binary_normalizer=normalizer,
            ingestion=IngestionService(loaders=registry, chunker=ParagraphChunker()),
            loaders=registry,
            embeddings=SimpleNamespace(
                model="controlled", embed=AsyncMock(side_effect=lambda texts: [[1.0] for _ in texts])
            ),
            indexer=SimpleNamespace(replace_for_source=AsyncMock(return_value=1)),
            metadata_extractor=SimpleNamespace(
                extract=Mock(return_value=SimpleNamespace(to_dict=lambda: {}))
            ),
            source_repository=repositories["source"],
            chunk_repository=repositories["chunk"],
            audit=SimpleNamespace(record=AsyncMock()),
            event_publisher=None,
            object_store=lineage.store,
            settings=settings or CanonSettings(store_originals=True, pii_policy="disabled"),
        )
    )
    return service


async def submit(intake, content=b"raw original", logical="doc1", operation="upload1"):
    from flycanon.interfaces.dtos.source import SubmitSourceRequest

    return await intake.submit(
        request=SubmitSourceRequest(),
        content=content,
        tenant_id="t",
        workspace_id="w",
        actor="actor",
        filename="one.txt",
        logical_source_key=logical,
        operation_id=operation,
    )


async def test_retry_of_failed_admission_after_another_commit_stops_before_normalizer_and_embedding(
    lineage, repositories
):
    from pyfly.kernel import ConflictException

    from flycanon.core.services.sources.lineage.dtos import DocumentScope
    from flycanon.interfaces.dtos.source import SubmitSourceRequest

    intake = intake_fixture(lineage, repositories)
    first = await submit(intake)
    previous = await lineage.head(DocumentScope("t", "w", "actor"), first.id)
    arguments = dict(
        source_id=first.id,
        request=SubmitSourceRequest(),
        content=b"new original",
        tenant_id="t",
        workspace_id="w",
        actor="actor",
        filename="one.txt",
        logical_source_key="doc1",
        expected_source_version_id=previous["version_id"],
        expected_extraction_id=previous["extraction_id"],
    )
    intake._binary_normalizer.normalise.side_effect = RuntimeError("controlled failure")
    with pytest.raises(RuntimeError):
        await intake.replace(**arguments, operation_id="failed-operation")
    intake._binary_normalizer.normalise.side_effect = None
    await intake.replace(**arguments, operation_id="winning-operation")
    calls = (intake._binary_normalizer.normalise.await_count, intake._embeddings.embed.await_count)
    with pytest.raises(ConflictException) as failure:
        await intake.replace(**arguments, operation_id="failed-operation")
    assert failure.value.code == "DOCUMENT_VERSION_CONFLICT"
    assert (intake._binary_normalizer.normalise.await_count, intake._embeddings.embed.await_count) == calls


async def test_strict_intake_admits_before_normalizer_and_never_aliases_normalized_content(
    lineage, repositories, session_factory
):
    from flycanon.models.entities.source_lineage import source_versions

    intake = intake_fixture(lineage, repositories)
    original = intake._binary_normalizer.normalise.side_effect

    async def normalize(*args, **kwargs):
        async with session_factory() as session:
            assert (await session.execute(select(source_versions))).mappings().all()
        return intake._binary_normalizer.normalise.return_value

    intake._binary_normalizer.normalise.side_effect = normalize
    first = await submit(intake)
    second = await submit(intake, b"another original", "doc2", "upload2")
    assert first.id != second.id
    assert first.content_sha256 == second.content_sha256
    assert original is None


async def test_replace_preserves_old_immutable_bytes_sections_and_chunks(lineage, repositories):
    from flycanon.core.services.sources.lineage.dtos import DocumentScope
    from flycanon.interfaces.dtos.source import SubmitSourceRequest

    scope = DocumentScope("t", "w", "actor")
    intake = intake_fixture(lineage, repositories)
    first = await submit(intake)
    old = dict(await lineage.head(scope, first.id))
    from pyfly.agentic.content.binary import BinaryArtifact

    intake._binary_normalizer.normalise.return_value = [
        BinaryArtifact(bytes=b"new normalized", media_type="text/plain", kind="text", filename="one.txt")
    ]
    updated = await intake.replace(
        source_id=first.id,
        request=SubmitSourceRequest(),
        content=b"new raw",
        tenant_id="t",
        workspace_id="w",
        actor="actor",
        logical_source_key="doc1",
        operation_id="replace1",
        expected_source_version_id=old["version_id"],
        expected_extraction_id=old["extraction_id"],
    )
    current = await lineage.head(scope, first.id)
    assert updated.id == first.id and current["extraction_id"] != old["extraction_id"]
    assert (
        await lineage.original(scope, first.id, old["version_id"], max_bytes=100)
    ).content == b"raw original"
    parts = await lineage.parts(scope, first.id, old["extraction_id"])
    assert any(part["kind"] == "section" and part["text"] == "normalized text" for part in parts.items)
    assert any(part["kind"] == "chunk" and part["text"] == "normalized text" for part in parts.items)


@pytest.mark.parametrize("failure", ["normalizer", "embedding", "index", "authority"])
async def test_failed_processing_or_promotion_preserves_exact_old_head_and_projection(
    lineage, repositories, failure
):
    from unittest.mock import AsyncMock

    from flycanon.core.services.sources.lineage.dtos import DocumentScope
    from flycanon.interfaces.dtos.source import SubmitSourceRequest

    scope = DocumentScope("t", "w", "actor")
    intake = intake_fixture(lineage, repositories)
    first = await submit(intake)
    old = dict(await lineage.head(scope, first.id))
    old_parts = await lineage.parts(scope, first.id, old["extraction_id"])
    callback = None
    if failure == "normalizer":
        intake._binary_normalizer.normalise.side_effect = RuntimeError("controlled failure")
    elif failure == "embedding":
        intake._embeddings.embed.side_effect = RuntimeError("controlled failure")
    elif failure == "index":
        intake._indexer.replace_for_source.side_effect = RuntimeError("controlled failure")
    else:
        callback = AsyncMock(side_effect=RuntimeError("controlled failure"))
    with pytest.raises(RuntimeError, match="controlled failure"):
        await intake.replace(
            source_id=first.id,
            request=SubmitSourceRequest(),
            content=b"new raw",
            tenant_id="t",
            workspace_id="w",
            actor="actor",
            logical_source_key="doc1",
            operation_id="replace1",
            expected_source_version_id=old["version_id"],
            expected_extraction_id=old["extraction_id"],
            authorize_commit=callback,
        )
    assert dict(await lineage.head(scope, first.id)) == old
    current = await repositories["source"].get(first.id, tenant_id="t", workspace_id="w")
    assert current.metadata_json["_source_lineage"]["extraction_id"] == old["extraction_id"]
    assert (await lineage.parts(scope, first.id, old["extraction_id"])).items == old_parts.items
    assert len((await lineage.history(scope, first.id)).items) == 2  # attempted raw admission remains durable


async def test_same_byte_reingest_changes_extraction_and_stale_extraction_cas_is_rejected(
    lineage, repositories
):
    from pyfly.kernel import ConflictException

    from flycanon.core.services.sources.lineage.dtos import DocumentScope
    from flycanon.interfaces.dtos.source import SubmitSourceRequest

    scope = DocumentScope("t", "w", "actor")
    intake = intake_fixture(lineage, repositories)
    first = await submit(intake)
    old = dict(await lineage.head(scope, first.id))
    kwargs = dict(
        source_id=first.id,
        request=SubmitSourceRequest(),
        content=b"raw original",
        tenant_id="t",
        workspace_id="w",
        actor="actor",
        logical_source_key="doc1",
        expected_source_version_id=old["version_id"],
        expected_extraction_id=old["extraction_id"],
    )
    await intake.replace(**kwargs, operation_id="reingest1")
    new = await lineage.head(scope, first.id)
    assert new["extraction_id"] != old["extraction_id"]
    with pytest.raises(ConflictException, match="extraction changed"):
        await intake.replace(**kwargs, operation_id="stale-reingest")


async def test_strict_storage_failure_makes_zero_normalizer_calls(lineage, repositories):
    from unittest.mock import AsyncMock

    from pyfly.kernel import ServiceUnavailableException

    intake = intake_fixture(lineage, repositories)
    intake._object_store.put = AsyncMock(side_effect=OSError("controlled storage failure"))
    with pytest.raises(ServiceUnavailableException):
        await submit(intake)
    intake._binary_normalizer.normalise.assert_not_awaited()


async def test_locked_admission_cannot_rebase_authorization_onto_a_newer_extraction(lineage, repositories):
    from pyfly.kernel import ConflictException

    from flycanon.core.services.sources.lineage.dtos import DocumentScope
    from flycanon.interfaces.dtos.source import SubmitSourceRequest

    scope = DocumentScope("t", "w", "actor")
    intake = intake_fixture(lineage, repositories)
    first = await submit(intake)
    old = dict(await lineage.head(scope, first.id))
    await intake.replace(
        source_id=first.id,
        request=SubmitSourceRequest(),
        content=b"new",
        tenant_id="t",
        workspace_id="w",
        actor="actor",
        logical_source_key="doc1",
        operation_id="replacement",
        expected_source_version_id=old["version_id"],
        expected_extraction_id=old["extraction_id"],
    )
    with pytest.raises(ConflictException):
        await lineage.admit(
            scope,
            source_id=first.id,
            logical_key="doc1",
            operation_id="stale-admission",
            content=b"stale",
            filename="one.txt",
            media_type="text/plain",
            expected_source_version_id=old["version_id"],
            expected_extraction_id=old["extraction_id"],
        )


async def test_missing_recorded_pair_fails_before_admission_and_normalizer(lineage, repositories):
    from pyfly.kernel import ConflictException

    from flycanon.core.services.sources.lineage.dtos import DocumentScope
    from flycanon.interfaces.dtos.source import SubmitSourceRequest

    scope = DocumentScope("t", "w", "actor")
    intake = intake_fixture(lineage, repositories)
    first = await submit(intake)
    count = intake._binary_normalizer.normalise.await_count
    with pytest.raises(ConflictException):
        await intake.replace(
            source_id=first.id,
            request=SubmitSourceRequest(),
            content=b"new",
            tenant_id="t",
            workspace_id="w",
            actor="actor",
            logical_source_key="doc1",
            operation_id="unreviewed",
        )
    assert intake._binary_normalizer.normalise.await_count == count
    assert (await lineage.history(scope, first.id)).total == 1


def _versioned_intake(dependencies):
    from flycanon.core.services.sources.intake_runtime import build_intake_components
    from flycanon.core.services.sources.intake_service import IntakeService
    from flycanon.core.services.sources.lineage.pipeline import DocumentLineagePipeline
    from flycanon.core.services.sources.lineage.service import DocumentLineage

    pipeline = DocumentLineagePipeline(
        build_intake_components(**dependencies),
        DocumentLineage(dependencies["source_repository"], dependencies["object_store"]),
    )
    return IntakeService(**dependencies, lineage_pipeline=pipeline, intake_policy=pipeline.components.policy)
