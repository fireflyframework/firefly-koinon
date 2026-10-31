# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from pyfly.kernel import ConflictException
from test_query_service import request


async def test_expired_query_generation_cannot_release_reclaimed_work(queries):
    from koinon.jobs.repository import JobRepository
    from koinon.knowledge.bulk.entities import now
    from koinon.knowledge.bulk_queries.queue import QueryBatchQueue
    from koinon.knowledge.bulk_queries.service import QueryBatches

    await queries.context.get_bean(QueryBatches).create("issuer|analyst", "north", request(queries), "create")
    queue = queries.context.get_bean(QueryBatchQueue)
    first = await queue.claim("old")
    jobs = queries.context.get_bean(JobRepository)
    job = await jobs.find_by_id(first.job_id)
    job.lease_until = now() - timedelta(seconds=1)
    await jobs.save(job)
    with pytest.raises(ConflictException) as expired:
        await queue.check(first)
    assert expired.value.code == "BULK_LEASE_LOST"
    current = await queue.claim("new")
    assert current.item_id == first.item_id and current.attempt == first.attempt + 1
    with pytest.raises(ConflictException) as stale:
        await queue.failed(first, code="STALE", unknown=True)
    assert stale.value.code == "BULK_LEASE_LOST"
    await queue.check(current)


async def test_disabled_provider_prevents_every_native_or_model_dispatch(queries):
    from koinon.assistants.repositories import ProviderRepository
    from koinon.knowledge.bulk_queries.execution import QueryBatchExecutor
    from koinon.knowledge.bulk_queries.queue import QueryBatchQueue
    from koinon.knowledge.bulk_queries.service import QueryBatches

    service = queries.context.get_bean(QueryBatches)
    batch = await service.create("issuer|analyst", "north", request(queries), "create")
    queue = queries.context.get_bean(QueryBatchQueue)
    lease = await queue.claim("worker")
    providers = queries.context.get_bean(ProviderRepository)
    provider = await providers.find_by_id("model-provider")
    provider.enabled = False
    await providers.save(provider)
    native = SimpleNamespace(inspect=AsyncMock(), execute=AsyncMock(), acknowledge=AsyncMock())
    await QueryBatchExecutor(queue, native).execute(lease)
    native.inspect.assert_not_awaited()
    native.execute.assert_not_awaited()
    native.acknowledge.assert_not_awaited()
    item = (await service.items("issuer|analyst", "north", batch.id)).items[0]
    assert item.status == "reconciling" and item.error_code == "BULK_QUERY_CONNECTION_REQUIRED"
