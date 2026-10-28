# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from hashlib import sha256
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from test_document_reads import native_document as native_document
from test_native_adapters import configured_connections


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
        SimpleNamespace(contains_type=lambda kind: kind in beans, resolve=beans.__getitem__)
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
