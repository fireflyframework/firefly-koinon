# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import asyncio
from hashlib import sha256

import pytest
from pyfly.kernel import ConflictException
from test_evidence_capture_consumer import fixture
from test_service import assistants as assistants

from koinon.answers.dtos import EvidenceAnswerPlan
from koinon.assistants.memory.service import PersonalConversationMemory
from koinon.assistants.queue import AssistantQueue
from koinon.catalog.errors import AccessDenied
from koinon.knowledge.capture_dtos import CapturedEvidence


async def prepared(assistants):
    service, context, run, entry, data, source = await fixture(assistants)
    source = source.model_copy(
        update={"used_revision": "chunk-sha256:" + sha256(source.quote.encode()).hexdigest()}
    )
    queue = context.get_bean(AssistantQueue)
    generation = await queue.begin_generation(
        run.id, "proposal-worker", model_id="controlled", model_class="ControlledModel", api="chat"
    )
    await context.get_bean(PersonalConversationMemory).build(run, generation_id=generation, token_budget=4096)
    result_id = await queue.evidence(
        run.id, "proposal-worker", "search", data, [entry.id], capture=CapturedEvidence(data, (source,), True)
    )
    return service, context, queue, run, result_id


async def test_only_a_whole_validated_release_publishes_text_and_pins_immutable_receipt(assistants):
    service, _, queue, run, result_id = await prepared(assistants)
    facts = await queue.fact_pool(run.id, "proposal-worker")
    assert facts and facts[0].result_id == result_id
    assert (await service.message_repository.find_by_id(run.message_id)).text == ""
    plan = EvidenceAnswerPlan(
        outcome="answer", quotes=[{"fact_id": facts[0].id, "quote": "Verified native chunk"}]
    )
    await queue.release_answer(run.id, "proposal-worker", plan, "en")
    message = await service.message_repository.find_by_id(run.message_id)
    assert "Verified native chunk" in message.text
    releases = [row for row in await service.results.find_all(run_id=run.id) if row.kind == "answer_release"]
    assert len(releases) == 1 and releases[0].payload["release"]["fact_ids"] == [facts[0].id]
    before = message.text
    with pytest.raises(ConflictException):
        await queue.release_answer(run.id, "proposal-worker", plan, "en")
    assert (await service.message_repository.find_by_id(run.message_id)).text == before


async def test_mixed_or_forged_plan_has_zero_textual_egress(assistants):
    service, _, queue, run, _ = await prepared(assistants)
    facts = await queue.fact_pool(run.id, "proposal-worker")
    plan = EvidenceAnswerPlan(
        outcome="answer",
        quotes=[
            {"fact_id": facts[0].id, "quote": "Verified native chunk"},
            {"fact_id": "forged", "quote": "Unsupported general claim"},
        ],
    )
    with pytest.raises(ValueError):
        await queue.release_answer(run.id, "proposal-worker", plan, "en")
    assert (await service.message_repository.find_by_id(run.message_id)).text == ""
    events = await service.events.find_after(run.id, 0)
    assert not any(event.type == "message_delta" for event in events)


async def test_legacy_unverified_text_is_hidden_without_rewriting_originals(assistants):
    service, _, queue, run, _ = await prepared(assistants)
    await queue.append(run.id, "proposal-worker", "message_delta", {"text": "UNVERIFIED_LEGACY_MODEL_CLAIM"})
    await queue.policy(run.id, "proposal-worker", {"outcome": "grounded"})
    await queue.finish(run.id, "proposal-worker")
    assert (
        await service.message_repository.find_by_id(run.message_id)
    ).text == "UNVERIFIED_LEGACY_MODEL_CLAIM"
    visible = await service.messages("issuer|admin", "north", run.thread_id)
    assert all("UNVERIFIED_LEGACY_MODEL_CLAIM" not in item["text"] for item in visible)
    events = await service.run_events("issuer|admin", "north", run.id)
    assert "UNVERIFIED_LEGACY_MODEL_CLAIM" not in str(events)


@pytest.mark.parametrize("case", ["text", "citation", "policy", "artifact", "source"])
async def test_replay_rechecks_sealed_text_and_all_selected_source_pins(assistants, case):
    from koinon.answers.receipts import verified_release

    service, _, queue, run, result_id = await prepared(assistants)
    fact = (await queue.fact_pool(run.id, "proposal-worker"))[0]
    await queue.release_answer(
        run.id,
        "proposal-worker",
        EvidenceAnswerPlan(outcome="answer", quotes=[{"fact_id": fact.id, "quote": "Verified native chunk"}]),
        "en",
    )
    message = await service.message_repository.find_by_id(run.message_id)
    rows = await service.results.find_all(run_id=run.id)
    assert verified_release(message, rows) is not None
    if case == "text":
        message.text += "UNVERIFIED_NEW_CLAIM"
    elif case == "citation":
        message.citations = [*message.citations, {"asset_id": "forged"}]
    elif case == "policy":
        message.answer_policy = {"outcome": "grounded", "code": "FORGED"}
    elif case == "artifact":
        message.artifacts = [*message.artifacts, {"id": "forged", "kind": "openui"}]
    elif case == "source":
        source = next(row for row in rows if row.id == result_id)
        source.payload = {**source.payload, "data": {"hits": [{"text": "UNVERIFIED_NEW_CLAIM"}]}}
        await service.results.save(source)
    await service.message_repository.save(message)
    assert verified_release(message, await service.results.find_all(run_id=run.id)) is None
    page = await service.messages("issuer|admin", "north", run.thread_id)
    events = await service.run_events("issuer|admin", "north", run.id)
    assert "UNVERIFIED_NEW_CLAIM" not in str(page) + str(events)
    assert "Verified native chunk" not in page[-1]["text"]


@pytest.mark.parametrize("interruption", [RuntimeError, asyncio.CancelledError])
async def test_event_publication_failure_rolls_back_the_entire_answer_release(
    assistants, monkeypatch, interruption
):
    service, _, queue, run, _ = await prepared(assistants)
    fact = (await queue.fact_pool(run.id, "proposal-worker"))[0]
    original = service.record_event

    async def failed(run, kind, data):
        if kind == "message_delta":
            raise interruption("Controlled publication interruption")
        return await original(run, kind, data)

    monkeypatch.setattr(service, "record_event", failed)
    with pytest.raises(interruption, match="Controlled publication"):
        await queue.release_answer(
            run.id,
            "proposal-worker",
            EvidenceAnswerPlan(
                outcome="answer", quotes=[{"fact_id": fact.id, "quote": "Verified native chunk"}]
            ),
            "en",
        )
    assert (await service.message_repository.find_by_id(run.message_id)).text == ""
    assert not any(row.kind == "answer_release" for row in await service.results.find_all(run_id=run.id))
    assert not any(row.type == "message_delta" for row in await service.events.find_after(run.id, 0))


async def test_sealed_answer_can_support_personal_context_but_new_turn_still_has_no_facts(assistants):
    from types import SimpleNamespace

    from koinon.evidence.ports import SourceResolverPort

    service, context, queue, run, _ = await prepared(assistants)

    async def resolve(subject, tenant_id, sources):
        return tuple(source.model_copy(update={"availability": "available"}) for source in sources)

    context.container.register_instance(SourceResolverPort, SimpleNamespace(resolve=resolve))
    fact = (await queue.fact_pool(run.id, "proposal-worker"))[0]
    await queue.release_answer(
        run.id,
        "proposal-worker",
        EvidenceAnswerPlan(outcome="answer", quotes=[{"fact_id": fact.id, "quote": "Verified native chunk"}]),
        "en",
    )
    await queue.finish(run.id, "proposal-worker")
    await service.submit(
        "issuer|admin",
        "north",
        run.thread_id,
        {"agent_id": run.agent_id, "message": "What about the same source?", "client_request_id": "new-turn"},
    )
    current = await queue.claim("new-turn-worker")
    generation = await queue.begin_generation(
        current.id, "new-turn-worker", model_id="controlled", model_class="controlled", api="chat"
    )
    memory = context.get_bean(PersonalConversationMemory)
    history = await memory.build(current, generation_id=generation)
    assert "Verified native chunk" in str(history)
    assert await queue.fact_pool(current.id, "new-turn-worker") == ()
    with pytest.raises(ValueError):
        await queue.release_answer(
            current.id,
            "new-turn-worker",
            EvidenceAnswerPlan(
                outcome="answer", quotes=[{"fact_id": fact.id, "quote": "Verified native chunk"}]
            ),
            "en",
        )
    assert (await service.message_repository.find_by_id(current.message_id)).text == ""


async def test_final_output_port_rejects_raw_legacy_and_allows_only_the_masked_snapshot(assistants):
    from koinon.evidence.ports import ConversationOutputPort, ConversationSnapshotPort

    service, context, queue, run, _ = await prepared(assistants)
    await queue.append(run.id, "proposal-worker", "message_delta", {"text": "LEGACY_UNSUPPORTED_FACT"})
    await queue.finish(run.id, "proposal-worker")
    port = context.get_bean(ConversationOutputPort)
    with pytest.raises(AccessDenied, match="verifiable sources"):
        await port.authorize_output("issuer|admin", "north", run.thread_id, [run.message_id])
    snapshot = await context.get_bean(ConversationSnapshotPort).snapshot(
        "issuer|admin", "north", run.thread_id, [run.message_id]
    )
    assert "LEGACY_UNSUPPORTED_FACT" not in str(snapshot)
    await port.authorize_output("issuer|admin", "north", run.thread_id, [run.message_id], snapshot=snapshot)
    forged = snapshot.model_copy(
        update={"messages": (snapshot.messages[0].model_copy(update={"text": "LEGACY_UNSUPPORTED_FACT"}),)}
    )
    with pytest.raises(AccessDenied, match="verifiable sources"):
        await port.authorize_output("issuer|admin", "north", run.thread_id, [run.message_id], snapshot=forged)


@pytest.mark.parametrize(
    "resource,change",
    [("agent", "enabled"), ("agent", "revision"), ("provider", "enabled"), ("provider", "revision")],
)
async def test_release_rechecks_agent_and_provider_fences_inside_its_native_transaction(
    assistants, resource, change
):
    service, _, queue, run, _ = await prepared(assistants)
    agent = await service.agents.find_by_id(run.agent_id)
    repository = service.agents if resource == "agent" else service.providers
    row = agent if resource == "agent" else await service.providers.find_by_id(agent.provider_id)
    setattr(row, change, False if change == "enabled" else row.revision + 1)
    await repository.save(row)
    with pytest.raises(ConflictException) as denied:
        await queue.release_answer(
            run.id, "proposal-worker", EvidenceAnswerPlan(outcome="insufficient_evidence"), "en"
        )
    assert denied.value.code == "CONFIGURATION_CHANGED"
    assert not (await service.message_repository.find_by_id(run.message_id)).text
    assert not any(row.kind == "answer_release" for row in await service.results.find_all(run_id=run.id))


async def refusal_without_generation(assistants):
    from test_service import configured

    service, context = assistants
    _, agent = await configured(service)
    thread = await service.create_thread("issuer|admin", "north", {})
    await service.submit(
        "issuer|admin",
        "north",
        thread["id"],
        {"agent_id": agent["id"], "message": "What is known?", "client_request_id": "early-refusal"},
    )
    queue = context.get_bean(AssistantQueue)
    run = await queue.claim("early-worker")
    await queue.release_answer(
        run.id, "early-worker", EvidenceAnswerPlan(outcome="insufficient_evidence"), "en"
    )
    return service, queue, run


async def test_retry_can_publish_a_current_sealed_refusal_before_a_generation_exists(assistants):
    from koinon.answers.receipts import verified_release

    service, queue, run = await refusal_without_generation(assistants)
    await queue.finish(run.id, "early-worker", code="CONTROLLED_FAILURE")
    await service.retry("issuer|admin", "north", run.id)
    current = await queue.claim("retry-worker")
    receipt = await queue.release_answer(
        current.id,
        "retry-worker",
        EvidenceAnswerPlan(outcome="insufficient_evidence"),
        "es",
        refusal_code="KNOWLEDGE_ONLY",
    )
    await queue.finish(current.id, "retry-worker")
    message = await service.message_repository.find_by_id(current.message_id)
    active = await service.active_results(current)
    assert receipt.generation_id is None and verified_release(message, active) == receipt
    page = await service.messages("issuer|admin", "north", current.thread_id)
    assert page[-1]["text"] == message.text and "organización" in page[-1]["text"]
    events = await service.run_events("issuer|admin", "north", current.id)
    assert "".join(item["data"]["text"] for item in events if item["type"] == "message_delta") == message.text
    assert (
        len([row for row in await service.results.find_all(run_id=run.id) if row.kind == "answer_release"])
        == 2
    )


@pytest.mark.parametrize("transition", ["reset", "generation"])
async def test_earlier_no_generation_release_never_attests_a_new_output_context(assistants, transition):
    from koinon.answers.receipts import verified_release

    service, queue, run = await refusal_without_generation(assistants)
    if transition == "reset":
        await queue.finish(run.id, "early-worker", code="CONTROLLED_FAILURE")
        await service.retry("issuer|admin", "north", run.id)
        run = await queue.claim("retry-worker")
        assert not any(row.kind == "answer_release" for row in await service.active_results(run))
        events = await service.run_events("issuer|admin", "north", run.id)
        assert not any(item["type"] == "message_delta" for item in events)
    else:
        await queue.begin_generation(
            run.id, "early-worker", model_id="controlled", model_class="controlled", api="chat"
        )
    message = await service.message_repository.find_by_id(run.message_id)
    assert verified_release(message, await service.active_results(run)) is None
    assert (
        len([row for row in await service.results.find_all(run_id=run.id) if row.kind == "answer_release"])
        == 1
    )


async def test_same_attempt_cannot_publish_a_second_pre_generation_refusal(assistants):
    service, queue, run = await refusal_without_generation(assistants)
    before = (await service.message_repository.find_by_id(run.message_id)).text
    with pytest.raises(ConflictException) as denied:
        await queue.release_answer(
            run.id, "early-worker", EvidenceAnswerPlan(outcome="insufficient_evidence"), "es"
        )
    assert denied.value.code == "ANSWER_ALREADY_RELEASED"
    assert (await service.message_repository.find_by_id(run.message_id)).text == before


@pytest.mark.parametrize(
    "case", ["reset_string", "reset_bool", "sequence_string", "sequence_bool", "context_hash"]
)
async def test_malformed_private_context_never_admits_a_release(assistants, case):
    from copy import deepcopy
    from types import SimpleNamespace

    service, _, run = await refusal_without_generation(assistants)
    row = next(row for row in await service.results.find_all(run_id=run.id) if row.kind == "answer_release")
    payload = deepcopy(row.payload)
    if case == "reset_string":
        payload["reset_sequence"] = "0"
    elif case == "reset_bool":
        payload["reset_sequence"] = False
    elif case == "sequence_string":
        payload["release"]["publication_sequence"] = str(payload["release"]["publication_sequence"])
    elif case == "sequence_bool":
        payload["release"]["publication_sequence"] = True
    else:
        payload["context_sha256"] = "0" * 64
    assert await service.active_results(run, [SimpleNamespace(kind=row.kind, payload=payload)]) == []


async def test_forged_reset_does_not_relabel_a_pre_reset_seal_as_current(assistants):
    from copy import deepcopy
    from types import SimpleNamespace

    from koinon.answers.contexts import context_hash

    service, queue, run = await refusal_without_generation(assistants)
    row = next(row for row in await service.results.find_all(run_id=run.id) if row.kind == "answer_release")
    await queue.finish(run.id, "early-worker", code="CONTROLLED_FAILURE")
    await service.retry("issuer|admin", "north", run.id)
    current = await queue.claim("retry-worker")
    reset = await service.events.latest_reset(run.id)
    payload = deepcopy(row.payload)
    payload["reset_sequence"] = reset
    payload["context_sha256"] = context_hash(payload["seal_sha256"], reset)
    assert payload["release"]["publication_sequence"] < reset
    assert (
        await service.active_results(current, [SimpleNamespace(id=row.id, kind=row.kind, payload=payload)])
        == []
    )


async def test_final_release_rechecks_authority_after_successful_selection_preview(assistants):
    from koinon.catalog.repositories import MembershipRepository

    service, context, queue, run, _ = await prepared(assistants)
    fact = (await queue.fact_pool(run.id, "proposal-worker"))[0]
    plan = EvidenceAnswerPlan(
        outcome="answer", quotes=[{"fact_id": fact.id, "quote": "Verified native chunk"}]
    )
    assert await queue.validate_answer_plan(run.id, "proposal-worker", plan, "en")
    await context.get_bean(MembershipRepository).delete_by_id("admin")
    with pytest.raises(AccessDenied):
        await queue.release_answer(run.id, "proposal-worker", plan, "en")
    assert not (await service.message_repository.find_by_id(run.message_id)).text
    assert not any(event.type == "message_delta" for event in await service.events.find_after(run.id, 0))


@pytest.mark.parametrize("mutation", ["missing", "altered", "shifted"])
async def test_chunk_replay_requires_the_entire_sealed_contiguous_publication(assistants, mutation):
    service, _, queue, run, _ = await prepared(assistants)
    fact = (await queue.fact_pool(run.id, "proposal-worker"))[0]
    await queue.release_answer(
        run.id,
        "proposal-worker",
        EvidenceAnswerPlan(outcome="answer", quotes=[{"fact_id": fact.id, "quote": "Verified native chunk"}]),
        "en",
    )
    message = await service.message_repository.find_by_id(run.message_id)
    assert message.answer_policy["publication"]["format"] == "verified-unicode-v1"
    rows = [row for row in await service.events.find_after(run.id, 0) if row.type == "message_delta"]
    if mutation == "missing":
        await service.events.delete_by_id(rows[0].id)
    elif mutation == "altered":
        rows[0].data = {**rows[0].data, "text": "UNSEALED"}
        await service.events.save(rows[0])
    else:
        rows[0].sequence += 100
        await service.events.save(rows[0])
    visible = await service.run_events("issuer|admin", "north", run.id)
    assert not any(row["type"] in {"message_delta", "citation", "openui_delta"} for row in visible)


async def test_historical_v1_single_delta_replays_without_changing_its_canonical_receipt(assistants):
    from koinon.answers.contexts import context_hash
    from koinon.answers.receipts import AnswerRelease, ResultPin, digest, text_digest
    from koinon.assistants.entities import ToolResult
    from koinon.assistants.lifecycle import timestamp

    service, _, _, run, result_id = await prepared(assistants)
    run = await service.runs.find_by_id(run.id)
    rows = await service.active_results(run)
    generation = next(row.id for row in rows if row.kind == "generation")
    result = next(row for row in rows if row.id == result_id)
    message = await service.message_repository.find_by_id(run.message_id)
    text, policy = "Historical exact answer", {"outcome": "grounded", "code": "VERIFIED_EVIDENCE_V1"}
    receipt = AnswerRelease(
        run_id=run.id,
        message_id=message.id,
        tenant_id=run.tenant_id,
        generation_id=generation,
        publication_sequence=run.sequence + 2,
        outcome="grounded",
        text_sha256=text_digest(text),
        citations_sha256=digest([]),
        artifacts_sha256=digest([]),
        policy_sha256=digest(policy),
        fact_ids=("historical-fact",),
        result_pins=(
            ResultPin(id=result.id, sha256=digest({"kind": result.kind, "payload": result.payload})),
        ),
        created_at=timestamp(),
    )
    data = receipt.model_dump(mode="json")
    seal = digest(data)
    await service.results.save(
        ToolResult(
            id="historical-release",
            run_id=run.id,
            kind="answer_release",
            payload={
                "release": data,
                "seal_sha256": seal,
                "generation_id": generation,
                "reset_sequence": 0,
                "context_sha256": context_hash(seal, 0),
            },
        )
    )
    message.text, message.answer_policy = text, policy
    message.artifacts, message.citations = [], []
    await service.message_repository.save(message)
    await service.record_event(run, "message_metadata", {"answer_policy": policy})
    await service.record_event(run, "message_delta", {"text": text})
    events = await service.run_events("issuer|admin", "north", run.id)
    assert [row["data"] for row in events if row["type"] == "message_delta"] == [{"text": text}]
    assert (await service.results.find_by_id("historical-release")).payload["release"] == data
