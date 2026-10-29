# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import asyncio
from dataclasses import replace
from unittest.mock import AsyncMock

import pytest
from pyfly.agentic.exceptions import ToolError
from pyfly.kernel import ConflictException, ServiceUnavailableException
from test_evidence_capture_consumer import fixture
from test_service import assistants as assistants
from test_service import configured

from koinon.assistants.audit import AnswerAudits
from koinon.assistants.execution import AssistantExecutor
from koinon.catalog.errors import AccessDenied
from koinon.knowledge.capture_dtos import CapturedEvidence
from koinon.knowledge.evidence_capture import NativeKnowledgeEvidence
from koinon.organization_knowledge.dtos import OrganizationKnowledgeSettingsInput
from koinon.organization_knowledge.runtime import bind_snapshot, current_snapshot, snapshot_for_run
from koinon.organization_knowledge.service import OrganizationKnowledgeService


async def change_policy(context, mode="rlm", limit=151, structured_changes=None):
    policy = context.get_bean(OrganizationKnowledgeService)
    current = await policy.get("issuer|admin", "north")
    await policy.update(
        "issuer|admin",
        "north",
        OrganizationKnowledgeSettingsInput(
            expected_revision=current.revision,
            documents=current.documents.model_copy(update={"answer_mode": mode, "retrieval_top_k": limit}),
            structured=current.structured.model_copy(update=structured_changes or {}),
        ),
    )
    return await policy.snapshot("issuer|admin", "north")


async def tool_fixture(assistants, mode="rag", limit=27):
    service, context, run, entry, data, source = await fixture(assistants)
    recorded = await change_policy(context, mode, limit)
    run.knowledge_settings_snapshot = recorded.model_dump(mode="json")
    await service.runs.save(run)
    native = type("ControlledNative", (), {})()
    native.search = AsyncMock(return_value=CapturedEvidence(data, (source,), True))
    context.container.register_instance(NativeKnowledgeEvidence, native)
    tool = (await context.get_bean(AssistantExecutor).tools(run.id, "proposal-worker", ["search_knowledge"]))[
        0
    ]
    return service, context, run, native, tool, recorded


async def test_admission_captures_policy_and_queued_edit_replay_retry_and_audit_preserve_it(assistants):
    service, context = assistants
    _, agent = await configured(service)
    expected = await change_policy(context)
    thread = await service.create_thread("issuer|viewer", "north", {})
    request = {"agent_id": agent["id"], "message": "Read knowledge", "client_request_id": "captured"}
    submitted = await service.submit("issuer|viewer", "north", thread["id"], request)
    run = await service.runs.find_by_id(submitted["run_id"])
    assert run.knowledge_settings_snapshot == expected.model_dump(mode="json")
    await change_policy(context, "rag", 7)
    assert await service.submit("issuer|viewer", "north", thread["id"], request) == submitted
    await service.cancel("issuer|viewer", "north", run.id)
    await service.retry("issuer|viewer", "north", run.id)
    assert snapshot_for_run(await service.runs.find_by_id(run.id)) == expected
    audit = await context.get_bean(AnswerAudits).get("issuer|viewer", "north", run.id)
    assert audit["knowledge_settings_snapshot"] == expected.model_dump(mode="json")


async def test_missing_policy_fails_admission_before_messages_or_run(assistants, monkeypatch):
    service, _ = assistants
    _, agent = await configured(service)
    thread = await service.create_thread("issuer|viewer", "north", {})
    monkeypatch.setattr(service, "organization_knowledge", None, raising=False)
    with pytest.raises(ServiceUnavailableException):
        await service.submit(
            "issuer|viewer",
            "north",
            thread["id"],
            {
                "agent_id": agent["id"],
                "message": "Must not queue",
                "client_request_id": "unavailable",
            },
        )
    assert await service.message_repository.find_all(thread_id=thread["id"]) == []
    assert await service.runs.find_all(thread_id=thread["id"]) == []


@pytest.mark.parametrize("mode,limit,expected_limit", [("rag", 27, 27), ("rlm", 151, 100)])
async def test_search_uses_recorded_mode_limit_and_scoped_policy(assistants, mode, limit, expected_limit):
    service, context, run, native, tool, recorded = await tool_fixture(assistants, mode, limit)
    await change_policy(context, "rlm" if mode == "rag" else "rag", 3)
    receipt = native.search.return_value
    if mode == "rlm":
        receipt = replace(
            receipt,
            data={
                **receipt.data,
                "answer": "Native final analysis",
                "citations": [{"id": receipt.sources[0].id}],
            },
        )
    seen = []

    async def search(subject, tenant, **kwargs):
        seen.append((current_snapshot(subject, tenant), kwargs))
        return receipt

    native.search.side_effect = search
    view = await tool.execute(question="Read this source")
    if mode == "rlm":
        assert view["derived_analysis"]["text"] == "Native final analysis"
        assert view["derived_analysis"]["result_id"] == view["evidence_id"]
    assert seen[0][0] == recorded
    assert seen[0][1]["answer"] is (mode == "rlm")
    assert seen[0][1]["limit"] == expected_limit
    assert current_snapshot("issuer|admin", "north") is None


async def test_inherited_task_cannot_reuse_closed_capture_policy(assistants):
    service, context, run, native, tool, recorded = await tool_fixture(assistants)
    receipt, escaped, release = native.search.return_value, [], asyncio.Event()

    async def child():
        await release.wait()
        return current_snapshot("issuer|admin", "north")

    async def search(subject, tenant, **kwargs):
        assert current_snapshot(subject, tenant) == recorded
        escaped.append(asyncio.create_task(child()))
        return receipt

    native.search.side_effect = search
    await tool.execute(question="Read")
    release.set()
    with pytest.raises(AccessDenied) as error:
        await escaped[0]
    assert error.value.code == "KNOWLEDGE_POLICY_CLOSED"


async def test_historical_run_never_borrows_parent_or_current_policy(assistants):
    service, context, run, native, tool, recorded = await tool_fixture(assistants)
    run.knowledge_settings_snapshot = None
    await service.runs.save(run)
    with bind_snapshot(recorded, "issuer|admin"), pytest.raises(ToolError) as error:
        await tool.execute(question="Read")
    assert isinstance(error.value.__cause__, ServiceUnavailableException)
    native.search.assert_not_called()
    await service.cancel("issuer|admin", "north", run.id)
    await service.retry("issuer|admin", "north", run.id)
    assert (await service.runs.find_by_id(run.id)).knowledge_settings_snapshot is None
    audit = await context.get_bean(AnswerAudits).get("issuer|admin", "north", run.id)
    assert audit["knowledge_settings_snapshot"] is None


async def test_invalid_recorded_policy_rejects_native_call_and_audit(assistants):
    service, context, run, native, tool, recorded = await tool_fixture(assistants)
    run.knowledge_settings_snapshot = {**recorded.model_dump(mode="json"), "digest": "0" * 64}
    await service.runs.save(run)
    with pytest.raises(ToolError) as error:
        await tool.execute(question="Read")
    assert isinstance(error.value.__cause__, ConflictException)
    native.search.assert_not_called()
    with pytest.raises(ConflictException):
        await context.get_bean(AnswerAudits).get("issuer|admin", "north", run.id)


async def test_query_tool_borrows_exact_recorded_structured_policy_through_evidence_persistence(
    assistants, monkeypatch
):
    from koinon.assistants.queue import AssistantQueue
    from koinon.evidence.dtos import SourceReference

    service, context = assistants
    _, agent = await configured(service)
    agent = await service.save_agent("issuer|admin", "north", {"tools": ["query_dataset"]}, agent["id"])
    parent = None
    for kind in ("workspace", "project", "collection", "source", "dataset"):
        parent = await service.catalog.create(
            "issuer|admin", "north", kind=kind, name=kind, parent_id=parent.id if parent else None
        )
    thread = await service.create_thread("issuer|admin", "north", {"scope": {"asset_ids": [parent.id]}})
    submitted = await service.submit(
        "issuer|admin",
        "north",
        thread["id"],
        {
            "agent_id": agent["id"],
            "message": "Query selected rows",
            "client_request_id": "query-policy",
        },
    )
    queue = context.get_bean(AssistantQueue)
    run = await queue.claim("query-worker")
    assert run.id == submitted["run_id"]
    recorded = snapshot_for_run(run)
    assert recorded is not None
    await change_policy(context, structured_changes={"generation_candidates": 7, "max_refine_retries": 0})
    data = {
        "query_id": "controlled-query",
        "execution_status": "OK",
        "preview": [{"total": 28}],
        "row_count": 1,
        "snapshot_pins": {"Facts": "snapshot-used"},
    }
    source = SourceReference(
        id="receipt",
        asset_id=parent.id,
        source_id=parent.parent_id,
        title="Facts",
        kind="dataset",
        used_revision="snapshot-used",
    )
    seen = []

    async def query(subject, tenant, **kwargs):
        seen.append(current_snapshot(subject, tenant))
        return CapturedEvidence(data, (source,), True)

    native = type("ControlledQuery", (), {})()
    native.query = AsyncMock(side_effect=query)
    context.container.register_instance(NativeKnowledgeEvidence, native)
    original = queue.evidence

    async def persist(*args, **kwargs):
        assert current_snapshot("issuer|admin", "north") == recorded
        return await original(*args, **kwargs)

    monkeypatch.setattr(queue, "evidence", persist)
    tool = (await context.get_bean(AssistantExecutor).tools(run.id, "query-worker", ["query_dataset"]))[0]
    view = await tool.execute(dataset_id=parent.id, question="Sum the rows")
    assert seen == [recorded] and view["preview"] == [{"total": 28}]
    assert seen[0].structured.generation_candidates != 7
    assert current_snapshot("issuer|admin", "north") is None


@pytest.mark.parametrize(
    "code",
    [
        "RLM_DOCUMENT_VIEWS_REQUIRED",
        "KNOWLEDGE_RLM_UNQUALIFIED",
        "KNOWLEDGE_SETTINGS_SNAPSHOT_REQUIRED",
        "KNOWLEDGE_SETTINGS_SNAPSHOT_INVALID",
    ],
)
@pytest.mark.parametrize("locale", ["en-US", "es-ES"])
async def test_native_policy_prerequisite_has_preserved_code_and_human_refusal(
    assistants, monkeypatch, code, locale
):
    from koinon.assistants.grounding import refusal_message

    service, context, run, entry, data, source = await fixture(assistants)
    message = await service.message_repository.find_by_id(run.message_id)
    message.presentation = {"locale": locale, "response_language": "auto"}
    await service.message_repository.save(message)
    executor = context.get_bean(AssistantExecutor)

    async def fail(*args):
        try:
            raise ServiceUnavailableException("UNSAFE_RAW_DETAILS", code=code)
        except ServiceUnavailableException as error:
            raise RuntimeError("Wrapped native prerequisite") from error

    monkeypatch.setattr(executor, "generate", fail)
    await executor.execute(run.id, "proposal-worker")
    completed = await service.runs.find_by_id(run.id)
    answer = await service.message_repository.find_by_id(run.message_id)
    assert completed.error_code == code
    assert answer.answer_policy["code"] == code
    assert answer.text == refusal_message(locale, code)
    assert "UNSAFE_RAW_DETAILS" not in answer.text


async def test_failed_run_write_rolls_back_admitted_messages_in_the_same_transaction(assistants, monkeypatch):
    service, context = assistants
    _, agent = await configured(service)
    thread = await service.create_thread("issuer|viewer", "north", {})
    monkeypatch.setattr(service.runs, "save", AsyncMock(side_effect=RuntimeError("controlled run failure")))
    with pytest.raises(RuntimeError, match="controlled run failure"):
        await service.submit(
            "issuer|viewer",
            "north",
            thread["id"],
            {
                "agent_id": agent["id"],
                "message": "Atomic admission",
                "client_request_id": "rollback",
            },
        )
    assert await service.message_repository.find_all(thread_id=thread["id"]) == []
    assert await service.runs.find_all(thread_id=thread["id"]) == []
