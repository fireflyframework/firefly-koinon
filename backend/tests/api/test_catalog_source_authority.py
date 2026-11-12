# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Imported metadata is protected before catalog DTO projection."""

import importlib.util
from contextlib import asynccontextmanager
from pathlib import Path
from types import SimpleNamespace

import pytest

from koinon.api.controllers.catalog import CatalogController
from koinon.integrations.content_sources.errors import SourceError

spec = importlib.util.spec_from_file_location(
    "source_catalog_web_fixture", Path(__file__).resolve().parents[1] / "web/conftest.py"
)
assert spec and spec.loader
native = importlib.util.module_from_spec(spec)
spec.loader.exec_module(native)
client = native.client


@pytest.mark.asyncio
async def test_catalog_detail_denial_precedes_metadata_load(monkeypatch):
    loaded = []

    class Catalog:
        async def get(self, *args):
            loaded.append(args)
            raise AssertionError("Unauthorized catalog title loaded")

    class Reader:
        async def entries(self, *args):
            raise SourceError("access_denied")

    controller = object.__new__(CatalogController)
    controller.catalog, controller.reader = Catalog(), Reader()
    monkeypatch.setattr(
        "koinon.api.controllers.catalog.identity_from_request", lambda _: SimpleNamespace(subject="reader")
    )
    with pytest.raises(SourceError, match="access_denied"):
        await controller.catalog_get("tenant", "imported", object())
    assert loaded == []


@pytest.mark.parametrize("deny", [False, True])
def test_http_catalog_detail_checks_local_fence_before_loading_metadata(client, monkeypatch, deny):
    from koinon.catalog.service import CatalogService

    protected = False
    hydrated = []

    class Operation:
        @asynccontextmanager
        async def read_fence(self):
            nonlocal protected
            if deny:
                raise SourceError("authority_changed")
            protected = True
            try:
                yield
            finally:
                protected = False

        async def release(self):
            return None

    async def entries(*args):
        return Operation()

    context = client.native_app.state.context
    service = context.get_bean(CatalogService)
    original = service.get

    async def get(*args):
        assert protected, "Catalog payload loaded before local source fence"
        hydrated.append(args[-1])
        return await original(*args)

    monkeypatch.setattr(context.get_bean(CatalogController).reader, "entries", entries)
    monkeypatch.setattr(service, "get", get)
    response = client.get(f"/api/v1/tenants/north/catalog/{client.workspace_id}", headers=native.bearer())
    if deny:
        assert response.status_code in (403, 409), response.text
        assert not hydrated and "Research" not in response.text
    else:
        assert response.status_code == 200, response.text
        assert response.json()["name"] == "Research" and hydrated == [client.workspace_id]
