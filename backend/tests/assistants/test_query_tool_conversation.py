# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

from koinon.assistants.execution import AssistantExecutor
from koinon.knowledge.capture_dtos import CapturedEvidence
from koinon.organization_knowledge.dtos import OrganizationKnowledgeSnapshot, snapshot_digest
from koinon.organization_knowledge.runtime import current_snapshot


def recorded_policy():
    value = {
        "tenant_id": "tenant",
        "schema_version": 1,
        "revision": 0,
        "origin": "deployment",
        "documents": {
            "answer_mode": "rag",
            "retrieval_top_k": 27,
            "retrieval_per_query_k": 40,
            "retrieval_rrf_k": 60,
            "query_expansion_enabled": False,
            "query_expansion_n": 3,
            "answer_top_k": 10,
            "rlm_max_iters": 3,
            "rlm_sub_budget": 0,
            "rlm_max_depth": 0,
            "rlm_self_consistency": 1,
            "rlm_extended_reasoning": False,
        },
        "structured": {
            "top_k_schema": 12,
            "top_k_examples": 5,
            "top_k_metrics": 8,
            "rrf_k": 60,
            "generation_candidates": 1,
            "max_refine_retries": 0,
            "grounding_min_confidence": 0.55,
        },
    }
    return OrganizationKnowledgeSnapshot.model_validate({**value, "digest": snapshot_digest(value)})


async def test_query_tool_does_not_pass_root_thread_id_as_a_native_conversation():
    run = SimpleNamespace(
        id="run",
        attempts=1,
        thread_id="root-thread",
        tenant_id="tenant",
        scope={"asset_ids": ["dataset"]},
        knowledge_settings_snapshot=recorded_policy().model_dump(mode="json"),
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
    assert current_snapshot("issuer|reader", "tenant") is None
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
        id="run",
        attempts=1,
        thread_id="thread",
        tenant_id="tenant",
        scope={"asset_ids": ["dataset"]},
        knowledge_settings_snapshot=recorded_policy().model_dump(mode="json"),
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

    async def record_observation(*args, **kwargs):
        assert current_snapshot("issuer|reader", "tenant") == recorded_policy()

    executor.queue.observation.side_effect = record_observation
    tool = (await executor.tools("run", "worker", ["query_dataset"]))[0]
    with pytest.raises(asyncio.CancelledError) as raised:
        await tool.execute(dataset_id="dataset", question="Question")
    assert raised.value is stopped
    assert current_snapshot("issuer|reader", "tenant") is None
    executor.queue.observation.assert_awaited_once()
    assert executor.queue.observation.await_args.kwargs["capture"] is stopped.native_evidence_capture
    executor.queue.evidence.assert_not_awaited()
