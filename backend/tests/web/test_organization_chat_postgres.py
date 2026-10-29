# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Opt-in native17 migration and CAS proof on a newly restored, dedicated PostgreSQL database."""

import asyncio
import importlib.util
import json
import os
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest
from alembic import command
from pyfly.container.scanner import scan_package
from pyfly.context import ApplicationContext
from pyfly.core import Config
from pyfly.data.relational.datasource_registry import DataSourceRegistry
from pyfly.data.transaction import infrastructure_unit
from pyfly.kernel import ConflictException
from sqlalchemy import create_engine, func, inspect, select, text, update
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError

from koinon.assistants.entities import AgentConfiguration, Provider
from koinon.assistants.repositories import AgentRepository, ProviderRepository
from koinon.catalog.entities import AuditEvent, Membership, Tenant
from koinon.catalog.repositories import MembershipRepository, TenantRepository
from koinon.organization_chat.entities import OrganizationChatSetting
from koinon.organization_chat.service import OrganizationChatService

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not os.getenv("KOINON_ORGANIZATION_CHAT_POSTGRES_URL"), reason="new dedicated PostgreSQL restore"
    ),
]
OBSERVATIONS: list[dict] = []


def target_url():
    target = make_url(os.environ["KOINON_ORGANIZATION_CHAT_POSTGRES_URL"])
    if not (
        target.host == "127.0.0.1"
        and target.port == 18783
        and (target.database or "").startswith("koinon_org_chat_qualification_")
    ):
        pytest.fail("Organization chat PostgreSQL proof requires its newly restored dedicated database")
    return target


def fingerprint(connection, table):
    return connection.execute(
        text(
            f"SELECT count(*),md5(coalesce(string_agg(md5(row_to_json(retained)::text),'' "
            f"ORDER BY id),'')) FROM {table} retained"
        )
    ).one()


@pytest.fixture(scope="module")
def native17():
    target = target_url()
    root = Path(__file__).resolve().parents[3]
    specification = importlib.util.spec_from_file_location(
        "org_chat_migration_helper", root / "deploy/migrate.py"
    )
    helper = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(helper)
    engine = create_engine(target.set(drivername="postgresql+psycopg"))
    try:
        with engine.connect() as connection:
            assert connection.scalar(text("SELECT current_database()")) == target.database
            assert connection.scalar(text("SELECT version_num FROM koinon_native_version")) == (
                "koinon_0016_authorized_apps"
            ), "Use a new dedicated restore at explicit native16 for each qualification run"
            assert "koinon_organization_chat_settings" not in inspect(connection).get_table_names()
            before = {name: fingerprint(connection, name) for name in ("koinon_agents", "koinon_chat_runs")}
            assert all(value[0] > 0 for value in before.values()), (
                "Restore must retain existing agents and runs"
            )
            related = connection.scalar(
                text("SELECT count(*) FROM koinon_chat_runs r JOIN koinon_agents a ON a.id=r.agent_id")
            )
            assert related == before["koinon_chat_runs"][0]
            connection.execute(text("SET lock_timeout='10s'"))
            connection.execute(text("SELECT pg_advisory_lock(hashtext('koinon-schema-migrations'))"))
            connection.commit()
            try:
                configuration = helper.history_config(
                    "native", root / "deploy/migrations/native_versions", connection
                )
                command.upgrade(configuration, "koinon_0017_org_chat")
                connection.commit()
            finally:
                connection.rollback()
                connection.execute(text("SELECT pg_advisory_unlock(hashtext('koinon-schema-migrations'))"))
                connection.commit()
            assert connection.scalar(text("SELECT version_num FROM koinon_native_version")) == (
                "koinon_0017_org_chat"
            )
            after = {name: fingerprint(connection, name) for name in before}
            assert after == before
            assert (
                connection.scalar(
                    text("SELECT count(*) FROM koinon_chat_runs r JOIN koinon_agents a ON a.id=r.agent_id")
                )
                == related
            )
            tables = inspect(connection).get_table_names()
            assert "koinon_bulk_batches" not in tables
            foreign_keys = inspect(connection).get_foreign_keys("koinon_chat_runs")
            assert any(
                fk["constrained_columns"] == ["agent_id"] and fk["referred_table"] == "koinon_agents"
                for fk in foreign_keys
            )
            assert connection.scalar(text("SELECT count(*) FROM koinon_organization_chat_settings")) == 0
            OBSERVATIONS.append(
                dict(
                    case="native17_restored_migration",
                    initial_revision="koinon_0016_authorized_apps",
                    final_revision="koinon_0017_org_chat",
                    retained_agent_count=before["koinon_agents"][0],
                    retained_run_count=before["koinon_chat_runs"][0],
                    retained_row_hashes_unchanged=True,
                    run_agent_foreign_key_preserved=True,
                    bulk18_absent=True,
                )
            )
        return target
    finally:
        engine.dispose()


@pytest.fixture
async def pg_settings(native17, monkeypatch):
    from pyfly.agentic.models import ModelFactory

    monkeypatch.setattr(
        ModelFactory,
        "build_with_secret",
        lambda *args, **kwargs: pytest.fail(
            "Provider/model calls are forbidden in PostgreSQL settings proof"
        ),
    )
    context = ApplicationContext(
        Config(
            {
                "pyfly": {
                    "banner": {"mode": "off"},
                    "agentic": {"enabled": True},
                    "eda": {"provider": "memory"},
                    "data": {
                        "relational": {
                            "enabled": True,
                            "ddl-auto": "none",
                            "url": native17.set(drivername="postgresql+asyncpg").render_as_string(
                                hide_password=False
                            ),
                        }
                    },
                },
            }
        )
    )
    for package in ("koinon.catalog", "koinon.assistants", "koinon.organization_chat"):
        scan_package(package, context.container)
    await context.start()
    try:
        tenant, other = "pg-org-" + uuid4().hex, "pg-other-" + uuid4().hex
        subjects = ["fictional-pg-org|" + uuid4().hex for _ in range(2)]
        for identifier in (tenant, other):
            await context.get_bean(TenantRepository).save(
                Tenant(id=identifier, name="Fictional PostgreSQL proof")
            )
        for subject in subjects:
            await context.get_bean(MembershipRepository).save(
                Membership(id=uuid4().hex, subject=subject, tenant_id=tenant, role="admin")
            )
        agents = []
        for selected_tenant in (tenant, other):
            provider = await context.get_bean(ProviderRepository).save(
                Provider(
                    id=uuid4().hex,
                    tenant_id=selected_tenant,
                    name="No-call PostgreSQL fixture",
                    kind="ollama",
                    api="chat",
                    base_url="http://127.0.0.1:1",
                    model_ids=["fictional-model"],
                )
            )
            agents.append(
                await context.get_bean(AgentRepository).save(
                    AgentConfiguration(
                        id=uuid4().hex,
                        tenant_id=selected_tenant,
                        provider_id=provider.id,
                        name="No-call PostgreSQL agent",
                        model_id="fictional-model",
                        tools=[],
                        scope={},
                    )
                )
            )
        yield SimpleNamespace(
            context=context,
            datasource=context.get_bean(DataSourceRegistry).get("primary"),
            service=context.get_bean(OrganizationChatService),
            tenant=tenant,
            subjects=subjects,
            agents=agents,
        )
    finally:
        await context.stop()


def test_postgres_native17_migration_preserves_retained_agent_run_rows_and_foreign_key(native17):
    assert OBSERVATIONS[0]["retained_row_hashes_unchanged"]
    assert OBSERVATIONS[0]["bulk18_absent"]


async def audit_count(fixture):
    async with infrastructure_unit(fixture.datasource, read_only=True) as session:
        return await session.scalar(
            select(func.count())
            .select_from(AuditEvent)
            .where(AuditEvent.tenant_id == fixture.tenant, AuditEvent.action == "organization_chat.updated")
        )


async def test_postgres_composite_default_foreign_key_rejects_another_tenant(pg_settings):
    fixture = pg_settings
    current = await fixture.service.update(fixture.subjects[0], fixture.tenant, fixture.agents[0].id, 0)
    assert current["default_agent_id"] == fixture.agents[0].id
    with pytest.raises(IntegrityError) as rejected:
        async with infrastructure_unit(fixture.datasource) as session:
            await session.execute(
                update(OrganizationChatSetting)
                .where(OrganizationChatSetting.tenant_id == fixture.tenant)
                .values(default_agent_id=fixture.agents[1].id)
            )
    assert rejected.value.orig.sqlstate == "23503"
    assert (await fixture.service.get(fixture.subjects[0], fixture.tenant)) == current
    assert await audit_count(fixture) == 1
    OBSERVATIONS.append(dict(case="composite_tenant_agent_foreign_key", rejected_sqlstate="23503"))


async def concurrent_writers(fixture, revision):
    written, release = asyncio.Event(), asyncio.Event()
    pids = {}

    async def writer(index):
        async with infrastructure_unit(fixture.datasource) as session:
            await session.execute(text("SET LOCAL lock_timeout='8s'"))
            pids[index] = await session.scalar(text("SELECT pg_backend_pid()"))
            result = await fixture.service.update(
                fixture.subjects[index], fixture.tenant, fixture.agents[0].id if index else None, revision
            )
            if index == 0:
                written.set()
                await release.wait()
            return result

    first = asyncio.create_task(writer(0))
    await asyncio.wait_for(written.wait(), 5)
    second = asyncio.create_task(writer(1))
    try:
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
        assert blocked, "Second independent PostgreSQL connection must wait for the uncommitted CAS winner"
    finally:
        release.set()
        results = await asyncio.gather(first, second, return_exceptions=True)
    assert isinstance(results[0], dict) and results[0]["revision"] == revision + 1, results
    assert isinstance(results[1], ConflictException), results
    OBSERVATIONS.append(
        dict(
            case="first_create_cas" if revision == 0 else "revision_update_cas",
            independent_connections=True,
            conflicting_writer_blocked=True,
            winner_count=1,
            conflict_count=1,
        )
    )


async def test_postgres_first_create_cas_serializes_connections_and_stale_writer_has_no_audit(pg_settings):
    fixture = pg_settings
    await concurrent_writers(fixture, 0)
    assert await audit_count(fixture) == 1
    with pytest.raises(ConflictException):
        await fixture.service.update(fixture.subjects[1], fixture.tenant, fixture.agents[0].id, 0)
    assert await audit_count(fixture) == 1
    current = await fixture.service.get(fixture.subjects[0], fixture.tenant)
    assert current["revision"] == 1 and current["default_agent_id"] is None


async def test_postgres_update_cas_serializes_connections_and_stale_writer_has_no_audit(pg_settings):
    fixture = pg_settings
    await fixture.service.update(fixture.subjects[0], fixture.tenant, fixture.agents[0].id, 0)
    await concurrent_writers(fixture, 1)
    assert await audit_count(fixture) == 2
    with pytest.raises(ConflictException):
        await fixture.service.update(fixture.subjects[1], fixture.tenant, fixture.agents[0].id, 1)
    assert await audit_count(fixture) == 2
    async with infrastructure_unit(fixture.datasource, read_only=True) as session:
        stored = await session.get(OrganizationChatSetting, fixture.tenant)
        assert stored.revision == 2 and stored.default_agent_id is None
        assert stored.updated_by == fixture.subjects[0] and stored.updated_at.tzinfo is not None
        events = list(
            (
                await session.scalars(
                    select(AuditEvent).where(
                        AuditEvent.tenant_id == fixture.tenant,
                        AuditEvent.action == "organization_chat.updated",
                    )
                )
            ).all()
        )
        assert all(event.subject == fixture.subjects[0] for event in events)


def teardown_module():
    destination = os.getenv("KOINON_ORGANIZATION_CHAT_POSTGRES_EVIDENCE")
    if destination:
        target = Path(destination)
        target.write_text(json.dumps(OBSERVATIONS, indent=2) + "\n")
        target.chmod(0o600)
