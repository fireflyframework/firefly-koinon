# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from pyfly.kernel import ConflictException
from test_index_persistence import index_rows as index_rows

from koinon.knowledge.indexes.worker import IndexWorker, IndexWorkerSettings
from koinon.workers.admission import WorkAdmission, WorkAdmissionSettings


def test_worker_lease_must_cover_provider_budget_and_commit_margin():
    IndexWorkerSettings(enabled=True).validate()
    for settings in (
        IndexWorkerSettings(batch_timeout_seconds=91),
        IndexWorkerSettings(lease_seconds=60, batch_timeout_seconds=45),
    ):
        with pytest.raises(ValueError):
            settings.validate()


async def test_expired_worker_is_denied_before_provider_secret_or_model_client(index_rows):
    provider = AsyncMock(side_effect=AssertionError("A stale lease must not open the provider"))
    lifecycle = SimpleNamespace(reader=SimpleNamespace(planner=SimpleNamespace(provider=provider)))
    queue = SimpleNamespace(
        jobs=SimpleNamespace(
            repository=SimpleNamespace(
                find_by_id=AsyncMock(return_value=SimpleNamespace(id="job", tenant_id="tenant"))
            )
        ),
        fence=AsyncMock(side_effect=ConflictException("Lease lost", code="INDEX_LEASE_LOST")),
    )
    worker = IndexWorker(lifecycle, queue, IndexWorkerSettings(), WorkAdmission(WorkAdmissionSettings()))
    with pytest.raises(ConflictException):
        await worker.execute("job")
    provider.assert_not_awaited()
