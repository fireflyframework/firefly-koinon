# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Opt-in native18/CAS proof in a new private Unix-only PostgreSQL cluster.

The predecessor is source-derived, not a managed database restore. No external
URL, role/grant changes, extension installation, provider or model is used.
"""

import asyncio
import getpass
import importlib.util
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest
from alembic import command
from flycanon.config import CanonSettings
from flyquery.config import FlyquerySettings
from pyfly.container.scanner import scan_package
from pyfly.context import ApplicationContext
from pyfly.core import Config
from pyfly.data.relational.datasource_registry import DataSourceRegistry
from pyfly.data.transaction import infrastructure_unit
from pyfly.kernel import ConflictException
from sqlalchemy import MetaData, create_engine, func, inspect, select, text
from sqlalchemy.engine import URL
from sqlalchemy.exc import DataError, IntegrityError
from test_contract import documents, input_policy

from koinon.catalog.entities import AuditEvent, CatalogEntry, Membership, Tenant
from koinon.catalog.errors import AccessDenied
from koinon.catalog.repositories import MembershipRepository, TenantRepository
from koinon.organization_knowledge.dtos import (
    OrganizationKnowledgeSettings,
    OrganizationKnowledgeSettingsInput,
    OrganizationKnowledgeSnapshot,
)
from koinon.organization_knowledge.entities import OrganizationKnowledgeSetting
from koinon.organization_knowledge.service import OrganizationKnowledgeService

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def owned_postgres():
    if os.environ.get("KOINON_KNOWLEDGE_OWNED_POSTGRES") != "1":
        pytest.skip("Explicitly opt in to a new private PostgreSQL cluster")
    located = shutil.which("initdb")
    configured = os.environ.get("KOINON_TEST_POSTGRES_BIN")
    binary = Path(configured) if configured else Path(located).parent if located else None
    if binary is None or not all((binary / name).is_file() for name in ("initdb", "pg_ctl", "postgres")):
        pytest.skip("PostgreSQL server binaries are unavailable")
    with tempfile.TemporaryDirectory(prefix="koinon-policy-pg-", dir="/tmp") as temporary:
        root = Path(temporary)
        socket = root / "socket"
        socket.mkdir(mode=0o700)
        data = root / "data"
        subprocess.run(
            [str(binary / "initdb"), "-D", str(data), "-A", "trust", "--no-locale", "-E", "UTF8"],
            check=True,
            capture_output=True,
            timeout=30,
        )
        options = (
            f"-k {socket} -h '' -p 55498 -c shared_buffers=16MB "
            "-c max_connections=12 -c unix_socket_permissions=0700"
        )
        subprocess.run(
            [
                str(binary / "pg_ctl"),
                "-D",
                str(data),
                "-l",
                str(root / "postgres.log"),
                "-o",
                options,
                "-w",
                "start",
            ],
            check=True,
            capture_output=True,
            timeout=30,
        )
        try:
            yield URL.create(
                "postgresql+psycopg",
                username=getpass.getuser(),
                database="postgres",
                query={"host": str(socket), "port": "55498"},
            )
        finally:
            subprocess.run(
                [str(binary / "pg_ctl"), "-D", str(data), "-m", "fast", "-w", "stop"],
                check=True,
                capture_output=True,
                timeout=30,
            )


def history(connection):
    root = Path(__file__).resolve().parents[3]
    specification = importlib.util.spec_from_file_location("knowledge_pg_migrate", root / "deploy/migrate.py")
    helper = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(helper)
    return helper.history_config("native", root / "deploy/migrations/native_versions", connection)


@pytest.fixture
def native18(owned_postgres):
    # Each case gets a new database; cluster teardown removes only its own files.
    name = "knowledge_" + uuid4().hex
    owner = create_engine(owned_postgres, isolation_level="AUTOCOMMIT")
    try:
        with owner.connect() as connection:
            connection.exec_driver_sql("CREATE DATABASE " + name)
    finally:
        owner.dispose()
    target = owned_postgres.set(database=name)
    engine = create_engine(target)
    try:
        with engine.begin() as connection:
            predecessor = MetaData()
            for entity in (Tenant, CatalogEntry, Membership, AuditEvent):
                entity.__table__.to_metadata(predecessor)
            predecessor.create_all(connection)
            connection.exec_driver_sql("INSERT INTO lattice_tenants VALUES ('retained','Retained',now())")
            connection.exec_driver_sql("CREATE TABLE koinon_agents (id VARCHAR(64) PRIMARY KEY)")
            connection.exec_driver_sql("INSERT INTO koinon_agents VALUES ('retained-agent')")
            connection.exec_driver_sql(
                "CREATE TABLE koinon_chat_runs (id VARCHAR(64) PRIMARY KEY, "
                "agent_id VARCHAR(64) REFERENCES koinon_agents(id), status VARCHAR(32))"
            )
            connection.exec_driver_sql(
                "INSERT INTO koinon_chat_runs VALUES ('retained-run','retained-agent','completed')"
            )
            configuration = history(connection)
            command.stamp(configuration, "koinon_0017_org_chat")
            before = connection.exec_driver_sql("SELECT id,agent_id,status FROM koinon_chat_runs").all()
            foreign_keys = inspect(connection).get_foreign_keys("koinon_chat_runs")
            command.upgrade(configuration, "koinon_0018_org_knowledge")
            assert connection.exec_driver_sql("SELECT version_num FROM koinon_native_version").scalar() == (
                "koinon_0018_org_knowledge"
            )
            assert (
                connection.exec_driver_sql("SELECT id,agent_id,status FROM koinon_chat_runs").all() == before
            )
            assert connection.exec_driver_sql("SELECT * FROM koinon_agents").all() == [("retained-agent",)]
            assert inspect(connection).get_foreign_keys("koinon_chat_runs") == foreign_keys
            assert connection.exec_driver_sql(
                "SELECT knowledge_settings_snapshot FROM koinon_chat_runs"
            ).all() == [(None,)]
            assert (
                connection.exec_driver_sql("SELECT * FROM koinon_organization_knowledge_settings").all() == []
            )
            assert "koinon_bulk_batches" not in inspect(connection).get_table_names()
        yield target
    finally:
        engine.dispose()


@pytest.fixture
async def pg_policy(native18):
    context = ApplicationContext(
        Config(
            {
                "pyfly": {
                    "banner": {"mode": "off"},
                    "data": {
                        "relational": {
                            "enabled": True,
                            "ddl-auto": "none",
                            "url": native18.set(drivername="postgresql+asyncpg").render_as_string(
                                hide_password=False
                            ),
                        }
                    },
                }
            }
        )
    )
    context.container.register_instance(CanonSettings, CanonSettings())
    context.container.register_instance(FlyquerySettings, FlyquerySettings())
    for package in ("koinon.catalog", "koinon.organization_knowledge"):
        scan_package(package, context.container)
    await context.start()
    try:
        for tenant, actor in (("north", "admin"), ("south", "outside")):
            await context.get_bean(TenantRepository).save(Tenant(id=tenant, name=tenant))
            await context.get_bean(MembershipRepository).save(
                Membership(id=actor, subject=actor, tenant_id=tenant, role="admin")
            )
        yield SimpleNamespace(
            context=context,
            service=context.get_bean(OrganizationKnowledgeService),
            datasource=context.get_bean(DataSourceRegistry).get("primary"),
        )
    finally:
        await context.stop()


def policy(revision=0, iterations=4):
    return OrganizationKnowledgeSettingsInput.model_validate(
        input_policy()
        | {"expected_revision": revision, "documents": documents() | {"rlm_max_iters": iterations}}
    )


async def audits(fixture):
    async with infrastructure_unit(fixture.datasource, read_only=True) as session:
        return list(
            (
                await session.scalars(
                    select(AuditEvent).where(AuditEvent.action == "organization_knowledge.updated")
                )
            ).all()
        )


async def contested_write(fixture, revision):
    written, release = asyncio.Event(), asyncio.Event()
    pids = {}

    async def writer(index):
        async with infrastructure_unit(fixture.datasource) as session:
            await session.execute(text("SET LOCAL lock_timeout='8s'"))
            pids[index] = await session.scalar(text("SELECT pg_backend_pid()"))
            value = await fixture.service.update("admin", "north", policy(revision, 4 + index))
            if index == 0:
                written.set()
                await release.wait()
            return value

    first = asyncio.create_task(writer(0))
    second = None
    try:
        await asyncio.wait_for(written.wait(), 5)
        second = asyncio.create_task(writer(1))
        blocked = False
        for _ in range(160):
            if 1 in pids:
                assert pids[0] != pids[1]
                async with infrastructure_unit(fixture.datasource, read_only=True) as session:
                    blockers = await session.scalar(text("SELECT pg_blocking_pids(:pid)"), {"pid": pids[1]})
                if pids[0] in blockers:
                    blocked = True
                    break
            await asyncio.sleep(0.025)
        assert blocked, "The independent stale writer must block on the uncommitted PostgreSQL CAS winner"
    finally:
        release.set()
        tasks = [first] + ([second] if second else [])
        results = await asyncio.gather(*tasks, return_exceptions=True)
    assert isinstance(results[0], OrganizationKnowledgeSettings), results
    assert results[0].revision == revision + 1
    assert isinstance(results[1], ConflictException), results
    assert results[1].code == "ORGANIZATION_KNOWLEDGE_CHANGED"


def test_native18_real_postgres_preserves_history_fk_and_enforces_bounds(native18):
    engine = create_engine(native18)
    try:
        with engine.begin() as connection:
            insert = text("""INSERT INTO koinon_organization_knowledge_settings
                (tenant_id,schema_version,revision,documents,structured,updated_by,updated_at)
                VALUES (:tenant,:schema,:revision,'{}','{}','owner',now())""")
            for tenant, schema, revision, state, exception in (
                ("missing", 1, 1, "23503", IntegrityError),
                ("retained", 2, 1, "23514", IntegrityError),
                ("retained", 1, 0, "23514", IntegrityError),
                ("retained", 1, 2147483648, "22003", DataError),
            ):
                with pytest.raises(exception) as rejected, connection.begin_nested():
                    connection.execute(insert, {"tenant": tenant, "schema": schema, "revision": revision})
                assert rejected.value.orig.sqlstate == state
            connection.execute(insert, {"tenant": "retained", "schema": 1, "revision": 2147483647})
    finally:
        engine.dispose()


@pytest.mark.parametrize("revision", [0, 1])
async def test_postgres_independent_connections_cas_and_stale_audit_are_atomic(pg_policy, revision):
    fixture = pg_policy
    if revision:
        await fixture.service.update("admin", "north", policy())
    await contested_write(fixture, revision)
    saved = await fixture.service.get("admin", "north")
    assert saved.revision == revision + 1 and saved.documents.rlm_max_iters == 4
    before = [event.id for event in await audits(fixture)]
    with pytest.raises(ConflictException):
        await fixture.service.update("admin", "north", policy(revision, 13))
    assert [event.id for event in await audits(fixture)] == before
    assert len(before) == revision + 1
    for event in await audits(fixture):
        snapshot = OrganizationKnowledgeSnapshot.model_validate(event.details)
        assert snapshot.tenant_id == "north" and event.subject == "admin"
    assert await fixture.service.get("admin", "north") == saved


async def test_postgres_audit_failure_rolls_back_and_tenant_policy_stays_isolated(pg_policy, monkeypatch):
    fixture = pg_policy

    async def failure(*args, **kwargs):
        raise RuntimeError("Controlled audit failure")

    with monkeypatch.context() as patch:
        patch.setattr(fixture.service.catalog, "_audit", failure)
        with pytest.raises(RuntimeError, match="Controlled audit failure"):
            await fixture.service.update("admin", "north", policy())
    assert (await fixture.service.get("admin", "north")).revision == 0
    assert await audits(fixture) == []
    await fixture.service.update("admin", "north", policy())
    assert (await fixture.service.get("outside", "south")).revision == 0
    with pytest.raises(AccessDenied):
        await fixture.service.update("admin", "south", policy())
    async with infrastructure_unit(fixture.datasource, read_only=True) as session:
        assert await session.scalar(select(func.count()).select_from(OrganizationKnowledgeSetting)) == 1
