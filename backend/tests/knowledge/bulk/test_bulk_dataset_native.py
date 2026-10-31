# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from koinon.knowledge.bulk.dataset_native import DatasetBulkNative
from koinon.knowledge.bulk.dtos import BulkDestination
from koinon.knowledge.bulk.queue import BulkLease
from koinon.knowledge.bulk.structured_dtos import (
    PreparedStructuredTable,
    StructuredCommitReceipt,
    StructuredOperationIdentity,
    StructuredOperationState,
)


@pytest.mark.parametrize("prepared", [False, True])
async def test_dataset_dispatch_binds_embedding_only_and_prepared_resume_has_no_model_scope(prepared):
    identity = StructuredOperationIdentity(
        operation_id=uuid4(),
        tenant_id="north",
        workspace_id=uuid4(),
        dataset_id=uuid4(),
        file_id=uuid4(),
        actor="owner",
        catalog_source_id="source",
        catalog_dataset_id="asset",
        catalog_file_version_id="version",
        filename="facts.csv",
        sha256="a" * 64,
        size_bytes=8,
    )
    table = PreparedStructuredTable(
        ordinal=0,
        table_id=uuid4(),
        snapshot_id=uuid4(),
        name="facts",
        catalog_table_id="table",
        lineage_run_id=uuid4(),
        n_columns=1,
        n_rows_actual=2,
        parquet_key="private",
        parquet_sha256="b" * 64,
        parquet_byte_size=7,
        schema_sha256="c" * 64,
    )
    state = StructuredOperationState(
        identity=identity,
        status="committed",
        plan=(table,),
        prepared=(table,),
        receipt=StructuredCommitReceipt(
            file_id=identity.file_id,
            dataset_id=identity.dataset_id,
            sha256=identity.sha256,
            size_bytes=8,
            object_key="private/raw",
            tables=(table,),
        ),
    )
    lease = BulkLease(
        job_id="job",
        item_id=str(identity.operation_id),
        batch_id="batch",
        tenant_id="north",
        subject="owner",
        token_id="original-token",
        worker_id="worker",
        attempt=1,
        source_id="source",
        asset_id="asset",
        filename="facts.csv",
        size_bytes=8,
        sha256=identity.sha256,
        mode="dataset",
        destination=BulkDestination(workspace_id="workspace", project_id="project", parent_id="collection"),
    )
    scopes = []

    @asynccontextmanager
    async def models(*args, **values):
        scopes.append("models")
        assert values["roles"] == ("structured.embedding",) and values["purpose"] == "ingest"
        assert values["catalog_workspace_id"] == "workspace"
        yield

    @asynccontextmanager
    async def lineage(**values):
        scopes.append("lineage")
        assert values["source_catalog_id"] == "source" and values["dataset_id"] == str(identity.dataset_id)
        yield

    pipeline = SimpleNamespace(prepare=AsyncMock(), finalize=AsyncMock(return_value=state))
    service = DatasetBulkNative(
        SimpleNamespace(),
        pipeline,
        SimpleNamespace(),
        SimpleNamespace(),
        SimpleNamespace(
            get=lambda: SimpleNamespace(
                domains=SimpleNamespace(model_connections=models, structured_lineage=lineage)
            )
        ),
    )
    service.identity = AsyncMock(return_value=identity)
    receipt = (
        await service.finalize_prepared(lease) if prepared else await service.execute(lease, b"original")
    )
    assert receipt.tables[0].catalog_table_id == "table" and receipt.file_version_id == "version"
    assert receipt.native_file_id == str(identity.file_id)
    pipeline.finalize.assert_awaited_once_with(lease, identity)
    if prepared:
        assert scopes == []
        pipeline.prepare.assert_not_awaited()
    else:
        assert scopes == ["models", "lineage"]
        pipeline.prepare.assert_awaited_once_with(lease, identity, b"original")
