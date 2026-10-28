# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from datetime import UTC, datetime

import pytest
from pyfly.core import PyFlyApplication
from pyfly.kernel import DuplicateKeyException

from koinon.app import KoinonApplication
from koinon.assistants.entities import Provider
from koinon.assistants.repositories import ProviderRepository
from koinon.catalog.entities import CatalogEntry, Tenant
from koinon.catalog.repositories import CatalogRepository, TenantRepository
from koinon.knowledge.indexes.entities import KnowledgeIndex
from koinon.knowledge.indexes.repositories import KnowledgeIndexRepository


@pytest.fixture
async def index_rows(tmp_path):
    config = tmp_path / "pyfly.yaml"
    config.write_text(
        "pyfly:\n  banner:\n    mode: off\n  agentic:\n    enabled: false\n  data:\n"
        "    relational:\n      enabled: true\n      ddl-auto: create\n"
        + f"      url: sqlite+aiosqlite:///{tmp_path / 'indexes.db'}\n"
    )
    app = PyFlyApplication(KoinonApplication, config_path=str(config))
    app.context.register_bean(KnowledgeIndexRepository)
    app.context.register_bean(ProviderRepository)
    await app.startup()
    try:
        await app.context.get_bean(TenantRepository).save(Tenant(id="tenant", name="Owned"))
        await app.context.get_bean(CatalogRepository).save(
            CatalogEntry(
                id="workspace",
                tenant_id="tenant",
                workspace_id="workspace",
                kind="workspace",
                name="Owned",
                created_by="issuer|actor",
                updated_by="issuer|actor",
            )
        )
        await app.context.get_bean(ProviderRepository).save(
            Provider(
                id="provider",
                tenant_id="tenant",
                name="Owned",
                kind="ollama",
                base_url="http://127.0.0.1:11434/v1",
                model_ids=["embedding"],
            )
        )
        yield app.context.get_bean(KnowledgeIndexRepository)
    finally:
        await app.shutdown()


def record(identifier, *, native="native", live=None):
    return KnowledgeIndex(
        id=identifier,
        tenant_id="tenant",
        workspace_id="workspace",
        native_workspace_id="workspace",
        domain="documents",
        native_id=native,
        provider_id="provider",
        provider_kind="ollama",
        model_id="embedding",
        dimensions=768,
        storage_dimensions=768,
        embedding_fingerprint="fingerprint",
        provider_revision=1,
        status="building",
        build_slot=live,
        created_by="issuer|actor",
        updated_by="issuer|actor",
    )


async def test_database_enforces_one_live_rebuild_and_unique_native_set(index_rows):
    await index_rows.save(record("first", live="tenant-document-workspace"))
    with pytest.raises(DuplicateKeyException):
        await index_rows.save(record("second", native="new", live="tenant-document-workspace"))
    with pytest.raises(DuplicateKeyException):
        await index_rows.save(record("third", native="native"))
    assert len(await index_rows.find_all(tenant_id="tenant")) == 1


async def test_native_repository_pages_only_requested_tenant_and_workspace(index_rows):
    await index_rows.save(record("first"))
    page = await index_rows.page("tenant", "workspace", "documents", limit=1, offset=0)
    assert [row.id for row in page[0]] == ["first"] and page[1] == 1
    assert await index_rows.page("foreign", "workspace", "documents", limit=1, offset=0) == ([], 0)
    assert await index_rows.page("tenant", "foreign", "documents", limit=1, offset=0) == ([], 0)
    assert page[0][0].created_at <= datetime.now(UTC)
