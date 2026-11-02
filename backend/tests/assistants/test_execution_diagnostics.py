# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from test_service import assistants as assistants
from test_service import configured

from koinon.assistants.execution import AssistantExecutor
from koinon.assistants.queue import AssistantQueue


async def test_failed_generation_records_safe_diagnostics_and_preserves_terminal_state(
    assistants, monkeypatch, caplog
):
    service, context = assistants
    _, agent = await configured(service)
    thread = await service.create_thread("issuer|viewer", "north", {})
    await service.submit(
        "issuer|viewer",
        "north",
        thread["id"],
        {"agent_id": agent["id"], "message": "Private question", "client_request_id": "failure"},
    )
    queue = context.get_bean(AssistantQueue)
    run = await queue.claim("diagnostic-worker")
    executor = context.get_bean(AssistantExecutor)

    async def failed(*args):
        try:
            raise ValueError("confidential-provider-response")
        except ValueError as cause:
            raise RuntimeError("confidential-model-prompt") from cause

    monkeypatch.setattr(executor, "generate", failed)
    await executor.execute(run.id, "diagnostic-worker")
    stored = await service.runs.find_by_id(run.id)
    assert stored.status == "failed" and stored.error_code == "GENERATION_FAILED"
    records = [row for row in caplog.records if row.message.startswith("Conversation execution failed")]
    assert len(records) == 1
    assert run.id in records[0].message
    assert "ValueError" in records[0].message and "RuntimeError" in records[0].message
    assert "confidential" not in records[0].message and "Private question" not in records[0].message
    assert records[0].exc_info is None
