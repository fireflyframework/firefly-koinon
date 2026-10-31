# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Private attachment storage releases only application-owned transports."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from pyfly.container import bean, configuration
from pyfly.context import ApplicationContext
from pyfly.core import Config

import koinon.knowledge.attachments.storage as module
from koinon.knowledge.attachments.settings import AttachmentSettings
from koinon.knowledge.attachments.storage import AttachmentStorage
from koinon.storage.cloud import CloudBlobStore
from koinon.storage.s3 import S3BlobStore
from koinon.storage.settings import AttachmentStorageProfile


@pytest.mark.parametrize("backend", ["gcs", "s3"])
@pytest.mark.parametrize("owns_client", [True, False])
async def test_native_attachment_owner_disposes_created_transport_without_closing_borrowed_client(
    monkeypatch, owns_client, backend
):
    closed = []
    profile = AttachmentStorageProfile(backend=backend, gcs_bucket="owned-private", s3_bucket="owned-private")
    kind = CloudBlobStore if backend == "gcs" else S3BlobStore
    created = kind(
        profile, client=SimpleNamespace(close=lambda: closed.append("client")), owns_client=owns_client
    )
    monkeypatch.setattr(
        module, "CloudBlobStore" if backend == "gcs" else "S3BlobStore", lambda selected: created
    )

    @configuration
    class Settings:
        @bean
        def settings(self) -> AttachmentSettings:
            return AttachmentSettings()

        @bean
        def profile(self) -> AttachmentStorageProfile:
            return profile

    context = ApplicationContext(Config({}))
    context.register_bean(Settings)
    context.register_bean(AttachmentStorage)
    await context.start()
    owner = context.get_bean(AttachmentStorage)
    assert owner.configured() is created and closed == []
    await context.stop()
    assert created.native._closed if backend == "gcs" else created._lifecycle.closed
    assert closed == (["client"] if owns_client else [])
    await owner.close()
    assert closed == (["client"] if owns_client else [])
    with pytest.raises(RuntimeError, match="closed"):
        owner.configured()


async def test_attachment_owner_never_closes_a_borrowed_store():
    borrowed = SimpleNamespace(close=AsyncMock())
    owner = AttachmentStorage(
        AttachmentSettings(), AttachmentStorageProfile(backend="gcs", gcs_bucket="owned-private")
    )
    owner.store = borrowed
    await owner.close()
    borrowed.close.assert_not_awaited()


async def test_private_s3_lazy_client_is_shared_across_concurrent_requests(monkeypatch):
    import asyncio
    import time

    import boto3

    clients = []
    closed = []

    def create(*args, **kwargs):
        time.sleep(0.02)
        client = SimpleNamespace(put_object=lambda **kwargs: None, close=lambda: closed.append(True))
        clients.append(client)
        return client

    monkeypatch.setattr(boto3, "client", create)
    store = S3BlobStore(AttachmentStorageProfile(backend="s3", s3_bucket="owned-private"))
    await asyncio.gather(store.put("tenant/first", b"first"), store.put("tenant/second", b"second"))
    await store.close()
    assert len(clients) == 1 and closed == [True]


async def test_replacing_current_store_does_not_abandon_the_original_owned_transport(monkeypatch):
    owned = SimpleNamespace(close=AsyncMock())
    borrowed = SimpleNamespace(close=AsyncMock())
    monkeypatch.setattr(module, "CloudBlobStore", lambda profile: owned)
    owner = AttachmentStorage(
        AttachmentSettings(), AttachmentStorageProfile(backend="gcs", gcs_bucket="owned-private")
    )
    assert owner.configured() is owned
    owner.store = borrowed
    await owner.close()
    owned.close.assert_awaited_once()
    borrowed.close.assert_not_awaited()
