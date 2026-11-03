# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Owned PostgreSQL proves native readiness generations cover SQL mutations."""

import importlib.util
import os
from pathlib import Path
from uuid import uuid4

import psycopg
import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from psycopg import sql
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url

pytestmark = pytest.mark.integration
ROOT = Path(__file__).parents[3]
MIGRATION = ROOT / "packages/canon/migrations/koinon_versions/20261103_0100_0022_readiness_generations.py"


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_readiness_migration_is_available():
    assert MIGRATION.is_file(), "Document readiness needs a database-enforced mutation generation"


@pytest.fixture(scope="module")
def readiness_db(record_testsuite_property):
    uri = os.environ.get("KOINON_MEMORY_AUTHORITY_TEST_PG_URL")
    if not uri:
        pytest.skip("Requires an explicitly owned PostgreSQL fixture")
    url = make_url(uri)
    assert url.host == "127.0.0.1" and url.port != 18783
    suffix = uuid4().hex[:10]
    database, runtime = "readiness_" + suffix, "readiness_app_" + suffix
    with psycopg.connect(uri, autocommit=True) as connection:
        connection.execute(
            sql.SQL("CREATE ROLE {} LOGIN NOSUPERUSER NOBYPASSRLS").format(sql.Identifier(runtime))
        )
        connection.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database)))
    record_testsuite_property("owned_database", database)
    record_testsuite_property("owned_role", runtime)
    url = url.set(database=database)
    engine = create_engine(url.set(drivername="postgresql+psycopg"))
    # Register product curated models with the same native metadata used by runtime.
    from flycanon.core.services.retrieval.pgvector_store import vector_table_ddl
    from flycanon.models.entities import Base
    from flycanon.models.entities.source_lineage import metadata

    import koinon.knowledge.curated.domain_entities  # noqa: F401

    with engine.begin() as connection:
        connection.exec_driver_sql("CREATE EXTENSION vector")
        Base.metadata.create_all(connection)
        metadata.create_all(connection)
        for statement in vector_table_ddl("canon_chunk_vectors"):
            connection.exec_driver_sql(statement)
        connection.exec_driver_sql("ALTER TABLE canon_chunk_vectors ENABLE ROW LEVEL SECURITY")
        connection.exec_driver_sql("ALTER TABLE canon_chunk_vectors FORCE ROW LEVEL SECURITY")
        connection.exec_driver_sql(
            "CREATE POLICY tenant_workspace_isolation ON canon_chunk_vectors "
            "USING(namespace=current_setting('app.scope_namespace',true))"
        )
        provision = load(
            ROOT / "packages/canon/migrations/koinon_versions/20261027_1200_0018_index_provisioning.py",
            "readiness_provision",
        )
        with Operations.context(MigrationContext.configure(connection)):
            provision.upgrade()
            load(MIGRATION, "readiness_generation").upgrade()
    engine.dispose()
    grants = load(ROOT / "deploy/provision_roles.py", "readiness_grants")
    owner_uri = url.set(drivername="postgresql").render_as_string(hide_password=False)
    with psycopg.connect(owner_uri) as connection:
        connection.execute(sql.SQL("GRANT USAGE ON SCHEMA public TO {}").format(sql.Identifier(runtime)))
        for (table,) in connection.execute(
            "SELECT tablename FROM pg_tables WHERE schemaname='public'"
        ).fetchall():
            grants.grant_table(connection, table, runtime)
    return url, runtime


def connect(readiness_db, tenant, *, owner=False):
    url, role = readiness_db
    if not owner:
        url = url.set(username=role, password=None)
    connection = psycopg.connect(url.set(drivername="postgresql").render_as_string(hide_password=False))
    connection.execute("SELECT set_config('app.tenant_id',%s,false)", (tenant,))
    connection.commit()
    return connection


def generation(connection, tenant):
    row = connection.execute(
        "SELECT generation FROM canon_readiness_generations WHERE tenant_id=%s", (tenant,)
    ).fetchone()
    return row[0] if row else 0


def test_raw_statement_changes_coalesce_and_rollback(readiness_db):
    tenant = "tenant-" + uuid4().hex
    with connect(readiness_db, tenant) as connection:
        connection.execute("SELECT public.koinon_ensure_canon_readiness(%s)", (tenant,))
        assert generation(connection, tenant) == 0
        connection.execute(
            "INSERT INTO canon_workspaces(id,tenant_id,name) VALUES('a',%s,'A'),('b',%s,'B')",
            (tenant, tenant),
        )
        assert generation(connection, tenant) == 0
        connection.commit()
        assert generation(connection, tenant) == 1
        changes = connection.execute(
            "SELECT workspace_id,generation FROM canon_readiness_changes ORDER BY workspace_id"
        ).fetchall()
        assert changes == [("a", 1), ("b", 1)]
        connection.commit()
        connection.execute("UPDATE canon_workspaces SET name='Changed' WHERE tenant_id=%s", (tenant,))
        assert generation(connection, tenant) == 1
        connection.rollback()
        assert generation(connection, tenant) == 1
        connection.execute("DELETE FROM canon_workspaces WHERE tenant_id=%s", (tenant,))
        connection.commit()
        assert generation(connection, tenant) == 2
        assert connection.execute("SELECT count(*) FROM canon_readiness_changes").fetchone()[0] == 2


def test_runtime_cannot_reset_epochs_or_edit_journal_and_other_tenant_is_hidden(readiness_db):
    tenant = "tenant-" + uuid4().hex
    with connect(readiness_db, tenant) as connection:
        connection.execute("SELECT public.koinon_ensure_canon_readiness(%s)", (tenant,))
        assert generation(connection, tenant) == 0
        connection.commit()
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            connection.execute(
                "UPDATE canon_readiness_generations SET generation=0 WHERE tenant_id=%s", (tenant,)
            )
        connection.rollback()
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            connection.execute("DELETE FROM canon_readiness_changes")
        connection.rollback()
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            connection.execute("SELECT public.koinon_bump_canon_readiness(%s,ARRAY['a'])", (tenant,))
        connection.rollback()
        assert (
            connection.execute(
                "SELECT count(*) FROM canon_readiness_generations WHERE tenant_id<>%s", (tenant,)
            ).fetchone()[0]
            == 0
        )


async def test_snapshot_change_pages_and_held_fence_block_mutation(readiness_db):
    import asyncio

    from flycanon.models.repositories.readiness_generation_repository import (
        ReadinessGenerationChangedError,
        ReadinessGenerationRepository,
    )
    from flycanon.models.repositories.source_repository import SourceRepository
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    tenant, workspace = "tenant-" + uuid4().hex, "workspace-" + uuid4().hex
    url, role = readiness_db
    engine = create_async_engine(
        url.set(drivername="postgresql+asyncpg", username=role, password=None), pool_size=1, max_overflow=0
    )
    repository = ReadinessGenerationRepository(SourceRepository(async_sessionmaker(engine)))
    try:
        empty = await repository.snapshot(tenant)
        assert empty.tenant_generation == 0
        with connect(readiness_db, tenant) as connection:
            connection.execute(
                "INSERT INTO canon_workspaces(id,tenant_id,name) VALUES(%s,%s,'A')", (workspace, tenant)
            )
        current = await repository.snapshot(tenant)
        assert await repository.changes(tenant, after_generation=current.tenant_generation) == []
        changes = await repository.changes(tenant, after_generation=0, limit=1)
        assert [(row.workspace_id, row.generation) for row in changes] == [
            (workspace, current.tenant_generation)
        ]
        assert (
            await repository.changes(
                tenant, after_generation=changes[0].generation, after_workspace_id=workspace
            )
            == []
        )

        async def mutate():
            async with await psycopg.AsyncConnection.connect(
                url.set(drivername="postgresql", username=role, password=None).render_as_string(
                    hide_password=False
                )
            ) as connection:
                await connection.execute("SELECT set_config('app.tenant_id',%s,true)", (tenant,))
                await connection.execute(
                    "UPDATE canon_workspaces SET name='Changed' WHERE id=%s", (workspace,)
                )

        async with repository.hold(tenant, current):
            running = asyncio.create_task(mutate())
            with pytest.raises(TimeoutError):
                await asyncio.wait_for(asyncio.shield(running), 0.2)
        await asyncio.wait_for(running, 3)
        with pytest.raises(ReadinessGenerationChangedError):
            async with repository.hold(tenant, current):
                pytest.fail("A changed corpus cannot pass its previous readiness fence")
        assert engine.pool.checkedout() == 0
    finally:
        await engine.dispose()


def test_source_delete_cascade_and_vector_delete_remain_observable(readiness_db):
    tenant, source = "tenant-" + uuid4().hex, str(uuid4())
    with connect(readiness_db, tenant) as connection:
        connection.execute(
            "INSERT INTO canon_sources(id,tenant_id,workspace_id,kind,status,"
            "content_sha256,content_bytes,n_chunks,metadata_json) VALUES(%s,%s,'docs',"
            "'text','ingested',%s,1,1,'{}')",
            (source, tenant, uuid4().hex * 2),
        )
        connection.execute(
            "INSERT INTO canon_chunks(id,tenant_id,workspace_id,source_id,index_in_source,"
            "total_chunks,content,char_start,char_end,metadata_json) VALUES(%s,%s,'docs',"
            "%s,0,1,'text',0,4,'{}')",
            (str(uuid4()), tenant, source),
        )
        connection.commit()
        before = generation(connection, tenant)
        connection.execute("DELETE FROM canon_sources WHERE id=%s", (source,))
        connection.commit()
        assert generation(connection, tenant) == before + 1
        assert (
            connection.execute("SELECT count(*) FROM canon_chunks WHERE source_id=%s", (source,)).fetchone()[
                0
            ]
            == 0
        )
        namespace = f"t/{tenant}/w/docs"
        connection.execute("SELECT set_config('app.scope_namespace',%s,false)", (namespace,))
        set_id = create_set(connection, tenant, "docs")
        vector = "[" + ",".join(["0.1"] * 64) + "]"
        connection.execute(
            "INSERT INTO canon_chunk_vectors(id,set_id,namespace,embedding,dim,model,text) "
            "SELECT n::text,%s,%s,%s::vector,64,'model','text' FROM generate_series(1,20) n",
            (set_id, namespace, vector),
        )
        connection.commit()
        before = generation(connection, tenant)
        connection.execute("DELETE FROM canon_chunk_vectors WHERE namespace=%s", (namespace,))
        connection.commit()
        assert generation(connection, tenant) == before + 1
        assert connection.execute("SELECT count(*) FROM canon_readiness_changes").fetchone()[0] == 1


def create_set(connection, tenant, workspace):
    set_id = "es-" + uuid4().hex
    connection.execute(
        "INSERT INTO canon_embedding_sets(id,tenant_id,workspace_id,provider,model,"
        "dimensions,status,config_fingerprint,chunk_count,vector_count) VALUES(%s,%s,"
        "%s,'openai','test',64,'building',%s,0,0)",
        (set_id, tenant, workspace, "a" * 64),
    )
    return set_id


def test_provisioning_fences_real_ddl_and_replay_does_not_invalidate(readiness_db):
    tenant, workspace = "tenant-" + uuid4().hex, "workspace-" + uuid4().hex
    with connect(readiness_db, tenant, owner=True) as connection:
        connection.execute("SELECT set_config('app.workspace_id',%s,false)", (workspace,))
        connection.execute(
            "INSERT INTO canon_workspaces(id,tenant_id,name) VALUES(%s,%s,'A')", (workspace, tenant)
        )
        set_id = create_set(connection, tenant, workspace)
        connection.execute(
            "INSERT INTO canon_index_provisions(set_id,tenant_id,workspace_id,index_id,"
            "dimensions,embedding_fingerprint,provider,model,native_fingerprint,actor) "
            "VALUES(%s,%s,%s,%s,64,%s,'openai','test',%s,'test')",
            (set_id, tenant, workspace, uuid4().hex, "b" * 64, "a" * 64),
        )
        connection.commit()
        before = generation(connection, tenant)
        index_name = connection.execute(
            "SELECT public.koinon_provision_document_index(%s,%s,%s)", (tenant, workspace, set_id)
        ).fetchone()[0]
        connection.commit()
        assert generation(connection, tenant) == before + 1
        assert connection.execute("SELECT to_regclass(%s)", (index_name,)).fetchone()[0] == index_name
        connection.execute(
            "SELECT public.koinon_provision_document_index(%s,%s,%s)", (tenant, workspace, set_id)
        )
        connection.commit()
        assert generation(connection, tenant) == before + 1


def test_vector_namespace_cannot_refer_to_another_tenants_set(readiness_db):
    tenant = "tenant-" + uuid4().hex
    with connect(readiness_db, tenant) as connection:
        set_id = create_set(connection, tenant, "docs")
        connection.commit()
        connection.execute("SELECT set_config('app.scope_namespace','t/another/w/docs',true)")
        with pytest.raises(psycopg.errors.InsufficientPrivilege, match="Vector namespace must match"):
            connection.execute(
                "INSERT INTO canon_chunk_vectors(id,set_id,namespace,embedding,dim,model,text) "
                "VALUES('foreign',%s,'t/another/w/docs',%s::vector,64,'openai:test','text')",
                (set_id, "[" + ",".join(["0.1"] * 64) + "]"),
            )


async def test_standalone_ann_creation_and_empty_drop_invalidate_same_scope(readiness_db):
    from flycanon.core.services.embeddings.embedding_sets import EmbeddingSetBinding
    from flycanon.core.services.retrieval.pgvector_store import RlsPgVectorVectorStore
    from pyfly.config.properties.data import DataSourceProperties
    from pyfly.data.relational.datasource_registry import DataSource
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    tenant, workspace = "tenant-" + uuid4().hex, "workspace-" + uuid4().hex
    with connect(readiness_db, tenant, owner=True) as connection:
        set_id = create_set(connection, tenant, workspace)
        connection.commit()
        before = generation(connection, tenant)
    url, _ = readiness_db
    engine = create_async_engine(url.set(drivername="postgresql+asyncpg"))
    source = DataSource(
        "readiness_ann", engine, async_sessionmaker(engine), properties=DataSourceProperties()
    )
    store = RlsPgVectorVectorStore(datasource=source, dimension=64, create_schema=False)
    binding = EmbeddingSetBinding(set_id, "openai", "test", 64)
    try:
        assert await store.ensure_set_index(binding, namespace=f"t/{tenant}/w/{workspace}")
        with connect(readiness_db, tenant, owner=True) as connection:
            assert generation(connection, tenant) == before + 1
        await store.drop_set(set_id, namespace=f"t/{tenant}/w/{workspace}")
        with connect(readiness_db, tenant, owner=True) as connection:
            assert generation(connection, tenant) == before + 2
    finally:
        await engine.dispose()


async def test_native_writers_with_opposite_row_and_epoch_order_both_commit(readiness_db):
    import asyncio

    tenant = "tenant-" + uuid4().hex
    first, second = "a-" + uuid4().hex, "b-" + uuid4().hex
    with connect(readiness_db, tenant) as connection:
        connection.execute(
            "INSERT INTO canon_workspaces(id,tenant_id,name) VALUES(%s,%s,'A'),(%s,%s,'B')",
            (first, tenant, second, tenant),
        )
    url, role = readiness_db
    uri = url.set(drivername="postgresql", username=role, password=None).render_as_string(hide_password=False)
    async with (
        await psycopg.AsyncConnection.connect(uri) as writer_a,
        await psycopg.AsyncConnection.connect(uri) as writer_b,
    ):
        for connection in (writer_a, writer_b):
            await connection.execute("SELECT set_config('app.tenant_id',%s,true)", (tenant,))
        await writer_a.execute("SELECT id FROM canon_workspaces WHERE id=%s FOR UPDATE", (first,))
        await writer_b.execute("UPDATE canon_workspaces SET name='B changed' WHERE id=%s", (second,))

        async def update_and_commit(connection, value):
            try:
                await connection.execute("UPDATE canon_workspaces SET name=%s WHERE id=%s", (value, first))
                await connection.commit()
            except Exception:
                await connection.rollback()
                raise

        results = await asyncio.wait_for(
            asyncio.gather(
                update_and_commit(writer_a, "A"), update_and_commit(writer_b, "B"), return_exceptions=True
            ),
            5,
        )
        assert results == [None, None], "Readiness must not invert content locks between native writers"


async def test_forced_early_seal_rejects_more_writes_before_waiting_for_content_locks(readiness_db):
    import asyncio

    tenant = "tenant-" + uuid4().hex
    first, second = "a-" + uuid4().hex, "b-" + uuid4().hex
    with connect(readiness_db, tenant) as connection:
        connection.execute(
            "INSERT INTO canon_workspaces(id,tenant_id,name) VALUES(%s,%s,'A'),(%s,%s,'B')",
            (first, tenant, second, tenant),
        )
    url, role = readiness_db
    uri = url.set(drivername="postgresql", username=role, password=None).render_as_string(hide_password=False)
    async with (
        await psycopg.AsyncConnection.connect(uri) as sealed,
        await psycopg.AsyncConnection.connect(uri) as blocker,
    ):
        for connection in (sealed, blocker):
            await connection.execute("SELECT set_config('app.tenant_id',%s,true)", (tenant,))
        await blocker.execute("SELECT id FROM canon_workspaces WHERE id=%s FOR UPDATE", (second,))
        await sealed.execute("UPDATE canon_workspaces SET name='Before seal' WHERE id=%s", (first,))
        await sealed.execute("SET CONSTRAINTS readiness_commit IMMEDIATE")
        with pytest.raises(psycopg.errors.InvalidTransactionState, match="readiness was sealed"):
            await asyncio.wait_for(
                sealed.execute("UPDATE canon_workspaces SET name='After seal' WHERE id=%s", (second,)), 0.5
            )
        await sealed.rollback()
        await blocker.rollback()


def test_many_statements_in_one_transaction_produce_one_epoch_and_no_retained_pending_work(readiness_db):
    tenant, workspace = "tenant-" + uuid4().hex, "workspace-" + uuid4().hex
    with connect(readiness_db, tenant) as connection:
        connection.execute(
            "INSERT INTO canon_workspaces(id,tenant_id,name) VALUES(%s,%s,'A')", (workspace, tenant)
        )
        for index in range(20):
            connection.execute("UPDATE canon_workspaces SET name=%s WHERE id=%s", (str(index), workspace))
        assert generation(connection, tenant) == 0
        connection.commit()
        assert generation(connection, tenant) == 1
        assert not connection.execute(
            "SELECT has_table_privilege(current_user,'canon_readiness_pending','SELECT')"
        ).fetchone()[0]
    with connect(readiness_db, tenant, owner=True) as connection:
        assert (
            connection.execute(
                "SELECT count(*) FROM canon_readiness_pending WHERE tenant_id=%s", (tenant,)
            ).fetchone()[0]
            == 0
        )


def test_truncate_cannot_bypass_scope_readiness_even_for_owner(readiness_db):
    with (
        connect(readiness_db, "maintenance", owner=True) as connection,
        pytest.raises(psycopg.errors.FeatureNotSupported, match="Use scoped DELETE"),
    ):
        connection.execute("TRUNCATE canon_sources CASCADE")


async def test_ann_ddl_finishes_before_waiting_for_final_readiness_commit_fence(readiness_db):
    import asyncio

    from flycanon.models.repositories.readiness_generation_repository import ReadinessGenerationRepository
    from flycanon.models.repositories.source_repository import SourceRepository
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    tenant, workspace = "tenant-" + uuid4().hex, "workspace-" + uuid4().hex
    with connect(readiness_db, tenant, owner=True) as connection:
        connection.execute(
            "INSERT INTO canon_workspaces(id,tenant_id,name) VALUES(%s,%s,'A')", (workspace, tenant)
        )
        set_id = create_set(connection, tenant, workspace)
        connection.execute(
            "INSERT INTO canon_index_provisions(set_id,tenant_id,workspace_id,index_id,dimensions,"
            "embedding_fingerprint,provider,model,native_fingerprint,actor) "
            "VALUES(%s,%s,%s,%s,64,%s,'openai','test',%s,'test')",
            (set_id, tenant, workspace, uuid4().hex, "b" * 64, "a" * 64),
        )
    url, role = readiness_db
    engine = create_async_engine(
        url.set(drivername="postgresql+asyncpg", username=role, password=None), pool_size=1, max_overflow=0
    )
    repository = ReadinessGenerationRepository(SourceRepository(async_sessionmaker(engine)))
    ddl_finished = asyncio.Event()

    async def provision():
        async with await psycopg.AsyncConnection.connect(
            url.set(drivername="postgresql").render_as_string(hide_password=False)
        ) as connection:
            await connection.execute(
                "SELECT set_config('app.tenant_id',%s,true),set_config('app.workspace_id',%s,true)",
                (tenant, workspace),
            )
            await connection.execute(
                "SELECT public.koinon_provision_document_index(%s,%s,%s)", (tenant, workspace, set_id)
            )
            ddl_finished.set()
            await connection.commit()

    try:
        before = await repository.snapshot(tenant)
        async with repository.hold(tenant, before):
            running = asyncio.create_task(provision())
            await asyncio.wait_for(ddl_finished.wait(), 3)
            with pytest.raises(TimeoutError):
                await asyncio.wait_for(asyncio.shield(running), 0.2)
        await asyncio.wait_for(running, 3)
        assert (await repository.snapshot(tenant)).tenant_generation == before.tenant_generation + 1
    finally:
        await engine.dispose()
