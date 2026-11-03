# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Owned PostgreSQL proves that provider waits release a one-connection primary pool."""

import asyncio
import os
from types import SimpleNamespace
from uuid import uuid4

import psycopg
import pytest
from psycopg import sql
from pyfly.core import PyFlyApplication
from pyfly.data.relational.datasource_registry import DataSourceRegistry
from pyfly.data.transaction import current_unit_of_work
from sqlalchemy.engine import make_url
from test_index_persistence import seed_index_rows
from test_index_provider_transactions import worker_fixture

from koinon.app import KoinonApplication
from koinon.assistants.repositories import ProviderRepository
from koinon.catalog.entities import Membership
from koinon.catalog.repositories import CatalogRepository, MembershipRepository
from koinon.catalog.service import CatalogService
from koinon.knowledge.indexes.repositories import KnowledgeIndexRepository

pytestmark = pytest.mark.integration


@pytest.fixture
async def pg_indexes(tmp_path, record_property):
    uri = os.environ.get("KOINON_MEMORY_AUTHORITY_TEST_PG_URL")
    if not uri:
        pytest.skip("Requires an explicitly owned PostgreSQL fixture")
    url = make_url(uri)
    assert url.host == "127.0.0.1" and url.port != 18783
    suffix = uuid4().hex[:12]
    database, owner = "index_publication_" + suffix, "index_owner_" + suffix
    with psycopg.connect(uri, autocommit=True) as connection:
        connection.execute(
            sql.SQL("CREATE ROLE {} LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS").format(
                sql.Identifier(owner)
            )
        )
        connection.execute(
            sql.SQL("CREATE DATABASE {} OWNER {}").format(sql.Identifier(database), sql.Identifier(owner))
        )
    record_property("owned_database", database)
    record_property("owned_role", owner)
    runtime = url.set(drivername="postgresql+asyncpg", username=owner, password=None, database=database)
    config = tmp_path / "pyfly.yaml"
    config.write_text(
        "pyfly:\n  banner:\n    mode: off\n  agentic:\n    enabled: false\n  data:\n"
        "    relational:\n      enabled: true\n      ddl-auto: create\n"
        "      pool:\n        size: 1\n        max-overflow: 0\n        timeout: 0.5\n"
        f"      url: {runtime.render_as_string(hide_password=False)!r}\n"
        "      datasources:\n        canon:\n          ddl-auto: none\n"
        f"          url: {runtime.render_as_string(hide_password=False)!r}\n"
    )
    app = PyFlyApplication(KoinonApplication, config_path=str(config))
    app.context.register_bean(KnowledgeIndexRepository)
    app.context.register_bean(ProviderRepository)
    await app.startup()
    try:
        await seed_index_rows(app.context)
        await app.context.get_bean(MembershipRepository).save(
            Membership(
                id="actor",
                subject="issuer|actor",
                tenant_id="tenant",
                role="admin",
                active=True,
            )
        )
        yield app.context
    finally:
        await app.shutdown()
    # Retained test database and role support independent inspection.


@pytest.mark.parametrize("change", ["cancel", "membership", "provider"])
async def test_concurrent_change_during_provider_wait_finishes_before_network_and_blocks_publication(
    pg_indexes, change, record_property
):
    context = pg_indexes
    rows = context.get_bean(KnowledgeIndexRepository)
    pool = context.get_bean(DataSourceRegistry).primary.engine.pool
    assert pool.size() == 1
    entered, release = asyncio.Event(), asyncio.Event()

    async def provider(providers):
        assert all(current_unit_of_work(name) is None for name in ("primary", "canon", "structured"))
        assert pool.checkedout() == 0
        entered.set()
        await release.wait()

    worker, job, published = await worker_fixture(rows, provider)
    catalog = context.get_bean(CatalogService)
    worker.lifecycle.reader.facade = SimpleNamespace(catalog=catalog)

    async def authority(subject, tenant, workspace_id, *, write=False):
        await catalog.authorize(subject, tenant, "indexes:manage", workspace_id)
        return await context.get_bean(CatalogRepository).find_by_id(workspace_id)

    worker.lifecycle.reader.authority = authority
    running = asyncio.create_task(worker.execute(job.id))
    try:
        await asyncio.wait_for(entered.wait(), timeout=5)
        if change == "cancel":
            await asyncio.wait_for(worker.queue.jobs.cancel("tenant", job.id), timeout=2)
        elif change == "membership":
            repository = context.get_bean(MembershipRepository)
            member = await repository.find_by_id("actor")
            member.active = False
            await asyncio.wait_for(repository.save(member), timeout=2)
        else:
            repository = context.get_bean(ProviderRepository)
            selected = await repository.find_by_id("provider")
            selected.revision += 1
            await asyncio.wait_for(repository.save(selected), timeout=2)
        assert not running.done()
        release.set()
        with pytest.raises(Exception) as failure:
            await asyncio.wait_for(running, timeout=5)
        assert (
            getattr(failure.value, "code", None)
            == {
                "cancel": "JOB_LEASE_LOST",
                "membership": "ACCESS_DENIED",
                "provider": "INDEX_PROVIDER_CHANGED",
            }[change]
        )
        assert published == [] and pool.checkedout() == 0
        record_property("provider_pool_checked_out", 0)
    finally:
        release.set()
        if not running.done():
            running.cancel()
        await asyncio.gather(running, return_exceptions=True)


@pytest.mark.parametrize("mutation", ["update", "delete", "source_update", "source_delete"])
async def test_native_publication_locks_current_chunk_and_rejects_changed_or_deleted_source(
    pg_indexes, mutation
):
    from contextvars import Context

    from flycanon.models.entities import Base
    from flycanon.models.entities.knowledge_chunk import KnowledgeChunkRow
    from flycanon.models.entities.source import SourceRow
    from flycanon.models.repositories.chunk_repository import ChunkRepository
    from pyfly.data.transaction import infrastructure_unit
    from sqlalchemy import text

    native = pg_indexes.get_bean(DataSourceRegistry).get("canon")
    async with native.engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    async with infrastructure_unit(native) as session:
        assert (
            await session.execute(
                text("SELECT rolsuper,rolbypassrls FROM pg_roles WHERE rolname=current_user")
            )
        ).one() == (False, False)
        session.add(
            SourceRow(
                id="source",
                tenant_id="tenant",
                workspace_id="workspace",
                kind="text",
                status="ingested",
                content_sha256="a" * 64,
            )
        )
        await session.flush()
        session.add(
            KnowledgeChunkRow(
                id="chunk",
                source_id="source",
                tenant_id="tenant",
                workspace_id="workspace",
                content="Original",
                metadata_json={},
            )
        )
    repository = ChunkRepository(native.sessionmaker)
    snapshot = await repository.get_many(["chunk"])
    source_snapshot = await repository.reindex_sources(snapshot, tenant_id="tenant", workspace_id="workspace")
    assert native.engine.pool.checkedout() == 0
    uri = native.engine.url.set(drivername="postgresql").render_as_string(hide_password=False)
    application = "index-publication-race-" + uuid4().hex
    started = asyncio.Event()

    async def change():
        async with await psycopg.AsyncConnection.connect(uri, application_name=application) as connection:
            started.set()
            await connection.execute(
                {
                    "update": "UPDATE canon_chunks SET content='Changed' WHERE id='chunk'",
                    "delete": "DELETE FROM canon_chunks WHERE id='chunk'",
                    "source_update": "UPDATE canon_sources SET content_sha256=repeat('b',64) "
                    "WHERE id='source'",
                    "source_delete": "DELETE FROM canon_sources WHERE id='source'",
                }[mutation]
            )

    running = None
    try:
        async with infrastructure_unit(native):
            assert source_snapshot == await repository.reindex_sources(
                snapshot, tenant_id="tenant", workspace_id="workspace", lock=True
            )
            assert await repository.matches_reindex_batch(
                snapshot, tenant_id="tenant", workspace_id="workspace"
            )
            running = asyncio.create_task(change(), context=Context())
            await asyncio.wait_for(started.wait(), timeout=5)
            async with await psycopg.AsyncConnection.connect(uri, autocommit=True) as inspection:
                async with asyncio.timeout(5):
                    while True:
                        cursor = await inspection.execute(
                            "SELECT wait_event_type FROM pg_stat_activity WHERE application_name=%s",
                            (application,),
                        )
                        row = await cursor.fetchone()
                        if row and row[0] == "Lock":
                            break
                        await asyncio.sleep(0.02)
            assert not running.done()
        await asyncio.wait_for(running, timeout=5)
        async with infrastructure_unit(native):
            if mutation.startswith("source_"):
                assert source_snapshot != await repository.reindex_sources(
                    snapshot, tenant_id="tenant", workspace_id="workspace", lock=True
                )
            else:
                assert not await repository.matches_reindex_batch(
                    snapshot, tenant_id="tenant", workspace_id="workspace"
                )
    finally:
        if running is not None:
            if not running.done():
                running.cancel()
            await asyncio.gather(running, return_exceptions=True)


@pytest.mark.parametrize("kind", ["schema", "example"])
async def test_structured_publication_counts_only_current_source_hash(pg_indexes, kind):
    from flyquery.models.repositories.embedding_set_repository import EmbeddingSetRepository
    from pyfly.data.transaction import infrastructure_unit
    from sqlalchemy import text

    native = pg_indexes.get_bean(DataSourceRegistry).get("canon")
    admin = make_url(os.environ["KOINON_MEMORY_AUTHORITY_TEST_PG_URL"]).set(
        database=native.engine.url.database
    )
    with psycopg.connect(admin.render_as_string(hide_password=False), autocommit=True) as connection:
        connection.execute("CREATE EXTENSION IF NOT EXISTS vector")
    statements = (
        "CREATE TABLE flyquery_schema_objects (id uuid PRIMARY KEY,tenant_id text,workspace_id uuid,"
        "is_active boolean,qualified_name text,data_type text,description text,synonyms_json jsonb,"
        "profile_json jsonb,sample_values_json jsonb)",
        "CREATE TABLE flyquery_examples (id uuid PRIMARY KEY,tenant_id text,workspace_id uuid,"
        "quality text,question text,generated_sql text)",
        "CREATE TABLE flyquery_embedding_sets (id text PRIMARY KEY,tenant_id text,"
        "workspace_id uuid,status text)",
        "CREATE TABLE flyquery_embedding_vectors (set_id text,kind text,object_id uuid,tenant_id text,"
        "workspace_id uuid,content_hash text,embedding vector(1536),model text,text text,"
        "PRIMARY KEY(set_id,kind,object_id))",
    )
    workspace, identifier = uuid4(), uuid4()
    params = {"workspace": workspace, "id": identifier}
    table = "flyquery_schema_objects" if kind == "schema" else "flyquery_examples"
    async with infrastructure_unit(native) as session:
        for statement in statements:
            await session.execute(text(statement))
        await session.execute(
            text("INSERT INTO flyquery_embedding_sets VALUES ('target','tenant',:workspace,'building')"),
            params,
        )
        await session.execute(
            text(
                "INSERT INTO flyquery_schema_objects "
                "VALUES (:id,'tenant',:workspace,true,'amount','INTEGER','Original',null,null,null)"
                if kind == "schema"
                else "INSERT INTO flyquery_examples "
                "VALUES (:id,'tenant',:workspace,'APPROVED','Original','SELECT 1')"
            ),
            params,
        )
    repository = EmbeddingSetRepository(native.sessionmaker)
    scope = {"tenant_id": "tenant", "workspace_id": workspace, "set_id": "target"}
    snapshot = (await repository.missing(**scope))[0]
    async with infrastructure_unit(native) as session:
        column = "description" if kind == "schema" else "question"
        await session.execute(text(f"UPDATE {table} SET {column}='Changed' WHERE id=:id"), params)
    row = {
        "id": identifier,
        "kind": kind,
        "content_hash": snapshot["source_hash"],
        "embedding": [0.1] * 1536,
        "model": "selected",
    }
    assert await repository.upsert(**scope, rows=[row]) == 0
    assert await repository.counts(**scope) == {"chunk_count": 1, "vector_count": 0}
    current = (await repository.missing(**scope))[0]
    row["content_hash"] = current["source_hash"]
    assert await repository.upsert(**scope, rows=[row]) == 1
    assert await repository.counts(**scope) == {"chunk_count": 1, "vector_count": 1}
    async with infrastructure_unit(native) as session:
        await session.execute(text(f"DELETE FROM {table} WHERE id=:id"), params)
    assert await repository.upsert(**scope, rows=[row]) == 0
    assert await repository.counts(**scope) == {"chunk_count": 0, "vector_count": 0}
