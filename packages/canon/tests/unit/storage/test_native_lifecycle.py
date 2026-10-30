# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""The application owns singleton cloud clients, without provider traffic."""

from types import SimpleNamespace

import pytest
from koinon_storage.cloud import CloudProfile
from pyfly.container import bean, configuration
from pyfly.context import ApplicationContext
from pyfly.core import Config

from flycanon.config import CanonSettings
from flycanon.core.configuration import CanonCoreConfiguration
from flycanon.core.services.storage.cloud import CloudObjectStore
from flycanon.core.services.storage.object_store import ObjectStore


async def test_actual_canon_object_store_bean_releases_its_created_client():
    closed = []

    @configuration
    class Storage:
        @bean
        def settings(self) -> CanonSettings:
            return CanonSettings(object_store_backend="gcs", object_store_gcs_bucket="owned-private")

        object_store = CanonCoreConfiguration.object_store

    context = ApplicationContext(Config({}))
    context.register_bean(Storage)
    await context.start()
    store = context.get_bean(ObjectStore)
    store.native._client = SimpleNamespace(close=lambda: closed.append("client"))
    await context.stop()
    assert closed == ["client"] and store.native._closed
    await store.close()
    assert closed == ["client"]


@pytest.mark.parametrize("owns_client", [True, False])
async def test_cloud_override_preserves_explicit_supplied_client_ownership(owns_client):
    closed = []

    @configuration
    class Storage:
        @bean
        def object_store(self) -> ObjectStore:
            return CloudObjectStore(
                CloudProfile(backend="gcs", gcs_bucket="owned-private"),
                client=SimpleNamespace(close=lambda: closed.append("client")),
                owns_client=owns_client,
            )

    context = ApplicationContext(Config({}))
    context.register_bean(Storage)
    await context.start()
    store = context.get_bean(ObjectStore)
    await context.stop()
    assert store.native._closed and closed == (["client"] if owns_client else [])


async def test_actual_s3_bean_releases_its_owned_sdk_client(monkeypatch):
    import flycanon.core.services.storage.s3 as module

    closed = []
    monkeypatch.setattr(
        module.boto3, "client", lambda *args, **kwargs: SimpleNamespace(close=lambda: closed.append("client"))
    )

    @configuration
    class Storage:
        @bean
        def settings(self) -> CanonSettings:
            return CanonSettings(object_store_backend="s3", object_store_s3_bucket="owned-private")

        object_store = CanonCoreConfiguration.object_store

    context = ApplicationContext(Config({}))
    context.register_bean(Storage)
    await context.start()
    store = context.get_bean(ObjectStore)
    await context.stop()
    assert closed == ["client"]
    await store.close()
    assert closed == ["client"]


async def test_s3_read_drains_before_shutdown_and_closes_response_body(monkeypatch):
    import asyncio
    import io
    import threading

    from flycanon.core.services.storage.s3 import S3ObjectStore

    entered, release = threading.Event(), threading.Event()
    closed = []

    class Stream(io.BytesIO):
        def read(self, *args):
            entered.set()
            assert release.wait(2)
            assert closed == []
            return super().read(*args)

    body = Stream(b"retained")
    client = SimpleNamespace(
        get_object=lambda **kwargs: {"Body": body}, close=lambda: closed.append("client")
    )
    store = S3ObjectStore("owned-private", client=client)
    task = asyncio.create_task(store.get("retained/file"))
    assert await asyncio.to_thread(entered.wait, 2)
    shutdown = asyncio.create_task(store.close())
    await asyncio.sleep(0)
    release.set()
    assert await task == b"retained"
    await shutdown
    assert body.closed and closed == ["client"]
