# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Index operations honor the application-managed native service replacement."""

from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from pyfly.container import Container
from pyfly.data.relational.datasource_registry import DataSourceRegistry

from koinon.knowledge.adapters import NativeDomains
from koinon.knowledge.indexes import adapters


@pytest.fixture
def managed_index(monkeypatch):
    from flycanon.config import CanonSettings
    from flycanon.core.services.embeddings.embedding_service import EmbeddingRegistry
    from flycanon.core.services.embeddings.embedding_sets import EmbeddingSetService
    from flycanon.core.services.retrieval.corpus_factory import CorpusContext
    from flycanon.models.repositories import ChunkRepository, IngestJobRepository
    from flycanon.models.repositories.embedding_set_repository import EmbeddingSetRepository

    activations, pointers, statuses = [], [], []

    async def activate(**values):
        activations.append(values)

    async def point(**values):
        pointers.append(values)

    async def status(**values):
        statuses.append(values)

    native_set = SimpleNamespace(
        id="set",
        provider="ollama",
        model="embedding",
        dimensions=3,
        config_fingerprint="8e91918230a8def64ed156b35a480762a86c0810092331b2c3d160bca2e0cccf",
    )
    sets = SimpleNamespace(list_for=AsyncMock(return_value=[native_set]), activate=activate)
    chunks = SimpleNamespace(coverage_counts=AsyncMock(return_value={"chunk_count": 2, "vector_count": 2}))
    corpus = SimpleNamespace(
        backend="pgvector", initialise=AsyncMock(), vector_store=object(), dense_backend=object()
    )
    services = {
        CanonSettings: object(),
        EmbeddingRegistry: object(),
        EmbeddingSetService: sets,
        CorpusContext: corpus,
        ChunkRepository: chunks,
        IngestJobRepository: object(),
        EmbeddingSetRepository: SimpleNamespace(point_workspace_at=point, set_status=status),
    }
    native = SimpleNamespace(_resolve=services.__getitem__)
    source = object()

    class Session:
        async def execute(self, statement, params):
            return SimpleNamespace(
                mappings=lambda: SimpleNamespace(
                    one_or_none=lambda: {
                        "provider": "ollama",
                        "model": "embedding",
                        "dimensions": 3,
                        "status": "ready",
                    }
                )
            )

    @asynccontextmanager
    async def unit(selected):
        assert selected is source
        yield Session()

    monkeypatch.setattr(adapters, "infrastructure_unit", unit)
    container = Container()
    container.register_instance(Container, container)
    container.register_instance(DataSourceRegistry, SimpleNamespace(get=lambda name: source))
    container.register_instance(NativeDomains, native)
    container.register(adapters.NativeIndexAdapter)
    adapter = container.resolve(adapters.NativeIndexAdapter)

    def unmanaged(*args, **kwargs):
        raise AssertionError("The managed native service must not be reconstructed")

    monkeypatch.setattr(adapters, "NativeDomains", unmanaged)
    record = SimpleNamespace(
        id="index",
        domain="documents",
        tenant_id="tenant",
        native_workspace_id="workspace",
        native_id="set",
        updated_by="actor",
        provider_kind="ollama",
        model_id="embedding",
        dimensions=3,
        batch_size=16,
    )
    return SimpleNamespace(
        adapter=adapter,
        record=record,
        services=services,
        activations=activations,
        pointers=pointers,
        statuses=statuses,
        chunks=chunks,
    )


async def test_container_override_supplies_document_coverage(managed_index):
    result = await managed_index.adapter.coverage(managed_index.record)
    assert result == {"chunk_count": 2, "vector_count": 2, "complete": True}


async def test_container_override_supplies_immutable_target_inspection(managed_index):
    result = await managed_index.adapter.create(
        managed_index.record, actor="actor", endpoint="https://models.example.test/v1"
    )
    assert result == "8e91918230a8def64ed156b35a480762a86c0810092331b2c3d160bca2e0cccf"


async def test_container_override_supplies_reindex_operation_dependencies(managed_index, monkeypatch):
    from flycanon.core.services.embeddings import reindex_service
    from flycanon.models.repositories import ChunkRepository, IngestJobRepository

    class Reindex:
        def __init__(self, **dependencies):
            assert dependencies["chunks"] is managed_index.services[ChunkRepository]
            assert dependencies["jobs"] is managed_index.services[IngestJobRepository]

        async def step(self, **values):
            assert values["tenant_id"] == "tenant" and values["workspace_id"] == "workspace"
            return {"complete": False, "processed": 1}

    monkeypatch.setattr(reindex_service, "ReindexService", Reindex)
    result = await managed_index.adapter.step(
        managed_index.record, embedder=object(), validate_write=AsyncMock()
    )
    assert result == {
        "complete": False,
        "processed": 1,
        "chunk_count": 2,
        "vector_count": 2,
        "indexed": False,
    }


@pytest.mark.parametrize("restore,previous", [(False, "previous"), (True, "previous"), (True, None)])
async def test_container_override_supplies_activation_and_restore(
    managed_index, monkeypatch, restore, previous
):
    monkeypatch.setattr(
        managed_index.adapter, "overview", AsyncMock(return_value={"active_native_id": "set"})
    )
    monkeypatch.setattr(adapters, "ann_qualified", AsyncMock(return_value=True))
    await managed_index.adapter.activate(managed_index.record, previous_native_id=previous, restore=restore)
    if restore and previous is None:
        assert managed_index.pointers == [
            {"tenant_id": "tenant", "workspace_id": "workspace", "set_id": None}
        ]
        assert managed_index.statuses == [
            {
                "tenant_id": "tenant",
                "workspace_id": "workspace",
                "set_id": "set",
                "status": "ready",
            }
        ]
        assert managed_index.activations == []
    else:
        assert managed_index.activations == [
            {
                "tenant_id": "tenant",
                "workspace_id": "workspace",
                "set_id": previous if restore else "set",
            }
        ]
