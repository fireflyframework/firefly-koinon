# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

from koinon.assistants.execution import AssistantExecutor
from koinon.knowledge.capture_dtos import CapturedEvidence


async def test_query_tool_does_not_pass_root_thread_id_as_a_native_conversation():
    run = SimpleNamespace(
        id="run", attempts=1, thread_id="root-thread", tenant_id="tenant", scope={"asset_ids": ["dataset"]}
    )
    thread = SimpleNamespace(subject="issuer|reader")
    catalog = SimpleNamespace(
        get=AsyncMock(return_value=SimpleNamespace(kind="dataset", workspace_id="workspace")),
        authorize=AsyncMock(),
    )
    knowledge = SimpleNamespace(
        query=AsyncMock(
            return_value=CapturedEvidence({"query_id": "query", "preview": [{"total": 12}]}, (), True)
        )
    )
    executor = object.__new__(AssistantExecutor)
    executor.assistants = SimpleNamespace(
        catalog=catalog, validate_scope=AsyncMock(), settings=SimpleNamespace(tool_result_tokens=4096)
    )
    executor.queue = SimpleNamespace(
        append=AsyncMock(),
        evidence=AsyncMock(return_value="evidence"),
        tool_activity=AsyncMock(),
        capture_limits=AsyncMock(return_value=None),
    )
    executor.container = SimpleNamespace(
        resolve=Mock(return_value=knowledge), contains_type=Mock(return_value=True)
    )
    executor.authority = AsyncMock(return_value=(run, thread, None, None))
    tool = (await executor.tools("run", "worker", ["query_dataset"]))[0]
    result = await tool.execute(dataset_id="dataset", question="Sum total")
    assert result["evidence_id"] == "evidence"
    assert knowledge.query.await_args.args == ("issuer|reader", "tenant")
    assert knowledge.query.await_args.kwargs == {
        "dataset_id": "dataset",
        "question": "Sum total",
        "_limits": None,
    }
    catalog.authorize.assert_awaited_once_with("issuer|reader", "tenant", "query:execute", "workspace")


async def test_cancelled_native_query_retains_audit_receipt_without_converting_cancellation():
    import asyncio

    import pytest

    from koinon.knowledge.capture_dtos import NativeReadFingerprint

    run = SimpleNamespace(
        id="run", attempts=1, thread_id="thread", tenant_id="tenant", scope={"asset_ids": ["dataset"]}
    )
    thread = SimpleNamespace(subject="issuer|reader")
    stopped = asyncio.CancelledError()
    stopped.native_evidence_capture = CapturedEvidence(
        {},
        (),
        False,
        (
            NativeReadFingerprint(
                "generation", "structured", "tenant", "workspace", "dataset", "a" * 64, (), ("snapshot",)
            ),
        ),
    )
    native = SimpleNamespace(query=AsyncMock(side_effect=stopped))
    executor = object.__new__(AssistantExecutor)
    executor.assistants = SimpleNamespace(
        catalog=SimpleNamespace(
            get=AsyncMock(return_value=SimpleNamespace(kind="dataset", workspace_id="workspace")),
            authorize=AsyncMock(),
        ),
        validate_scope=AsyncMock(),
        settings=SimpleNamespace(tool_result_tokens=4096),
    )
    executor.queue = SimpleNamespace(
        observation=AsyncMock(),
        evidence=AsyncMock(),
        tool_activity=AsyncMock(),
        capture_limits=AsyncMock(return_value=None),
    )
    executor.container = SimpleNamespace(
        contains_type=Mock(return_value=True), resolve=Mock(return_value=native)
    )
    executor.authority = AsyncMock(return_value=(run, thread, None, None))
    tool = (await executor.tools("run", "worker", ["query_dataset"]))[0]
    with pytest.raises(asyncio.CancelledError) as raised:
        await tool.execute(dataset_id="dataset", question="Question")
    assert raised.value is stopped
    executor.queue.observation.assert_awaited_once()
    assert executor.queue.observation.await_args.kwargs["capture"] is stopped.native_evidence_capture
    executor.queue.evidence.assert_not_awaited()
