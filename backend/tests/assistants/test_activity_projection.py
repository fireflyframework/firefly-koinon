# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from pyfly.kernel import InvalidRequestException
from test_service import assistants as assistants
from test_service import configured

from koinon.assistants.lifecycle import timestamp
from koinon.assistants.queue import AssistantQueue
from koinon.assistants.tool_activity import ToolActivity
from koinon.catalog.errors import AccessDenied


async def populated(service, context):
    _, agent = await configured(service)
    thread = await service.create_thread("issuer|viewer", "north", {})
    await service.submit(
        "issuer|viewer",
        "north",
        thread["id"],
        {"agent_id": agent["id"], "message": "Question", "client_request_id": "activity"},
    )
    queue = context.get_bean(AssistantQueue)
    run = await queue.claim("activity-worker")
    for index in range(7):
        for status in ("queued", "running", "completed"):
            await queue.tool_activity(
                run.id,
                "activity-worker",
                run.attempts,
                ToolActivity(
                    call_id=f"call-{index}",
                    tool_name="inspect_schema",
                    status=status,
                    occurred_at=timestamp().isoformat(),
                    summary="Inspect dataset schema",
                ),
            )
    return thread, run


async def test_activity_is_sql_paged_latest_per_call_with_bounded_batch_history(assistants):
    service, context = assistants
    thread, run = await populated(service, context)
    page = await service.activity_page("issuer|viewer", "north", run.id, page=2, page_size=2)
    assert page["total"] == 7 and page["pages"] == 4
    assert [item["call_id"] for item in page["items"]] == ["call-2", "call-3"]
    assert all(item["status"] == "completed" for item in page["items"])
    messages = (await service.message_page("issuer|viewer", "north", thread["id"]))["items"]
    answer = next(item for item in messages if item["role"] == "assistant")
    assert answer["tool_activity_count"] == 7 and answer["tool_activity_has_more"] is True
    assert len(answer["tool_activities"]) == 5
    assert [item["call_id"] for item in answer["tool_activities"]] == [f"call-{index}" for index in range(5)]
    for subject, tenant in (("issuer|other", "north"), ("issuer|outsider", "south")):
        with pytest.raises(AccessDenied):
            await service.activity_page(subject, tenant, run.id)
    for value in (0, True):
        with pytest.raises(InvalidRequestException):
            await service.activity_page("issuer|viewer", "north", run.id, page=value)


async def test_latest_reset_discards_old_attempt_and_metadata_survives_private_expiry(assistants):
    service, context = assistants
    thread, run = await populated(service, context)
    run.lease_until = timestamp() - timedelta(seconds=1)
    await service.runs.save(run)
    queue = context.get_bean(AssistantQueue)
    renewed = await queue.claim("replacement-worker")
    await queue.tool_activity(
        run.id,
        "replacement-worker",
        renewed.attempts,
        ToolActivity(
            call_id="new-attempt",
            tool_name="inspect_schema",
            status="running",
            occurred_at=timestamp().isoformat(),
            summary="Inspect dataset schema",
        ),
    )
    service.attachments = SimpleNamespace(
        for_run=AsyncMock(side_effect=AccessDenied("Expired file")),
        summaries_for_message=AsyncMock(return_value=()),
    )
    page = await service.activity_page("issuer|viewer", "north", run.id)
    assert page["total"] == 1 and page["items"][0]["call_id"] == "new-attempt"
    service.attachments.for_run.assert_not_awaited()
    with pytest.raises(AccessDenied):
        await service.run_events("issuer|viewer", "north", run.id)
