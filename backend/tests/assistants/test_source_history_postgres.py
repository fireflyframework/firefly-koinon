# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Native assistant releases use the reader's exact current source authority."""

import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest
from pyfly.context import ApplicationContext
from pyfly.data.relational.datasource_registry import DataSourceRegistry
from release_helpers import seal_first_quote
from source_reader_fixture import assistant_source_reader
from sqlalchemy import event, update
from test_memory_authority_postgres import pg_assistants as pg_assistants
from test_service import configured

from koinon.assistants.queue import AssistantQueue
from koinon.assistants.snapshots import ConversationSnapshots
from koinon.catalog.entities import Membership
from koinon.catalog.errors import AccessDenied
from koinon.catalog.repositories import MembershipRepository
from koinon.evidence.dtos import SourceReference
from koinon.evidence.ports import SourceResolverPort
from koinon.integrations.content_sources.entities import PersonalSourceConnection
from koinon.integrations.content_sources.errors import SourceError
from koinon.integrations.content_sources.read_context import reader_source_scope
from koinon.integrations.content_sources.read_dtos import ReaderSelectionInput
from koinon.integrations.content_sources.read_repository import SourceReadRepository
from koinon.integrations.content_sources.reader_selection_repository import SourceReaderSelectionRepository
from koinon.integrations.content_sources.sync_entities import SourceImportedVersion
from koinon.knowledge.capture_dtos import CapturedEvidence

spec = importlib.util.spec_from_file_location(
    "assistant_source_fixture", Path(__file__).parents[1] / "exports/test_source_release_postgres.py"
)
assert spec and spec.loader
source_fixture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(source_fixture)
pytestmark = pytest.mark.integration


@pytest.mark.parametrize("pg_assistants", [{"migrated_primary": True}], indirect=True)
@pytest.mark.parametrize("mode", ["saved", "explicit"])
async def test_queued_selection_rejects_stored_unicode_size_before_insert(pg_assistants, mode):
    from pyfly.kernel import InvalidRequestException
    from sqlalchemy import func, select, text

    from koinon.assistants.entities import ChatRun
    from koinon.catalog.service import CatalogService
    from koinon.integrations.content_sources.reader_selection_service import SourceReaderSelections

    service, context, sessions = pg_assistants
    choices = [
        {"provider": "sharepoint", "connection_id": str(index), "external_tenant": str(index) + "界" * 450}
        for index in range(50)
    ]
    async with sessions.begin() as session:
        session.add_all(
            PersonalSourceConnection(
                id=value["connection_id"],
                tenant_id="north",
                owner="issuer|admin",
                provider=value["provider"],
                external_tenant=value["external_tenant"],
                status="connected",
                external_subject="remote-admin",
            )
            for value in choices
        )
    selections = SourceReaderSelections(
        context.get_bean(SourceReaderSelectionRepository), context.get_bean(CatalogService)
    )
    service.source_reader = SimpleNamespace(get=lambda: SimpleNamespace(selections=selections))
    await selections.replace(
        "issuer|admin",
        "north",
        ReaderSelectionInput(expected_revision=0, operation_id=uuid4(), connections=choices),
    )
    _, agent = await configured(service)
    thread = await service.create_thread("issuer|admin", "north", {})
    request = {"agent_id": agent["id"], "message": "Question", "client_request_id": "unicode"}
    if mode == "explicit":
        request["reader_source_connections"] = choices
    with pytest.raises(InvalidRequestException) as denied:
        await service.submit("issuer|admin", "north", thread["id"], request)
    assert denied.value.code == "INVALID_SOURCE_SELECTION"
    async with sessions() as session:
        assert await session.scalar(select(func.count()).select_from(ChatRun)) == 0
        assert await session.scalar(
            text(
                "SELECT EXISTS (SELECT 1 FROM pg_trigger "
                "WHERE tgrelid='public.koinon_chat_runs'::regclass "
                "AND tgname='koinon_chat_reader_selection_guard' "
                "AND tgenabled='O' AND NOT tgisinternal)"
            )
        )
    fitting = choices[:46]
    await selections.replace(
        "issuer|admin",
        "north",
        ReaderSelectionInput(expected_revision=1, operation_id=uuid4(), connections=fitting),
    )
    if mode == "explicit":
        request["reader_source_connections"] = fitting
    result = await service.submit("issuer|admin", "north", thread["id"], request)
    async with sessions() as session:
        row = (
            await session.execute(
                text(
                    "SELECT reader_source_selection,octet_length(reader_source_selection::text) "
                    "FROM koinon_chat_runs WHERE id=:id"
                ),
                {"id": result["run_id"]},
            )
        ).one()
    assert row[0]["mode"] == mode
    assert row[0]["connections"] == sorted(
        fitting, key=lambda item: (item["provider"], item["external_tenant"], item["connection_id"])
    )
    assert row[1] == len(json.dumps(row[0]).encode("utf-8")) <= 131072


@pytest.mark.parametrize("pg_assistants", [{"migrated_primary": True}], indirect=True)
async def test_queued_source_choice_is_part_of_idempotent_request(pg_assistants, monkeypatch):
    from pyfly.kernel import ConflictException

    service, _, _, _, _, _, _ = await native_imported_output(pg_assistants, monkeypatch, bind_before=True)
    _, agent = await configured(service)
    thread = await service.create_thread("owner", "north", {})
    request = {"agent_id": agent["id"], "message": "Private request", "client_request_id": "choice"}
    created = await service.submit("owner", "north", thread["id"], request)
    assert await service.submit("owner", "north", thread["id"], request) == created
    with pytest.raises(ConflictException) as denied:
        await service.submit("owner", "north", thread["id"], {**request, "reader_source_connections": []})
    assert denied.value.code == "IDEMPOTENCY_CONFLICT"


@pytest.mark.parametrize("pg_assistants", [{"migrated_primary": True}], indirect=True)
async def test_concurrent_enqueue_and_lease_recovery_keep_one_immutable_request(pg_assistants):
    import asyncio
    from datetime import timedelta

    from sqlalchemy import func, select

    from koinon.assistants.entities import ChatMessage, ChatRun
    from koinon.assistants.lifecycle import timestamp

    service, context, sessions = pg_assistants
    _, agent = await configured(service)
    thread = await service.create_thread("issuer|admin", "north", {})
    payload = {
        "agent_id": agent["id"],
        "message": "Local only",
        "client_request_id": "same",
        "reader_source_connections": [],
    }
    first, replay = await asyncio.gather(
        *(service.submit("issuer|admin", "north", thread["id"], payload) for _ in range(2))
    )
    assert first == replay
    async with sessions() as session:
        assert await session.scalar(select(func.count()).select_from(ChatRun)) == 1
        assert await session.scalar(select(func.count()).select_from(ChatMessage)) == 2
    queue = context.get_bean(AssistantQueue)
    previous = await queue.claim("previous-worker")
    async with sessions.begin() as session:
        await session.execute(
            update(ChatRun)
            .where(ChatRun.id == previous.id)
            .values(lease_until=timestamp() - timedelta(seconds=1))
        )
    reclaimed = await asyncio.gather(
        AssistantQueue(service).claim("one"), AssistantQueue(service).claim("two")
    )
    claimed = [value for value in reclaimed if value is not None]
    assert len(claimed) == 1
    assert claimed[0].id == first["run_id"] and claimed[0].attempts == 2
    assert claimed[0].reader_source_selection == previous.reader_source_selection


@pytest.mark.parametrize("mode", ["saved", "explicit", "local_only", "saved_empty"])
@pytest.mark.parametrize("pg_assistants", [{"migrated_primary": True}], indirect=True)
async def test_queue_restart_preserves_choice_without_resolving_new_defaults(
    pg_assistants, monkeypatch, mode
):
    from koinon.assistants.execution import AssistantExecutor

    service, _, _, reader, remote, _, context = await native_imported_output(pg_assistants, monkeypatch)
    choices = [{"provider": "google_drive", "connection_id": "connection"}]
    if mode == "saved_empty":
        await reader.selections.replace(
            "owner",
            "north",
            ReaderSelectionInput(
                expected_revision=1,
                operation_id=uuid4(),
                connections=[],
            ),
        )
    _, agent = await configured(service)
    scope = {} if mode in {"local_only", "saved_empty"} else {"asset_ids": ["asset"]}
    thread = await service.create_thread("owner", "north", {"scope": scope})
    request = {
        "agent_id": agent["id"],
        "message": "Frozen choice",
        "client_request_id": "restart",
        "scope": scope,
    }
    if mode in {"explicit", "local_only"}:
        request["reader_source_connections"] = choices if mode == "explicit" else []
    created = await service.submit("owner", "north", thread["id"], request)
    stored = (await service.runs.find_by_id(created["run_id"])).reader_source_selection
    assert stored["mode"] == ("saved" if mode == "saved_empty" else mode)
    assert stored["connections"] == (
        [] if mode in {"local_only", "saved_empty"} else [{**choices[0], "external_tenant": None}]
    )
    await reader.selections.replace(
        "owner",
        "north",
        ReaderSelectionInput(
            expected_revision=2 if mode == "saved_empty" else 1,
            operation_id=uuid4(),
            connections=choices if mode == "saved_empty" else [],
        ),
    )
    assert await service.submit("owner", "north", thread["id"], request) == created
    assert (await service.runs.find_by_id(created["run_id"])).reader_source_selection == stored
    restarted_queue = AssistantQueue(service)
    claimed = await restarted_queue.claim("restarted-worker")
    assert claimed.id == created["run_id"]
    remote.calls.clear()
    if mode in {"saved", "saved_empty"}:
        with pytest.raises(SourceError, match="authority_changed"):
            await context.get_bean(AssistantExecutor).authority(claimed.id, "restarted-worker")
        assert remote.calls == []
    else:
        current, _, _, _ = await context.get_bean(AssistantExecutor).authority(claimed.id, "restarted-worker")
        assert current.reader_source_selection == stored
        assert all(connection == "connection" for _, _, connection in remote.calls)
        if mode == "local_only":
            assert remote.calls == []


async def running_imported(pg_assistants, monkeypatch):
    from datetime import timedelta

    from koinon.assistants.entities import ChatRun
    from koinon.assistants.lifecycle import timestamp

    service, _, snapshot, reader, remote, sessions, context = await native_imported_output(
        pg_assistants, monkeypatch
    )
    run = (await service.runs.find_all(thread_id=snapshot.thread_id))[0]
    async with sessions.begin() as session:
        await session.execute(
            update(ChatRun)
            .where(ChatRun.id == run.id)
            .values(
                status="running", worker_id="source-worker", lease_until=timestamp() + timedelta(minutes=5)
            )
        )
    return service, run, reader, remote, sessions, context


@pytest.mark.parametrize("pg_assistants", [{"migrated_primary": True}], indirect=True)
@pytest.mark.parametrize("cancelled", [False, True])
async def test_forensic_observation_keeps_only_exact_safe_correlation(pg_assistants, monkeypatch, cancelled):
    from sqlalchemy import select

    from koinon.assistants.entities import ChatRun, ToolResult
    from koinon.knowledge.capture_dtos import (
        NativeReadFingerprint,
        NativeReadOrigin,
        NativeSqlAttempt,
        NativeTableSnapshot,
    )

    service, run, _, remote, sessions, context = await running_imported(pg_assistants, monkeypatch)
    queue = context.get_bean(AssistantQueue)
    generation_id = await queue.begin_generation(
        run.id, "source-worker", model_id="controlled", model_class="FunctionModel", api="chat"
    )
    source = SourceReference(
        id="source-pin",
        asset_id="asset",
        source_id="source",
        kind="document",
        title="SENSITIVE_title",
        quote="SENSITIVE_quote",
        section="SENSITIVE_path",
        used_revision="chunk-sha256:" + "a" * 64,
    )
    capture = CapturedEvidence(
        {"nested": {"tool_result": "SENSITIVE_result"}},
        (source,),
        False,
        (
            NativeReadFingerprint(
                "retrieval",
                "documents",
                "north",
                "workspace",
                "asset",
                "a" * 64,
                ("native-doc",),
                (),
                origin=NativeReadOrigin(
                    original_filename="SENSITIVE_file", sheet_or_json_path="SENSITIVE_path"
                ),
            ),
        ),
        (
            NativeSqlAttempt(
                1,
                "query",
                "b" * 64,
                "select",
                "failed",
                True,
                {"SENSITIVE_table": "snapshot"},
                statement="SELECT SENSITIVE_column FROM SENSITIVE_table",
                database="SENSITIVE_database",
                tables=(NativeTableSnapshot("table-id", "SENSITIVE_table", "snapshot"),),
            ),
        ),
    )
    async with sessions.begin() as session:
        retained = (
            await session.execute(
                select(ToolResult.id, ToolResult.payload).where(ToolResult.run_id == run.id)
            )
        ).all()
        await session.execute(
            update(PersonalSourceConnection)
            .where(PersonalSourceConnection.id == "connection")
            .values(status="disconnected")
        )
        if cancelled:
            await session.execute(
                update(ChatRun)
                .where(ChatRun.id == run.id)
                .values(
                    status="cancelled",
                    worker_id=None,
                    lease_until=None,
                )
            )
    remote.calls.clear()
    producer = {"generation_id": generation_id, "attempt": run.attempts}
    identifier = await queue.observation(
        run.id, "source-worker", "search", ["asset"], capture=capture, **producer
    )
    assert (
        await queue.observation(run.id, "source-worker", "search", ["asset"], capture=capture, **producer)
        == identifier
    )
    async with sessions() as session:
        saved = await session.get(ToolResult, identifier)
        assert "SENSITIVE_" not in json.dumps(saved.payload)
        assert saved.payload["generation_id"] == generation_id
        assert saved.payload["source_manifest"]["complete"] is False
        assert saved.payload["native_reads"][0]["content_sha256"] == "a" * 64
        assert saved.payload["sql_attempts"][0]["statement_sha256"] == "b" * 64
        assert (
            await session.execute(
                select(ToolResult.id, ToolResult.payload).where(
                    ToolResult.run_id == run.id, ToolResult.id != identifier
                )
            )
        ).all() == retained
    assert remote.calls == []


@pytest.mark.parametrize("pg_assistants", [{"migrated_primary": True}], indirect=True)
@pytest.mark.parametrize(
    "substitution", ["generation", "worker", "attempt", "tenant", "takeover", "publish", "unbound"]
)
async def test_cancelled_observation_rejects_substituted_producer(pg_assistants, monkeypatch, substitution):
    from pyfly.kernel import ConflictException, InvalidRequestException
    from sqlalchemy import func, select

    from koinon.assistants.entities import ChatRun, ToolResult
    from koinon.knowledge.capture_dtos import NativeReadFingerprint

    _, run, _, _, sessions, context = await running_imported(pg_assistants, monkeypatch)
    queue = context.get_bean(AssistantQueue)
    generation = await queue.begin_generation(
        run.id, "source-worker", model_id="controlled", model_class="FunctionModel", api="chat"
    )
    async with sessions.begin() as session:
        await session.execute(
            update(ChatRun)
            .where(ChatRun.id == run.id)
            .values(
                status="cancelled",
                worker_id=None,
                lease_until=None,
                attempts=run.attempts + (substitution == "takeover"),
            )
        )
    producer = {"generation_id": generation, "attempt": run.attempts}
    worker = "source-worker"
    capture = CapturedEvidence({}, (), False)
    if substitution == "generation":
        producer["generation_id"] = "foreign-generation"
    elif substitution == "worker":
        worker = "foreign-worker"
    elif substitution == "attempt":
        producer["attempt"] = run.attempts - 1
    elif substitution == "unbound":
        producer = {}
    elif substitution == "tenant":
        capture = CapturedEvidence(
            {},
            (),
            False,
            (
                NativeReadFingerprint(
                    "retrieval",
                    "documents",
                    "south",
                    "workspace",
                    "asset",
                    "a" * 64,
                    (),
                    (),
                ),
            ),
        )
    with pytest.raises((ConflictException, InvalidRequestException, SourceError)):
        if substitution == "publish":
            await queue.evidence(run.id, worker, "search", {}, [], capture=CapturedEvidence({}, (), True))
        else:
            await queue.observation(run.id, worker, "search", ["asset"], capture=capture, **producer)
    async with sessions() as session:
        assert (
            await session.scalar(
                select(func.count())
                .select_from(ToolResult)
                .where(ToolResult.run_id == run.id, ToolResult.kind == "observation")
            )
            == 0
        )
        assert await session.scalar(select(ChatRun.status).where(ChatRun.id == run.id)) == "cancelled"


@pytest.mark.parametrize("action", ["execute", "presentation", "policy", "capture_limits", "citations"])
@pytest.mark.parametrize("pg_assistants", [{"migrated_primary": True}], indirect=True)
async def test_revoked_queue_operations_do_not_hydrate_protected_bodies(pg_assistants, monkeypatch, action):
    from koinon.assistants.execution import AssistantExecutor

    _, run, _, remote, sessions, context = await running_imported(pg_assistants, monkeypatch)
    async with sessions.begin() as session:
        await session.execute(
            update(PersonalSourceConnection)
            .where(PersonalSourceConnection.id == "connection")
            .values(status="disconnected")
        )
    protected_reads = []

    def observe(_connection, _cursor, statement, _parameters, _context, _executemany):
        if statement.lstrip().startswith("SELECT") and any(
            column in statement
            for column in (
                "koinon_chat_threads.title,",
                "koinon_chat_messages.text,",
                "koinon_chat_tool_results.payload,",
            )
        ):
            protected_reads.append(statement)

    engine = sessions.kw["bind"].sync_engine
    event.listen(engine, "before_cursor_execute", observe)
    queue = context.get_bean(AssistantQueue)
    remote.calls.clear()
    try:
        if action == "execute":
            await context.get_bean(AssistantExecutor).execute(run.id, "source-worker")
        elif action == "presentation":
            await queue.presentation(
                run.id,
                "source-worker",
                {
                    "locale": "en",
                    "time_zone": "UTC",
                    "response_language": "en",
                },
            )
        elif action == "policy":
            await queue.policy(run.id, "source-worker", {"outcome": "refused"})
        else:
            with pytest.raises(SourceError):
                if action == "capture_limits":
                    await queue.capture_limits(run.id, "source-worker", "search")
                else:
                    await queue.citations(run.id, "source-worker")
    finally:
        event.remove(engine, "before_cursor_execute", observe)
    assert protected_reads == []
    assert remote.calls == []


@pytest.mark.parametrize(
    "attack",
    [
        "nested_write",
        "new_capture",
        "child_task",
        "expired",
        "different_run",
        "changed_body",
        "foreign_reader",
        "read_escalation",
    ],
)
@pytest.mark.parametrize("pg_assistants", [{"migrated_primary": True}], indirect=True)
async def test_queue_admission_rejects_context_and_payload_reuse(pg_assistants, monkeypatch, attack):
    import asyncio
    from contextvars import copy_context

    from koinon.assistants.entities import ChatMessage
    from koinon.assistants.run_sources import consume_memory_admission, run_source_unit

    service, run, reader, _, _, context = await running_imported(pg_assistants, monkeypatch)
    queue = context.get_bean(AssistantQueue)
    if attack == "expired":
        async with run_source_unit(service, run.id, "source-worker", write=True, purpose="release_answer"):
            copied = copy_context()
        with pytest.raises(SourceError):
            await asyncio.create_task(queue.fact_pool(run.id, "source-worker"), context=copied)
        return
    with pytest.raises(SourceError):
        async with run_source_unit(
            service,
            run.id,
            "source-worker",
            write=attack not in {"nested_write", "read_escalation"},
            purpose="release_answer",
        ):
            if attack == "nested_write":
                await queue.evidence(
                    run.id, "source-worker", "search", {}, [], capture=CapturedEvidence({}, (), True)
                )
            elif attack in {"new_capture", "read_escalation"}:
                async with run_source_unit(
                    service,
                    run.id,
                    "source-worker",
                    purpose="fact_pool",
                    capture=CapturedEvidence({}, (), True) if attack == "new_capture" else None,
                    write=attack == "read_escalation",
                ):
                    pytest.fail("A nested operation widened its admission")
            elif attack == "foreign_reader":
                from copy import copy

                from koinon.assistants.memory.service import PersonalConversationMemory

                memory = copy(context.get_bean(PersonalConversationMemory))
                memory.source_reader = SimpleNamespace(get=lambda: copy(reader))
                await memory.authorize_many("owner", "north", (run.id,))
            elif attack == "child_task":
                await asyncio.create_task(queue.fact_pool(run.id, "source-worker"))
            elif attack == "different_run":
                await queue.fact_pool("other-run", "source-worker")
            else:
                await service.runs._require_session().execute(
                    update(ChatMessage)
                    .where(ChatMessage.id == run.user_message_id)
                    .values(text="Changed after admission")
                )
                await consume_memory_admission("owner", "north", (run.id,), reader=reader)


@pytest.mark.parametrize("mutation", ["message", "memory", "result", "lease", "saved"])
@pytest.mark.parametrize("pg_assistants", [{"migrated_primary": True}], indirect=True)
async def test_queue_rechecks_preflight_identity_after_provider_io(pg_assistants, monkeypatch, mutation):
    from sqlalchemy import select

    from koinon.assistants.entities import ChatMessage, ChatRun, ToolResult
    from koinon.assistants.memory.entities import ChatMemoryManifest

    service, run, reader, remote, sessions, context = await running_imported(pg_assistants, monkeypatch)
    original = remote.check
    changed = False
    protected_reads = []

    def observe(_connection, _cursor, statement, _parameters, _context, _executemany):
        if statement.lstrip().startswith("SELECT") and "koinon_chat_tool_results.payload," in statement:
            protected_reads.append(statement)

    async def mutate(*args):
        nonlocal changed
        if not changed:
            changed = True
            if mutation == "saved":
                await reader.selections.replace(
                    "owner",
                    "north",
                    ReaderSelectionInput(
                        expected_revision=1,
                        operation_id=uuid4(),
                        connections=[],
                    ),
                )
            else:
                async with sessions.begin() as session:
                    if mutation == "message":
                        await session.execute(
                            update(ChatMessage)
                            .where(ChatMessage.id == run.user_message_id)
                            .values(text="Changed prompt")
                        )
                    elif mutation == "memory":
                        row = await session.scalar(
                            select(ChatMemoryManifest).where(ChatMemoryManifest.run_id == run.id)
                        )
                        row.manifest_json = {**row.manifest_json, "forged": True}
                    elif mutation == "result":
                        await session.execute(
                            update(ToolResult)
                            .where(ToolResult.run_id == run.id, ToolResult.kind == "search")
                            .values(payload={"data": {"forged": "Protected replacement"}})
                        )
                    else:
                        await session.execute(
                            update(ChatRun)
                            .where(ChatRun.id == run.id)
                            .values(worker_id="new-worker", attempts=2)
                        )
        return await original(*args)

    monkeypatch.setattr(remote, "check", mutate)
    engine = sessions.kw["bind"].sync_engine
    event.listen(engine, "before_cursor_execute", observe)
    try:
        from pyfly.kernel import ConflictException

        with pytest.raises((SourceError, ConflictException)):
            await context.get_bean(AssistantQueue).fact_pool(run.id, "source-worker")
    finally:
        event.remove(engine, "before_cursor_execute", observe)
    assert changed
    assert protected_reads == []


@pytest.mark.parametrize("pg_assistants", [{"migrated_primary": True}], indirect=True)
@pytest.mark.parametrize("mutation", ["capture", "result"])
async def test_incoming_evidence_cannot_change_during_source_preflight(pg_assistants, monkeypatch, mutation):
    from sqlalchemy import func, select

    from koinon.assistants.entities import ToolResult

    service, run, _, remote, sessions, context = await running_imported(pg_assistants, monkeypatch)
    capture = CapturedEvidence({"hits": []}, (), True)
    data = {"hits": []}
    original = remote.check
    changed = False

    async def mutate(*args):
        nonlocal changed
        if not changed:
            changed = True
            (capture.data if mutation == "capture" else data)["unprepared"] = "Protected replacement"
        return await original(*args)

    monkeypatch.setattr(remote, "check", mutate)
    async with sessions() as session:
        before = await session.scalar(
            select(func.count()).select_from(ToolResult).where(ToolResult.run_id == run.id)
        )
    with pytest.raises(SourceError):
        await context.get_bean(AssistantQueue).evidence(
            run.id, "source-worker", "search", data, [], capture=capture
        )
    assert changed
    async with sessions() as session:
        assert (
            await session.scalar(
                select(func.count()).select_from(ToolResult).where(ToolResult.run_id == run.id)
            )
            == before
        )


@pytest.mark.parametrize("pg_assistants", [{"migrated_primary": True}], indirect=True)
@pytest.mark.parametrize("boundary", ["fact_pool", "capture_limits", "citations"])
async def test_queue_consumption_keeps_original_token_authority(pg_assistants, monkeypatch, boundary):
    from pyfly.kernel import ServiceUnavailableException

    from koinon.assistants.entities import ChatRun

    _, run, _, _, sessions, context = await running_imported(pg_assistants, monkeypatch)
    async with sessions.begin() as session:
        await session.execute(
            update(ChatRun).where(ChatRun.id == run.id).values(access_token_id="revoked-origin")
        )
    queue = context.get_bean(AssistantQueue)
    with pytest.raises((AccessDenied, ServiceUnavailableException)):
        if boundary == "capture_limits":
            await queue.capture_limits(run.id, "source-worker", "search")
        else:
            await getattr(queue, boundary)(run.id, "source-worker")


@pytest.mark.parametrize("pg_assistants", [{"migrated_primary": True}], indirect=True)
@pytest.mark.parametrize("configuration", ["agent", "provider"])
async def test_run_admission_rejects_live_configuration_change_during_provider_check(
    pg_assistants, monkeypatch, configuration
):
    from pyfly.kernel import ConflictException

    from koinon.assistants.entities import AgentConfiguration, Provider
    from koinon.assistants.run_sources import run_source_unit

    service, run, _, remote, sessions, _ = await running_imported(pg_assistants, monkeypatch)
    original = remote.check
    changed = False

    async def mutate(*args):
        nonlocal changed
        if not changed:
            changed = True
            entity = AgentConfiguration if configuration == "agent" else Provider
            async with sessions.begin() as session:
                await session.execute(
                    update(entity).where(entity.tenant_id == "north").values(revision=entity.revision + 1)
                )
        return await original(*args)

    monkeypatch.setattr(remote, "check", mutate)
    entered = False
    with pytest.raises((SourceError, ConflictException)):
        async with run_source_unit(service, run.id, "source-worker"):
            entered = True
    assert changed and not entered


@pytest.mark.parametrize("pg_assistants", [{"migrated_primary": True}], indirect=True)
async def test_queued_native_generation_keeps_source_reader_active(pg_assistants, monkeypatch):
    service, _, snapshot, _, _, _, _ = await native_imported_output(
        pg_assistants, monkeypatch, bind_before=True
    )
    assert "A protected quotation." in snapshot.messages[-1].text
    runs = await service.runs.find_all(thread_id=snapshot.thread_id)
    assert len(runs) == 1 and runs[0].status == "completed"


async def test_queue_source_denial_precedes_executor_metadata_and_model(pg_assistants, monkeypatch):
    from koinon.assistants.entities import ChatRun
    from koinon.assistants.execution import AssistantExecutor

    service, _, snapshot, _, remote, sessions, context = await native_imported_output(
        pg_assistants, monkeypatch, bind_before=True
    )
    run = (await service.runs.find_all(thread_id=snapshot.thread_id))[0]
    from datetime import timedelta

    from koinon.assistants.lifecycle import timestamp

    async with sessions.begin() as session:
        await session.execute(
            update(ChatRun)
            .where(ChatRun.id == run.id)
            .values(
                status="running", worker_id="denied-worker", lease_until=timestamp() + timedelta(minutes=1)
            )
        )
        await session.execute(
            update(PersonalSourceConnection)
            .where(PersonalSourceConnection.id == "connection")
            .values(status="disconnected", revision=2)
        )
    remote.calls.clear()
    with pytest.raises(SourceError):
        await context.get_bean(AssistantExecutor).generate(run.id, "denied-worker")
    assert remote.calls == []


@pytest.mark.parametrize(
    "case",
    [
        "imported",
        "explicit",
        "local",
        "saved_changed",
        "denied",
        "revoked_during_model",
        "tool_answer",
        "revoked_after_tool",
        "automatic_title",
        "title_membership",
        "title_source",
        "title_provider",
    ],
)
@pytest.mark.parametrize("pg_assistants", [{"migrated_primary": True}], indirect=True)
async def test_real_queued_model_source_boundaries(pg_assistants, monkeypatch, case):
    import json
    from time import perf_counter
    from unittest.mock import AsyncMock

    from pydantic_ai.messages import ModelResponse, TextPart, ToolCallPart, ToolReturnPart
    from pydantic_ai.models.function import DeltaToolCall, FunctionModel
    from pyfly.agentic.exceptions import ToolError
    from pyfly.agentic.models import ModelFactory
    from pyfly.data.transaction import current_unit_of_work

    from koinon.assistants.execution import AssistantExecutor
    from koinon.assistants.probe import ProviderProbe

    service, _, _, reader, remote, sessions, context = await native_imported_output(
        pg_assistants, monkeypatch, bind_before=True
    )
    monkeypatch.setattr(
        ProviderProbe,
        "check",
        AsyncMock(
            return_value=[{"id": "connection", "status": "passed"}, {"id": "models", "status": "passed"}]
        ),
    )
    provider, agent = await configured(service)
    await service.validate_provider("issuer|admin", "north", provider["id"])
    actor = "issuer|admin"
    title_case = case == "automatic_title" or case.startswith("title_")
    async with sessions.begin() as session:
        session.add(
            PersonalSourceConnection(
                id="generation-connection",
                tenant_id="north",
                owner=actor,
                provider="google_drive",
                status="connected",
                external_subject="generation-reader",
                issuer="https://accounts.google.com",
                config_fingerprint="f" * 64,
                scopes=["https://www.googleapis.com/auth/drive.readonly"],
            )
        )
    await reader.selections.replace(
        actor,
        "north",
        ReaderSelectionInput(
            expected_revision=0,
            operation_id=uuid4(),
            connections=[{"provider": "google_drive", "connection_id": "generation-connection"}],
        ),
    )
    scope = {} if case == "local" else {"asset_ids": ["asset"]}
    thread = await service.create_thread(
        actor, "north", {"scope": scope, **({} if title_case else {"title": "Source selection evaluation"})}
    )
    await service.submit(
        actor,
        "north",
        thread["id"],
        {
            "agent_id": agent["id"],
            "message": "Summarize authorized knowledge",
            "client_request_id": case,
            "scope": scope,
            **(
                {"reader_source_connections": []}
                if case == "local"
                else {
                    "reader_source_connections": [
                        {"provider": "google_drive", "connection_id": "generation-connection"}
                    ]
                }
                if case == "explicit"
                else {}
            ),
        },
    )
    queue = context.get_bean(AssistantQueue)
    run = await queue.claim("model-worker")
    if case in {"explicit", "saved_changed", "local"}:
        await reader.selections.replace(
            actor,
            "north",
            ReaderSelectionInput(
                expected_revision=1,
                operation_id=uuid4(),
                connections=[],
            ),
        )
    calls = []
    native_calls = []
    title_calls = []
    title_checks = []
    if title_case:
        original_check = AssistantExecutor.model_authority

        async def observed_check(self, *args):
            try:
                return await original_check(self, *args)
            except Exception:
                import traceback

                title_checks.append(traceback.format_exc())
                raise

        monkeypatch.setattr(AssistantExecutor, "model_authority", observed_check)

    async def titled(messages, info):
        title_calls.append(messages)
        async with sessions.begin() as session:
            if case == "title_membership":
                await session.execute(update(Membership).where(Membership.id == "admin").values(active=False))
            elif case == "title_source":
                await session.execute(
                    update(PersonalSourceConnection)
                    .where(PersonalSourceConnection.id == "generation-connection")
                    .values(status="disconnected", revision=2)
                )
            elif case == "title_provider":
                from koinon.assistants.entities import Provider

                await session.execute(
                    update(Provider)
                    .where(Provider.id == provider["id"])
                    .values(revision=Provider.revision + 1)
                )
        result = {"title": "Authorized knowledge"}
        return ModelResponse(
            [ToolCallPart(info.output_tools[0].name, result)]
            if info.output_tools
            else [TextPart(json.dumps(result))]
        )

    async def disconnect():
        async with sessions.begin() as session:
            await session.execute(
                update(PersonalSourceConnection)
                .where(PersonalSourceConnection.id == "generation-connection")
                .values(status="disconnected", revision=2)
            )

    if case in {"tool_answer", "revoked_after_tool"}:
        from koinon.knowledge.evidence_capture import NativeKnowledgeEvidence

        source = SourceReference(
            id="source-pin",
            asset_id="asset",
            source_id="source",
            title="Protected document",
            kind="document",
            source_version_id="v1",
            extraction_id="extraction",
            source_part_id="part",
            source_part_sha256="a" * 64,
            page_basis="recorded_loader",
            used_revision="source-part-sha256:" + "a" * 64,
            current_revision="source-part-sha256:" + "a" * 64,
            quote="A protected quotation.",
            availability="available",
        )

        async def controlled_search(subject, tenant, **arguments):
            assert current_unit_of_work("primary") is None
            native_calls.append((subject, tenant, arguments))
            if case == "revoked_after_tool":
                await disconnect()
            data = {
                "hits": [
                    {
                        "id": "part",
                        "asset_id": "asset",
                        "source_id": "source",
                        "title": source.title,
                        "text": source.quote,
                    }
                ]
            }
            return CapturedEvidence(data, (source,), True)

        context.container.register_instance(
            NativeKnowledgeEvidence, SimpleNamespace(search=controlled_search)
        )

    async def streamed(messages, info):
        assert current_unit_of_work("primary") is None
        calls.append(messages)
        if case == "revoked_during_model":
            await disconnect()
        plan = {"outcome": "insufficient_evidence", "language": "en"}
        if case in {"tool_answer", "revoked_after_tool"}:
            returned = [
                part
                for message in messages
                for part in message.parts
                if isinstance(part, ToolReturnPart) and part.tool_name == "search_knowledge"
            ]
            if not returned:
                yield {0: DeltaToolCall(name="search_knowledge", json_args=json.dumps({"question": "quote"}))}
                return
            assert not (await service.message_repository.find_by_id(run.message_id)).text
            fact = returned[-1].content["answer_facts"][0]
            plan = {
                "outcome": "answer",
                "language": "en",
                "quotes": [{"fact_id": fact["id"], "quote": "A protected quotation."}],
                "values": [],
            }
        yield {
            0: DeltaToolCall(
                name=info.output_tools[0].name,
                json_args=json.dumps(plan),
            )
        }

    monkeypatch.setattr(
        ModelFactory,
        "build_with_secret",
        lambda *args: FunctionModel(function=titled if title_case else None, stream_function=streamed),
    )
    if case == "denied":
        await disconnect()
    remote.calls.clear()
    started = perf_counter()
    remote.trace_enabled = case == "tool_answer"
    if case.startswith("title_"):
        from pyfly.kernel import ConflictException

        with pytest.raises((AccessDenied, SourceError, ConflictException)):
            await context.get_bean(AssistantExecutor).generate(run.id, "model-worker")
        assert (await service.threads.find_by_id(thread["id"])).title == "New conversation"
        assert len(title_calls) == 1
    elif case in {"denied", "revoked_during_model", "saved_changed", "revoked_after_tool"}:
        with pytest.raises(ToolError if case == "revoked_after_tool" else SourceError):
            await context.get_bean(AssistantExecutor).generate(run.id, "model-worker")
        assert not (await service.message_repository.find_by_id(run.message_id)).text
        assert not [
            row for row in await service.results.find_all(run_id=run.id) if row.kind == "answer_release"
        ]
    else:
        await context.get_bean(AssistantExecutor).generate(run.id, "model-worker")
        assert (await service.runs.find_by_id(run.id)).status == "completed"
        assert (await service.message_repository.find_by_id(run.message_id)).answer_policy["outcome"] == (
            "grounded" if case == "tool_answer" else "refused"
        )
        if case == "tool_answer":
            assert (
                "A protected quotation." in (await service.message_repository.find_by_id(run.message_id)).text
            )
    assert len(calls) == (0 if case in {"denied", "saved_changed"} else 2 if case == "tool_answer" else 1)
    assert len(native_calls) == (1 if case in {"tool_answer", "revoked_after_tool"} else 0)
    if native_calls:
        assert native_calls[0][0:2] == (actor, "north")
        assert native_calls[0][2]["asset_ids"] == ["asset"]
    if case == "automatic_title":
        assert (await service.threads.find_by_id(thread["id"])).title == "Authorized knowledge", "\n".join(
            title_checks
        )
        assert len(title_calls) == 1
    if case in {"denied", "saved_changed", "local"}:
        assert remote.calls == []
    else:
        assert remote.calls and all(
            connection == "generation-connection" for _, _, connection in remote.calls
        )
    print(
        f"controlled {case}: {perf_counter() - started:.3f}s; model_calls={len(calls)}; "
        f"title_calls={len(title_calls)}; source_checks={len(remote.calls)}; "
        f"native_calls={len(native_calls)}; cost_usd=0"
    )
    if remote.trace_enabled:
        from collections import Counter

        unique_pins = {pin for _, _, _, pins in remote.traces for pin in pins}
        unique_targets = {target for _, _, targets, _ in remote.traces for target in targets}
        counts = Counter(boundary for boundary, *_ in remote.traces)
        unique_checks = {(connection, targets) for _, connection, targets, _ in remote.traces}
        repeated = {
            boundary: count
            - len(
                {
                    (connection, targets)
                    for stage, connection, targets, _ in remote.traces
                    if stage == boundary
                }
            )
            for boundary, count in counts.items()
        }
        assert len(remote.traces) == len(remote.calls)
        assert unique_pins and len(unique_targets) == 1
        print(
            "controlled source trace: "
            + json.dumps(
                {
                    "check_interface_invocations": len(remote.traces),
                    "provider_http_calls": 0,
                    "unique_local_pins": len(unique_pins),
                    "unique_provider_object_versions": len(unique_targets),
                    "identical_repeated_checks": len(remote.traces) - len(unique_checks),
                    "by_boundary": dict(counts),
                    "repeated_by_boundary": repeated,
                },
                sort_keys=True,
            )
        )


@pytest.mark.parametrize("ancestry", ["remembered", "missing", "malformed"])
async def test_legacy_counts_exclude_remembered_or_unknown_ancestry(pg_assistants, monkeypatch, ancestry):
    from sqlalchemy import select

    from koinon.assistants.entities import ToolResult
    from koinon.assistants.memory.entities import ChatMemoryManifest

    service, _, snapshot, _, _, sessions, context = await native_imported_output(
        pg_assistants, monkeypatch, create_local=True
    )
    local = (await service.list_threads("owner", "north"))[0]
    run = (await service.runs.find_all(thread_id=local["id"]))[0]
    async with sessions.begin() as session:
        if ancestry == "remembered":
            imported = await session.scalar(select(ToolResult).where(ToolResult.kind == "search"))
            manifest = await session.scalar(
                select(ChatMemoryManifest).where(ChatMemoryManifest.run_id == run.id)
            )
            manifest.manifest_json = {
                **manifest.manifest_json,
                "dependencies": [
                    {"run_id": imported.run_id, "result_pins": [{"id": imported.id, "sha256": "a" * 64}]}
                ],
            }
        else:
            sources = {} if ancestry == "malformed" else None
            manifest = {"complete": True}
            if sources is not None:
                manifest["sources"] = sources
            session.add(
                ToolResult(
                    id="unknown-source", run_id=run.id, kind="search", payload={"source_manifest": manifest}
                )
            )
    assert await service.list_threads("owner", "north") == []


@pytest.fixture(autouse=True)
def reader_repositories(monkeypatch):
    from pyfly.container.scanner import scan_package

    original = ApplicationContext.start

    async def start(context):
        context.register_bean(SourceReadRepository)
        context.register_bean(SourceReaderSelectionRepository)
        for package in ("koinon.profiles", "koinon.tokens", "koinon.evidence", "koinon.sharing"):
            scan_package(package, context.container)
        await original(context)

    monkeypatch.setattr(ApplicationContext, "start", start)


async def native_imported_output(pg_assistants, monkeypatch, *, create_local=False, bind_before=True):
    service, context, _ = pg_assistants
    for actor in ("owner", "reader"):
        await context.get_bean(MembershipRepository).save(
            Membership(id=actor, subject=actor, tenant_id="north", role="admin")
        )
    reader, sessions, remote = await assistant_source_reader(context, source_fixture.imported_graph)
    evidence = SimpleNamespace(source_reader=SimpleNamespace(get=lambda: reader))
    if bind_before:
        from koinon.assistants.memory.egress import MemoryEgress
        from koinon.assistants.memory.service import PersonalConversationMemory

        service.source_reader = evidence.source_reader
        context.get_bean(PersonalConversationMemory).source_reader = evidence.source_reader
        context.get_bean(MemoryEgress).source_reader = evidence.source_reader
    _, agent = await configured(service)
    thread = await service.create_thread("owner", "north", {"scope": {"asset_ids": ["asset"]}})
    await service.submit(
        "owner",
        "north",
        thread["id"],
        {"agent_id": agent["id"], "message": "A synthetic imported question", "client_request_id": "native"},
    )
    queue = context.get_bean(AssistantQueue)
    run = await queue.claim("native-worker")
    source = SourceReference(
        id="source-pin",
        asset_id="asset",
        source_id="source",
        title="Protected document",
        kind="document",
        source_version_id="v1",
        extraction_id="extraction",
        source_part_id="part",
        source_part_sha256="a" * 64,
        page_basis="recorded_loader",
        used_revision="source-part-sha256:" + "a" * 64,
        current_revision="source-part-sha256:" + "a" * 64,
        quote="A protected quotation.",
        availability="available",
    )

    class Resolver:
        async def resolve(self, *args):
            return (source,)

    context.container.register_instance(SourceResolverPort, Resolver())
    data = {
        "hits": [
            {
                "id": "part",
                "asset_id": "asset",
                "source_id": "source",
                "title": source.title,
                "text": source.quote,
            }
        ]
    }
    await queue.evidence(
        run.id, "native-worker", "search", data, ["asset"], capture=CapturedEvidence(data, (source,), True)
    )
    await seal_first_quote(context, run, "native-worker")
    await queue.finish(run.id, "native-worker")
    if create_local:
        from test_snapshots import final_turn

        await final_turn(service, context, subject="owner", generation=True)
    service.source_reader = evidence.source_reader
    from koinon.assistants.memory.egress import MemoryEgress
    from koinon.assistants.memory.service import PersonalConversationMemory

    context.get_bean(PersonalConversationMemory).source_reader = evidence.source_reader
    context.get_bean(MemoryEgress).source_reader = evidence.source_reader
    async with sessions.begin() as session:
        session.add(
            PersonalSourceConnection(
                id="reader-connection",
                tenant_id="north",
                owner="reader",
                provider="google_drive",
                status="connected",
                external_subject="remote-reader",
                issuer="https://accounts.google.com",
                config_fingerprint="f" * 64,
                scopes=["https://www.googleapis.com/auth/drive.readonly"],
            )
        )
    await reader.selections.replace(
        "reader",
        "north",
        ReaderSelectionInput(
            expected_revision=0,
            operation_id=uuid4(),
            connections=[{"provider": "google_drive", "connection_id": "reader-connection"}],
        ),
    )
    native = context.get_bean(ConversationSnapshots)
    snapshot = await native.snapshot("owner", "north", thread["id"], [run.message_id])
    return service, native, snapshot, reader, remote, sessions, context


async def test_native_recipient_uses_own_connection_and_preserves_stored_owner(pg_assistants, monkeypatch):
    from time import perf_counter

    _, native, snapshot, _, remote, sessions, _ = await native_imported_output(pg_assistants, monkeypatch)
    # Current remote authority belongs to the reader, even if the provider would deny
    # a new owner read. Locally disabling the import itself invalidates its provenance.
    original = remote.check

    async def recipient_only(actor, *args):
        if actor == "owner":
            raise SourceError("access_denied")
        return await original(actor, *args)

    monkeypatch.setattr(remote, "check", recipient_only)
    remote.calls.clear()
    started = perf_counter()
    await native.authorize_output(
        "owner",
        "north",
        snapshot.thread_id,
        [m.id for m in snapshot.messages],
        snapshot=snapshot,
        reader_subject="reader",
    )
    assert remote.calls and all(call == ("reader", "north", "reader-connection") for call in remote.calls)
    print(
        f"Native reader output: {perf_counter() - started:.3f}s; "
        f"provider checks={len(remote.calls)}; model requests=0"
    )
    with pytest.raises((AccessDenied, SourceError)):
        await native.authorize_output(
            "reader", "north", snapshot.thread_id, [m.id for m in snapshot.messages], snapshot=snapshot
        )
    with pytest.raises((AccessDenied, SourceError)):
        await native.authorize_output(
            "owner",
            "south",
            snapshot.thread_id,
            [m.id for m in snapshot.messages],
            snapshot=snapshot,
            reader_subject="reader",
        )


async def test_shared_native_answer_rechecks_recipient_before_review_hydration(pg_assistants, monkeypatch):
    from datetime import UTC, datetime, timedelta

    from koinon.evidence.entities import EvidenceReview
    from koinon.evidence.reviews import EvidenceReviews, digest
    from koinon.sharing.entities import ConversationShare
    from koinon.sharing.service import ConversationShares

    _, native, snapshot, reader, remote, sessions, context = await native_imported_output(
        pg_assistants, monkeypatch
    )
    shares = context.get_bean(ConversationShares)
    reviews = context.get_bean(EvidenceReviews)
    reviews.source_reader = SimpleNamespace(get=lambda: reader)
    assert reviews.outputs.get() is native
    now = datetime.now(UTC)
    request = {"thread_id": snapshot.thread_id, "message_ids": [m.id for m in snapshot.messages]}
    payload = snapshot.model_dump(mode="json")
    async with sessions.begin() as session:
        session.add(
            EvidenceReview(
                id="native-shared-review",
                tenant_id="north",
                owner_subject="owner",
                kind="share",
                title=snapshot.title,
                revision=digest({"request": request, "snapshot": payload}),
                request_json=request,
                snapshot_json=payload,
                manifest_json=[source.model_dump(mode="json") for source in snapshot.sources],
                created_at=now,
                expires_at=now + timedelta(days=1),
            )
        )
        await session.flush()
        session.add(
            ConversationShare(
                id="native-share",
                tenant_id="north",
                owner_subject="owner",
                review_id="native-shared-review",
                created_at=now,
                expires_at=now + timedelta(days=1),
            )
        )
    remote.calls.clear()
    opened = await shares.read("reader", "north", "native-share")
    assert [message.text for message in opened.messages] == [message.text for message in snapshot.messages]
    assert any(message.text for message in opened.messages if message.role == "assistant")
    assert remote.calls and set(remote.calls) == {("reader", "north", "reader-connection")}

    async with sessions.begin() as session:
        await session.execute(
            update(PersonalSourceConnection)
            .where(PersonalSourceConnection.id == "reader-connection")
            .values(status="disconnected", revision=2)
        )
    statements = []
    engine = context.get_bean(DataSourceRegistry).primary.engine.sync_engine

    def observe(connection, cursor, statement, parameters, context, many):
        statements.append(statement)

    event.listen(engine, "before_cursor_execute", observe)
    try:
        with pytest.raises(SourceError):
            await shares.read("reader", "north", "native-share")
    finally:
        event.remove(engine, "before_cursor_execute", observe)
    assert statements
    assert not any("koinon_evidence_reviews.title" in statement for statement in statements)


@pytest.mark.parametrize("change", ["remote", "connection", "version", "borrowed", "missing_reader"])
async def test_native_recipient_denial_precedes_history_body(pg_assistants, monkeypatch, change):
    _, native, snapshot, reader, remote, sessions, context = await native_imported_output(
        pg_assistants, monkeypatch
    )
    if change == "missing_reader":
        native.assistants.source_reader = None
    elif change == "remote":

        async def deny(*args):
            raise SourceError("access_denied")

        monkeypatch.setattr(remote, "check", deny)
    elif change == "borrowed":
        with (
            reader_source_scope(
                "reader", "north", [{"provider": "google_drive", "connection_id": "connection"}]
            ),
            pytest.raises(SourceError),
        ):
            await native.authorize_output(
                "owner",
                "north",
                snapshot.thread_id,
                [m.id for m in snapshot.messages],
                snapshot=snapshot,
                reader_subject="reader",
            )
        return
    else:
        async with sessions.begin() as session:
            if change == "connection":
                await session.execute(
                    update(PersonalSourceConnection)
                    .where(PersonalSourceConnection.id == "reader-connection")
                    .values(status="disconnected", revision=2)
                )
            else:
                await session.execute(update(SourceImportedVersion).values(native_version_id="v2"))
    queries = []
    engine = context.get_bean(DataSourceRegistry).primary.engine.sync_engine

    def observe(connection, cursor, statement, parameters, context, many):
        queries.append(statement)

    event.listen(engine, "before_cursor_execute", observe)
    try:
        with pytest.raises((SourceError, AccessDenied)):
            await native.authorize_output(
                "owner",
                "north",
                snapshot.thread_id,
                [m.id for m in snapshot.messages],
                snapshot=snapshot,
                reader_subject="reader",
            )
    finally:
        event.remove(engine, "before_cursor_execute", observe)
    assert not any(
        "SELECT koinon_chat_messages.id, koinon_chat_messages.thread_id" in query for query in queries
    )


async def test_legacy_lists_filter_imports_before_search_and_folder_counts(pg_assistants, monkeypatch):
    from koinon.assistants.history.service import ChatHistoryService

    service, _, snapshot, _, _, _, context = await native_imported_output(pg_assistants, monkeypatch)
    history = context.get_bean(ChatHistoryService)
    folder = await history.create_folder("owner", "north", {"name": "Personal"})
    await history.patch_thread(
        "owner", "north", snapshot.thread_id, {"expected_revision": 1, "folder_id": folder["id"]}
    )
    local = await history.create_thread("owner", "north", {"title": "Local", "folder_id": folder["id"]})
    page = await history.thread_page("owner", "north", folder_id=folder["id"])
    assert page["total"] == 1 and [row["id"] for row in page["items"]] == [local["id"]]
    assert (await history.get_folder("owner", "north", folder["id"]))["conversation_count"] == 1
    assert (await history.thread_page("owner", "north", q=snapshot.title))["total"] == 0


async def test_large_conversation_pages_do_not_capture_unrequested_history(pg_assistants):
    from datetime import UTC, datetime, timedelta

    from koinon.assistants.entities import ChatMessage

    service, context, sessions = pg_assistants
    thread = await service.create_thread("issuer|admin", "north", {"title": "Long conversation"})
    now = datetime.now(UTC)
    async with sessions.begin() as session:
        session.add_all(
            ChatMessage(
                id=f"message-{index:05}",
                thread_id=thread["id"],
                role="user",
                text=f"Question {index}",
                created_at=now + timedelta(seconds=index),
            )
            for index in range(2105)
        )
    first = await service.message_page("issuer|admin", "north", thread["id"], limit=100)
    second = await service.message_page(
        "issuer|admin", "north", thread["id"], limit=100, before=first["next_cursor"]
    )
    assert len(first["items"]) == len(second["items"]) == 100
    assert {row["id"] for row in first["items"]}.isdisjoint(row["id"] for row in second["items"])
    assert first["items"][-1]["text"] == "Question 2104"
    assert second["items"][-1]["text"] == "Question 2004"
    from koinon.assistants.history.browse_dtos import MessageBrowseInput
    from koinon.assistants.history.service import ChatHistoryService

    history = context.get_bean(ChatHistoryService)
    cache = await source_fixture.shared_cursor_store(history, context)
    try:
        opaque = await history.browse_messages(
            "issuer|admin", "north", thread["id"], MessageBrowseInput(page_size=100)
        )
        following = await history.browse_messages(
            "issuer|admin",
            "north",
            thread["id"],
            MessageBrowseInput(page_size=100, cursor=opaque.next_cursor),
        )
        assert opaque.total is None and following.total_is_exact is False
        assert len(opaque.next_cursor) == 43
        assert [row["id"] for row in following.items] == [row["id"] for row in second["items"]]
    finally:
        await cache.stop()


async def test_new_result_between_admission_and_hydration_is_denied(pg_assistants, monkeypatch):
    from koinon.assistants.entities import ToolResult

    service, native, snapshot, reader, _, sessions, _ = await native_imported_output(
        pg_assistants, monkeypatch
    )
    original = reader.runs
    injected = False

    async def changed(*args, **kwargs):
        nonlocal injected
        operation = await original(*args, **kwargs)
        if not injected:
            injected = True
            async with sessions.begin() as session:
                session.add(
                    ToolResult(
                        id="unadmitted",
                        run_id=args[2][0],
                        kind="search",
                        payload={"source_manifest": {"complete": False}},
                    )
                )
        return operation

    monkeypatch.setattr(reader, "runs", changed)
    with pytest.raises(AccessDenied):
        await service.message_page("owner", "north", snapshot.thread_id)


async def test_metadata_preserves_safe_titles_without_releasing_unknown_ai_title(pg_assistants, monkeypatch):
    from koinon.assistants.entities import ChatThread
    from koinon.assistants.history.service import ChatHistoryService

    service, _, snapshot, _, _, sessions, context = await native_imported_output(pg_assistants, monkeypatch)
    history = context.get_bean(ChatHistoryService)
    async with sessions.begin() as session:
        await session.execute(
            update(ChatThread)
            .where(ChatThread.id == snapshot.thread_id)
            .values(title="Protected old generated title", title_source="ai")
        )
    assert (await history.get_thread("owner", "north", snapshot.thread_id))["title"] == "Conversation"
    async with sessions.begin() as session:
        await session.execute(
            update(ChatThread)
            .where(ChatThread.id == snapshot.thread_id)
            .values(title="My own title", title_source="manual")
        )
    assert (await history.get_thread("owner", "north", snapshot.thread_id))["title"] == "My own title"


async def test_history_cursor_is_bound_to_actor_filters_and_saved_selection(pg_assistants, monkeypatch):
    from pyfly.kernel import InvalidRequestException

    from koinon.assistants.history.browse_dtos import HistoryBrowseInput
    from koinon.assistants.history.service import ChatHistoryService

    service, _, snapshot, reader, _, _, context = await native_imported_output(pg_assistants, monkeypatch)
    history = context.get_bean(ChatHistoryService)
    await service.create_thread("owner", "north", {"title": "Second"})
    cache = await source_fixture.shared_cursor_store(history, context)
    try:
        page = await history.browse("owner", "north", HistoryBrowseInput(page_size=1))
        assert page.total is None and page.total_is_exact is False and page.next_cursor
        assert len(page.items) == 1
        for actor, tenant, changes in (
            ("reader", "north", {}),
            ("owner", "south", {}),
            ("owner", "north", {"q": "changed"}),
            ("owner", "north", {"reader_source_connections": []}),
        ):
            with pytest.raises((InvalidRequestException, SourceError, AccessDenied)):
                await history.browse(
                    actor, tenant, HistoryBrowseInput(page_size=1, cursor=page.next_cursor, **changes)
                )
        await reader.selections.replace(
            "owner", "north", ReaderSelectionInput(expected_revision=1, operation_id=uuid4(), connections=[])
        )
        with pytest.raises(InvalidRequestException):
            await history.browse("owner", "north", HistoryBrowseInput(page_size=1, cursor=page.next_cursor))
    finally:
        await cache.stop()


async def test_final_reader_revocation_discards_already_validated_output(pg_assistants, monkeypatch):
    _, native, snapshot, _, _, sessions, _ = await native_imported_output(pg_assistants, monkeypatch)
    original = native._authorize_output_owner

    async def changed(*args, **kwargs):
        await original(*args, **kwargs)
        async with sessions.begin() as session:
            await session.execute(
                update(PersonalSourceConnection)
                .where(PersonalSourceConnection.id == "reader-connection")
                .values(status="disconnected", revision=2)
            )

    monkeypatch.setattr(native, "_authorize_output_owner", changed)
    with pytest.raises(SourceError):
        await native.authorize_output(
            "owner",
            "north",
            snapshot.thread_id,
            [row.id for row in snapshot.messages],
            snapshot=snapshot,
            reader_subject="reader",
        )


async def test_history_capture_cannot_be_inherited_by_another_task(pg_assistants):
    import asyncio

    from koinon.assistants.source_reads import history_read

    service, _, _ = pg_assistants
    thread = await service.create_thread("issuer|admin", "north", {})
    async with history_read(
        service, "issuer|admin", "north", thread_id=thread["id"], selection={"run_ids": ()}
    ):
        with pytest.raises(AccessDenied):
            await asyncio.create_task(service.message_page("issuer|admin", "north", thread["id"]))


@pytest.mark.parametrize("failure", ["exception", "cancellation"])
async def test_title_model_boundary_restores_parent_capture_on_failure(pg_assistants, failure):
    import asyncio

    from koinon.assistants.source_reads import _title_model_boundary, has_history_capture, history_read

    service, _, _ = pg_assistants
    thread = await service.create_thread("issuer|admin", "north", {})
    async with history_read(
        service,
        "issuer|admin",
        "north",
        thread_id=thread["id"],
        selection={"run_ids": (), "user_prompt_only": True},
    ):
        error = asyncio.CancelledError if failure == "cancellation" else RuntimeError
        with pytest.raises(error):
            async with _title_model_boundary():
                assert not has_history_capture()
                raise error("Controlled interruption")
        assert has_history_capture()
        assert (await service.thread("issuer|admin", "north", thread["id"])).id == thread["id"]
    assert not has_history_capture()


@pytest.mark.parametrize("misuse", ["child", "inactive", "transaction", "hydration", "other_read"])
async def test_title_model_boundary_rejects_nonparent_or_active_unit(pg_assistants, misuse):
    import asyncio
    from contextvars import copy_context

    from koinon.assistants.source_reads import _title_model_boundary, history_read
    from koinon.security.authority import primary_authority

    service, _, _ = pg_assistants
    thread = await service.create_thread("issuer|admin", "north", {})
    reached = []

    async def invoke():
        async with _title_model_boundary():
            reached.append(True)

    async with history_read(
        service,
        "issuer|admin",
        "north",
        thread_id=thread["id"],
        selection={"run_ids": (), "user_prompt_only": misuse != "other_read"},
    ) as capture:
        saved = copy_context()
        if misuse == "other_read":
            with pytest.raises(AccessDenied):
                await invoke()
        elif misuse == "child":
            with pytest.raises(AccessDenied):
                await asyncio.create_task(invoke())
        elif misuse == "transaction":
            async with primary_authority(fresh=True):
                with pytest.raises(AccessDenied):
                    await invoke()
        elif misuse == "hydration":
            capture.hydration_unit = object()
            try:
                with pytest.raises(AccessDenied):
                    await invoke()
            finally:
                capture.hydration_unit = None
    if misuse == "inactive":
        with pytest.raises(AccessDenied):
            await asyncio.create_task(invoke(), context=saved)
    assert reached == []
