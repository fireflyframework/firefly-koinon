# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Reader catalog pages never publish hidden totals or hydrate denied entries."""

from contextlib import asynccontextmanager
from types import SimpleNamespace

import pytest

from koinon.catalog.errors import AccessDenied


@pytest.mark.asyncio
async def test_denied_entry_never_reaches_metadata_or_total(monkeypatch):
    from koinon.catalog.browse import CatalogBrowse
    from koinon.catalog.browse_dtos import CatalogBrowseInput

    class Catalog:
        async def page(self, actor, tenant, **filters):
            return {"items": ["denied"], "scan_full": False}

        async def get(self, actor, tenant, identifier):
            pytest.fail("Denied metadata was loaded")

    class Operation:
        selection = SimpleNamespace(revision=1, connections=())

        async def release(self):
            return None

        @asynccontextmanager
        async def read_fence(self):
            yield

    class Reader:
        async def begin(self, actor, tenant, overrides):
            return Operation()

        async def entries(self, actor, tenant, identifiers, **options):
            raise AccessDenied("Unavailable")

    browse = CatalogBrowse(Catalog(), Reader(), None, None)
    result = await browse.page("reader", "tenant", CatalogBrowseInput())
    assert result.items == [] and result.total is None and result.total_is_exact is False
    assert result.next_cursor is None and result.actors == {}


@pytest.mark.asyncio
async def test_authorized_metadata_is_hydrated_only_inside_revalidated_read_fence(monkeypatch):
    from koinon.catalog.browse import CatalogBrowse
    from koinon.catalog.browse_dtos import CatalogBrowseInput

    protected = False
    calls = []

    class Operation:
        selection = SimpleNamespace(revision=1, connections=())

        async def release(self):
            calls.append("fresh")

        @asynccontextmanager
        async def read_fence(self):
            nonlocal protected
            assert calls[-1] == "fresh"
            protected = True
            try:
                yield
            finally:
                protected = False

    class Reader:
        async def begin(self, *args):
            return Operation()

        async def entries(self, *args, **kwargs):
            calls.append("admit")

    class Catalog:
        async def page(self, *args, **kwargs):
            return {"items": ["folder"], "scan_full": False}

        async def get(self, *args):
            assert protected, "Source payload hydrated outside the checked local snapshot"
            calls.append("hydrate")
            return SimpleNamespace(
                id="folder",
                kind="collection",
                name="Visible",
                metadata_json={},
                status="ready",
                created_by=None,
                updated_by=None,
            )

    monkeypatch.setattr("koinon.catalog.browse.entry_dto", lambda entry: {"id": entry.id})
    monkeypatch.setattr("koinon.catalog.browse.CatalogEntryOutput.model_validate", lambda value: value)
    monkeypatch.setattr(
        "koinon.catalog.browse.CatalogBrowseOutput", lambda **values: SimpleNamespace(**values)
    )
    result = await CatalogBrowse(Catalog(), Reader()).page("reader", "tenant", CatalogBrowseInput())
    assert result.items == [{"id": "folder"}]
    assert calls == ["admit", "fresh", "hydrate", "fresh"]
