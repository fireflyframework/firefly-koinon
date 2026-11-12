# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from koinon.workers.admission import WorkAdmission, WorkAdmissionSettings


async def test_query_worker_uses_shared_owned_process_fence_and_never_dispatches_intake(monkeypatch):
    import subprocess

    from koinon.knowledge.bulk.entities import now
    from koinon.knowledge.bulk.settings import BulkSettings
    from koinon.knowledge.bulk.worker import ProcessSupervisor
    from koinon.knowledge.bulk_queries.worker import QueryWorker

    calls = []

    def child(command, **options):
        calls.append((command, options))
        return SimpleNamespace(pid=1, poll=lambda: 0)

    monkeypatch.setattr(subprocess, "Popen", child)
    monkeypatch.setattr("koinon.knowledge.bulk.worker.wait_owned_child", AsyncMock(return_value=0))
    monkeypatch.setattr("koinon.knowledge.bulk.worker.stop_owned_child", lambda _: None)
    queue = SimpleNamespace(check=AsyncMock(), failed=AsyncMock(), claim=AsyncMock())
    settings = BulkSettings(worker_enabled=True)
    worker = QueryWorker(queue, settings, WorkAdmission(WorkAdmissionSettings()))
    assert isinstance(worker, ProcessSupervisor)
    await worker.tick()
    queue.claim.assert_not_awaited()
    lease = SimpleNamespace(
        item_id="query", worker_id="worker", attempt=1, expires_at=now() + timedelta(seconds=300)
    )
    await worker.supervise(lease)
    command, options = calls[0]
    assert command[1:5] == ["-I", "-B", "-m", "koinon.knowledge.bulk_queries.worker"]
    assert options["start_new_session"] is True
    queue.failed.assert_awaited_once_with(lease, code="BULK_CHILD_OUTCOME_UNCONFIRMED", unknown=True)


@pytest.mark.parametrize("crash_after_commit", [False, True])
async def test_committed_query_recovers_without_live_model_authority_or_second_execution(crash_after_commit):
    from koinon.knowledge.bulk_queries.execution import QueryBatchExecutor

    state = {"committed": not crash_after_commit, "executions": 0, "acknowledged": []}
    descriptor = object()
    lease = SimpleNamespace(subject="reader", token_id=None)

    async def inspect(_):
        return ("committed", descriptor) if state["committed"] else ("absent", None)

    async def check(_):
        if state["committed"]:
            raise PermissionError("Source and model connection were revoked after native commit")

    async def execute(_):
        state["executions"] += 1
        state["committed"] = True
        raise ConnectionError("Lost acknowledgement after native commit")

    async def acknowledge(_, value):
        state["acknowledged"].append(value)

    native = SimpleNamespace(
        inspect_commit_metadata=inspect, execute=execute, acknowledge_commit_metadata=acknowledge
    )
    queue = SimpleNamespace(check=check, failed=AsyncMock())
    await QueryBatchExecutor(queue, native).execute(lease)
    assert state["acknowledged"] == [descriptor]
    assert state["executions"] == int(crash_after_commit)
    queue.failed.assert_not_awaited()
