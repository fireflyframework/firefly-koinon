# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Reader summaries preserve admitted metadata without inventing aggregate visibility."""

from contextlib import asynccontextmanager
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from koinon.catalog.browse import CatalogBrowse
from koinon.catalog.browse_dtos import CatalogBrowseInput
from koinon.catalog.errors import AccessDenied


@pytest.mark.asyncio
async def test_browse_serializes_only_admitted_own_metadata_and_unknown_counts():
    protected = False
    now = datetime(2026, 11, 10, tzinfo=UTC)
    metadata = {
        "format": "PDF",
        "language": " EN ",
        "tags": ["Legal", "legal", 7],
        "page_count": 0,
        "size_bytes": 1234,
        "row_count": True,
        "column_count": -1,
        "child_count": 999,
        "table_count": 99,
    }

    class Operation:
        selection = SimpleNamespace(revision=1, connections=())

        async def release(self):
            pass

        @asynccontextmanager
        async def read_fence(self):
            nonlocal protected
            protected = True
            try:
                yield
            finally:
                protected = False

    class Reader:
        async def begin(self, *args):
            return Operation()

        async def entries(self, actor, tenant, identifiers, **kwargs):
            if "hidden" in identifiers:
                raise AccessDenied("Unavailable")

    class Catalog:
        async def page(self, *args, **kwargs):
            return {"items": ["document", "folder", "hidden"], "scan_full": False}

        async def get(self, actor, tenant, identifier):
            assert protected
            assert identifier != "hidden", "Unauthorized metadata must not be hydrated"
            return SimpleNamespace(
                id=identifier,
                tenant_id=tenant,
                kind="document" if identifier == "document" else "collection",
                name="Visible.pdf",
                parent_id=None,
                workspace_id="workspace",
                project_id=None,
                description="",
                metadata_json=metadata,
                status="ready",
                created_by="actor",
                updated_by=None,
                created_at=now,
                updated_at=now,
            )

    result = (
        await CatalogBrowse(Catalog(), Reader()).page("actor", "tenant", CatalogBrowseInput())
    ).model_dump()
    assert set(result.get("summaries", {})) == {"document", "folder"}
    document = result["summaries"]["document"]
    assert document["format"] == "pdf" and document["language"] == "en"
    assert document["tags"] == ["pdf", "en", "Legal"]
    assert document["page_count"] == 0 and document["size_bytes"] == 1234
    assert document["row_count"] is None and document["column_count"] is None
    assert all(
        result["summaries"]["folder"][key] is None
        for key in ("child_count", "document_count", "dataset_count", "table_count")
    )
    assert result["total"] is None and result["total_is_exact"] is False
