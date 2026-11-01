# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Opt-in real pgvector/function/RLS proof of the initial document ready phase."""

import importlib.util
import os
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4

import psycopg
import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from flycanon.core.services.retrieval.pgvector_store import vector_table_ddl
from flycanon.data import TenantGucCustomizer
from flycanon.models.repositories import ChunkRepository
from flyquery.data import TenantGucCustomizer as StructuredGucCustomizer
from psycopg import sql
from pyfly.context import ApplicationContext
from pyfly.core import Config
from pyfly.data.relational.datasource_registry import DataSourceRegistry
from pyfly.data.relational.sqlalchemy import Base
from pyfly.data.transaction import TransactionTemplate
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from test_installation_manifest import example

from koinon.assistants.entities import Provider
from koinon.assistants.repositories import ProviderRepository
from koinon.catalog.entities import AuditEvent, CatalogEntry, Tenant
from koinon.catalog.repositories import (
    AuditRepository,
    CatalogRepository,
    MembershipRepository,
    TenantRepository,
)
from koinon.catalog.service import CatalogService
from koinon.communications.entities import InstallationRecord
from koinon.installation.authority import InstallationAdmissions
from koinon.installation.dtos import InstallationPlan
from koinon.installation.entities import InstallationRun
from koinon.installation.indexes import NativeInstallationIndexes
from koinon.installation.repositories import InstallationRepository
from koinon.installation.writes import NativeInstallationWrites, resource_id
from koinon.knowledge.entities import DomainBinding
from koinon.knowledge.indexes.adapters import NativeIndexAdapter
from koinon.knowledge.indexes.entities import KnowledgeIndex
from koinon.knowledge.indexes.planner import IndexPlanner
from koinon.knowledge.indexes.repositories import KnowledgeIndexRepository
from koinon.knowledge.repositories import DomainBindingRepository

pytestmark = pytest.mark.integration


def migration(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


@pytest.fixture(scope="module")
def ann_database():
    uri = os.environ.get("KOINON_INSTALLATION_ANN_TEST_PG_URL")
    if not uri:
        pytest.skip("Requires an explicitly owned PostgreSQL/pgvector fixture")
    url = make_url(uri)
    assert url.host == "127.0.0.1" and url.port != 18783
    suffix = uuid4().hex[:12]
    database, owner, runtime, admin, structured_runtime = (
        prefix + suffix for prefix in ("ann_", "owner_", "runtime_", "admin_", "structured_")
    )
    with psycopg.connect(uri, autocommit=True) as connection:
        connection.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database)))
        for role, login in (
            (owner, "NOLOGIN"),
            (runtime, "LOGIN"),
            (admin, "LOGIN"),
            (structured_runtime, "LOGIN"),
        ):
            connection.execute(
                sql.SQL(
                    "CREATE ROLE {} "
                    + login
                    + " NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS"
                ).format(sql.Identifier(role))
            )
    url = url.set(database=database)
    engine = create_engine(url.set(drivername="postgresql+psycopg"))
    Base.metadata.create_all(
        engine,
        tables=[
            Tenant.__table__,
            InstallationRecord.__table__,
            InstallationRun.__table__,
            CatalogEntry.__table__,
            AuditEvent.__table__,
            Provider.__table__,
            KnowledgeIndex.__table__,
            DomainBinding.__table__,
        ],
    )
    root = Path(__file__).parents[3]
    core = migration(
        root / "packages/canon/migrations/versions/20260924_1200_0017_embedding_sets.py", "ann_core_migration"
    )
    provision = migration(
        root / "packages/canon/migrations/koinon_versions/20261027_1200_0018_index_provisioning.py",
        "ann_provision_migration",
    )
    with engine.begin() as connection:
        connection.exec_driver_sql("CREATE EXTENSION vector")
        connection.exec_driver_sql("REVOKE CREATE ON SCHEMA public FROM PUBLIC")
        connection.exec_driver_sql(f'GRANT USAGE, CREATE ON SCHEMA public TO "{owner}"')
        connection.exec_driver_sql(f'SET LOCAL ROLE "{owner}"')
        connection.exec_driver_sql(
            "CREATE TABLE canon_workspaces(id text PRIMARY KEY,tenant_id text NOT NULL,"
            "active_embedding_set_id text)"
        )
        connection.exec_driver_sql(
            "CREATE TABLE canon_chunks(id text PRIMARY KEY,tenant_id text NOT NULL,"
            "workspace_id text NOT NULL,content text)"
        )
        for statement in vector_table_ddl("canon_chunk_vectors"):
            connection.exec_driver_sql(statement)
        connection.exec_driver_sql("ALTER TABLE canon_chunk_vectors ENABLE ROW LEVEL SECURITY")
        connection.exec_driver_sql("ALTER TABLE canon_chunk_vectors FORCE ROW LEVEL SECURITY")
        connection.exec_driver_sql(
            "CREATE POLICY namespace_scope ON canon_chunk_vectors "
            "USING(namespace=current_setting('app.scope_namespace',true))"
        )
        for statement in core.embedding_sets_ddl():
            connection.exec_driver_sql(statement)
        structured = migration(
            root / "packages/structured/migrations/versions/0015_versioned_embedding_sets.py",
            "ann_structured_migration",
        )
        with Operations.context(MigrationContext.configure(connection)):
            provision.upgrade()
            structured.upgrade()
        connection.exec_driver_sql(
            "CREATE TABLE flyquery_schema_objects(id uuid PRIMARY KEY,tenant_id text,workspace_id uuid,"
            "is_active boolean,embedding vector(1536),embedding_model text,qualified_name text,"
            "data_type text,description text,synonyms_json jsonb,profile_json jsonb,sample_values_json jsonb)"
        )
        connection.exec_driver_sql(
            "CREATE TABLE flyquery_examples(id uuid PRIMARY KEY,tenant_id text,workspace_id uuid,"
            "quality text,question text,generated_sql text)"
        )
        for table in ("flyquery_schema_objects", "flyquery_examples"):
            connection.exec_driver_sql(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
            connection.exec_driver_sql(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
            connection.exec_driver_sql(
                f"CREATE POLICY scoped ON {table} USING(tenant_id=current_setting('app.tenant_id',true) "
                "AND workspace_id::text=current_setting('app.workspace_id',true))"
            )
        connection.exec_driver_sql(f'GRANT USAGE ON SCHEMA public TO "{structured_runtime}"')
        connection.exec_driver_sql(
            "GRANT SELECT ON flyquery_embedding_sets,flyquery_embedding_vectors,"
            f'flyquery_schema_objects,flyquery_examples TO "{structured_runtime}"'
        )
        connection.exec_driver_sql(
            f'GRANT UPDATE(status,ready_at) ON flyquery_embedding_sets TO "{structured_runtime}"'
        )
        for table in ("canon_workspaces", "canon_chunks"):
            connection.exec_driver_sql(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
            connection.exec_driver_sql(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
            scope = "tenant_id=current_setting('app.tenant_id',true)" + (
                " AND workspace_id=current_setting('app.workspace_id',true)"
                if table == "canon_chunks"
                else " AND id=current_setting('app.workspace_id',true)"
            )
            connection.exec_driver_sql(f"CREATE POLICY scoped ON {table} USING ({scope})")
        for role in (runtime, admin):
            connection.exec_driver_sql(f'GRANT USAGE ON SCHEMA public TO "{role}"')
            connection.exec_driver_sql(
                "GRANT SELECT ON canon_workspaces,canon_chunks,canon_chunk_vectors,"
                f'canon_embedding_sets TO "{role}"'
            )
        connection.exec_driver_sql(f'GRANT UPDATE(status,ready_at) ON canon_embedding_sets TO "{runtime}"')
        connection.exec_driver_sql(f'GRANT SELECT,INSERT ON canon_index_provisions TO "{admin}"')
        connection.exec_driver_sql(
            f'GRANT EXECUTE ON FUNCTION public.koinon_provision_document_index(text,text,text) TO "{admin}"'
        )
    engine.dispose()
    return SimpleNamespace(
        url=url, owner=owner, runtime=runtime, admin=admin, structured_runtime=structured_runtime
    )


@pytest.fixture
async def pg_phase(ann_database, request):
    fixture = ann_database
    context = ApplicationContext(
        Config(
            {
                "pyfly": {
                    "banner": {"mode": "off"},
                    "data": {
                        "relational": {
                            "enabled": True,
                            "ddl-auto": "none",
                            "url": fixture.url.set(drivername="postgresql+asyncpg").render_as_string(
                                hide_password=False
                            ),
                        }
                    },
                }
            }
        )
    )
    for bean in (
        TenantRepository,
        MembershipRepository,
        CatalogRepository,
        AuditRepository,
        ProviderRepository,
        KnowledgeIndexRepository,
        DomainBindingRepository,
        InstallationRepository,
        InstallationAdmissions,
    ):
        context.register_bean(bean)
    await context.start()
    try:
        get = context.get_bean
        registry = get(DataSourceRegistry)
        canon = registry.register(
            "canon",
            fixture.url.set(drivername="postgresql+asyncpg", username=fixture.runtime).render_as_string(
                hide_password=False
            ),
        )
        registry.register(
            "canon_admin",
            fixture.url.set(drivername="postgresql+asyncpg", username=fixture.admin).render_as_string(
                hide_password=False
            ),
        )
        registry.add_customizer(TenantGucCustomizer("canon"), datasource="canon")
        registry.register(
            "structured",
            fixture.url.set(
                drivername="postgresql+asyncpg", username=fixture.structured_runtime
            ).render_as_string(hide_password=False),
        )
        registry.add_customizer(StructuredGucCustomizer("structured"), datasource="structured")
        chunks = ChunkRepository(canon.sessionmaker, engine=canon.engine)
        domains = SimpleNamespace(_resolve=lambda kind: chunks if kind is ChunkRepository else None)
        adapter = NativeIndexAdapter(registry, domains)
        tenant = "fixture-" + uuid4().hex[:12]
        await get(TenantRepository).save(Tenant(id=tenant, name="Owned fixture"))
        document = example()
        document["tenant_id"] = tenant
        legacy = getattr(request, "param", False) is True
        is_structured = getattr(request, "param", False) == "structured"
        if is_structured:
            document["indexes"][0].update(domain="structured", key="tables")
        if legacy:
            document["indexes"][0]["key"] = "company-documents"
        plan = InstallationPlan.model_validate(document)
        admissions = get(InstallationAdmissions)
        permit = await admissions.admit(plan, resume=False)
        async with TransactionTemplate("primary").transaction():
            for value in plan.providers:
                row = await get(ProviderRepository).save(
                    Provider(
                        id=resource_id(permit, "provider:" + value.key),
                        tenant_id=tenant,
                        name=value.name,
                        kind=value.kind,
                        api=value.api,
                        base_url=value.base_url,
                        model_ids=value.model_ids,
                    )
                )
                await admissions.checkpoint(
                    permit,
                    "provider:" + value.key,
                    {"status": "done", "resource_id": row.id, "revision": row.revision},
                )
        catalog = CatalogService(
            get(TenantRepository), get(MembershipRepository), get(CatalogRepository), get(AuditRepository)
        )
        writes = NativeInstallationWrites(
            admissions, Mock(), SimpleNamespace(get=lambda: catalog), Mock(), Mock()
        )
        for key in plan.catalog_order():
            await writes.catalog_node(permit, next(value for value in plan.catalog if value.key == key))
        planner = IndexPlanner(get(ProviderRepository), Mock(), Mock())

        async def prepare(tenant, value):
            return await planner.provider(tenant, value.provider_id, value.model_id), {
                "dimensions": 1536,
                "storage_dimensions": 1536,
            }

        planner.prepare = prepare
        reader = SimpleNamespace(
            records=get(KnowledgeIndexRepository),
            planner=planner,
            adapter=adapter,
            facade=SimpleNamespace(catalog=catalog),
            connections=SimpleNamespace(selected=unused_selected),
        )
        writer = NativeInstallationIndexes(admissions, SimpleNamespace(get=lambda: reader))
        # Seed precisely the durable post-create boundary; no model/provider calls are needed for this phase.
        if legacy:
            from hashlib import sha256
            from json import dumps

            from koinon.installation.authority import ACTOR
            from koinon.knowledge.connections.service import embedding_fingerprint
            from koinon.knowledge.indexes.adapters import index_id

            value = plan.indexes[0]
            workspace = resource_id(permit, "catalog:" + value.workspace_key)
            native = "es-" + resource_id(permit, "index:" + value.key).replace("-", "")
            identifier = index_id(tenant, workspace, "documents", native)
            async with TransactionTemplate("primary").transaction():
                provider = await planner.provider(
                    tenant, resource_id(permit, "provider:" + value.provider_key), value.model_id
                )
                transient = KnowledgeIndex(
                    id=identifier,
                    tenant_id=tenant,
                    workspace_id=workspace,
                    native_workspace_id=workspace,
                    native_id=native,
                    domain="documents",
                    provider_id=provider.id,
                    provider_kind=provider.kind,
                    provider_revision=1,
                    model_id=value.model_id,
                    dimensions=1536,
                    storage_dimensions=1536,
                    embedding_fingerprint=embedding_fingerprint(provider, value.model_id, 1536, 1536),
                    build_slot=sha256(dumps([tenant, "documents", workspace]).encode()).hexdigest(),
                    status="queued",
                    cursor={},
                    transition={},
                    created_by=ACTOR,
                    updated_by=ACTOR,
                )
                managed = await reader.records.save(transient)
                assert managed.revision == 1 and transient.revision is None
                await admissions.checkpoint(
                    permit,
                    "index-intent:" + value.key,
                    {
                        "status": "done",
                        "resource_id": identifier,
                        "dimensions": 1536,
                        "revision": None,
                        "row_status": "queued",
                    },
                )
            await admissions.fail(permit)
            permit = await admissions.admit(plan, resume=True)
            assert permit.generation == 2
            await writer.intent(permit, value)
        else:
            identifier = await writer.intent(permit, plan.indexes[0])
        async with TransactionTemplate("primary").transaction():
            row = await reader.records.find_by_id(identifier)
            native_fingerprint = row.embedding_fingerprint if is_structured else "e" * 64
            row.cursor = {"native_config_fingerprint": native_fingerprint}
            row.revision = 2
            await reader.records.save(row)
            await admissions.checkpoint(
                permit,
                "index-created:" + plan.indexes[0].key,
                {
                    "status": "done",
                    "resource_id": identifier,
                    "revision": 2,
                    "row_status": "queued",
                    "native_fingerprint": native_fingerprint,
                },
            )
        if not is_structured:
            with psycopg.connect(
                fixture.url.set(drivername="postgresql").render_as_string(hide_password=False)
            ) as connection:
                connection.execute(
                    "INSERT INTO canon_workspaces(id,tenant_id) VALUES(%s,%s)",
                    (row.native_workspace_id, tenant),
                )
                connection.execute(
                    "INSERT INTO canon_embedding_sets(id,tenant_id,workspace_id,provider,model,dimensions,"
                    "status,config_fingerprint,created_by) "
                    "VALUES(%s,%s,%s,%s,%s,1536,'queued',%s,'system:installation')",
                    (
                        row.native_id,
                        tenant,
                        row.native_workspace_id,
                        row.provider_kind,
                        row.model_id,
                        "e" * 64,
                    ),
                )
        if is_structured:
            with psycopg.connect(
                fixture.url.set(drivername="postgresql").render_as_string(hide_password=False)
            ) as connection:
                connection.execute(
                    "INSERT INTO flyquery_embedding_sets(id,tenant_id,workspace_id,provider,model,dimensions,"
                    "config_fingerprint,status,created_by) "
                    "VALUES(%s,%s,%s,%s,%s,1536,%s,'queued','system:installation')",
                    (
                        row.native_id,
                        tenant,
                        row.native_workspace_id,
                        row.provider_kind,
                        row.model_id,
                        native_fingerprint,
                    ),
                )
        if legacy:
            await admissions.fail(permit)
            permit = await admissions.admit(plan, resume=True)
            assert permit.generation == 3
        yield SimpleNamespace(
            writer=writer,
            permit=permit,
            value=plan.indexes[0],
            row=row,
            reader=reader,
            adapter=adapter,
            admissions=admissions,
            fixture=fixture,
        )
    finally:
        await context.stop()


async def unused_selected(*args):
    return None


async def test_empty_document_ready_provisions_real_hnsw_under_scoped_native_roles(pg_phase):
    state = pg_phase
    await state.writer.ready(state.permit, state.value)
    receipt = await state.admissions.receipt(state.permit)
    assert receipt["checkpoints"]["index-ready:documents"]["row_status"] == "ready"
    actual = await state.adapter.get_native(
        tenant_id=state.row.tenant_id,
        native_workspace_id=state.row.native_workspace_id,
        catalog_workspace_id=state.row.workspace_id,
        domain="documents",
        actor="system:installation",
        identifier=state.row.id,
    )
    assert (
        actual["indexed"] is True
        and actual["status"] == "ready"
        and actual["chunk_count"] == actual["vector_count"] == 0
    )


@pytest.mark.parametrize("pg_phase", [True], indirect=True)
async def test_explicit_gen3_resume_preserves_gen2_null_reconciliation_and_created_history(pg_phase):
    state = pg_phase
    key = state.value.key
    before = await state.admissions.receipt(state.permit)
    assert before["generation"] == 3
    assert before["checkpoints"]["index-intent:" + key]["revision"] is None
    assert before["checkpoints"]["index-intent-reconciled:" + key]["generation"] == 2
    assert before["checkpoints"]["index-created:" + key]["revision"] == 2
    assert await state.writer.intent(state.permit, state.value) == state.row.id
    await state.writer.create(state.permit, state.value)
    await state.writer.ready(state.permit, state.value)
    after = await state.admissions.receipt(state.permit)
    for stage in ("index-intent:", "index-intent-reconciled:", "index-created:"):
        assert before["checkpoints"][stage + key] == after["checkpoints"][stage + key]
    assert after["checkpoints"]["index-ready:" + key]["revision"] == 3
    assert not any(k.startswith(("connection:", "agent:")) for k in after["checkpoints"])


async def test_registered_queued_target_remains_rejected_by_original_sql_function(pg_phase):
    from sqlalchemy.exc import ProgrammingError

    state = pg_phase
    with pytest.raises(ProgrammingError) as error:
        await state.adapter.provision_document(state.row)
    assert error.value.orig.sqlstate == "42501"


@pytest.mark.parametrize(
    "change",
    [
        "cancelled",
        "failed",
        "active",
        "fingerprint",
        "provider",
        "model",
        "dimensions",
        "tenant",
        "creator",
        "activated_at",
        "retired_at",
    ],
)
async def test_initial_native_transition_never_revives_changed_or_foreign_target(pg_phase, change):
    from koinon.installation.authority import InstallationError

    state = pg_phase
    field, value = (
        ("status", change)
        if change in {"cancelled", "failed", "active"}
        else {
            "fingerprint": ("config_fingerprint", "f" * 64),
            "provider": ("provider", "manual"),
            "model": ("model", "manual"),
            "dimensions": ("dimensions", 768),
            "tenant": ("tenant_id", "foreign-tenant"),
            "creator": ("created_by", "issuer|manual"),
            "activated_at": ("activated_at", datetime(2026, 10, 1, tzinfo=UTC)),
            "retired_at": ("retired_at", datetime(2026, 10, 1, tzinfo=UTC)),
        }[change]
    )
    with psycopg.connect(
        state.fixture.url.set(drivername="postgresql").render_as_string(hide_password=False)
    ) as connection:
        connection.execute(
            sql.SQL("UPDATE canon_embedding_sets SET {}=%s WHERE id=%s").format(sql.Identifier(field)),
            (value, state.row.native_id),
        )
    with pytest.raises(InstallationError, match="INSTALLATION_MANUAL_CHANGE"):
        await state.writer.ready(state.permit, state.value)
    with psycopg.connect(
        state.fixture.url.set(drivername="postgresql").render_as_string(hide_password=False)
    ) as connection:
        assert (
            connection.execute(
                sql.SQL("SELECT {} FROM canon_embedding_sets WHERE id=%s").format(sql.Identifier(field)),
                (state.row.native_id,),
            ).fetchone()[0]
            == value
        )
        assert (
            connection.execute(
                "SELECT count(*) FROM canon_index_provisions WHERE set_id=%s", (state.row.native_id,)
            ).fetchone()[0]
            == 0
        )
    assert (
        "index-ready:" + state.value.key not in (await state.admissions.receipt(state.permit))["checkpoints"]
    )


@pytest.mark.parametrize("native_status", ["building", "ready"])
async def test_initial_native_phase_replays_committed_build_or_ready_without_regression(
    pg_phase, native_status
):
    state = pg_phase
    with psycopg.connect(
        state.fixture.url.set(drivername="postgresql").render_as_string(hide_password=False)
    ) as connection:
        connection.execute(
            "UPDATE canon_embedding_sets SET status=%s WHERE id=%s", (native_status, state.row.native_id)
        )
    await state.writer.ready(state.permit, state.value)
    await state.writer.ready(state.permit, state.value)
    receipt = await state.admissions.receipt(state.permit)
    assert receipt["checkpoints"]["index-ready:" + state.value.key]["row_status"] == "ready"


async def test_runtime_cannot_call_owner_function_or_issue_ann_ddl(pg_phase):
    state = pg_phase
    for role, statement in [
        (
            state.fixture.runtime,
            "SELECT public.koinon_provision_document_index('x','y','es-" + "0" * 32 + "')",
        ),
        (state.fixture.admin, "CREATE INDEX forbidden_ann ON public.canon_chunk_vectors(set_id)"),
    ]:
        with psycopg.connect(
            state.fixture.url.set(drivername="postgresql", username=role).render_as_string(
                hide_password=False
            )
        ) as connection:
            with pytest.raises(psycopg.errors.InsufficientPrivilege) as error:
                connection.execute(statement)
            assert error.value.sqlstate == "42501"


async def test_ann_capability_missing_never_records_ready_and_building_can_resume(pg_phase):
    from koinon.installation.authority import InstallationError

    state = pg_phase
    with psycopg.connect(
        state.fixture.url.set(drivername="postgresql").render_as_string(hide_password=False)
    ) as connection:
        connection.execute(
            sql.SQL(
                "REVOKE EXECUTE ON FUNCTION public.koinon_provision_document_index(text,text,text) FROM {}"
            ).format(sql.Identifier(state.fixture.admin))
        )
    try:
        with pytest.raises(InstallationError, match="INSTALLATION_ANN_PROVISION_REQUIRED"):
            await state.writer.ready(state.permit, state.value)
        receipt = await state.admissions.receipt(state.permit)
        assert "index-ready:" + state.value.key not in receipt["checkpoints"]
        with psycopg.connect(
            state.fixture.url.set(drivername="postgresql").render_as_string(hide_password=False)
        ) as connection:
            assert (
                connection.execute(
                    "SELECT status FROM canon_embedding_sets WHERE id=%s", (state.row.native_id,)
                ).fetchone()[0]
                == "building"
            )
    finally:
        with psycopg.connect(
            state.fixture.url.set(drivername="postgresql").render_as_string(hide_password=False)
        ) as connection:
            connection.execute(
                sql.SQL(
                    "GRANT EXECUTE ON FUNCTION public.koinon_provision_document_index(text,text,text) TO {}"
                ).format(sql.Identifier(state.fixture.admin))
            )
    await state.admissions.fail(state.permit)
    plan = InstallationPlan.model_validate({**example(), "tenant_id": state.row.tenant_id})
    permit = await state.admissions.admit(plan, resume=True)
    await state.writer.ready(permit, state.value)
    assert (await state.admissions.receipt(permit))["checkpoints"]["index-ready:" + state.value.key][
        "row_status"
    ] == "ready"


async def test_native_runtime_scope_is_enforced_by_actual_forced_rls(pg_phase):
    state = pg_phase
    with psycopg.connect(
        state.fixture.url.set(drivername="postgresql", username=state.fixture.runtime).render_as_string(
            hide_password=False
        )
    ) as connection:
        assert connection.execute(
            "SELECT rolsuper,rolbypassrls FROM pg_roles WHERE rolname=current_user"
        ).fetchone() == (False, False)
        assert connection.execute(
            "SELECT relrowsecurity,relforcerowsecurity FROM pg_class "
            "WHERE oid='public.canon_embedding_sets'::regclass"
        ).fetchone() == (True, True)
        assert (
            connection.execute(
                "SELECT count(*) FROM canon_embedding_sets WHERE id=%s", (state.row.native_id,)
            ).fetchone()[0]
            == 0
        )
        connection.execute(
            "SELECT set_config('app.tenant_id',%s,true),set_config('app.workspace_id',%s,true)",
            (state.row.tenant_id, state.row.native_workspace_id),
        )
        assert (
            connection.execute(
                "SELECT count(*) FROM canon_embedding_sets WHERE id=%s", (state.row.native_id,)
            ).fetchone()[0]
            == 1
        )
        connection.execute("SELECT set_config('app.workspace_id','foreign',true)")
        assert (
            connection.execute(
                "UPDATE canon_embedding_sets SET status='building' WHERE id=%s RETURNING id",
                (state.row.native_id,),
            ).fetchone()
            is None
        )


async def test_cancel_during_real_ann_provision_is_not_revived_ready(pg_phase):
    from koinon.installation.authority import InstallationError

    state = pg_phase
    provision = state.adapter.provision_document

    async def provision_then_cancel(row):
        indexed = await provision(row)
        with psycopg.connect(
            state.fixture.url.set(drivername="postgresql").render_as_string(hide_password=False)
        ) as connection:
            connection.execute(
                "UPDATE canon_embedding_sets SET status='cancelled' WHERE id=%s", (row.native_id,)
            )
        return indexed

    state.adapter.provision_document = provision_then_cancel
    with pytest.raises(InstallationError, match="INSTALLATION_MANUAL_CHANGE"):
        await state.writer.ready(state.permit, state.value)
    with psycopg.connect(
        state.fixture.url.set(drivername="postgresql").render_as_string(hide_password=False)
    ) as connection:
        assert (
            connection.execute(
                "SELECT status FROM canon_embedding_sets WHERE id=%s", (state.row.native_id,)
            ).fetchone()[0]
            == "cancelled"
        )
    assert (
        "index-ready:" + state.value.key not in (await state.admissions.receipt(state.permit))["checkpoints"]
    )


@pytest.mark.parametrize("pg_phase", ["structured"], indirect=True)
async def test_initial_structured_empty_target_ready_uses_real15_ann_and_rls(pg_phase):
    state = pg_phase
    await state.writer.ready(state.permit, state.value)
    actual = await state.adapter.get_native(
        tenant_id=state.row.tenant_id,
        native_workspace_id=state.row.native_workspace_id,
        catalog_workspace_id=state.row.workspace_id,
        domain="structured",
        actor="system:installation",
        identifier=state.row.id,
    )
    assert (
        actual["indexed"] is True
        and actual["status"] == "ready"
        and actual["chunk_count"] == actual["vector_count"] == 0
    )
    with psycopg.connect(
        state.fixture.url.set(
            drivername="postgresql", username=state.fixture.structured_runtime
        ).render_as_string(hide_password=False)
    ) as connection:
        assert connection.execute(
            "SELECT relrowsecurity,relforcerowsecurity FROM pg_class "
            "WHERE oid='public.flyquery_embedding_sets'::regclass"
        ).fetchone() == (True, True)
        assert (
            connection.execute(
                "SELECT count(*) FROM flyquery_embedding_sets WHERE id=%s", (state.row.native_id,)
            ).fetchone()[0]
            == 0
        )
        connection.execute(
            "SELECT set_config('app.tenant_id',%s,true),set_config('app.workspace_id',%s,true)",
            (state.row.tenant_id, state.row.native_workspace_id),
        )
        assert (
            connection.execute(
                "SELECT count(*) FROM flyquery_embedding_sets WHERE id=%s", (state.row.native_id,)
            ).fetchone()[0]
            == 1
        )


@pytest.mark.parametrize("pg_phase", ["structured"], indirect=True)
@pytest.mark.parametrize("change", ["cancelled", "creator", "retired_at", "fingerprint", "tenant"])
async def test_initial_structured_ready_never_revives_changed_or_foreign_target(pg_phase, change):
    from koinon.installation.authority import InstallationError

    state = pg_phase
    field, value = {
        "cancelled": ("status", "cancelled"),
        "creator": ("created_by", "issuer|manual"),
        "retired_at": ("retired_at", datetime(2026, 10, 1, tzinfo=UTC)),
        "fingerprint": ("config_fingerprint", "f" * 64),
        "tenant": ("tenant_id", "foreign"),
    }[change]
    with psycopg.connect(
        state.fixture.url.set(drivername="postgresql").render_as_string(hide_password=False)
    ) as connection:
        connection.execute(
            sql.SQL("UPDATE flyquery_embedding_sets SET {}=%s WHERE id=%s").format(sql.Identifier(field)),
            (value, state.row.native_id),
        )
    with pytest.raises(InstallationError, match="INSTALLATION_MANUAL_CHANGE"):
        await state.writer.ready(state.permit, state.value)
    with psycopg.connect(
        state.fixture.url.set(drivername="postgresql").render_as_string(hide_password=False)
    ) as connection:
        assert (
            connection.execute(
                sql.SQL("SELECT {} FROM flyquery_embedding_sets WHERE id=%s").format(sql.Identifier(field)),
                (state.row.native_id,),
            ).fetchone()[0]
            == value
        )
    assert (
        "index-ready:" + state.value.key not in (await state.admissions.receipt(state.permit))["checkpoints"]
    )


@pytest.mark.parametrize("pg_phase", [False, "structured"], indirect=True)
async def test_observed_cancel_after_final_native_cas_never_gets_ready_checkpoint(pg_phase):
    from koinon.installation.authority import InstallationError

    state = pg_phase
    read_native = state.adapter.get_native

    async def cancel_then_read(**arguments):
        table = "canon_embedding_sets" if state.row.domain == "documents" else "flyquery_embedding_sets"
        with psycopg.connect(
            state.fixture.url.set(drivername="postgresql").render_as_string(hide_password=False)
        ) as connection:
            connection.execute(
                sql.SQL("UPDATE {} SET status='cancelled' WHERE id=%s").format(sql.Identifier(table)),
                (state.row.native_id,),
            )
        return await read_native(**arguments)

    state.adapter.get_native = cancel_then_read
    with pytest.raises(InstallationError, match="INSTALLATION_MANUAL_CHANGE"):
        await state.writer.ready(state.permit, state.value)
    assert (
        "index-ready:" + state.value.key not in (await state.admissions.receipt(state.permit))["checkpoints"]
    )
