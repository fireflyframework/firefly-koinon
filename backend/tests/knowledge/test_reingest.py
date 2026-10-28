# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from hashlib import sha256
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from test_content import updates
from test_facade import context as context
from test_facade import upload


async def test_document_reingest_checks_alias_writes_before_reading_stored_original(context):
    from koinon.catalog.errors import AccessDenied

    service = updates(context)
    _, catalog, domains, tree, _ = context
    document = (await upload(context))["assets"][0]["id"]
    domains.document_original = AsyncMock(return_value={"filename": "facts.txt", "content": b"evidence"})
    arguments = {"expected_sha256": "a" * 64, "acknowledge_chunk_invalidation": True}
    with pytest.raises(AccessDenied):
        await service.reingest_document("issuer|reader", "north", document, **arguments)
    await catalog.archive("issuer|admin", "north", tree["collection"].id)
    with pytest.raises(AccessDenied):
        await service.reingest_document("issuer|admin", "north", document, **arguments)
    domains.document_original.assert_not_awaited()
    domains.replace_document.assert_not_awaited()


async def test_document_reingest_runs_retained_replacement_even_for_identical_bytes(context):
    service = updates(context)
    _, _, domains, _, _ = context
    document = (await upload(context))["assets"][0]["id"]
    domains.document_original = AsyncMock(return_value={"filename": "facts.txt", "content": b"evidence"})
    result = await service.reingest_document(
        "issuer|admin", "north", document, expected_sha256="a" * 64, acknowledge_chunk_invalidation=True
    )
    assert domains.replace_document.await_args.kwargs["force_reingest"] is True
    assert domains.replace_document.await_args.kwargs["content"] == b"evidence"
    assert result["version"]["metadata"]["operation"] == "document.reingest"
    assert result["effects"]["previous_chunk_ids_invalidated"] is True


async def test_table_reingest_uses_verified_native_file_and_preserves_snapshot_effects(context):
    service = updates(context)
    _, catalog, domains, _, _ = context
    domains.ingest_dataset.return_value["tables"] = [
        {"table_id": "native-table", "name": "orders", "snapshot_id": "snapshot-old"}
    ]
    dataset = (await upload(context, "dataset"))["assets"][0]["id"]
    table = (await catalog.list("issuer|admin", "north", kind="table", parent_id=dataset))[0]
    domains.table_original = AsyncMock(
        return_value={"filename": "orders.csv", "content": b"total\n3", "file_id": "stored-file"}
    )
    response = await service.reingest_table(
        "issuer|admin", "north", dataset, table.id, expected_snapshot_id="snapshot-old"
    )
    assert domains.table_original.await_args.kwargs["dataset_id"] == "native-dataset"
    assert domains.table_original.await_args.kwargs["table_id"] == "native-table"
    assert response["effects"]["reingested_from_file_id"] == "stored-file"
    assert response["effects"]["historical_snapshots_preserved"] is True
    assert response["version"]["metadata"]["operation"] == "table.reingest"


async def test_native_table_bytes_are_bounded_and_hash_verified_before_reingestion(monkeypatch):
    from contextlib import asynccontextmanager

    from flyquery.config import FlyquerySettings
    from flyquery.core.services.storage.object_store import ObjectStore
    from pyfly.kernel import PayloadTooLargeException, ServiceUnavailableException

    from koinon.knowledge.adapters import NativeDomains

    workspace, dataset, table, snapshot, file_id = [uuid4() for _ in range(5)]
    row = {
        "id": file_id,
        "original_filename": "orders.csv",
        "size_bytes": 8,
        "content_hash_sha256": sha256(b"original").hexdigest(),
        "object_store_key": "private/stored/file",
    }
    captured = []

    class Session:
        async def execute(self, statement, values):
            captured.append((str(statement), values))
            return SimpleNamespace(mappings=lambda: SimpleNamespace(one_or_none=lambda: row))

    @asynccontextmanager
    async def unit(*args, **kwargs):
        yield Session()

    monkeypatch.setattr("pyfly.data.transaction.infrastructure_unit", unit)
    content, closed = b"original", []

    async def stream():
        try:
            yield content
        finally:
            closed.append(True)

    store = SimpleNamespace(
        head=AsyncMock(return_value=SimpleNamespace(size_bytes=8)),
        get=AsyncMock(side_effect=lambda key: stream()),
    )
    beans = {FlyquerySettings: SimpleNamespace(native_datasource=lambda: object()), ObjectStore: store}
    adapter = NativeDomains(
        SimpleNamespace(contains_type=lambda kind: kind in beans, resolve=beans.__getitem__)
    )
    arguments = dict(
        tenant_id="north",
        workspace_id=str(workspace),
        dataset_id=str(dataset),
        table_id=str(table),
        expected_snapshot_id=str(snapshot),
        actor="issuer|editor",
        max_bytes=32,
    )
    result = await adapter.table_original(**arguments)
    assert result["content"] == b"original" and result["file_id"] == str(file_id)
    assert closed
    sql, values = captured[0]
    assert all(
        fragment in sql
        for fragment in ("tenant_id", "workspace_id", "dataset_id", "current_snapshot_id", "source_file_id")
    )
    assert values == {
        "tenant": "north",
        "workspace": workspace,
        "dataset": dataset,
        "table": table,
        "snapshot": snapshot,
    }
    store.get.reset_mock()
    store.head.return_value.size_bytes = 1000
    with pytest.raises(PayloadTooLargeException):
        await adapter.table_original(**arguments)
    store.get.assert_not_awaited()
    store.head.return_value.size_bytes = 8
    content = b"tampered"
    with pytest.raises(ServiceUnavailableException, match="integrity"):
        await adapter.table_original(**arguments)
