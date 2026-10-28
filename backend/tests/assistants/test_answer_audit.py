# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from unittest.mock import AsyncMock

import pytest
from test_evidence_capture_consumer import fixture
from test_service import assistants as assistants

from koinon.assistants.queue import AssistantQueue
from koinon.catalog.errors import AccessDenied
from koinon.evidence.ports import SourceResolverPort
from koinon.knowledge.capture_dtos import CapturedEvidence, NativeReadFingerprint, NativeSqlAttempt


async def test_owner_audit_preserves_used_revision_when_current_source_changes(assistants):
    from koinon.assistants.audit import AnswerAudits

    service, context, run, entry, data, source = await fixture(assistants)
    resolver = type("CurrentSources", (), {})()
    resolver.resolve = AsyncMock(
        return_value=(
            source.model_copy(
                update={"availability": "changed", "current_revision": "chunk-sha256:" + "b" * 64}
            ),
        )
    )
    context.container.register_instance(SourceResolverPort, resolver)
    queue = context.get_bean(AssistantQueue)
    native_read = NativeReadFingerprint(
        "retrieval", "documents", "north", entry.workspace_id, entry.id, "c" * 64, ("source",), ()
    )
    sql = NativeSqlAttempt(
        1, "execution", "d" * 64, "SELECT", "succeeded", True, {"table": "snapshot"}, 1, False, None
    )
    capture = CapturedEvidence(data, (source,), True, (native_read,), (sql,))
    await queue.evidence(run.id, "proposal-worker", "search", data, [entry.id], capture=capture)
    await queue.begin_generation(
        run.id, "proposal-worker", model_id="selected-model", model_class="OpenAIChatModel", api="chat"
    )
    await queue.finish(run.id, "proposal-worker")
    audit = await context.get_bean(AnswerAudits).get("issuer|admin", "north", run.id)
    assert audit["sources"][0]["used_revision"] == source.used_revision
    assert audit["sources"][0]["availability"] == "changed"
    assert audit["native_reads"][0]["content_sha256"] == "c" * 64
    assert audit["sql_attempts"][0]["executed"] is True
    assert audit["generations"][0]["model_id"] == "selected-model"
    assert audit["generations"][0]["agent_revision"] == run.agent_revision
    assert audit["generations"][0]["finished_at"] is not None
    assert audit["private_files"] == []
    assert "base_url" not in str(audit) and "private-provider-key" not in str(audit)
    with pytest.raises(AccessDenied):
        await context.get_bean(AnswerAudits).get("issuer|viewer", "north", run.id)
    member = await service.catalog.membership_repository.find_by_id("admin")
    member.active = False
    await service.catalog.membership_repository.save(member)
    with pytest.raises(AccessDenied):
        await context.get_bean(AnswerAudits).get("issuer|admin", "north", run.id)


async def test_legacy_audit_is_not_backfilled_from_current_configuration(assistants):
    from koinon.assistants.audit import AnswerAudits

    _, context, run, _, _, _ = await fixture(assistants)
    audit = await context.get_bean(AnswerAudits).get("issuer|admin", "north", run.id)
    assert audit["provenance_status"] == "not_recorded"
    assert audit["generations"] == []
    assert audit["sources"] == []


async def test_foreign_native_receipt_is_rejected_before_persistence(assistants):
    from pyfly.kernel import InvalidRequestException

    service, context, run, entry, data, source = await fixture(assistants)
    read = NativeReadFingerprint(
        "retrieval", "documents", "south", entry.workspace_id, entry.id, "c" * 64, (), ()
    )
    before = len(await service.results.find_all(run_id=run.id))
    with pytest.raises(InvalidRequestException):
        await context.get_bean(AssistantQueue).evidence(
            run.id,
            "proposal-worker",
            "search",
            data,
            [entry.id],
            capture=CapturedEvidence(data, (source,), True, (read,), ()),
        )
    assert len(await service.results.find_all(run_id=run.id)) == before


async def test_partial_native_reads_are_audit_only_and_cannot_ground_or_render(assistants):
    from koinon.assistants.audit import AnswerAudits

    service, context, run, entry, data, source = await fixture(assistants)
    resolver = type("CurrentSources", (), {})()
    resolver.resolve = AsyncMock(return_value=(source,))
    context.container.register_instance(SourceResolverPort, resolver)
    read = NativeReadFingerprint(
        "reranking", "documents", "north", entry.workspace_id, entry.id, "c" * 64, ("native-source",), ()
    )
    capture = CapturedEvidence({}, (source,), False, (read,), ())
    queue = context.get_bean(AssistantQueue)
    before = list((await service.message_repository.find_by_id(run.message_id)).artifacts)
    await queue.observation(run.id, "proposal-worker", "search", [entry.id], capture=capture)
    answer = await service.message_repository.find_by_id(run.message_id)
    assert answer.artifacts == before
    assert answer.answer_policy == {}
    observation = next(
        row for row in await service.results.find_all(run_id=run.id) if row.kind == "observation"
    )
    assert "data" not in observation.payload
    audit = await context.get_bean(AnswerAudits).get("issuer|admin", "north", run.id)
    assert audit["source_provenance_complete"] is False
    assert audit["native_reads"][0]["stage"] == "reranking"
    with pytest.raises(AccessDenied):
        await service.result("issuer|admin", "north", run.id, observation.id)


async def test_retry_completion_never_invents_an_old_cancelled_generations_end_time(assistants):
    service, context, run, entry, data, source = await fixture(assistants)
    queue = context.get_bean(AssistantQueue)
    first = await queue.begin_generation(
        run.id, "proposal-worker", model_id="model", model_class="OpenAIChatModel", api="chat"
    )
    await service.cancel("issuer|admin", "north", run.id)
    await service.retry("issuer|admin", "north", run.id)
    await queue.claim("proposal-worker")
    second = await queue.begin_generation(
        run.id, "proposal-worker", model_id="model", model_class="OpenAIChatModel", api="chat"
    )
    await queue.finish(run.id, "proposal-worker")
    old = (await service.results.find_by_id(first)).payload["generation"]
    current = (await service.results.find_by_id(second)).payload["generation"]
    assert old["finished_at"] is None and old["status"] == "started"
    assert current["finished_at"] is not None and current["status"] == "completed"
    assert current["start_sequence"] > old["start_sequence"]
