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


@pytest.mark.parametrize("outcome", ["completed", "rejected", "failed", "halted"])
async def test_typed_rlm_tool_receipts_survive_queue_audit_and_access_checks(assistants, outcome):
    from koinon.assistants.audit import AnswerAudits
    from koinon.knowledge.capture_dtos import NativeRlmTool

    _, context, run, entry, data, source = await fixture(assistants)
    resolver = type("ControlledSources", (), {})()
    resolver.resolve = AsyncMock(return_value=(source,))
    context.container.register_instance(SourceResolverPort, resolver)
    queue = context.get_bean(AssistantQueue)
    read = NativeReadFingerprint(
        "rlm.root",
        "documents",
        "north",
        entry.workspace_id,
        entry.id,
        "a" * 64,
        ("native-source",),
        (),
    )
    tool = NativeRlmTool(
        tenant_id="north",
        workspace_id="native",
        source_ids=("native-source",),
        tool_call_id="genuine-provider-id",
        tool_name="final_answer",
        request_sha256="a" * 64,
        schema_sha256="b" * 64,
        arguments_sha256="c" * 64,
        result_sha256="d" * 64,
        result_kind="accepted_final" if outcome == "halted" else "tool_return",
        execution_sha256="e" * 64,
        outcome=outcome,
        execution_status={"failed": "error"}.get(outcome, outcome),
        execution_state="halted" if outcome == "halted" else "ready",
    )
    capture = CapturedEvidence(data, (source,), outcome != "failed", (read,), (), (tool,))
    if outcome == "failed":
        await queue.observation(run.id, "proposal-worker", "search", [entry.id], capture=capture)
    else:
        await queue.evidence(run.id, "proposal-worker", "search", data, [entry.id], capture=capture)
    audit = await context.get_bean(AnswerAudits).get("issuer|admin", "north", run.id)
    result = audit["rlm_tools"][0]
    assert result["tool_call_id"] == "genuine-provider-id" and result["outcome"] == outcome
    assert result["arguments_sha256"] == "c" * 64 and result["result_sha256"] == "d" * 64
    assert result["result_id"] == audit["native_reads"][0]["result_id"]
    assert len(audit["native_reads"]) == 1 and audit["sql_attempts"] == []
    with pytest.raises(AccessDenied):
        await context.get_bean(AnswerAudits).get("issuer|viewer", "north", run.id)


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
        run.id,
        "proposal-worker",
        model_id="selected-model",
        model_class="OpenAIChatModel",
        api="chat",
        binding_output_mode="default",
        model_options_sha256="e" * 64,
    )
    await queue.finish(run.id, "proposal-worker")
    audit = await context.get_bean(AnswerAudits).get("issuer|admin", "north", run.id)
    assert audit["sources"][0]["used_revision"] == source.used_revision
    assert audit["sources"][0]["availability"] == "changed"
    assert audit["native_reads"][0]["content_sha256"] == "c" * 64
    assert audit["sql_attempts"][0]["executed"] is True
    assert audit["generations"][0]["model_id"] == "selected-model"
    assert audit["generations"][0]["binding_output_mode"] == "default"
    assert audit["generations"][0]["model_options_sha256"] == "e" * 64
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


async def test_ordinary_search_part_receipt_survives_persistence_audit_and_conversation_snapshot(assistants):
    from hashlib import sha256

    from koinon.assistants.audit import AnswerAudits
    from koinon.evidence.dtos import SourceReference
    from koinon.evidence.ports import ConversationSnapshotPort

    service, context, run, entry, data, _ = await fixture(assistants)
    source = SourceReference(
        id="immutable-part",
        asset_id=entry.id,
        source_id=entry.parent_id,
        title="Recorded document title",
        kind="document",
        source_version_id="version",
        extraction_id="ingestion",
        source_part_id="part",
        source_part_sha256=sha256(b"Verified native chunk").hexdigest(),
        used_revision="source-part-sha256:" + sha256(b"Verified native chunk").hexdigest(),
        quote="Verified native chunk",
        recorded_page=7,
        page_basis="recorded_loader",
        section="Recorded scope",
    )
    context.container.register_instance(SourceResolverPort, SimpleSources(source))
    queue = context.get_bean(AssistantQueue)
    read = NativeReadFingerprint(
        "retrieval",
        "documents",
        "north",
        entry.workspace_id,
        entry.id,
        "b" * 64,
        ("native-source",),
        (),
        read_kind="document_extraction",
        source_version_id="version",
        extraction_id="ingestion",
    )
    await queue.evidence(
        run.id,
        "proposal-worker",
        "search",
        data,
        [entry.id],
        capture=CapturedEvidence(data, (source,), True, (read,)),
    )
    from release_helpers import seal_first_quote

    await seal_first_quote(context, run, "proposal-worker")
    await queue.finish(run.id, "proposal-worker")
    audit = await context.get_bean(AnswerAudits).get("issuer|admin", "north", run.id)
    saved = audit["sources"][0]
    assert saved["source_part_id"] == "part" and saved["chunk_id"] is None
    assert saved["source_version_id"] == "version" and saved["extraction_id"] == "ingestion"
    assert saved["title"] == "Recorded document title" and saved["quote"] == "Verified native chunk"
    assert saved["availability"] == "changed" and saved["recorded_page"] == 7
    assert audit["native_reads"][0]["extraction_id"] == "ingestion" and audit["rlm_tools"] is None
    snapshot = await context.get_bean(ConversationSnapshotPort).snapshot(
        "issuer|admin",
        "north",
        run.thread_id,
        [run.message_id],
    )
    assert snapshot.source_manifest_complete and snapshot.sources == (source,)


class SimpleSources:
    def __init__(self, source):
        self.source = source

    async def resolve(self, subject, tenant_id, sources):
        return (
            self.source.model_copy(
                update={
                    "availability": "changed",
                    "current_revision": None,
                    "title": "Today's title",
                    "quote": "Today's passage",
                    "recorded_page": 99,
                }
            ),
        )


async def test_legacy_audit_is_not_backfilled_from_current_configuration(assistants):
    from koinon.assistants.audit import AnswerAudits

    _, context, run, _, _, _ = await fixture(assistants)
    audit = await context.get_bean(AnswerAudits).get("issuer|admin", "north", run.id)
    assert audit["provenance_status"] == "not_recorded"
    assert audit["generations"] == []
    assert audit["sources"] == []
    assert audit["rlm_tools"] is None


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
