# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import asyncio
from unittest.mock import AsyncMock

import pytest
from pyfly.kernel import ServiceUnavailableException
from test_evidence_capture_consumer import fixture
from test_service import assistants as assistants

from koinon.assistants.execution import AssistantExecutor
from koinon.assistants.queue import AssistantQueue
from koinon.knowledge.capture_dtos import CapturedEvidence, NativeReadFingerprint
from koinon.knowledge.evidence_capture import NativeKnowledgeEvidence


async def nearly_full(assistants):
    service, context, run, entry, data, source = await fixture(assistants)
    queue = context.get_bean(AssistantQueue)
    read = NativeReadFingerprint(
        "retrieval", "documents", "north", entry.workspace_id, entry.id, "a" * 64, ("native-source",), ()
    )
    for count in (500, 499):
        await queue.evidence(
            run.id,
            "proposal-worker",
            "search",
            data,
            [entry.id],
            capture=CapturedEvidence(data, (source,), True, (read,) * count),
        )
    return service, context, run, entry, data, source, read


async def test_parallel_native_tools_cannot_oversubscribe_current_generation_receipt_budget(assistants):
    service, context, run, entry, data, source, read = await nearly_full(assistants)
    queue = context.get_bean(AssistantQueue)
    allowance = await queue.capture_limits(run.id, "proposal-worker", "search")
    assert allowance.reads == 1
    assert allowance.sources == 499
    calls = []

    async def search(*args, **kwargs):
        calls.append(kwargs["_limits"])
        await asyncio.sleep(0.01)
        return CapturedEvidence(data, (source,), True, (read,))

    native = type("ControlledRead", (), {})()
    native.search = AsyncMock(side_effect=search)
    context.container.register_instance(NativeKnowledgeEvidence, native)
    tool = (await context.get_bean(AssistantExecutor).tools(run.id, "proposal-worker", ["search_knowledge"]))[
        0
    ]
    outcomes = await asyncio.gather(
        tool.execute(question="First"), tool.execute(question="Second"), return_exceptions=True
    )
    assert len(calls) == 1 and calls[0].reads == 1
    assert sum(isinstance(value, dict) for value in outcomes) == 1
    assert sum(isinstance(value, Exception) for value in outcomes) == 1
    rows = await service.results.find_all(run_id=run.id)
    assert sum(len(row.payload.get("native_reads", [])) for row in rows) == 1000


async def test_persistence_guard_rejects_oversized_run_even_without_native_admission(assistants):
    service, context, run, entry, data, source, read = await nearly_full(assistants)
    before = len(await service.results.find_all(run_id=run.id))
    with pytest.raises(ServiceUnavailableException) as error:
        await context.get_bean(AssistantQueue).evidence(
            run.id,
            "proposal-worker",
            "search",
            data,
            [entry.id],
            capture=CapturedEvidence(data, (source,), True, (read, read)),
        )
    assert error.value.code == "EVIDENCE_BUDGET_EXCEEDED"
    assert len(await service.results.find_all(run_id=run.id)) == before


async def test_new_retry_has_new_budget_without_disclosing_prior_attempt_content(assistants):
    service, context, run, entry, data, source, read = await nearly_full(assistants)
    await service.cancel("issuer|admin", "north", run.id)
    await service.retry("issuer|admin", "north", run.id)
    claimed = await context.get_bean(AssistantQueue).claim("new-budget")
    assert claimed.id == run.id
    limits = await context.get_bean(AssistantQueue).capture_limits(run.id, "new-budget", "query")
    assert (limits.reads, limits.attempts, limits.sources) == (512, 128, 500)
    from koinon.assistants.audit import AnswerAudits

    audit = await context.get_bean(AnswerAudits).get("issuer|admin", "north", run.id)
    assert audit["native_reads"] == [] and audit["sources"] == []
    assert audit["source_provenance_complete"] is None
