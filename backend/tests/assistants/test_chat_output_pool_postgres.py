# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Fresh output checks must not wait on an enclosing navigation read connection."""

import asyncio
import base64
import re
from datetime import timedelta
from hashlib import sha256
from unittest.mock import AsyncMock

import pytest
from pyfly.container.scanner import scan_package
from pyfly.data.relational.datasource_registry import DataSourceRegistry
from pyfly.data.transaction import Propagation, TransactionTemplate, current_unit_of_work
from pyfly.security.context import SecurityContext
from pyfly.security.context_holder import SecurityContextHolder
from release_helpers import seal_first_quote
from sqlalchemy import event, text, update
from test_memory_authority_postgres import pg_assistants as pg_assistants
from test_service import configured

from koinon.assistants.audit import AnswerAudits
from koinon.assistants.lifecycle import timestamp
from koinon.assistants.memory.egress import MemoryEgress
from koinon.assistants.memory.service import PersonalConversationMemory
from koinon.assistants.queue import AssistantQueue
from koinon.assistants.scope import KnowledgeScopePolicy
from koinon.assistants.snapshots import ConversationSnapshots
from koinon.catalog.entities import Membership
from koinon.catalog.errors import AccessDenied
from koinon.catalog.service import ROLE_PERMISSIONS
from koinon.evidence.dtos import SourceReference
from koinon.evidence.ports import SourceResolverPort
from koinon.knowledge.capture_dtos import CapturedEvidence
from koinon.security.authority import primary_authority
from koinon.tokens.authorization import TokenRestriction
from koinon.tokens.entities import PersonalToken
from koinon.tokens.repositories import PersonalTokenRepository

pytestmark = pytest.mark.integration
POOLS = [1, 5]


async def released(pg_assistants):
    service, context, _ = pg_assistants
    _, agent = await configured(service)
    entry = None
    for kind in ("workspace", "project", "collection", "source", "document"):
        entry = await service.catalog.create(
            "issuer|admin", "north", kind=kind, name=kind, parent_id=entry.id if entry else None
        )
    scan_package("koinon.tokens", context.container)
    service.catalog.restriction = context.get_bean(TokenRestriction)
    await context.get_bean(PersonalTokenRepository).save(
        PersonalToken(
            id="output-origin",
            subject="issuer|admin",
            tenant_id="north",
            name="Controlled origin",
            token_hash="0" * 64,
            prefix="fixture",
            scopes=sorted(ROLE_PERMISSIONS["admin"]),
            expires_at=timestamp() + timedelta(hours=1),
        )
    )
    with SecurityContextHolder.using(
        SecurityContext(
            user_id="admin", attributes={"iss": "issuer", "sub": "admin", "koinon_token_id": "output-origin"}
        )
    ):
        thread = await service.create_thread("issuer|admin", "north", {"scope": {"asset_ids": [entry.id]}})
        await service.submit(
            "issuer|admin",
            "north",
            thread["id"],
            {
                "agent_id": agent["id"],
                "message": "A fixed synthetic question",
                "client_request_id": "output-pool",
            },
        )
    queue = context.get_bean(AssistantQueue)
    run = await queue.claim("output-worker")
    assert run.access_token_id == "output-origin"
    source = SourceReference(
        id="fixed-source",
        asset_id=entry.id,
        source_id=entry.parent_id,
        title=entry.name,
        kind="document",
        chunk_id="fixed-chunk",
        quote="A fixed native quotation.",
        used_revision="chunk-sha256:" + sha256(b"A fixed native quotation.").hexdigest(),
        current_revision="chunk-sha256:" + sha256(b"A fixed native quotation.").hexdigest(),
        availability="available",
    )
    resolver = type("ControlledSources", (), {})()
    resolver.resolve = AsyncMock(return_value=(source,))
    context.container.register_instance(SourceResolverPort, resolver)
    data = {
        "hits": [
            {
                "id": "fixed-chunk",
                "asset_id": entry.id,
                "source_id": entry.parent_id,
                "title": entry.name,
                "text": source.quote,
            }
        ]
    }
    await queue.evidence(
        run.id, "output-worker", "search", data, [entry.id], capture=CapturedEvidence(data, (source,), True)
    )
    await seal_first_quote(context, run, "output-worker")
    await queue.finish(run.id, "output-worker")
    run = await service.runs.find_by_id(run.id)
    memory = context.get_bean(PersonalConversationMemory)
    generation = await memory.repository.generation(run.id)
    assert await memory.repository.for_generation(generation.id) is not None
    return service, context, run


@pytest.fixture
async def pg_outputs(pg_assistants, request):
    from flycanon.config import CanonSettings
    from flyquery.config import FlyquerySettings
    from pyfly.context import ApplicationContext
    from pyfly.core import Config

    service, writer, run = await released(pg_assistants)
    database = writer.get_bean(DataSourceRegistry).primary.engine.url
    options = request.param if isinstance(request.param, dict) else {"size": request.param}
    replica = (
        {"read-replica": {"url": str(database.set(database="postgres"))}} if options.get("replica") else {}
    )
    reader = ApplicationContext(
        Config(
            {
                "pyfly": {
                    "banner": {"mode": "off"},
                    "scheduling": {"enabled": False},
                    "agentic": {"enabled": True},
                    "eda": {"provider": "memory"},
                    "data": {
                        "relational": {
                            "enabled": True,
                            "ddl-auto": "none",
                            "url": str(database),
                            "pool": {"size": options["size"], "max-overflow": 0, "timeout": 2},
                            **replica,
                        }
                    },
                },
                "koinon": {
                    "assistants": {
                        "master_key": base64.urlsafe_b64encode(b"k" * 32).decode(),
                        "allowed_provider_hosts": ["127.0.0.1", "models.example.test"],
                    }
                },
            }
        )
    )
    reader.container.register_instance(CanonSettings, CanonSettings(answer_mode="rag"))
    reader.container.register_instance(FlyquerySettings, FlyquerySettings())
    reader.container.register_instance(SourceResolverPort, writer.get_bean(SourceResolverPort))
    for package in (
        "koinon.catalog",
        "koinon.organization_knowledge",
        "koinon.organization_branding",
        "koinon.assistants",
        "koinon.tokens",
    ):
        scan_package(package, reader.container)
    await reader.start()
    try:
        from koinon.assistants.service import AssistantService

        current = reader.get_bean(AssistantService)
        assert current.catalog.restriction is not None
        yield current, reader, run
    finally:
        await reader.stop()


def reads(service, context, run):
    snapshots = context.get_bean(ConversationSnapshots)
    return {
        "activity": lambda: service.activity_page("issuer|admin", "north", run.id),
        "threads": lambda: service.thread_page("issuer|admin", "north"),
        "audit": lambda: context.get_bean(AnswerAudits).get("issuer|admin", "north", run.id),
        "snapshot": lambda: snapshots.snapshot("issuer|admin", "north", run.thread_id, [run.message_id]),
        "output": lambda: snapshots.authorize_output(
            "issuer|admin", "north", run.thread_id, [run.message_id]
        ),
    }


@pytest.mark.parametrize("pg_outputs", [1], indirect=True)
async def test_audit_validates_memory_once_at_the_final_output_boundary(pg_outputs, monkeypatch):
    service, context, run = pg_outputs
    memory = context.get_bean(PersonalConversationMemory)
    authorize = AsyncMock(wraps=memory.authorize)
    monkeypatch.setattr(memory, "authorize", authorize)
    result = await reads(service, context, run)["audit"]()
    assert result["output_release"] is not None
    assert authorize.await_count == 1
    assert authorize.await_args.kwargs["captures"][0].run_id == run.id


@pytest.mark.parametrize("pg_outputs", [1], indirect=True)
async def test_audit_origin_checks_share_one_bounded_policy_snapshot(pg_outputs):
    _, context, run = pg_outputs
    engine = context.get_bean(DataSourceRegistry).primary.engine.sync_engine
    statements = []

    def capture(connection, cursor, statement, parameters, execution, many):
        statements.append(statement)

    event.listen(engine, "before_cursor_execute", capture)
    try:
        await context.get_bean(AnswerAudits).origin("issuer|admin", "north", run, run.access_token_id)
    finally:
        event.remove(engine, "before_cursor_execute", capture)
    assert len(statements) <= 12, f"Origin check issued {len(statements)} SQL statements"
    assert engine.pool.checkedout() == 0


@pytest.mark.parametrize("pg_outputs", POOLS, indirect=True)
async def test_sealed_memory_output_reads_complete_at_pool_capacity(pg_outputs, monkeypatch):
    service, context, run = pg_outputs
    pool = context.get_bean(DataSourceRegistry).primary.engine.pool
    policy = context.get_bean(KnowledgeScopePolicy)
    validate = policy.validate_scope
    entered, barrier = set(), asyncio.Barrier(pool.size())

    async def synchronized(*args, **kwargs):
        task = asyncio.current_task()
        if task not in entered:
            entered.add(task)
            await asyncio.wait_for(barrier.wait(), timeout=5)
        return await validate(*args, **kwargs)

    monkeypatch.setattr(policy, "validate_scope", synchronized)
    holders = {}
    acquire = pool._do_get

    def checked_out(connection, record, proxy):
        holders[record] = asyncio.current_task()

    def checked_in(connection, record):
        holders.pop(record, None)

    def independent_acquire():
        assert asyncio.current_task() not in holders.values(), (
            "Output authorization requested another connection while retaining its current one"
        )
        return acquire()

    # Detect recursive checkout directly rather than inferring it from a short timing window.
    monkeypatch.setattr(pool, "_do_get", independent_acquire)
    event.listen(pool, "checkout", checked_out)
    event.listen(pool, "checkin", checked_in)
    try:
        async with asyncio.timeout(15):
            values = await asyncio.gather(
                *(call() for call in reads(service, context, run).values()), return_exceptions=True
            )
    finally:
        event.remove(pool, "checkout", checked_out)
        event.remove(pool, "checkin", checked_in)
    assert not [value for value in values if isinstance(value, BaseException)], values
    assert values[2]["memory"] is not None and values[2]["output_release"] is not None
    assert values[3].messages[0].role == "assistant" and values[3].memory_bindings
    assert pool.checkedout() == 0


@pytest.mark.parametrize("pg_outputs", [5], indirect=True)
async def test_fresh_output_authority_does_not_reuse_observed_credentials(pg_outputs):
    service, context, run = pg_outputs
    restriction = service.catalog.restriction
    assert restriction is not None
    with SecurityContextHolder.using(
        SecurityContext(
            user_id="admin",
            attributes={"iss": "issuer", "sub": "admin", "koinon_token_id": run.access_token_id},
        )
    ):
        async with primary_authority() as outer:
            assert (await restriction.grant("issuer|admin")).id == run.access_token_id
            async with TransactionTemplate(
                "primary", propagation=Propagation.REQUIRES_NEW
            ).transaction() as writer:
                await writer.resource.execute(
                    update(PersonalToken)
                    .where(PersonalToken.id == run.access_token_id)
                    .values(revoked_at=timestamp())
                )
            with pytest.raises(AccessDenied):
                async with primary_authority(fresh=True):
                    await restriction.grant("issuer|admin")
            assert current_unit_of_work("primary") is outer
    assert context.get_bean(DataSourceRegistry).primary.engine.pool.checkedout() == 0


@pytest.mark.parametrize("pg_outputs", [POOLS[0]], indirect=True)
@pytest.mark.parametrize("method", ["audit", "snapshot", "output"])
async def test_final_output_rechecks_membership_after_materialization(pg_outputs, monkeypatch, method):
    service, context, run = pg_outputs
    registry = context.get_bean(DataSourceRegistry)
    changed = False

    async def revoke():
        nonlocal changed
        async with registry.primary.engine.begin() as connection:
            await connection.execute(update(Membership).where(Membership.id == "admin").values(active=False))
        changed = True

    if method == "audit":
        memory = context.get_bean(PersonalConversationMemory)
        original = memory.authorize

        async def final_audit(*args, **kwargs):
            if kwargs.get("captures"):
                await revoke()
            return await original(*args, **kwargs)

        monkeypatch.setattr(memory, "authorize", final_audit)
    elif method == "snapshot":
        egress = context.get_bean(MemoryEgress)
        original = egress.authorize

        async def final_snapshot(*args, **kwargs):
            if kwargs.get("captures"):
                await revoke()
            return await original(*args, **kwargs)

        monkeypatch.setattr(egress, "authorize", final_snapshot)
    else:
        original = service.message_repository.snapshot_messages

        async def selected(*args, **kwargs):
            rows = await original(*args, **kwargs)
            await revoke()
            return rows

        monkeypatch.setattr(service.message_repository, "snapshot_messages", selected)
    with pytest.raises(AccessDenied):
        await reads(service, context, run)[method]()
    assert changed and registry.primary.engine.pool.checkedout() == 0


@pytest.mark.parametrize("pg_outputs", [POOLS[0]], indirect=True)
@pytest.mark.parametrize("method", ["audit", "snapshot", "output"])
async def test_current_owner_cannot_release_an_answer_after_origin_token_revocation(pg_outputs, method):
    service, context, run = pg_outputs
    registry = context.get_bean(DataSourceRegistry)
    async with registry.primary.engine.begin() as connection:
        await connection.execute(
            update(PersonalToken)
            .where(PersonalToken.id == run.access_token_id)
            .values(revoked_at=timestamp())
        )
    with pytest.raises(AccessDenied):
        await reads(service, context, run)[method]()
    assert registry.primary.engine.pool.checkedout() == 0


@pytest.mark.parametrize("pg_outputs", [{"size": 1, "replica": True}], indirect=True)
async def test_output_reads_suspend_replica_and_use_readonly_primary_auto_units(pg_outputs):
    service, context, run = pg_outputs
    source = context.get_bean(DataSourceRegistry).primary
    replica = source.replica
    assert replica is not None
    replica_statements, primary_statements = [], []

    def observed_replica(connection, cursor, statement, parameters, execution_context, executemany):
        replica_statements.append(statement)

    def observed_primary(connection, cursor, statement, parameters, execution_context, executemany):
        primary_statements.append(statement)

    event.listen(replica.engine.sync_engine, "before_cursor_execute", observed_replica)
    event.listen(source.engine.sync_engine, "before_cursor_execute", observed_primary)
    try:
        async with TransactionTemplate("primary", read_only=True).transaction() as caller:
            assert not caller.read_from_primary
            assert await caller.resource.scalar(text("SELECT to_regclass('public.koinon_chat_runs')")) is None
            for call in reads(service, context, run).values():
                await call()
                assert current_unit_of_work("primary") is caller
        assert any("koinon_chat_runs" in statement for statement in primary_statements)
        assert not any(
            re.match(r"\s*(INSERT|UPDATE|DELETE|CREATE|ALTER|DROP|TRUNCATE)\b", statement, re.I)
            for statement in primary_statements
        )
        assert not any(
            "lattice_" in statement or "koinon_" in statement
            for statement in replica_statements
            if statement != "SELECT to_regclass('public.koinon_chat_runs')"
        )
    finally:
        event.remove(replica.engine.sync_engine, "before_cursor_execute", observed_replica)
        event.remove(source.engine.sync_engine, "before_cursor_execute", observed_primary)
    assert source.engine.pool.checkedout() == 0 and replica.engine.pool.checkedout() == 0
