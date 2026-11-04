# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from importlib import import_module
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from pyfly.data.transaction import current_unit_of_work
from test_mode_discovery import discovery, tree
from test_organization_knowledge_service import update_input

from koinon.workers.admission import WorkAdmission, WorkAdmissionSettings

pytest_plugins = ("test_organization_knowledge_service",)


async def worker(knowledge):
    await tree(knowledge, 0)
    service, queue, targets, scanner = discovery(knowledge)
    request = await service.request("admin", "north", update_input(), "worker-mode")
    module = import_module("koinon.organization_knowledge.transitions.worker")
    progress = import_module("koinon.organization_knowledge.transitions.progress").ModeProgress(
        queue, targets
    )
    stages = [SimpleNamespace(step=AsyncMock()) for _ in range(3)]
    verification = SimpleNamespace(step=AsyncMock())
    activation = SimpleNamespace(activate=AsyncMock())
    admission = WorkAdmission(WorkAdmissionSettings())
    instance = module.ModeWorker(
        queue,
        scanner,
        *stages,
        verification,
        activation,
        progress,
        module.ModeWorkerSettings(enabled=True),
        admission,
    )
    return service, request, instance, admission


async def test_mode_worker_discovers_one_page_and_releases_durable_lease(knowledge):
    service, request, instance, admission = await worker(knowledge)
    try:
        await instance.tick()
        row = await service.get("admin", "north", request.id)
        assert row.stage == "preflight" and row.status == "queued"
        job = await service.jobs.repository.find_by_id(request.job_id)
        assert job.lease_until is None and job.attempts == 0
        assert row.counters["catalog_scanned"] == 1
    finally:
        admission.close_workers()


@pytest.mark.parametrize(
    "stage,field",
    [
        ("preflight", "preflight"),
        ("repair_views", "views"),
        ("prepare_indexes", "indexes"),
        ("verify", "verification"),
    ],
)
async def test_worker_dispatches_native_work_outside_primary_units(knowledge, stage, field):
    service, request, instance, admission = await worker(knowledge)
    row = await service.records.find_by_id(request.id)
    row.stage = stage
    await service.records.save(row)

    async def step(tenant_id, identifier, worker_id):
        assert current_unit_of_work("primary") is None
        await instance.progress.record(tenant_id, identifier, worker_id, stage=stage, milliseconds=1)

    getattr(instance, field).step.side_effect = step
    try:
        await instance.tick()
        getattr(instance, field).step.assert_awaited_once()
        assert (await service.get("admin", "north", request.id)).status == "queued"
    finally:
        admission.close_workers()


async def test_worker_failure_preserves_mode_and_has_safe_durable_error(knowledge):
    service, request, instance, admission = await worker(knowledge)
    row = await service.records.find_by_id(request.id)
    row.stage = "prepare_indexes"
    await service.records.save(row)
    instance.indexes.step.side_effect = RuntimeError("private provider detail")
    try:
        await instance.tick()
        failed = await service.get("admin", "north", request.id)
        assert failed.status == "failed" and failed.active_mode == "rlm"
        assert "private" not in failed.error and failed.error_code == "KNOWLEDGE_MODE_FAILED"
    finally:
        admission.close_workers()
