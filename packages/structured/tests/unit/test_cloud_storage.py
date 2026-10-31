# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import asyncio
from unittest.mock import AsyncMock

import pytest
from koinon_storage.cloud import ObjectTooLargeError


@pytest.fixture(params=["azure", "gcs"])
def store(request):
    if request.param == "azure":
        from flyquery.core.services.storage.adapters.azure_blob import AzureBlobObjectStore

        return AzureBlobObjectStore(
            "azure://owned-private/retained",
            account_url="https://owned.blob.core.windows.net",
            max_object_bytes=8,
        )
    from flyquery.core.services.storage.adapters.gcs import GcsObjectStore

    return GcsObjectStore("gs://owned-private/retained", max_object_bytes=8)


async def test_stream_write_stops_at_bound_before_cloud_upload(store):
    store.native.put = AsyncMock()

    async def body():
        yield b"12345"
        yield b"67890"
        raise AssertionError("must stop before consuming remainder")

    with pytest.raises(ObjectTooLargeError):
        await store.put("tenant/file/1", body(), "text/plain")
    store.native.put.assert_not_called()


async def test_input_cancellation_never_publishes_partial_object(store):
    store.native.put = AsyncMock()

    async def body():
        yield b"12345"
        raise asyncio.CancelledError

    with pytest.raises(asyncio.CancelledError):
        await store.put("tenant/file/1", body(), "text/plain")
    store.native.put.assert_not_called()


async def test_stream_write_preserves_key_and_exact_byte_metadata(store):
    store.native.put = AsyncMock()

    async def body():
        yield b"1234"
        yield b"5678"

    meta = await store.put("tenant/file/1", body(), "text/plain", kms_key_uri="existing-key")
    store.native.put.assert_awaited_once_with(
        "tenant/file/1", b"12345678", "text/plain", kms_key_uri="existing-key"
    )
    assert meta.key == "tenant/file/1" and meta.size_bytes == 8 and meta.kms_key_uri == "existing-key"


def test_retained_root_schemes_preserve_bucket_prefix():
    from flyquery.core.services.storage.adapters.gcs import GcsObjectStore

    store = GcsObjectStore("gs://owned-private/retained")
    assert store.native._full_key("tenant/source/1") == "retained/tenant/source/1"


@pytest.mark.parametrize("backend", ["azure", "gcs"])
async def test_native_resolver_uses_configured_cloud_uri_and_preserves_snapshot_key(backend):
    from types import SimpleNamespace
    from unittest.mock import AsyncMock

    from flyquery.config import FlyquerySettings
    from flyquery.core.services.execution.table_resolver import TableResolver

    settings = FlyquerySettings(
        object_store=backend,
        object_store_azure_container="owned-private",
        object_store_azure_prefix="retained",
        object_store_gcs_bucket="owned-private",
        object_store_gcs_prefix="retained",
    )
    session = SimpleNamespace(
        execute=AsyncMock(
            return_value=SimpleNamespace(
                mappings=lambda: [
                    {
                        "name": "orders",
                        "parquet_object_key": "tenant/dataset/version.parquet",
                        "snapshot_id": "version",
                        "table_id": "table",
                    },
                ]
            )
        )
    )
    result = await TableResolver(session, settings).resolve("dataset", ["orders"], pins={"orders": "version"})
    scheme = "azure" if backend == "azure" else "gs"
    assert result == {"orders": f"{scheme}://owned-private/retained/tenant/dataset/version.parquet"}


async def test_cloud_query_cancellation_drains_native_fetch_and_removes_scratch(monkeypatch):
    import tempfile
    import threading
    from pathlib import Path
    from types import SimpleNamespace

    from flyquery.config import FlyquerySettings
    from flyquery.core.services.execution.duckdb_executor import DuckDBExecutor

    entered, release = threading.Event(), threading.Event()
    settings = FlyquerySettings(object_store="gcs", object_store_gcs_bucket="owned-private")

    class Native:
        profile = SimpleNamespace(max_object_bytes=67108864)

        def get_sync(self, key):
            entered.set()
            release.wait(2)
            return b"parquet"

    monkeypatch.setattr(
        "flyquery.core.services.storage.object_store_factory.build_object_store",
        lambda selected: SimpleNamespace(native=Native()),
    )
    directories = []
    original = tempfile.TemporaryDirectory

    def temporary(**kwargs):
        directory = original(**kwargs)
        directories.append(directory.name)
        return directory

    monkeypatch.setattr(
        "flyquery.core.services.execution.duckdb_executor.tempfile.TemporaryDirectory", temporary
    )
    executor = DuckDBExecutor(settings)
    task = asyncio.create_task(
        executor.execute("SELECT * FROM orders", {"orders": "gs://owned-private/tenant/version.parquet"})
    )
    assert await asyncio.to_thread(entered.wait, 2)
    task.cancel()
    release.set()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert directories and all(not Path(path).exists() for path in directories)


async def test_cloud_query_aggregate_bound_cleans_partial_materialization(monkeypatch):
    import tempfile
    from pathlib import Path
    from types import SimpleNamespace

    from flyquery.config import FlyquerySettings
    from flyquery.core.services.execution.duckdb_executor import DuckDBExecutor, ExecutionError

    settings = FlyquerySettings(object_store="gcs", object_store_gcs_bucket="owned-private")
    native = SimpleNamespace(profile=SimpleNamespace(max_object_bytes=10), get_sync=lambda key: b"12345678")
    monkeypatch.setattr(
        "flyquery.core.services.storage.object_store_factory.build_object_store",
        lambda selected: SimpleNamespace(native=native),
    )
    directories = []
    original = tempfile.TemporaryDirectory

    def temporary(**kwargs):
        directory = original(**kwargs)
        directories.append(directory.name)
        return directory

    monkeypatch.setattr(
        "flyquery.core.services.execution.duckdb_executor.tempfile.TemporaryDirectory", temporary
    )
    result = await DuckDBExecutor(settings).execute(
        "SELECT * FROM orders JOIN items ON true",
        {
            "orders": "gs://owned-private/tenant/orders.parquet",
            "items": "gs://owned-private/tenant/items.parquet",
        },
    )
    assert isinstance(result, ExecutionError) and "byte bound" in result.message
    assert directories and all(not Path(path).exists() for path in directories)


@pytest.mark.parametrize("owns_client", [True, False])
async def test_native_context_owns_cloud_store_and_executor_borrows_it(owns_client):
    from types import SimpleNamespace

    from pyfly.container import bean, configuration
    from pyfly.context import ApplicationContext
    from pyfly.core import Config

    from flyquery.config import FlyquerySettings
    from flyquery.core.configuration import FlyqueryConfiguration
    from flyquery.core.services.execution.duckdb_executor import DuckDBExecutor
    from flyquery.core.services.storage.adapters.gcs import GcsObjectStore
    from flyquery.core.services.storage.object_store import ObjectStore

    closed = []

    @configuration
    class Storage:
        @bean
        def settings(self) -> FlyquerySettings:
            return FlyquerySettings(object_store="gcs", object_store_gcs_bucket="owned-private")

        @bean
        def object_store(self) -> ObjectStore:
            return GcsObjectStore(
                "gs://owned-private",
                client=SimpleNamespace(close=lambda: closed.append("client")),
                owns_client=owns_client,
            )

        executor = FlyqueryConfiguration.executor

    context = ApplicationContext(Config({}))
    context.register_bean(Storage)
    await context.start()
    store = context.get_bean(ObjectStore)
    executor = context.get_bean(DuckDBExecutor)
    try:
        assert executor._cloud_store is store
        await executor.close()
        assert closed == [] and not store.native._closed
    finally:
        await context.stop()
    assert store.native._closed
    assert closed == (["client"] if owns_client else [])
    await store.close()
    assert closed == (["client"] if owns_client else [])
