# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Personal memory uses only bounded, authorized conversations in the opted-in folder."""

import pytest
from test_service import assistants as assistants
from test_service import configured

from koinon.assistants.execution import AssistantExecutor
from koinon.assistants.history.service import ChatHistoryService
from koinon.assistants.queue import AssistantQueue


@pytest.mark.parametrize("enabled", [False, True])
async def test_same_folder_completed_question_is_reused_only_after_explicit_opt_in(assistants, enabled):
    service, context = assistants
    history = context.get_bean(ChatHistoryService)
    folder = await history.create_folder(
        "issuer|admin", "north", {"name": "My project", "memory_enabled": enabled}
    )
    provider, agent = await configured(service)
    old = await history.create_thread(
        "issuer|admin", "north", {"folder_id": folder["id"], "title": "Earlier"}
    )
    await service.submit(
        "issuer|admin",
        "north",
        old["id"],
        {
            "agent_id": agent["id"],
            "message": "Remember my preferred invoice layout.",
            "client_request_id": "earlier",
        },
    )
    queue = context.get_bean(AssistantQueue)
    first = await queue.claim("memory-worker")
    await queue.finish(first.id, "memory-worker")
    current = await history.create_thread(
        "issuer|admin", "north", {"folder_id": folder["id"], "title": "Now"}
    )
    await service.submit(
        "issuer|admin",
        "north",
        current["id"],
        {
            "agent_id": agent["id"],
            "message": "Continue the project.",
            "client_request_id": "current",
        },
    )
    run = await queue.claim("memory-worker")
    messages = await context.get_bean(AssistantExecutor).history(run)
    text = str(messages)
    assert ("Remember my preferred invoice layout." in text) is enabled


async def test_actual_model_history_has_generation_bound_manifest_and_legacy_answer_is_omitted(
    assistants, monkeypatch
):
    import json
    from unittest.mock import AsyncMock

    from pydantic_ai.models.function import FunctionModel
    from pyfly.agentic.models import ModelFactory

    from koinon.assistants.memory.repositories import ChatMemoryRepository
    from koinon.assistants.probe import ProviderProbe

    service, context = assistants
    history = context.get_bean(ChatHistoryService)
    folder = await history.create_folder("issuer|admin", "north", {"name": "Project", "memory_enabled": True})
    monkeypatch.setattr(
        ProviderProbe,
        "check",
        AsyncMock(
            return_value=[{"id": "connection", "status": "passed"}, {"id": "models", "status": "passed"}]
        ),
    )
    provider, agent = await configured(service)
    await service.validate_provider("issuer|admin", "north", provider["id"])
    queue = context.get_bean(AssistantQueue)
    first_thread = await history.create_thread("issuer|admin", "north", {"folder_id": folder["id"]})
    await service.submit(
        "issuer|admin",
        "north",
        first_thread["id"],
        {
            "agent_id": agent["id"],
            "message": "My project uses the blue invoice layout.",
            "client_request_id": "first",
        },
    )
    first = await queue.claim("memory-model")
    await queue.append(first.id, "memory-model", "message_delta", {"text": "UNVERIFIED_LEGACY_BODY"})
    await queue.finish(first.id, "memory-model")
    current_thread = await history.create_thread("issuer|admin", "north", {"folder_id": folder["id"]})
    await service.submit(
        "issuer|admin",
        "north",
        current_thread["id"],
        {
            "agent_id": agent["id"],
            "message": "Continue this project",
            "client_request_id": "second",
        },
    )
    seen = []

    async def streamed(messages, info):
        seen.append(str(messages))
        yield "I cannot establish current facts without retrieving source evidence."

    monkeypatch.setattr(
        ModelFactory, "build_with_secret", lambda self, spec, secret: FunctionModel(stream_function=streamed)
    )
    run = await queue.claim("memory-model")
    await context.get_bean(AssistantExecutor).execute(run.id, "memory-model")
    assert seen, (await service.runs.find_by_id(run.id)).error_code
    assert "My project uses the blue invoice layout." in seen[0]
    assert "UNVERIFIED_LEGACY_BODY" not in seen[0]
    repository = context.get_bean(ChatMemoryRepository)
    generation = await repository.generation(run.id)
    manifest = await repository.for_generation(generation.id)
    assert (
        manifest.generation_id == generation.id
        and manifest.start_sequence == generation.payload["generation"]["start_sequence"]
    )
    assert manifest.manifest_json["turns"][0]["run_id"] == first.id
    assert manifest.manifest_json["turns"][0]["answer_included"] is False
    assert "UNVERIFIED_LEGACY_BODY" not in json.dumps(manifest.manifest_json)


@pytest.mark.parametrize("verified", [False, True])
async def test_historical_answer_body_requires_manifest_and_current_source_proof(assistants, verified):
    from types import SimpleNamespace

    from koinon.assistants.memory.service import PersonalConversationMemory
    from koinon.evidence.dtos import SourceReference
    from koinon.evidence.ports import SourceResolverPort
    from koinon.knowledge.capture_dtos import CapturedEvidence

    service, context = assistants
    history = context.get_bean(ChatHistoryService)
    folder = await history.create_folder(
        "issuer|admin", "north", {"name": "Proof project", "memory_enabled": True}
    )
    provider, agent = await configured(service)
    parent = None
    for kind in ["workspace", "project", "collection", "source", "document"]:
        parent = await service.catalog.create(
            "issuer|admin", "north", kind=kind, name=kind, parent_id=parent.id if parent else None
        )
    scope = {"asset_ids": [parent.id]}
    queue = context.get_bean(AssistantQueue)
    memory = context.get_bean(PersonalConversationMemory)
    earlier = await history.create_thread("issuer|admin", "north", {"folder_id": folder["id"]})
    await service.submit(
        "issuer|admin",
        "north",
        earlier["id"],
        {
            "agent_id": agent["id"],
            "message": "What is the recorded threshold?",
            "scope": scope,
            "client_request_id": "proof-first",
        },
    )
    first = await queue.claim("proof-worker")
    generation = await queue.begin_generation(
        first.id, "proof-worker", model_id="controlled", model_class="controlled", api="chat"
    )
    await memory.build(first, generation_id=generation)
    reference = SourceReference(
        id="verified-fixture",
        kind="document",
        asset_id=parent.id,
        source_id=parent.parent_id,
        title="Controlled source",
        used_revision="fixture-version",
    )
    data = {"hits": [{"asset_id": parent.id, "text": "The historical threshold was47."}]}
    await queue.evidence(
        first.id,
        "proof-worker",
        "search",
        data,
        [parent.id],
        capture=CapturedEvidence(data, (reference,), True),
    )
    await queue.append(first.id, "proof-worker", "message_delta", {"text": "HISTORICAL_VERIFIED_ANSWER_47"})
    await queue.policy(
        first.id, "proof-worker", {"outcome": "grounded", "code": "GROUNDED", "reason": "Controlled evidence"}
    )
    await queue.finish(first.id, "proof-worker")
    if verified:

        async def resolve(subject, tenant, values):
            return tuple(value.model_copy(update={"availability": "available"}) for value in values)

        context.container.register_instance(SourceResolverPort, SimpleNamespace(resolve=resolve))
    newer = await history.create_thread("issuer|admin", "north", {"folder_id": folder["id"]})
    await service.submit(
        "issuer|admin",
        "north",
        newer["id"],
        {
            "agent_id": agent["id"],
            "message": "Continue",
            "scope": scope,
            "client_request_id": "proof-second",
        },
    )
    second = await queue.claim("proof-worker")
    current_generation = await queue.begin_generation(
        second.id, "proof-worker", model_id="controlled", model_class="controlled", api="chat"
    )
    messages = await memory.build(second, generation_id=current_generation)
    assert "HISTORICAL_VERIFIED_ANSWER_47" not in str(messages)
    saved = await memory.repository.for_generation(current_generation)
    assert saved.manifest_json["turns"][0]["answer_included"] is False


async def memory_pair(assistants, *, origin_token_id=None):
    from koinon.assistants.memory.service import PersonalConversationMemory

    service, context = assistants
    history = context.get_bean(ChatHistoryService)
    folder = await history.create_folder(
        "issuer|admin", "north", {"name": "Fixed context", "memory_enabled": True}
    )
    provider, agent = await configured(service)
    queue = context.get_bean(AssistantQueue)
    source = await history.create_thread(
        "issuer|admin", "north", {"folder_id": folder["id"], "title": "Source"}
    )
    from contextlib import nullcontext

    from pyfly.security.context import SecurityContext
    from pyfly.security.context_holder import SecurityContextHolder

    scope = (
        SecurityContextHolder.using(
            SecurityContext(
                user_id="admin",
                attributes={
                    "iss": "issuer",
                    "sub": "admin",
                    "koinon_token_id": origin_token_id,
                },
            )
        )
        if origin_token_id
        else nullcontext()
    )
    with scope:
        await service.submit(
            "issuer|admin",
            "north",
            source["id"],
            {
                "agent_id": agent["id"],
                "message": "My retained personal project question.",
                "client_request_id": "pair-source",
            },
        )
    old = await queue.claim("pair-worker")
    await queue.finish(old.id, "pair-worker")
    target = await history.create_thread(
        "issuer|admin", "north", {"folder_id": folder["id"], "title": "Target"}
    )
    await service.submit(
        "issuer|admin",
        "north",
        target["id"],
        {
            "agent_id": agent["id"],
            "message": "Continue with context.",
            "client_request_id": "pair-target",
        },
    )
    run = await queue.claim("pair-worker")
    generation = await queue.begin_generation(
        run.id, "pair-worker", model_id="controlled", model_class="controlled", api="chat"
    )
    memory = context.get_bean(PersonalConversationMemory)
    await memory.build(run, generation_id=generation)
    assert service.memory.get() is memory
    return service, history, queue, memory, folder, source, old, target, run, generation


@pytest.mark.parametrize("change", ["disable", "delete", "move"])
async def test_consent_or_source_change_aborts_inflight_but_completed_replay_remains_owned(
    assistants, change
):
    from koinon.catalog.errors import AccessDenied

    service, history, queue, memory, folder, source, old, target, run, generation = await memory_pair(
        assistants
    )
    saved = await memory.repository.for_generation(generation)
    original_hash = saved.manifest_sha256
    if change == "disable":
        await history.patch_folder(
            "issuer|admin", "north", folder["id"], {"expected_revision": 1, "memory_enabled": False}
        )
    elif change == "delete":
        await history.delete_thread("issuer|admin", "north", source["id"], expected_revision=1)
    else:
        other = await history.create_folder(
            "issuer|admin", "north", {"name": "Other folder", "memory_enabled": True}
        )
        await history.patch_thread(
            "issuer|admin", "north", source["id"], {"expected_revision": 1, "folder_id": other["id"]}
        )
    with pytest.raises(AccessDenied):
        await memory.authorize("issuer|admin", "north", run.id)
    await queue.finish(run.id, "pair-worker")
    replay = await memory.authorize("issuer|admin", "north", run.id)
    assert replay.validation_mode == "historical_replay"
    assert (
        replay.turns[0].availability
        == {"disable": "memory_disabled", "delete": "deleted", "move": "moved"}[change]
    )
    assert replay.context_available is False
    assert replay.manifest_sha256 == original_hash
    assert (await memory.repository.for_generation(generation)).manifest_sha256 == original_hash
    with pytest.raises(AccessDenied):
        await memory.authorize("issuer|other", "north", run.id)


async def test_harmless_renames_do_not_break_completed_replay_but_acl_revocation_does(assistants):
    from koinon.catalog.errors import AccessDenied

    service, history, queue, memory, folder, source, old, target, run, generation = await memory_pair(
        assistants
    )
    await queue.finish(run.id, "pair-worker")
    await history.patch_folder(
        "issuer|admin", "north", folder["id"], {"expected_revision": 1, "name": "Renamed"}
    )
    receipt = await memory.authorize("issuer|admin", "north", run.id)
    assert receipt.turns[0].availability == "available"
    assert receipt.validation_mode == "historical_replay"
    member = await service.catalog.membership_repository.find_by_id("admin")
    member.active = False
    await service.catalog.membership_repository.save(member)
    with pytest.raises(AccessDenied):
        await memory.authorize("issuer|admin", "north", run.id)


@pytest.mark.parametrize("limit", ["tokens", "messages"])
async def test_zero_history_limit_queries_no_candidates_and_seals_empty_manifest(
    assistants, monkeypatch, limit
):
    from unittest.mock import AsyncMock

    from koinon.assistants.memory.repositories import ChatMemoryRepository
    from koinon.assistants.settings import AssistantSettings

    service, context = assistants
    settings = context.get_bean(AssistantSettings)
    setattr(settings, "max_history_tokens" if limit == "tokens" else "max_history_messages", 0)
    repository = context.get_bean(ChatMemoryRepository)
    probe = AsyncMock(side_effect=AssertionError("Disabled memory must not load historical candidates"))
    monkeypatch.setattr(repository, "candidates", probe)
    _, _, _, memory, _, _, _, _, run, generation = await memory_pair(assistants)
    saved = await repository.for_generation(generation)
    assert saved.manifest_json["turns"] == saved.manifest_json["dependencies"] == []
    assert saved.manifest_json["input_sha256"] == __import__(
        "koinon.assistants.memory.mappers", fromlist=["digest"]
    ).digest([])
    probe.assert_not_awaited()


async def test_folder_candidates_exclude_other_owners_descendants_and_different_scope(assistants):
    service, context = assistants
    history = context.get_bean(ChatHistoryService)
    folder = await history.create_folder("issuer|admin", "north", {"name": "Parent", "memory_enabled": True})
    child = await history.create_folder(
        "issuer|admin", "north", {"name": "Child", "parent_id": folder["id"], "memory_enabled": True}
    )
    other_folder = await history.create_folder(
        "issuer|other", "north", {"name": "Other owner", "memory_enabled": True}
    )
    _, agent = await configured(service)
    queue = context.get_bean(AssistantQueue)
    for marker, owner, parent, scope in [
        ("VISIBLE_OWN_SAME_FOLDER", "issuer|admin", folder["id"], {}),
        ("HIDDEN_DESCENDANT", "issuer|admin", child["id"], {}),
        ("HIDDEN_DIFFERENT_SCOPE", "issuer|admin", folder["id"], {"asset_ids": []}),
        ("HIDDEN_OTHER_OWNER", "issuer|other", other_folder["id"], {}),
    ]:
        thread = await history.create_thread(owner, "north", {"folder_id": parent})
        await service.submit(
            owner,
            "north",
            thread["id"],
            {"agent_id": agent["id"], "message": marker, "scope": scope, "client_request_id": marker},
        )
        source = await queue.claim("isolation-worker")
        await queue.finish(source.id, "isolation-worker")
        if owner != "issuer|admin":
            # Defense against a legacy/imported cross-owner foreign-key relationship.
            row = await service.threads.find_by_id(thread["id"])
            row.folder_id = folder["id"]
            await service.threads.save(row)
    target = await history.create_thread("issuer|admin", "north", {"folder_id": folder["id"]})
    await service.submit(
        "issuer|admin",
        "north",
        target["id"],
        {"agent_id": agent["id"], "message": "Continue", "client_request_id": "isolation-target"},
    )
    run = await queue.claim("isolation-worker")
    text = str(await context.get_bean(AssistantExecutor).history(run))
    assert "VISIBLE_OWN_SAME_FOLDER" in text
    assert all(
        marker not in text for marker in ["HIDDEN_DESCENDANT", "HIDDEN_DIFFERENT_SCOPE", "HIDDEN_OTHER_OWNER"]
    )


async def second_manifest(assistants):
    service, history, queue, memory, folder, source, old, target, first, first_generation = await memory_pair(
        assistants
    )
    await queue.finish(first.id, "pair-worker")
    _, context = assistants
    run_agent = await service.agents.find_by_id(first.agent_id)
    next_thread = await history.create_thread("issuer|admin", "north", {"folder_id": folder["id"]})
    await service.submit(
        "issuer|admin",
        "north",
        next_thread["id"],
        {"agent_id": run_agent.id, "message": "Another answer", "client_request_id": "batch-next"},
    )
    second = await queue.claim("pair-worker")
    second_generation = await queue.begin_generation(
        second.id, "pair-worker", model_id="controlled", model_class="controlled", api="chat"
    )
    await memory.build(second, generation_id=second_generation)
    await queue.finish(second.id, "pair-worker")
    return service, history, memory, folder, first, second


async def test_batch_release_deduplicates_shared_dependencies_in_one_final_statement(assistants):
    from pyfly.data.relational.datasource_registry import DataSourceRegistry
    from sqlalchemy import event

    service, history, memory, folder, first, second = await second_manifest(assistants)
    engine = assistants[1].get_bean(DataSourceRegistry).get("primary").engine.sync_engine
    statements = []

    def observe(conn, cursor, statement, params, execution_context, many):
        if "memory_ancestry" in statement:
            statements.append(statement)

    event.listen(engine, "before_cursor_execute", observe)
    try:
        result = await memory.authorize_many("issuer|admin", "north", (first.id, second.id, first.id))
    finally:
        event.remove(engine, "before_cursor_execute", observe)
    assert set(result) == {first.id, second.id}
    assert len(statements) == 3


async def test_revocation_during_later_replay_check_blocks_entire_page(assistants, monkeypatch):
    import asyncio

    from pyfly.data.relational.datasource_registry import DataSourceRegistry
    from sqlalchemy import update

    from koinon.catalog.entities import Membership
    from koinon.catalog.errors import AccessDenied

    service, history, memory, folder, first, second = await second_manifest(assistants)
    await history.patch_folder(
        "issuer|admin",
        "north",
        folder["id"],
        {"expected_revision": 1, "name": "Rename triggers replay recheck"},
    )
    original = memory.validate_replay
    authorize_fixed = memory.authorize_fixed
    engine = assistants[1].get_bean(DataSourceRegistry).get("primary").engine
    seen = []
    writers = []

    async def revoke():
        async with engine.begin() as connection:
            await connection.execute(update(Membership).where(Membership.id == "admin").values(active=False))

    async def validate_then_revoke(value):
        await original(value)
        seen.append(value.run_id)
        if len(seen) == 2:
            writers.append(asyncio.create_task(revoke()))

    async def validate_then_commit_revocation(*args, **kwargs):
        stamp = await authorize_fixed(*args, **kwargs)
        await asyncio.gather(*writers)
        return stamp

    monkeypatch.setattr(memory, "validate_replay", validate_then_revoke)
    monkeypatch.setattr(memory, "authorize_fixed", validate_then_commit_revocation)
    with pytest.raises(AccessDenied):
        await memory.authorize_many("issuer|admin", "north", (first.id, second.id))
    assert len(seen) == 2


async def test_current_and_remembered_policies_share_the_primary_native_snapshot(assistants, monkeypatch):
    from pyfly.data.relational.datasource_registry import DataSourceRegistry
    from pyfly.data.transaction import Isolation, current_unit_of_work

    service, history, queue, memory, folder, source, old, target, run, generation = await memory_pair(
        assistants
    )
    await queue.finish(run.id, "pair-worker")
    await history.patch_folder(
        "issuer|admin",
        "north",
        folder["id"],
        {"expected_revision": 1, "name": "Recheck remembered authority"},
    )
    primary = assistants[1].get_bean(DataSourceRegistry).get("primary").engine
    sessions, phases = [], []
    validate_current, validate_replay = memory.validate_current, memory.validate_replay
    pinned_results = memory.repository.pinned_results

    def record(phase):
        unit = current_unit_of_work("primary")
        assert unit is not None and unit.isolation is Isolation.SERIALIZABLE
        assert unit.read_only and unit.read_from_primary
        assert unit.resource.bind is primary
        sessions.append(unit.resource)
        phases.append(phase)

    async def current(*args):
        record("current")
        await validate_current(*args)

    async def replay(value):
        record("replay")
        await validate_replay(value)

    async def pins(*args):
        record("pins")
        assert memory.repository._require_session() is sessions[0]
        return await pinned_results(*args)

    monkeypatch.setattr(memory, "validate_current", current)
    monkeypatch.setattr(memory, "validate_replay", replay)
    monkeypatch.setattr(memory.repository, "pinned_results", pins)
    assert (await memory.authorize("issuer|admin", "north", run.id)).context_available
    assert {"current", "replay", "pins"} <= set(phases)
    assert all(session is sessions[0] for session in sessions)


async def test_replica_lag_cannot_hide_a_generation_memory_manifest(assistants, tmp_path):
    from pyfly.data.relational.datasource_registry import DataSource, DataSourceRegistry
    from pyfly.data.relational.sqlalchemy import Base
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from koinon.catalog.errors import AccessDenied

    service, history, queue, memory, folder, source, old, target, run, generation = await memory_pair(
        assistants
    )
    await queue.finish(run.id, "pair-worker")
    registry = assistants[1].get_bean(DataSourceRegistry)
    primary = registry.get("primary")
    replica_engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'lagging-replica.db'}")
    try:
        async with replica_engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        primary.replica = DataSource(
            "primary",
            replica_engine,
            async_sessionmaker(replica_engine),
            properties=primary.properties,
            registry=registry,
            is_replica=True,
        )
        receipt = await memory.authorize("issuer|admin", "north", run.id)
        assert receipt is not None and receipt.generation_id == generation
        assert receipt.dependency_count == 1
        member = await service.catalog.membership_repository.find_by_id("admin")
        member.active = False
        await service.catalog.membership_repository.save(member)
        with pytest.raises(AccessDenied):
            await memory.authorize("issuer|admin", "north", run.id)
    finally:
        primary.replica = None
        await replica_engine.dispose()


async def test_small_history_with_valid_result_payloads_is_admitted(assistants):
    from koinon.assistants.memory.service import PersonalConversationMemory

    service, context = assistants
    history = context.get_bean(ChatHistoryService)
    queue = context.get_bean(AssistantQueue)
    folder = await history.create_folder(
        "issuer|admin", "north", {"name": "Review project", "memory_enabled": True}
    )
    _, agent = await configured(service)
    for ordinal in range(3):
        thread = await history.create_thread("issuer|admin", "north", {"folder_id": folder["id"]})
        await service.submit(
            "issuer|admin",
            "north",
            thread["id"],
            {
                "agent_id": agent["id"],
                "message": "Remember preference " + str(ordinal),
                "client_request_id": "history-" + str(ordinal),
            },
        )
        run = await queue.claim("reviewer")
        for _item in range(6):
            await queue.evidence(run.id, "reviewer", "lineage", {"data": "x" * 470000}, [])
        await queue.finish(run.id, "reviewer")
    thread = await history.create_thread("issuer|admin", "north", {"folder_id": folder["id"]})
    await service.submit(
        "issuer|admin",
        "north",
        thread["id"],
        {"agent_id": agent["id"], "message": "Continue my preferences", "client_request_id": "current"},
    )
    run = await queue.claim("reviewer")
    generation = await queue.begin_generation(
        run.id, "reviewer", model_id="fixture", model_class="fixture", api="chat"
    )
    messages = await context.get_bean(PersonalConversationMemory).build(
        run, generation_id=generation, token_budget=8192
    )
    assert len(messages) == 2
    assert "Remember preference 2" in str(messages)
    assert "Remember preference 1" not in str(messages)


async def test_current_generation_output_does_not_rehash_or_reselect_fixed_memory(assistants, monkeypatch):
    from unittest.mock import AsyncMock

    service, history, queue, memory, folder, source, old, target, run, generation = await memory_pair(
        assistants
    )
    saved = await memory.repository.for_generation(generation)
    monkeypatch.setattr(
        memory.repository, "candidates", AsyncMock(side_effect=AssertionError("No reselection"))
    )
    for ordinal in range(5):
        await queue.append(run.id, "pair-worker", "message_delta", {"text": "delta " + str(ordinal)})
        await queue.evidence(run.id, "pair-worker", "lineage", {"step": ordinal}, [])
        projected = await memory.authorize("issuer|admin", "north", run.id)
        assert projected.manifest_sha256 == saved.manifest_sha256
        assert projected.generation_id == generation


async def test_authority_sql_suppresses_payload_before_transfer_when_page_byte_cap_is_exceeded(
    assistants, monkeypatch
):
    import koinon.assistants.memory.authority_repository as authority
    from koinon.assistants.entities import ToolResult
    from koinon.assistants.lifecycle import identifier, timestamp
    from koinon.assistants.memory.mappers import digest
    from koinon.catalog.errors import AccessDenied

    service, history, queue, memory, folder, source, old, target, run, generation = await memory_pair(
        assistants
    )
    saved = await memory.repository.for_generation(generation)
    value = memory.decode(saved)
    result = ToolResult(
        id=identifier(),
        run_id=old.id,
        kind="lineage",
        payload={"data": "x" * 2000, "asset_ids": []},
        created_at=timestamp(),
    )
    await service.results.save(result)
    ref = value.dependencies[0]
    from koinon.assistants.memory.dtos import MemoryResultPin

    ref = ref.model_copy(
        update={
            "result_pins": (
                MemoryResultPin(
                    id=result.id, sha256=digest({"kind": result.kind, "payload": result.payload})
                ),
            )
        }
    )
    value = value.model_copy(update={"dependencies": (ref,)})
    original = authority.partition_material
    transferred = []

    def inspected(rows, values, *args):
        transferred.extend(item for item in rows if item[0] == "result")
        return original(rows, values, *args)

    monkeypatch.setattr(authority, "MAX_PAGE_RESULT_BYTES", 1024)
    monkeypatch.setattr(authority, "partition_material", inspected)
    with pytest.raises(AccessDenied, match="smaller conversation page"):
        await memory.observe(value, ())
    assert len(transferred) == 1 and transferred[0][4] is None


async def native_tokens(assistants, rows):
    from types import SimpleNamespace

    from pyfly.data.relational.datasource_registry import DataSourceRegistry
    from sqlalchemy import insert, select

    from koinon.tokens.authorization import TokenRestriction
    from koinon.tokens.entities import PersonalToken

    service, context = assistants
    engine = context.get_bean(DataSourceRegistry).get("primary").engine
    async with engine.begin() as connection:
        await connection.execute(insert(PersonalToken), rows)

    async def find_by_id(token_id):
        async with engine.connect() as connection:
            row = (
                (
                    await connection.execute(
                        select(PersonalToken.__table__).where(PersonalToken.id == token_id)
                    )
                )
                .mappings()
                .first()
            )
            return SimpleNamespace(**row) if row else None

    service.catalog.restriction = TokenRestriction(
        SimpleNamespace(find_by_id=find_by_id), service.catalog.catalog_repository
    )
    return engine


def token_row(identifier, scopes):
    from datetime import timedelta

    from koinon.assistants.lifecycle import timestamp

    return dict(
        id=identifier,
        subject="issuer|admin",
        tenant_id="north",
        name="Controlled token",
        token_hash="x" * 64,
        prefix="controlled",
        scopes=scopes,
        expires_at=timestamp() + timedelta(hours=1),
    )


async def test_completed_memory_intersects_current_pat_and_rechecks_revoked_origin(assistants):
    from pyfly.security.context import SecurityContext
    from pyfly.security.context_holder import SecurityContextHolder
    from sqlalchemy import update

    from koinon.assistants.lifecycle import timestamp
    from koinon.catalog.errors import AccessDenied
    from koinon.tokens.entities import PersonalToken

    engine = await native_tokens(
        assistants,
        [
            token_row("origin", ["catalog:read", "chat:use"]),
            token_row("reader", ["catalog:read", "chat:use"]),
            token_row("no-chat", ["catalog:read"]),
        ],
    )
    service, history, queue, memory, folder, source, old, target, run, generation = await memory_pair(
        assistants, origin_token_id="origin"
    )
    await queue.finish(run.id, "pair-worker")
    ordinary = await memory.authorize("issuer|admin", "north", run.id)
    for token_id, allowed in [("reader", True), ("no-chat", False)]:
        with SecurityContextHolder.using(
            SecurityContext(
                user_id="admin", attributes={"iss": "issuer", "sub": "admin", "koinon_token_id": token_id}
            )
        ):
            if allowed:
                assert (
                    await memory.authorize("issuer|admin", "north", run.id)
                ).manifest_sha256 == ordinary.manifest_sha256
            else:
                with pytest.raises(AccessDenied):
                    await memory.authorize("issuer|admin", "north", run.id)
    async with engine.begin() as connection:
        await connection.execute(
            update(PersonalToken).where(PersonalToken.id == "origin").values(revoked_at=timestamp())
        )
    with pytest.raises(AccessDenied):
        await memory.authorize("issuer|admin", "north", run.id)


async def test_result_window_rejects_large_retained_rows_before_fetching_payloads(assistants):
    from pyfly.data.relational.datasource_registry import DataSourceRegistry
    from sqlalchemy import event

    from koinon.assistants.memory.repositories import ChatMemoryRepository

    service, context = assistants
    _, agent = await configured(service)
    thread = await context.get_bean(ChatHistoryService).create_thread("issuer|admin", "north", {})
    await service.submit(
        "issuer|admin",
        "north",
        thread["id"],
        {"agent_id": agent["id"], "message": "Controlled question", "client_request_id": "oversized-window"},
    )
    queue = context.get_bean(AssistantQueue)
    run = await queue.claim("window-worker")
    for _ in range(7):
        await queue.evidence(run.id, "window-worker", "lineage", {"data": "x" * 470000}, [])
    engine = context.get_bean(DataSourceRegistry).get("primary").engine.sync_engine
    statements = []

    def observed(connection, cursor, statement, parameters, query_context, executemany):
        statements.append(statement)

    event.listen(engine, "before_cursor_execute", observed)
    try:
        assert await context.get_bean(ChatMemoryRepository).result_window(run.id) is None
    finally:
        event.remove(engine, "before_cursor_execute", observed)
    statements = [item for item in statements if item.lstrip().upper().startswith("SELECT")]
    assert len(statements) == 1 and "sum(" in statements[0].lower()


async def test_unchanged_origin_token_expiry_is_detected_by_fresh_database_clock(assistants):
    import asyncio
    from datetime import timedelta

    from sqlalchemy import update

    from koinon.assistants.lifecycle import timestamp
    from koinon.catalog.errors import AccessDenied
    from koinon.tokens.entities import PersonalToken

    engine = await native_tokens(assistants, [token_row("expiring", ["catalog:read", "chat:use"])])
    service, history, queue, memory, folder, source, old, target, run, generation = await memory_pair(
        assistants, origin_token_id="expiring"
    )
    await queue.finish(run.id, "pair-worker")
    expires_at = timestamp() + timedelta(seconds=1)
    async with engine.begin() as connection:
        await connection.execute(
            update(PersonalToken).where(PersonalToken.id == "expiring").values(expires_at=expires_at)
        )
    await memory.authorize("issuer|admin", "north", run.id)
    await asyncio.sleep(max(0, (expires_at - timestamp()).total_seconds()) + 0.05)
    with pytest.raises(AccessDenied):
        await memory.authorize("issuer|admin", "north", run.id)


@pytest.mark.parametrize("output", ["page", "result"])
@pytest.mark.parametrize("attack", ["swap", "aba"])
async def test_message_page_never_combines_current_and_memory_with_disjoint_source_authority(
    assistants, monkeypatch, output, attack
):
    from pyfly.data.relational.datasource_registry import DataSourceRegistry
    from sqlalchemy import insert, update

    from koinon.assistants.lifecycle import identifier
    from koinon.assistants.memory.authority_repository import ChatMemoryAuthorityRepository
    from koinon.assistants.memory.service import PersonalConversationMemory
    from koinon.catalog.entities import CatalogEntry, Membership
    from koinon.catalog.errors import AccessDenied
    from koinon.knowledge.curated.entities import CuratedCatalogState, CuratedSourceRoot

    service, context = assistants
    history = context.get_bean(ChatHistoryService)
    folder = await history.create_folder(
        "issuer|admin", "north", {"name": "Release proof", "memory_enabled": True}
    )
    _, agent = await configured(service)
    collections = []
    documents = []
    for label in ["common", "A", "B"]:
        parent = None
        for kind in ["workspace", "project", "collection", "source", "document"]:
            parent = await service.catalog.create(
                "issuer|admin", "north", kind=kind, name=label + kind, parent_id=parent.id if parent else None
            )
            if kind == "collection":
                collections.append(parent)
        documents.append(parent)
    items = []
    for label in ["A", "B"]:
        item = CatalogEntry(
            id=identifier(),
            tenant_id="north",
            created_by="issuer|admin",
            kind="knowledge_item",
            name="Memory " + label,
            parent_id=collections[0].id,
            workspace_id=collections[0].workspace_id,
            project_id=collections[0].project_id,
        )
        await service.catalog.catalog_repository.save(item)
        items.append(item)
    engine = context.get_bean(DataSourceRegistry).get("primary").engine
    async with engine.begin() as connection:
        for item, root in zip(items, documents[1:], strict=True):
            await connection.execute(
                insert(CuratedCatalogState),
                dict(
                    item_id=item.id,
                    tenant_id="north",
                    workspace_id=item.workspace_id,
                    native_item_id=item.id,
                    native_workspace_id=item.workspace_id,
                    head_version=1,
                    head_version_id=item.id,
                    head_operation_id=item.id,
                    serving_version=1,
                    serving_version_id=item.id,
                    serving_operation_id=item.id,
                    root_count=1,
                ),
            )
            await connection.execute(
                insert(CuratedSourceRoot),
                dict(
                    id=item.id,
                    tenant_id="north",
                    item_id=item.id,
                    native_version_id=item.id,
                    source_asset_id=root.id,
                ),
            )
    queue = context.get_bean(AssistantQueue)
    memory = context.get_bean(PersonalConversationMemory)
    scope = {"workspace_id": collections[0].workspace_id}
    source = await history.create_thread("issuer|admin", "north", {"folder_id": folder["id"], "scope": scope})
    await service.submit(
        "issuer|admin",
        "north",
        source["id"],
        {"agent_id": agent["id"], "message": "Earlier B", "scope": scope, "client_request_id": "composed-B"},
    )
    old = await queue.claim("composed")
    await queue.evidence(old.id, "composed", "lineage", {"description": "B"}, [items[1].id])
    await queue.finish(old.id, "composed")
    target = await history.create_thread("issuer|admin", "north", {"folder_id": folder["id"], "scope": scope})
    await service.submit(
        "issuer|admin",
        "north",
        target["id"],
        {"agent_id": agent["id"], "message": "Now A", "scope": scope, "client_request_id": "composed-A"},
    )
    run = await queue.claim("composed")
    generation = await queue.begin_generation(
        run.id, "composed", model_id="fixture", model_class="fixture", api="chat"
    )
    await memory.build(run, generation_id=generation)
    result_a = await queue.evidence(run.id, "composed", "lineage", {"description": "A"}, [items[0].id])
    await queue.append(run.id, "composed", "message_delta", {"text": "CURRENT_A_PLUS_RECORDED_B"})
    await queue.finish(run.id, "composed")
    async with engine.begin() as connection:
        await connection.execute(update(Membership).where(Membership.id == "admin").values(active=False))
        for label, workspace, active in [
            ("W", collections[0].workspace_id, True),
            ("A", collections[1].workspace_id, True),
            ("B", collections[2].workspace_id, False),
        ]:
            await connection.execute(
                insert(Membership),
                dict(
                    id="composed-" + label,
                    tenant_id="north",
                    subject="issuer|admin",
                    workspace_id=workspace,
                    role="viewer",
                    active=active,
                ),
            )
    observe = ChatMemoryAuthorityRepository.observe_many
    swapped = False

    async def swap_before_first_snapshot(repository, *args, **kwargs):
        nonlocal swapped
        if not swapped:
            swapped = True
            async with engine.begin() as connection:
                await connection.execute(
                    update(Membership).where(Membership.id == "composed-A").values(active=False)
                )
                await connection.execute(
                    update(Membership).where(Membership.id == "composed-B").values(active=True)
                )
        return await observe(repository, *args, **kwargs)

    pending = []
    if attack == "swap":
        monkeypatch.setattr(ChatMemoryAuthorityRepository, "observe_many", swap_before_first_snapshot)
    else:
        import asyncio
        from contextlib import suppress

        validate_current = memory.validate_current if output == "page" else memory.validate_result_current
        validate_replay = memory.validate_replay

        async def swap(a, b):
            nonlocal swapped
            async with engine.begin() as connection:
                await connection.execute(
                    update(Membership).where(Membership.id == "composed-A").values(active=a)
                )
                await connection.execute(
                    update(Membership).where(Membership.id == "composed-B").values(active=b)
                )
            swapped = True

        async def current_then_swap(*args):
            await validate_current(*args)
            writer = asyncio.create_task(swap(False, True))
            pending.append(writer)
            # A consistent primary unit can hold the writer until the release check ends.
            with suppress(TimeoutError):
                await asyncio.wait_for(asyncio.shield(writer), 0.1)

        async def memory_then_restore(value):
            await validate_replay(value)
            await swap(True, False)

        monkeypatch.setattr(
            memory, "validate_current" if output == "page" else "validate_result_current", current_then_swap
        )
        monkeypatch.setattr(memory, "validate_replay", memory_then_restore)
    try:
        with pytest.raises(AccessDenied):
            if output == "page":
                await service.message_page("issuer|admin", "north", target["id"])
            else:
                await service.result("issuer|admin", "north", run.id, result_a)
    finally:
        if pending:
            await asyncio.gather(*pending)
    assert swapped


async def test_unchanged_streaming_delta_reuses_only_successful_current_authority_fingerprint(
    assistants, monkeypatch
):
    from unittest.mock import AsyncMock

    from koinon.catalog.errors import AccessDenied

    service, history, queue, memory, folder, source, old, target, run, generation = await memory_pair(
        assistants
    )
    memory._current_admissions.clear()
    validated = AsyncMock(wraps=memory.validate_current)
    observed = AsyncMock(wraps=memory.authority_repository.observe_many)
    monkeypatch.setattr(memory, "validate_current", validated)
    monkeypatch.setattr(memory.authority_repository, "observe_many", observed)
    await memory.authorize("issuer|admin", "north", run.id)
    assert validated.await_count == 1 and observed.await_count == 2
    for ordinal in range(5):
        await queue.append(run.id, "pair-worker", "message_delta", {"text": "chunk " + str(ordinal)})
        await memory.authorize("issuer|admin", "north", run.id)
    assert validated.await_count == 1 and observed.await_count == 7
    member = await service.catalog.membership_repository.find_by_id("admin")
    member.active = False
    await service.catalog.membership_repository.save(member)
    with pytest.raises(AccessDenied):
        await memory.authorize("issuer|admin", "north", run.id)


async def test_fixed_rows_cannot_be_silently_reselected_away_after_reset():
    from types import SimpleNamespace
    from unittest.mock import AsyncMock

    from koinon.assistants.service import AssistantService
    from koinon.catalog.errors import AccessDenied

    run = SimpleNamespace(id="target")
    fixed = SimpleNamespace(id="old-result", payload={"asset_ids": ["revoked-source"]})
    denied = AsyncMock(side_effect=AccessDenied("Source was revoked"))
    service = SimpleNamespace(
        scoped=AsyncMock(return_value=run),
        runs=object(),
        active_results=AsyncMock(return_value=[]),
        catalog=SimpleNamespace(get=denied),
        origin_authority=AsyncMock(),
        memory=None,
    )
    with pytest.raises(AccessDenied):
        await AssistantService.authorize_results(
            service, "owner", "north", "target", require_memory=False, result_rows=(fixed,)
        )
    denied.assert_awaited_once_with("owner", "north", "revoked-source")
    service.active_results.assert_not_awaited()


async def test_page_captured_before_retry_cannot_use_post_reset_empty_manifest(assistants, monkeypatch):
    from sqlalchemy import update

    from koinon.assistants.lifecycle import timestamp
    from koinon.assistants.memory.repositories import ChatMemoryRepository
    from koinon.catalog.errors import AccessDenied
    from koinon.tokens.entities import PersonalToken

    engine = await native_tokens(assistants, [token_row("context-origin", ["catalog:read", "chat:use"])])
    service, history, queue, memory, folder, source, old, target, run, generation = await memory_pair(
        assistants, origin_token_id="context-origin"
    )
    await queue.append(run.id, "pair-worker", "message_delta", {"text": "OLD_RECORDED_CONTEXT_BODY"})
    await queue.finish(run.id, "pair-worker", code="CONTROLLED_FAILURE")
    async with engine.begin() as connection:
        await connection.execute(
            update(PersonalToken).where(PersonalToken.id == "context-origin").values(revoked_at=timestamp())
        )
    original = ChatMemoryRepository.active_manifests
    reset = False

    async def reset_before_read(repository, *args, **kwargs):
        nonlocal reset
        if not reset:
            reset = True
            await service.retry("issuer|admin", "north", run.id)
        return await original(repository, *args, **kwargs)

    monkeypatch.setattr(ChatMemoryRepository, "active_manifests", reset_before_read)
    with pytest.raises(AccessDenied):
        await service.message_page("issuer|admin", "north", target["id"])
    assert reset
    assert (await service.runs.find_by_id(run.id)).status == "queued"


async def test_event_capture_reset_is_checked_at_final_statement(assistants, monkeypatch):
    from koinon.assistants.memory.authority_repository import ChatMemoryAuthorityRepository
    from koinon.assistants.memory.projections import MemoryOutputCapture
    from koinon.catalog.errors import AccessDenied

    service, history, queue, memory, folder, source, old, target, run, generation = await memory_pair(
        assistants
    )
    await queue.finish(run.id, "pair-worker", code="CONTROLLED_FAILURE")
    await memory.authorize("issuer|admin", "north", run.id)
    original = ChatMemoryAuthorityRepository.observe_many
    reset = False

    async def reset_before_cut(repository, *args, **kwargs):
        nonlocal reset
        if not reset:
            reset = True
            await service.retry("issuer|admin", "north", run.id)
        return await original(repository, *args, **kwargs)

    monkeypatch.setattr(ChatMemoryAuthorityRepository, "observe_many", reset_before_cut)
    with pytest.raises(AccessDenied):
        await memory.authorize(
            "issuer|admin", "north", run.id, captures=(MemoryOutputCapture(run.id, "reset", 0),)
        )
    assert reset


async def test_as_of_page_body_remains_valid_when_only_new_deltas_append(assistants, monkeypatch):
    from koinon.assistants.memory.repositories import ChatMemoryRepository

    service, history, queue, memory, folder, source, old, target, run, generation = await memory_pair(
        assistants
    )
    await queue.append(run.id, "pair-worker", "message_delta", {"text": "First captured chunk"})
    cursor = (await service.runs.find_by_id(run.id)).sequence
    original = ChatMemoryRepository.active_manifests
    appended = False

    async def append_before_memory(repository, *args, **kwargs):
        nonlocal appended
        if not appended:
            appended = True
            await queue.append(run.id, "pair-worker", "message_delta", {"text": " Later chunk"})
        return await original(repository, *args, **kwargs)

    monkeypatch.setattr(ChatMemoryRepository, "active_manifests", append_before_memory)
    page = await service.message_page("issuer|admin", "north", target["id"])
    answer = next(item for item in page["items"] if item.get("run_id") == run.id)
    from koinon.answers.receipts import legacy_notice

    assert answer["text"] == legacy_notice("en")
    assert answer["event_cursor"] == str(cursor)
    assert (await service.runs.find_by_id(run.id)).sequence > cursor


async def test_native100_message_page_can_hold51_assistants_at_two_half_turn_boundaries(assistants):
    import base64
    import json
    from datetime import timedelta

    from pyfly.data.relational.datasource_registry import DataSourceRegistry
    from sqlalchemy import insert

    from koinon.assistants.entities import ChatMessage, ChatRun
    from koinon.assistants.lifecycle import timestamp

    service, context = assistants
    _, agent = await configured(service)
    thread = await context.get_bean(ChatHistoryService).create_thread("issuer|admin", "north", {})
    engine = context.get_bean(DataSourceRegistry).get("primary").engine
    start = timestamp() - timedelta(seconds=60)
    async with engine.begin() as connection:
        for ordinal in range(1, 52):
            moment = start + timedelta(seconds=ordinal)
            user = f"u{ordinal:02d}"
            answer = f"z{ordinal:02d}" if ordinal == 1 else f"a{ordinal:02d}"
            await connection.execute(
                insert(ChatMessage),
                [
                    dict(id=user, thread_id=thread["id"], role="user", text="Question", created_at=moment),
                    dict(
                        id=answer, thread_id=thread["id"], role="assistant", text="Answer", created_at=moment
                    ),
                ],
            )
            await connection.execute(
                insert(ChatRun),
                dict(
                    id=f"capacity-{ordinal}",
                    tenant_id="north",
                    thread_id=thread["id"],
                    user_message_id=user,
                    message_id=answer,
                    agent_id=agent["id"],
                    agent_revision=1,
                    provider_revision=1,
                    client_request_id=f"capacity-{ordinal}",
                    payload_hash="a" * 64,
                    status="completed",
                    created_at=moment,
                ),
            )
    before = (start + timedelta(seconds=51), "u51")
    rows = await service.message_repository.find_thread_messages(thread["id"], before=before, limit=100)
    assert len(rows) == 100
    assert len({row[1] for row in rows if row[1]}) == 51
    assert all(row[1] is None for row in rows if row[0].role == "user")
    cursor = (
        base64.urlsafe_b64encode(json.dumps([before[0].isoformat(), before[1]]).encode()).decode().rstrip("=")
    )
    page = await service.message_page("issuer|admin", "north", thread["id"], before=cursor, limit=100)
    assert len(page["items"]) == 100 and page["next_cursor"] is not None


@pytest.mark.parametrize("retry", [False, True])
async def test_result_payload_keeps_exact_generation_memory_authority(assistants, retry):
    from sqlalchemy import update

    from koinon.assistants.lifecycle import timestamp
    from koinon.catalog.errors import AccessDenied
    from koinon.evidence.dtos import SourceReference
    from koinon.knowledge.capture_dtos import CapturedEvidence
    from koinon.tokens.entities import PersonalToken

    engine = await native_tokens(assistants, [token_row("memory-origin", ["catalog:read", "chat:use"])])
    service, history, queue, memory, folder, source, old, target, run, generation = await memory_pair(
        assistants, origin_token_id="memory-origin"
    )
    parent = None
    for kind in ["workspace", "project", "collection", "source", "dataset"]:
        parent = await service.catalog.create(
            "issuer|admin", "north", kind=kind, name="Public " + kind, parent_id=parent.id if parent else None
        )
    data = {
        "sql": "SELECT 'SECRET_FROM_REMEMBERED_B' AS selected_value",
        "execution_status": "OK",
        "preview": [{"selected_value": "SECRET_FROM_REMEMBERED_B"}],
        "query_id": "fixture-query",
        "row_count": 1,
    }
    ref = SourceReference(
        id="query-source-A",
        kind="dataset",
        asset_id=parent.id,
        source_id=parent.parent_id,
        title=parent.name,
        used_revision="snapshot:fixture",
        snapshot_id="fixture-snapshot",
        query_id="fixture-query",
    )
    result_id = await queue.evidence(
        run.id, "pair-worker", "query", data, [parent.id], capture=CapturedEvidence(data, (ref,), True)
    )
    await queue.finish(run.id, "pair-worker", code="CONTROLLED_FAILURE" if retry else None)
    assert (await service.result("issuer|admin", "north", run.id, result_id))["data"]["row_count"] == 1
    if retry:
        await service.retry("issuer|admin", "north", run.id)
        claimed = await queue.claim("fresh-generation")
        newer = await queue.begin_generation(
            claimed.id, "fresh-generation", model_id="fixture", model_class="fixture", api="chat"
        )
        assert newer != generation
        assert await memory.repository.for_generation(newer) is None
        assert (await service.result("issuer|admin", "north", run.id, result_id))["data"]["row_count"] == 1
    async with engine.begin() as connection:
        await connection.execute(
            update(PersonalToken).where(PersonalToken.id == "memory-origin").values(revoked_at=timestamp())
        )
    if not retry:
        with pytest.raises(AccessDenied):
            await memory.authorize("issuer|admin", "north", run.id)
    # Same requested generation contains the revoked context; its query row remains accessible.
    with pytest.raises(AccessDenied):
        result = await service.result("issuer|admin", "north", run.id, result_id)
        assert result["data"]["preview"][0]["selected_value"] == "SECRET_FROM_REMEMBERED_B"


async def test_nested_history_with_large_omitted_legacy_answers_retains_a_fitting_bounded_context(assistants):
    from types import SimpleNamespace

    from koinon.assistants.memory.service import PersonalConversationMemory
    from koinon.evidence.dtos import SourceReference
    from koinon.evidence.ports import SourceResolverPort
    from koinon.knowledge.capture_dtos import CapturedEvidence

    service, context = assistants
    history = context.get_bean(ChatHistoryService)
    queue = context.get_bean(AssistantQueue)
    memory = context.get_bean(PersonalConversationMemory)
    folder = await history.create_folder(
        "issuer|admin", "north", {"name": "Byte budget", "memory_enabled": True}
    )
    _, agent = await configured(service)
    target = await history.create_thread("issuer|admin", "north", {"folder_id": folder["id"]})
    parent = None
    for kind in ["workspace", "project", "collection", "source", "document"]:
        parent = await service.catalog.create(
            "issuer|admin", "north", kind=kind, name=kind, parent_id=parent.id if parent else None
        )
    ref = SourceReference(
        id="controlled",
        kind="document",
        asset_id=parent.id,
        source_id=parent.parent_id,
        title="Controlled source",
        used_revision="fixture",
    )

    async def resolve(subject, tenant, values):
        return tuple(value.model_copy(update={"availability": "available"}) for value in values)

    context.container.register_instance(SourceResolverPort, SimpleNamespace(resolve=resolve))
    for group in range(4):
        for ordinal in range(10):
            thread = await history.create_thread("issuer|admin", "north", {"folder_id": folder["id"]})
            await service.submit(
                "issuer|admin",
                "north",
                thread["id"],
                {
                    "agent_id": agent["id"],
                    "message": f"My preference {group}/{ordinal}",
                    "client_request_id": f"legacy-{group}-{ordinal}",
                },
            )
            old = await queue.claim("byte-worker")
            await queue.append(old.id, "byte-worker", "message_delta", {"text": "x" * 247000})
            await queue.finish(old.id, "byte-worker")
        await service.submit(
            "issuer|admin",
            "north",
            target["id"],
            {
                "agent_id": agent["id"],
                "message": f"Continue branch {group}",
                "client_request_id": f"branch-{group}",
            },
        )
        run = await queue.claim("byte-worker")
        generation = await queue.begin_generation(
            run.id, "byte-worker", model_id="fixture", model_class="fixture", api="chat"
        )
        messages = await memory.build(run, generation_id=generation)
        assert messages
        data = {"hits": [{"asset_id": parent.id, "text": "Recorded fact"}]}
        await queue.evidence(
            run.id, "byte-worker", "search", data, [parent.id], capture=CapturedEvidence(data, (ref,), True)
        )
        await queue.append(
            run.id, "byte-worker", "message_delta", {"text": f"Short verified historical answer {group}"}
        )
        await queue.policy(run.id, "byte-worker", {"outcome": "grounded", "code": "GROUNDED"})
        await queue.finish(run.id, "byte-worker")


async def test_authority_admission_counts_json_escape_expansion_before_fetch(assistants):
    from koinon.assistants.entities import ChatMessage
    from koinon.assistants.memory.repositories import ChatMemoryRepository

    service, context = assistants
    thread = await context.get_bean(ChatHistoryService).create_thread("issuer|admin", "north", {})
    for ordinal in range(3):
        await service.message_repository.save(
            ChatMessage(
                id=f"escaped-{ordinal}",
                thread_id=thread["id"],
                role="assistant",
                text="\x01" * 247000,
                status="completed",
            )
        )
    repository = context.get_bean(ChatMemoryRepository)
    assert await repository.pins_fit((), message_ids=("escaped-0", "escaped-1")) is True
    assert await repository.pins_fit((), message_ids=("escaped-0", "escaped-1", "escaped-2")) is False
