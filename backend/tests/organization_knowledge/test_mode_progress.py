# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from importlib import import_module

import pytest
from pyfly.kernel import ConflictException
from test_mode_discovery import discovery, tree
from test_organization_knowledge_service import update_input

pytest_plugins = ("test_organization_knowledge_service",)


async def setup(knowledge):
    await tree(knowledge, 1)
    service, queue, targets, scanner = discovery(knowledge)
    request = await service.request("admin", "north", update_input(), "progress")
    await queue.claim("worker")
    await scanner.step("north", request.id, "worker")
    progress = import_module("koinon.organization_knowledge.transitions.progress").ModeProgress(
        queue, targets
    )
    return service, queue, targets, request, progress


async def test_completed_bounded_step_releases_lease_without_spending_retry_budget(knowledge):
    service, queue, targets, request, progress = await setup(knowledge)
    target = (await targets.page("north", request.id))[0]
    await progress.record(
        "north",
        request.id,
        "worker",
        stage="preflight",
        target_id=target.id,
        status="prepared",
        result={"roles": {}},
        milliseconds=25,
    )
    current = await service.get("admin", "north", request.id)
    assert current.stage_milliseconds["preflight"] == 25
    assert current.counters["prepared"] == 1
    assert current.status == "queued"
    assert await queue.claim("restarted") == request.id
    job = await service.jobs.repository.find_by_id(request.job_id)
    assert job.attempts == 1
    assert (await targets.page("north", request.id, status="prepared"))[0].id == target.id


async def test_target_prerequisite_is_concrete_and_preserves_active_settings(knowledge):
    service, _, targets, request, progress = await setup(knowledge)
    target = next(row for row in await targets.page("north", request.id) if row.kind == "document")
    await progress.reject(
        "north",
        request.id,
        "worker",
        target_id=target.id,
        code="SOURCE_VERSION_PREPARATION_REQUIRED",
        milliseconds=12,
    )
    current = await service.get("admin", "north", request.id)
    row = await targets.find_by_id(target.id)
    assert current.status == "failed"
    assert row.error_code == "SOURCE_VERSION_PREPARATION_REQUIRED"
    assert row.result["action"] == "reprocess_document"
    assert row.result["catalog_id"] == target.catalog_id
    assert "committed document version" in current.error
    assert (await knowledge.service.get("admin", "north")).documents.answer_mode == "rlm"


async def test_old_step_cannot_overwrite_cancelled_transition(knowledge):
    service, _, targets, request, progress = await setup(knowledge)
    current = await service.get("admin", "north", request.id)
    await service.cancel("admin", "north", request.id, expected_revision=current.revision)
    target = (await targets.page("north", request.id))[0]
    with pytest.raises(ConflictException):
        await progress.record(
            "north",
            request.id,
            "worker",
            stage="preflight",
            target_id=target.id,
            status="prepared",
            result={},
            milliseconds=1,
        )
    assert (await targets.find_by_id(target.id)).status == "queued"


async def test_failed_preparation_keeps_existing_index_and_job_receipts(knowledge):
    _, _, targets, request, progress = await setup(knowledge)
    target = next(row for row in await targets.page("north", request.id) if row.kind == "workspace")
    target.result = {"index_id": "owned-index", "job_id": "owned-job", "roles": {}}
    await targets.save(target)
    await progress.reject(
        "north",
        request.id,
        "worker",
        target_id=target.id,
        code="INDEX_BUILD_FAILED",
        milliseconds=1,
    )
    stored = await targets.find_by_id(target.id)
    assert stored.result["index_id"] == "owned-index"
    assert stored.result["job_id"] == "owned-job"


async def test_target_progress_updates_exact_counters_without_scanning_all_targets(knowledge):
    from pyfly.data.relational.datasource_registry import DataSourceRegistry
    from sqlalchemy import event

    service, queue, targets, request, progress = await setup(knowledge)
    target = (await targets.page("north", request.id))[0]
    engine = knowledge.context.get_bean(DataSourceRegistry).primary.engine.sync_engine
    statements = []

    def observed(_connection, _cursor, statement, _parameters, _context, _many):
        statements.append(statement.lower())

    event.listen(engine, "before_cursor_execute", observed)
    try:
        await progress.record(
            "north",
            request.id,
            "worker",
            stage="preflight",
            target_id=target.id,
            status="prepared",
            result={},
            milliseconds=1,
        )
        assert not any("count(" in sql and "koinon_knowledge_mode_targets" in sql for sql in statements)
        current = await service.get("admin", "north", request.id)
        assert current.counters["queued"] == 1 and current.counters["prepared"] == 1
        await queue.claim("worker")
        await progress.record(
            "north",
            request.id,
            "worker",
            stage="preflight",
            target_id=target.id,
            status="prepared",
            result={},
            milliseconds=1,
        )
        current = await service.get("admin", "north", request.id)
        assert current.counters["queued"] == 1 and current.counters["prepared"] == 1
        await queue.claim("worker")
        await progress.reject(
            "north",
            request.id,
            "worker",
            target_id=target.id,
            code="SOURCE_PROCESSING_REQUIRED",
            milliseconds=1,
        )
        current = await service.get("admin", "north", request.id)
        assert current.counters["prepared"] == 0 and current.counters["failed"] == 1
        assert current.counters["queued"] == 1
    finally:
        event.remove(engine, "before_cursor_execute", observed)
