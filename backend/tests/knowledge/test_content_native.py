# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from hashlib import sha256
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from test_document_reads import native_document as native_document
from test_native_adapters import configured_connections

from koinon.workers.admission import WorkAdmission, WorkAdmissionSettings


def add_bean(adapter, kind, value):
    contains, resolve = adapter.container.contains_type, adapter.container.resolve
    adapter.container.contains_type = lambda candidate: candidate is kind or contains(candidate)
    adapter.container.resolve = lambda candidate: value if candidate is kind else resolve(candidate)


async def test_native_document_replacement_checks_version_before_ingestion_and_joins_rollback(
    native_document,
):
    from flycanon.core.services.sources.intake_service import IntakeService
    from pyfly.kernel import ConflictException

    adapter, sources, _, _ = native_document
    configured_connections(adapter.container)
    intake = SimpleNamespace(replace=AsyncMock())
    add_bean(adapter, IntakeService, intake)
    arguments = dict(
        tenant_id="north",
        workspace_id="workspace",
        source_id="source",
        filename="next.txt",
        content=b"next original",
        actor="issuer|editor",
    )
    with pytest.raises(ConflictException):
        await adapter.replace_document(**arguments, expected_sha256="a" * 64)
    intake.replace.assert_not_awaited()
    with pytest.raises(ConflictException):
        await adapter.replace_document(
            **{**arguments, "content": b"original"}, expected_sha256="a" * 64, force_reingest=True
        )
    intake.replace.assert_not_awaited()

    async def failing(**options):
        assert options["versioned_originals"] is True
        row = await sources.get("source", tenant_id="north", workspace_id="workspace")
        row.filename = "must-rollback.txt"
        await sources.update(row)
        raise RuntimeError("Provider failed after a retained write")

    intake.replace.side_effect = failing
    with pytest.raises(RuntimeError):
        await adapter.replace_document(**arguments, expected_sha256=sha256(b"original").hexdigest())
    assert (await sources.get("source", tenant_id="north", workspace_id="workspace")).filename == "facts.txt"
    with pytest.raises(RuntimeError):
        await adapter.replace_document(
            **{**arguments, "content": b"original"},
            expected_sha256=sha256(b"original").hexdigest(),
            force_reingest=True,
        )


@pytest.mark.parametrize("bound", [False, True])
async def test_same_bytes_source_replacement_keeps_its_new_operation_binding(native_document, bound):
    from flycanon.core.services.sources.intake_service import IntakeService
    from flycanon.core.services.sources.lineage.dtos import SourcePublicationBinding
    from flycanon.core.services.sources.lineage.service import DocumentLineage

    adapter, _, _, _ = native_document
    configured_connections(adapter.container)
    lineage = SimpleNamespace(
        head=AsyncMock(return_value={"version_id": "old-version", "extraction_id": "old-extraction"})
    )
    intake = SimpleNamespace(
        replace=AsyncMock(
            return_value=SimpleNamespace(
                n_chunks=1,
                metadata_json={
                    "_source_lineage": {"version_id": "new-version", "extraction_id": "new-extraction"}
                },
            )
        )
    )
    add_bean(adapter, DocumentLineage, lineage)
    add_bean(adapter, IntakeService, intake)
    binding = SourcePublicationBinding("new-attempt", "a" * 64) if bound else None
    guard = object()
    result = await adapter.replace_document(
        tenant_id="north",
        workspace_id="workspace",
        source_id="source",
        filename="facts.txt",
        content=b"original",
        expected_sha256=sha256(b"original").hexdigest(),
        actor="issuer|editor",
        logical_source_key="retained-source",
        operation_id="new-operation",
        expected_source_version_id="old-version",
        expected_extraction_id="old-extraction",
        _publication_guard=guard,
        _source_publication=binding,
    )
    if bound:
        assert result["unchanged"] is False
        assert (result["source_version_id"], result["extraction_id"]) == ("new-version", "new-extraction")
        options = intake.replace.await_args.kwargs
        assert options["source_publication"] is binding
        assert options["publication_guard"] is guard
        assert options["operation_id"] == "new-operation"
        assert options["logical_source_key"] == "retained-source"
    else:
        assert result["unchanged"] is True
        assert (result["source_version_id"], result["extraction_id"]) == ("old-version", "old-extraction")
        intake.replace.assert_not_awaited()


@pytest.mark.parametrize("missing", ["logical_source_key", "operation_id", "_publication_guard"])
async def test_bound_document_replacement_requires_its_exact_private_execution(
    native_document, missing, monkeypatch
):
    from flycanon.core.services.sources.lineage.dtos import SourcePublicationBinding

    from koinon.knowledge import document_lineage

    adapter, _, _, statements = native_document
    dispatch = AsyncMock(side_effect=AssertionError("Incomplete execution reached native replacement"))
    monkeypatch.setattr(document_lineage, "replace_document", dispatch)
    arguments = dict(
        tenant_id="north",
        workspace_id="workspace",
        source_id="source",
        filename="facts.txt",
        content=b"original",
        expected_sha256=sha256(b"original").hexdigest(),
        actor="issuer|editor",
        logical_source_key="retained-source",
        operation_id="new-operation",
        _publication_guard=object(),
        _source_publication=SourcePublicationBinding("new-attempt", "a" * 64),
    )
    arguments[missing] = None
    before = len(statements)
    with pytest.raises(ValueError, match="exact versioned source operation"):
        await adapter.replace_document(**arguments)
    assert len(statements) == before
    dispatch.assert_not_awaited()


async def test_native_table_reupload_rejects_mismatched_parent_and_stale_snapshot_before_ingestion():
    from flyquery.core.services.datasets.dataset_service import DatasetService
    from flyquery.core.services.ingestion.ingest_service import IngestService
    from flyquery.core.services.tables.table_service import TableService
    from pyfly.kernel import ConflictException, ForbiddenException

    from koinon.knowledge.adapters import NativeDomains

    workspace, dataset, table, snapshot = [uuid4() for _ in range(4)]
    tables = SimpleNamespace(
        get=AsyncMock(
            return_value={
                "id": table,
                "tenant_id": "north",
                "workspace_id": workspace,
                "dataset_id": dataset,
                "current_snapshot_id": snapshot,
            }
        )
    )
    datasets = SimpleNamespace(
        get=AsyncMock(
            return_value={"id": dataset, "tenant_id": "north", "workspace_id": workspace, "name": "orders"}
        )
    )
    ingestion = SimpleNamespace(ingest_reupload=AsyncMock())
    beans = {DatasetService: datasets, TableService: tables, IngestService: ingestion}
    adapter = NativeDomains(
        SimpleNamespace(contains_type=lambda kind: kind in beans, resolve=beans.__getitem__),
        admission=WorkAdmission(WorkAdmissionSettings()),
    )
    arguments = dict(
        tenant_id="north",
        workspace_id=str(workspace),
        dataset_id=str(dataset),
        table_id=str(table),
        filename="next.csv",
        content=b"total\n1",
        actor="issuer|editor",
    )
    with pytest.raises(ConflictException):
        await adapter.reupload_table(**arguments, expected_snapshot_id=str(uuid4()))
    tables.get.return_value["dataset_id"] = uuid4()
    with pytest.raises(ForbiddenException):
        await adapter.reupload_table(**arguments, expected_snapshot_id=str(snapshot))
    ingestion.ingest_reupload.assert_not_awaited()
