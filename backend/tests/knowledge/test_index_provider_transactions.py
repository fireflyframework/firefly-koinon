# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Provider waits must not retain database units or publish stale configuration."""

from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from pyfly.data.transaction import current_unit_of_work
from pyfly.kernel import ConflictException
from test_index_persistence import index_rows as index_rows

from koinon.assistants.repositories import ProviderRepository
from koinon.knowledge.indexes.planner import IndexPlanner
from koinon.knowledge.indexes.service import KnowledgeIndexService


def planning_service(rows, callback):
    providers = ProviderRepository()
    planner = IndexPlanner(providers, None, None)

    @asynccontextmanager
    async def opened(provider, model, dimensions=None):
        async def embed(texts):
            await callback(providers)
            return SimpleNamespace(embeddings=[[0.25] * 64, [0.5] * 64])

        yield SimpleNamespace(embed=embed)

    planner.open = opened
    reader = KnowledgeIndexService(
        SimpleNamespace(catalog=SimpleNamespace(_lock_tenant=AsyncMock())),
        SimpleNamespace(overview=AsyncMock(return_value={"active_native_id": None, "chunk_count": 3})),
        SimpleNamespace(authority=AsyncMock(), selected=AsyncMock(return_value=None)),
        planner,
        rows,
    )
    reader.authority = AsyncMock(return_value=SimpleNamespace(id="workspace"))
    reader.native_binding = AsyncMock(return_value=SimpleNamespace(native_workspace_id="workspace"))
    return reader


def request():
    return {
        "workspace_id": "workspace",
        "domain": "documents",
        "provider_id": "provider",
        "model_id": "embedding",
    }


async def test_dimension_probe_releases_database_before_network_io(index_rows):
    async def probe(providers):
        assert all(current_unit_of_work(name) is None for name in ("primary", "canon", "structured"))

    plan = await planning_service(index_rows, probe).plan("actor", "tenant", request())
    assert plan["dimensions"] == 64 and plan["chunk_count"] == 3


async def test_provider_change_during_probe_cannot_qualify_stale_configuration(index_rows):
    async def change(providers):
        provider = await providers.find_by_id("provider")
        provider.revision += 1
        await providers.save(provider)

    with pytest.raises(ConflictException) as error:
        await planning_service(index_rows, change).plan("actor", "tenant", request())
    assert error.value.code == "INDEX_PROVIDER_CHANGED"


async def worker_fixture(rows, callback):
    from test_index_queue import prepared

    from koinon.knowledge.connections.service import embedding_fingerprint
    from koinon.knowledge.indexes.lifecycle import IndexLifecycleService
    from koinon.knowledge.indexes.worker import IndexWorker, IndexWorkerSettings
    from koinon.workers.admission import WorkAdmission, WorkAdmissionSettings

    queue, job = await prepared(rows)
    reader = planning_service(rows, callback)
    reader.facade = SimpleNamespace(
        catalog=SimpleNamespace(
            _lock_tenant=AsyncMock(),
            _refresh_managed_memberships=AsyncMock(),
            restriction=None,
            membership_repository=SimpleNamespace(find_all=AsyncMock(return_value=[])),
        )
    )
    provider = await ProviderRepository().find_by_id("provider")
    row = await rows.find_by_id("target")
    row.embedding_fingerprint = embedding_fingerprint(provider, "embedding", 768, 768)
    await rows.save(row)
    lifecycle = IndexLifecycleService(reader, rows, queue.jobs)
    published = []

    async def step(record, *, embedder, validate_write, publication_guard=None):
        await embedder.embed(["Owned content"])
        if publication_guard is not None:
            async with publication_guard():
                await validate_write()
                published.append(record.native_id)
        else:
            await validate_write()
            published.append(record.native_id)
        return {"complete": True, "indexed": True, "chunk_count": 1, "vector_count": 1}

    reader.adapter.step = step
    worker = IndexWorker(lifecycle, queue, IndexWorkerSettings(), WorkAdmission(WorkAdmissionSettings()))
    assert await queue.claim(worker.worker_id) == job.id
    return worker, job, published


async def test_worker_does_not_keep_database_transactions_open_during_embedding(index_rows):
    async def probe(providers):
        assert all(current_unit_of_work(name) is None for name in ("primary", "canon", "structured"))

    worker, job, published = await worker_fixture(index_rows, probe)
    await worker.execute(job.id)
    assert published == ["native"]
    assert (await index_rows.find_by_id("target")).status == "ready"


async def test_worker_rechecks_provider_after_embedding_before_publishing(index_rows):
    async def change(providers):
        provider = await providers.find_by_id("provider")
        provider.revision += 1
        await providers.save(provider)

    worker, job, published = await worker_fixture(index_rows, change)
    with pytest.raises(ConflictException) as error:
        await worker.execute(job.id)
    assert error.value.code == "INDEX_PROVIDER_CHANGED"
    assert not published


async def test_plan_captures_tenant_before_workspace_or_provider_locks(index_rows):
    async def probe(providers):
        assert current_unit_of_work("primary") is None

    reader = planning_service(index_rows, probe)
    lock = AsyncMock()
    reader.facade = SimpleNamespace(catalog=SimpleNamespace(_lock_tenant=lock))
    calls = []

    async def authority(*args, **kwargs):
        calls.append("authority")
        assert lock.await_count == len(calls)
        return SimpleNamespace(id="workspace")

    reader.authority = authority
    await reader.plan("actor", "tenant", request())
    assert lock.await_count == 2
