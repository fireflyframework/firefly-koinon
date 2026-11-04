# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Real Canon22 and primary44 fences span the actual settings transaction commit."""

import asyncio
from contextvars import Context
from types import SimpleNamespace
from uuid import uuid4

import psycopg
import pytest
from flycanon.config import CanonSettings
from flycanon.models.repositories.source_repository import SourceRepository
from flyquery.config import FlyquerySettings
from pyfly.data.relational.datasource_registry import DataSourceRegistry
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from test_native_readiness_postgres import connect

from koinon.catalog.service import CatalogService
from koinon.jobs.repository import JobRepository
from koinon.jobs.service import JobService
from koinon.knowledge.indexes.repositories import KnowledgeIndexRepository
from koinon.organization_knowledge.dtos import OrganizationKnowledgeSettingsInput
from koinon.organization_knowledge.repositories import OrganizationKnowledgeRepository
from koinon.organization_knowledge.service import OrganizationKnowledgeService
from koinon.organization_knowledge.transitions.activation import ModeActivation
from koinon.organization_knowledge.transitions.generations import ModeGenerationRepository
from koinon.organization_knowledge.transitions.queue import ModeTransitionQueue
from koinon.organization_knowledge.transitions.readiness_fence import ModeReadinessFence
from koinon.organization_knowledge.transitions.repositories import (
    ModeTargetRepository,
    ModeTransitionRepository,
)
from koinon.organization_knowledge.transitions.service import KnowledgeModeTransitions

pytest_plugins = ("test_index_publication_postgres", "test_native_readiness_postgres")
pytestmark = pytest.mark.integration


async def wait_lock(uri, application):
    async with await psycopg.AsyncConnection.connect(uri, autocommit=True) as connection:
        async with asyncio.timeout(5):
            while True:
                result = await connection.execute(
                    "SELECT wait_event_type FROM pg_stat_activity WHERE application_name=%s", (application,)
                )
                if await result.fetchone() == ("Lock",):
                    return
                await asyncio.sleep(0.01)


async def test_canon_writer_remains_fenced_while_primary_commit_is_blocked(
    pg_indexes, readiness_db, record_property
):
    tenant, actor = "tenant", "issuer|actor"
    settings = OrganizationKnowledgeService(
        pg_indexes.get_bean(CatalogService),
        OrganizationKnowledgeRepository(),
        SimpleNamespace(get=lambda: CanonSettings(answer_mode="rag")),
        SimpleNamespace(get=FlyquerySettings),
    )
    service = KnowledgeModeTransitions(
        settings,
        ModeTransitionRepository(),
        JobService(JobRepository()),
        ModeTargetRepository(),
        KnowledgeIndexRepository(),
    )
    before = await settings.get(actor, tenant)
    values = OrganizationKnowledgeSettingsInput(
        expected_revision=before.revision,
        documents=before.documents.model_copy(update={"answer_mode": "rlm"}),
        structured=before.structured,
    )
    request = await service.request(actor, tenant, values, "actual-commit-fence")
    queue = ModeTransitionQueue(service)
    assert await queue.claim("worker") == request.id
    native_url, native_role = readiness_db
    with connect(readiness_db, tenant) as connection:
        connection.execute(
            "INSERT INTO canon_workspaces(id,tenant_id,name) VALUES('workspace',%s,'Controlled')", (tenant,)
        )
    native_engine = create_async_engine(
        native_url.set(drivername="postgresql+asyncpg", username=native_role, password=None),
        pool_size=1,
        max_overflow=0,
    )
    sources = SourceRepository(async_sessionmaker(native_engine))
    fence = ModeReadinessFence(ModeGenerationRepository(), SimpleNamespace(_resolve=lambda _type: sources))
    snapshot = await fence.snapshot(tenant)
    row = await service.records.find_by_id(request.id)
    row.stage = "activate"
    row.cursor = {
        "verified_generations": snapshot.encode(),
        "verification": {"phase": "settle", "watermark": snapshot.encode()},
    }
    await service.records.save(row)
    primary = pg_indexes.get_bean(DataSourceRegistry).primary
    primary_uri = primary.engine.url.set(drivername="postgresql").render_as_string(hide_password=False)
    native_uri = native_url.set(
        drivername="postgresql", username=native_role, password=None
    ).render_as_string(hide_password=False)
    commit_app, writer_app = "mode-commit-" + uuid4().hex, "mode-native-" + uuid4().hex
    advisory = int(uuid4().hex[:12], 16)
    with psycopg.connect(primary_uri) as owner:
        owner.execute(
            "CREATE FUNCTION controlled_mode_commit() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN "
            f"PERFORM set_config('application_name','{commit_app}',true); "
            f"PERFORM pg_advisory_xact_lock({advisory}); RETURN NULL; END $$"
        )
        owner.execute(
            "CREATE CONSTRAINT TRIGGER controlled_mode_commit AFTER INSERT "
            "ON koinon_organization_knowledge_settings DEFERRABLE INITIALLY DEFERRED "
            "FOR EACH ROW EXECUTE FUNCTION controlled_mode_commit()"
        )
    blocker = await psycopg.AsyncConnection.connect(primary_uri, autocommit=True)
    await blocker.execute("SELECT pg_advisory_lock(%s)", (advisory,))
    activation, writer = None, None

    async def mutate():
        async with await psycopg.AsyncConnection.connect(
            native_uri, application_name=writer_app
        ) as connection:
            await connection.execute("SELECT set_config('app.tenant_id',%s,true)", (tenant,))
            await connection.execute(
                "UPDATE canon_workspaces SET name='Controlled change' WHERE tenant_id=%s AND id='workspace'",
                (tenant,),
            )
        async with await psycopg.AsyncConnection.connect(primary_uri, autocommit=True) as connection:
            result = await connection.execute(
                "SELECT documents->>'answer_mode' FROM koinon_organization_knowledge_settings "
                "WHERE tenant_id=%s",
                (tenant,),
            )
            assert await result.fetchone() == ("rlm",)

    try:
        activation = asyncio.create_task(ModeActivation(queue, fence).activate(tenant, request.id, "worker"))
        await wait_lock(primary_uri, commit_app)
        writer = asyncio.create_task(mutate(), context=Context())
        await wait_lock(
            native_url.set(drivername="postgresql").render_as_string(hide_password=False), writer_app
        )
        assert not activation.done() and not writer.done()
        await blocker.execute("SELECT pg_advisory_unlock(%s)", (advisory,))
        await asyncio.wait_for(activation, 5)
        await asyncio.wait_for(writer, 5)
        assert (await settings.get(actor, tenant)).documents.answer_mode == "rlm"
        assert (await service.get(actor, tenant, request.id)).status == "succeeded"
        assert (await service.current(actor, tenant)).id == request.id
        assert (await service.target_page(actor, tenant, request.id)).items == []
        record_property("canon_fence_held_during_primary_commit", True)
        record_property("native_datasource_distinct_from_primary", True)
    finally:
        await blocker.execute("SELECT pg_advisory_unlock(%s)", (advisory,))
        await blocker.close()
        for task in (activation, writer):
            if task is not None and not task.done():
                task.cancel()
        await asyncio.gather(
            *(task for task in (activation, writer) if task is not None), return_exceptions=True
        )
        await native_engine.dispose()


async def test_new_request_waits_for_cancel_commit_and_keeps_pending_index_visible(pg_indexes):
    from pyfly.kernel import ConflictException
    from test_index_persistence import record

    tenant, actor = "tenant", "issuer|actor"
    settings = OrganizationKnowledgeService(
        pg_indexes.get_bean(CatalogService),
        OrganizationKnowledgeRepository(),
        SimpleNamespace(get=lambda: CanonSettings(answer_mode="rag")),
        SimpleNamespace(get=FlyquerySettings),
    )
    service = KnowledgeModeTransitions(
        settings,
        ModeTransitionRepository(),
        JobService(JobRepository()),
        ModeTargetRepository(),
        KnowledgeIndexRepository(),
    )
    before = await settings.get(actor, tenant)
    values = OrganizationKnowledgeSettingsInput(
        expected_revision=before.revision,
        documents=before.documents.model_copy(update={"answer_mode": "rlm"}),
        structured=before.structured,
    )
    previous = await service.request(actor, tenant, values, "previous-mode")
    index = record("pending-index")
    index.status = "activating"
    index.transition = {"parent_mode_transition_id": previous.id}
    await service.indexes.save(index)
    uri = (
        pg_indexes.get_bean(DataSourceRegistry)
        .primary.engine.url.set(drivername="postgresql")
        .render_as_string(hide_password=False)
    )
    pending = None
    try:
        async with await psycopg.AsyncConnection.connect(uri) as cancellation:
            await cancellation.execute("SELECT id FROM lattice_tenants WHERE id='tenant' FOR UPDATE")
            await cancellation.execute(
                "UPDATE koinon_knowledge_mode_transitions "
                "SET status='cancelled',active_slot=NULL WHERE id=%s",
                (previous.id,),
            )
            blocker = (await (await cancellation.execute("SELECT pg_backend_pid()")).fetchone())[0]
            pending = asyncio.create_task(
                service.request(actor, tenant, values, "next-mode"), context=Context()
            )
            async with await psycopg.AsyncConnection.connect(uri, autocommit=True) as inspection:
                async with asyncio.timeout(5):
                    while not (
                        await (
                            await inspection.execute(
                                "SELECT EXISTS(SELECT 1 FROM pg_stat_activity "
                                "WHERE %s=ANY(pg_blocking_pids(pid)))",
                                (blocker,),
                            )
                        ).fetchone()
                    )[0]:
                        await asyncio.sleep(0.01)
            assert not pending.done()
            await cancellation.commit()
        with pytest.raises(ConflictException) as error:
            await asyncio.wait_for(pending, 5)
        assert error.value.code == "MODE_INDEX_RECOVERY_REQUIRED"
        current = await service.current(actor, tenant)
        assert current.id == previous.id and current.status == "cancelled"
        assert current.pending_index_recoveries == 1 and current.active_mode == "rag"
    finally:
        if pending is not None and not pending.done():
            pending.cancel()
        if pending is not None:
            await asyncio.gather(pending, return_exceptions=True)
