# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from datetime import UTC, datetime, timedelta
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pyarrow as pa
import pyarrow.parquet as pq
import pytest
from pyfly.core import Config

from koinon.catalog.errors import AccessDenied
from koinon.knowledge.evidence_results import NativeStoredResults


def prepared():
    workspace, dataset, query = map(str, (uuid4(), uuid4(), uuid4()))
    buffer = BytesIO()
    pq.write_table(pa.table({"precise": [9007199254740993, 9007199254740995]}), buffer)
    content = buffer.getvalue()
    key = f"flyquery/tenant/{workspace}/{dataset}/results/{query}.parquet"
    result = {
        "tenant_id": "tenant",
        "workspace_id": workspace,
        "query_id": query,
        "result_object_key": key,
        "result_byte_size": len(content),
        "ttl_expires_at": datetime.now(UTC) + timedelta(hours=1),
    }
    metadata = {
        "tenant_id": "tenant",
        "workspace_id": workspace,
        "dataset_id": dataset,
        "execution_status": "OK",
        "table_id_snapshot_pins_json": {},
        "row_count": 2,
    }

    async def get(key):
        yield content

    store = SimpleNamespace(head=AsyncMock(return_value=SimpleNamespace(size_bytes=len(content))), get=get)
    repo = SimpleNamespace(
        get_query=AsyncMock(return_value=metadata), get_result=AsyncMock(return_value=result)
    )
    domains = SimpleNamespace(
        _resolve=lambda kind: repo, container=SimpleNamespace(resolve_by_name=lambda name: store)
    )
    knowledge = SimpleNamespace(
        _chain=AsyncMock(return_value=[SimpleNamespace(kind="dataset")]),
        binding=AsyncMock(return_value=SimpleNamespace(native_workspace_id=workspace, native_id=dataset)),
    )
    return NativeStoredResults(knowledge, domains, Config({})), store, result, query, content


async def test_legacy_footer_rows_are_actual_but_historical_completeness_remains_unknown():
    service, _, _, query, content = prepared()
    result = await service.describe("owner", "tenant", "asset", query)
    assert result.row_count == 2 and result.row_cap is None and result.truncated is None
    assert result.completeness == "unknown" and result.snapshot_ids == ()
    assert result.columns[0].name == "precise"
    assert b"".join([part async for part in service.read("owner", "tenant", result)]) == content


async def test_canonical_scope_and_exact_registered_key_are_checked_before_storage():
    service, store, row, query, _ = prepared()
    service.knowledge._chain.side_effect = AccessDenied("Denied")
    with pytest.raises(AccessDenied):
        await service.describe("foreign", "tenant", "asset", query)
    store.head.assert_not_awaited()
    service.knowledge._chain.side_effect = None
    row["result_object_key"] = "foreign/key.parquet"
    with pytest.raises(AccessDenied):
        await service.describe("owner", "tenant", "asset", query)
    store.head.assert_not_awaited()


async def test_expiry_is_rechecked_before_reading_a_previously_described_result():
    from pyfly.kernel import GoneException

    service, store, row, query, _ = prepared()
    result = await service.describe("owner", "tenant", "asset", query)
    store.head.reset_mock()
    row["ttl_expires_at"] = datetime.now(UTC) - timedelta(seconds=1)
    with pytest.raises(GoneException):
        _ = [part async for part in service.read("owner", "tenant", result)]
    store.head.assert_not_awaited()


async def test_native_object_store_coroutine_returns_its_async_byte_stream():
    service, store, _, query, content = prepared()
    original = store.get

    async def get(key):
        return original(key)

    store.get = get
    result = await service.describe("owner", "tenant", "asset", query)
    assert result.byte_size == len(content)


async def test_empty_execution_does_not_fabricate_artifact_or_column_schema():
    from pyfly.kernel import ResourceNotFoundException

    service, store, row, query, _ = prepared()
    row["result_object_key"], row["result_byte_size"] = None, None
    service.domains._resolve(None).get_query.return_value["row_count"] = 0
    result = await service.describe("owner", "tenant", "asset", query)
    assert result.row_count == result.byte_size == 0 and result.columns == ()
    with pytest.raises(ResourceNotFoundException):
        _ = [part async for part in service.read("owner", "tenant", result)]
    store.head.assert_not_awaited()


async def test_oversized_original_stream_is_closed_before_result_rejection():
    from pyfly.kernel import ConflictException

    service, store, _, query, content = prepared()
    closed = []

    async def stream(key):
        try:
            yield content + b"changed"
        finally:
            closed.append(True)

    store.get = stream
    with pytest.raises(ConflictException):
        await service.describe("owner", "tenant", "asset", query)
    assert closed == [True]
