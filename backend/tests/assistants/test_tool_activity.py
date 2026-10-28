# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import asyncio
from unittest.mock import AsyncMock

import pytest
from pyfly.agentic.tools import agent_tool
from test_service import assistants as assistants
from test_service import configured

from koinon.assistants.queue import AssistantQueue
from koinon.assistants.tool_activity import tracked_tool
from koinon.knowledge.capture_dtos import CapturedEvidence


@pytest.mark.parametrize("outcome", ["completed", "failed", "cancelled"])
async def test_actual_native_tool_call_persists_safe_stable_lifecycle(assistants, outcome):
    service, context = assistants
    _, agent = await configured(service)
    thread = await service.create_thread("issuer|viewer", "north", {})
    submitted = await service.submit(
        "issuer|viewer",
        "north",
        thread["id"],
        {"agent_id": agent["id"], "message": "Question", "client_request_id": outcome},
    )
    queue = context.get_bean(AssistantQueue)
    run = await queue.claim("timeline-worker")
    entered = asyncio.Event()
    evidence = await queue.evidence(
        run.id,
        "timeline-worker",
        "schema",
        {"tables": []},
        [],
        capture=CapturedEvidence({"tables": []}, (), True),
    )

    @agent_tool("inspect_schema", auto_register=False)
    @tracked_tool(
        queue, AsyncMock(return_value=(run, None, None, None)), run.id, "timeline-worker", "inspect_schema"
    )
    async def tool(secret_argument: str) -> dict:
        entered.set()
        if outcome == "failed":
            raise ValueError("sensitive SQL and credential must not be logged")
        if outcome == "cancelled":
            await asyncio.Event().wait()
        return {"evidence_id": evidence}

    task = asyncio.create_task(tool.execute(secret_argument="private-password"))
    await entered.wait()
    if outcome == "cancelled":
        await service.cancel("issuer|viewer", "north", run.id)
        task.cancel()
    if outcome == "completed":
        assert await task == {"evidence_id": evidence}
    else:
        with pytest.raises(asyncio.CancelledError if outcome == "cancelled" else Exception):
            await task
    events = await service.run_events("issuer|viewer", "north", submitted["run_id"])
    rows = [event["data"]["tool_activity"] for event in events if "tool_activity" in event["data"]]
    assert [row["status"] for row in rows] == ["queued", "running", outcome]
    assert len({row["call_id"] for row in rows}) == 1
    assert all(row["tool_name"] == "inspect_schema" and row["occurred_at"] for row in rows)
    assert rows[-1]["duration_ms"] >= 0 and rows[-1]["finished_at"]
    assert "private-password" not in str(rows) and "sensitive SQL" not in str(rows)
    assert rows[-1].get("result_id") == (evidence if outcome == "completed" else None)


async def test_old_attempt_cannot_append_tool_timeline(assistants):
    from pyfly.kernel import ConflictException

    from koinon.assistants.tool_activity import ToolActivity

    service, context = assistants
    _, agent = await configured(service)
    thread = await service.create_thread("issuer|viewer", "north", {})
    await service.submit(
        "issuer|viewer",
        "north",
        thread["id"],
        {"agent_id": agent["id"], "message": "Question", "client_request_id": "attempt"},
    )
    queue = context.get_bean(AssistantQueue)
    run = await queue.claim("worker")
    with pytest.raises(ConflictException):
        await queue.tool_activity(
            run.id,
            "worker",
            run.attempts + 1,
            ToolActivity(
                call_id="stale",
                tool_name="inspect_schema",
                status="completed",
                occurred_at="2026-10-27T00:00:00+00:00",
                summary="Inspect dataset schema",
            ),
        )


async def test_tool_timeline_rejects_another_runs_actual_persisted_evidence(assistants):
    from pyfly.kernel import InvalidRequestException

    from koinon.assistants.tool_activity import ToolActivity

    service, context = assistants
    _, agent = await configured(service)
    thread = await service.create_thread("issuer|viewer", "north", {})
    other = await service.create_thread("issuer|viewer", "north", {})
    for key, selected in (("first", thread), ("second", other)):
        await service.submit(
            "issuer|viewer",
            "north",
            selected["id"],
            {"agent_id": agent["id"], "message": "Question", "client_request_id": key},
        )
    queue = context.get_bean(AssistantQueue)
    first = await queue.claim("worker-one")
    second = await queue.claim("worker-two")
    evidence = await queue.evidence(
        second.id,
        "worker-two",
        "schema",
        {"tables": []},
        [],
        capture=CapturedEvidence({"tables": []}, (), True),
    )
    with pytest.raises(InvalidRequestException) as failure:
        await queue.tool_activity(
            first.id,
            "worker-one",
            first.attempts,
            ToolActivity(
                call_id="foreign-evidence",
                tool_name="inspect_schema",
                status="completed",
                occurred_at="2026-10-27T00:00:00Z",
                summary="Inspect dataset schema",
                result_id=evidence,
            ),
        )
    assert failure.value.code == "EVIDENCE_DENIED"
    assert not any(
        event["data"].get("tool_activity", {}).get("call_id") == "foreign-evidence"
        for event in await service.run_events("issuer|viewer", "north", first.id)
    )


@pytest.mark.parametrize("returns_after_cancel", [False, True])
async def test_durable_cancellation_records_terminal_activity_even_without_task_cancellation(
    assistants, returns_after_cancel
):
    from pyfly.agentic.exceptions import ToolError

    service, context = assistants
    _, agent = await configured(service)
    thread = await service.create_thread("issuer|viewer", "north", {})
    await service.submit(
        "issuer|viewer",
        "north",
        thread["id"],
        {"agent_id": agent["id"], "message": "Question", "client_request_id": "cancel-race"},
    )
    queue = context.get_bean(AssistantQueue)
    run = await queue.claim("tool-worker")

    @agent_tool("inspect_schema", auto_register=False)
    @tracked_tool(
        queue, AsyncMock(return_value=(run, None, None, None)), run.id, "tool-worker", "inspect_schema"
    )
    async def tool() -> dict:
        await service.cancel("issuer|viewer", "north", run.id)
        if returns_after_cancel:
            return {}
        await queue.evidence(
            run.id,
            "tool-worker",
            "schema",
            {"tables": []},
            [],
            capture=CapturedEvidence({"tables": []}, (), True),
        )
        return {}

    with pytest.raises(ToolError):
        await tool.execute()
    events = await service.run_events("issuer|viewer", "north", run.id)
    states = [
        event["data"]["tool_activity"]["status"] for event in events if "tool_activity" in event["data"]
    ]
    assert states == ["queued", "running", "cancelled"]
