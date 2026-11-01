# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import asyncio
import contextvars
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from koinon.knowledge.bulk.settings import BulkSettings
from koinon.knowledge.bulk.worker import BulkWorker
from koinon.knowledge.bulk_queries.worker import QueryWorker
from koinon.workers.admission import WorkAdmission, WorkAdmissionSettings


@pytest.mark.parametrize("kind", [BulkWorker, QueryWorker])
async def test_bulk_claim_waits_for_shared_permit_and_keeps_it_until_child_cleanup(kind):
    admission = WorkAdmission(WorkAdmissionSettings(worker_capacity=1))
    settings = BulkSettings(worker_enabled=True, query_worker_enabled=True)
    lease = SimpleNamespace(item_id="item")
    entered, drained = asyncio.Event(), asyncio.Event()
    queue = SimpleNamespace(claim=AsyncMock(return_value=lease))
    worker = kind(queue, settings, admission)

    async def execute(value):
        assert admission.worker_active == 1
        entered.set()
        try:
            await asyncio.Event().wait()
        finally:
            assert admission.worker_active == 1
            await asyncio.sleep(0.01)
            drained.set()

    worker.supervise = execute
    async with admission.hold("structured"):
        task = asyncio.create_task(worker.tick(), context=contextvars.Context())
        await asyncio.sleep(0.01)
        queue.claim.assert_not_awaited()
    await asyncio.wait_for(entered.wait(), 1)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert drained.is_set() and admission.worker_active == 0
    queue.claim.assert_awaited_once()


def test_api_forces_bulk_off_and_worker_retains_explicit_optin():
    from koinon.operations.process import process_configuration

    enabled = {"koinon": {"knowledge": {"bulk": {"worker_enabled": True, "query_worker_enabled": True}}}}
    api = process_configuration(enabled, role="api")
    assert not api["koinon"]["knowledge"]["bulk"]["worker_enabled"]
    assert not api["koinon"]["knowledge"]["bulk"]["query_worker_enabled"]
    worker = process_configuration(enabled, role="worker")
    assert worker["koinon"]["knowledge"]["bulk"]["worker_enabled"]
    assert worker["koinon"]["knowledge"]["bulk"]["query_worker_enabled"]
    assert not process_configuration({}, role="worker")["koinon"]["knowledge"]["bulk"]["worker_enabled"]


def test_claimed_child_is_resource_only_despite_inherited_worker_configuration(monkeypatch):
    from koinon.knowledge.bulk.worker import claimed_child_configuration, claimed_child_environment

    monkeypatch.setenv("PYFLY_KOINON_PROCESS_ROLE", "worker")
    monkeypatch.setenv("PYFLY_KOINON_KNOWLEDGE_BULK_WORKER_ENABLED", "true")
    monkeypatch.setenv("PYFLY_KOINON_KNOWLEDGE_BULK_QUERY_WORKER_ENABLED", "true")
    monkeypatch.setenv("PYFLY_SCHEDULING_ENABLED", "true")
    values = {
        "koinon": {
            "process": {"role": "worker"},
            "knowledge": {"bulk": {"worker_enabled": True, "query_worker_enabled": True}},
        },
        "pyfly": {"scheduling": {"enabled": True}},
    }
    child = claimed_child_configuration(values)
    environment = claimed_child_environment()
    assert child["koinon"]["process"]["role"] == "api"
    assert child["pyfly"]["scheduling"]["enabled"] is False
    assert child["koinon"]["knowledge"]["bulk"] == {"worker_enabled": False, "query_worker_enabled": False}
    assert environment["PYFLY_KOINON_PROCESS_ROLE"] == "api"
    assert all(
        environment[key] == "false"
        for key in (
            "PYFLY_SCHEDULING_ENABLED",
            "PYFLY_KOINON_KNOWLEDGE_BULK_WORKER_ENABLED",
            "PYFLY_KOINON_KNOWLEDGE_BULK_QUERY_WORKER_ENABLED",
        )
    )
    assert values["koinon"]["process"]["role"] == "worker"
