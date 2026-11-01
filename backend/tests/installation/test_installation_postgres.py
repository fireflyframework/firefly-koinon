# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Opt-in, owned PostgreSQL proof of the actual operator/runtime authority boundary."""

import asyncio
import importlib.util
import os
from pathlib import Path
from uuid import uuid4

import psycopg
import pytest
from psycopg import sql
from pyfly.context import ApplicationContext
from pyfly.core import Config
from pyfly.data.relational.sqlalchemy import Base
from pyfly.data.transaction import TransactionTemplate
from sqlalchemy import create_engine, func, select
from test_installation_manifest import example

from koinon.catalog.entities import Tenant
from koinon.communications.entities import InstallationRecord
from koinon.installation.authority import InstallationAdmissions, InstallationError
from koinon.installation.dtos import InstallationPlan
from koinon.installation.entities import InstallationRun
from koinon.installation.repositories import InstallationRepository

pytestmark = pytest.mark.integration


@pytest.fixture
def pg():
    uri = os.environ.get("KOINON_INSTALLATION_TEST_PG_URL")
    if not uri:
        pytest.skip("Requires an explicitly owned PostgreSQL fixture")
    name = "installation_" + uuid4().hex[:16]
    role = "runtime_" + uuid4().hex[:16]
    with psycopg.connect(uri, autocommit=True) as connection:
        connection.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
        connection.execute(sql.SQL("CREATE ROLE {} LOGIN").format(sql.Identifier(role)))
    from sqlalchemy.engine import make_url

    url = make_url(uri).set(database=name)
    owner = str(url.set(drivername="postgresql+psycopg"))
    engine = create_engine(owner)
    Base.metadata.create_all(engine, tables=[Tenant.__table__, InstallationRecord.__table__])
    from alembic.migration import MigrationContext
    from alembic.operations import Operations

    migration_path = Path(__file__).parents[3] / "deploy/migrations/native_versions/0036_installation.py"
    migration_spec = importlib.util.spec_from_file_location("installation_migration", migration_path)
    migration = importlib.util.module_from_spec(migration_spec)
    migration_spec.loader.exec_module(migration)
    with engine.begin() as connection, Operations.context(MigrationContext.configure(connection)):
        migration.upgrade()
    with engine.begin() as connection:
        connection.execute(Tenant.__table__.insert().values(id="example", name="Example"))
    with psycopg.connect(str(url), autocommit=True) as connection:
        connection.execute(sql.SQL("GRANT USAGE ON SCHEMA public TO {}").format(sql.Identifier(role)))
        connection.execute(
            sql.SQL("GRANT ALL ON ALL TABLES IN SCHEMA public TO {}").format(sql.Identifier(role))
        )
        spec = importlib.util.spec_from_file_location(
            "installation_role_provisioner", Path(__file__).parents[3] / "deploy/provision_roles.py"
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        module.grant_table(connection, "koinon_installation_runs", role)
    engine.dispose()
    return url, role


async def context_for(url):
    context = ApplicationContext(
        Config(
            {
                "pyfly": {
                    "banner": {"mode": "off"},
                    "data": {
                        "relational": {
                            "enabled": True,
                            "ddl-auto": "none",
                            "url": str(url.set(drivername="postgresql+asyncpg")),
                        }
                    },
                }
            }
        )
    )
    for cls in (InstallationRepository, InstallationAdmissions):
        context.register_bean(cls)
    await context.start()
    return context


async def test_runtime_cannot_admit_or_directly_mutate_ledger_before_any_identity_write(pg):
    url, role = pg
    context = await context_for(url.set(username=role))
    try:
        with pytest.raises(InstallationError, match="INSTALLATION_OPERATOR_REQUIRED"):
            await context.get_bean(InstallationAdmissions).admit(
                InstallationPlan.model_validate(example()), resume=False
            )
    finally:
        await context.stop()
    with (
        psycopg.connect(str(url.set(username=role))) as connection,
        pytest.raises(psycopg.errors.InsufficientPrivilege),
    ):
        connection.execute("DELETE FROM public.koinon_installation_runs")
    engine = create_engine(str(url.set(drivername="postgresql+psycopg")))
    with engine.connect() as connection:
        assert connection.scalar(select(func.count()).select_from(InstallationRecord)) == 0
        assert connection.scalar(select(func.count()).select_from(InstallationRun)) == 0
    engine.dispose()


async def test_partial_requires_explicit_resume_fences_old_owner_and_preserves_receipts(pg):
    url, _ = pg
    context = await context_for(url)
    try:
        admission = context.get_bean(InstallationAdmissions)
        plan = InstallationPlan.model_validate(example())
        first = await admission.admit(plan, resume=False)
        async with TransactionTemplate("primary").transaction():
            await admission.checkpoint(first, "provider:chat", {"resource_id": "owned", "status": "done"})
        await admission.fail(first)
        with pytest.raises(InstallationError, match="INSTALLATION_RESUME_REQUIRED"):
            await admission.admit(plan, resume=False)
        second = await admission.admit(plan, resume=True)
        assert second.generation == first.generation + 1
        with pytest.raises(InstallationError, match="INSTALLATION_LEASE_LOST"):
            await admission.renew(first)
        async with TransactionTemplate("primary").transaction():
            with pytest.raises(InstallationError, match="INSTALLATION_CHECKPOINT_CONFLICT"):
                await admission.checkpoint(
                    second, "provider:chat", {"resource_id": "retargeted", "status": "done"}
                )
        receipt = await admission.receipt(second)
        assert receipt["checkpoints"]["provider:chat"]["resource_id"] == "owned"
        await admission.finish(second)
        replay = await admission.admit(plan, resume=False)
        assert replay.completed
        assert (await admission.receipt(replay))["status"] == "completed"
        changed = example()
        changed["agent"]["name"] = "Changed"
        with pytest.raises(InstallationError, match="INSTALLATION_PLAN_CONFLICT"):
            await admission.admit(InstallationPlan.model_validate(changed), resume=True)
    finally:
        await context.stop()
    with psycopg.connect(str(url)) as connection:
        for statement in (
            "DELETE FROM public.koinon_installation_runs",
            "TRUNCATE public.koinon_installation_runs",
        ):
            with pytest.raises(psycopg.errors.IntegrityConstraintViolation):
                connection.execute(statement)
            connection.rollback()


async def test_concurrent_first_admission_has_only_one_live_operator_owner(pg):
    url, _ = pg
    context = await context_for(url)
    try:
        service = context.get_bean(InstallationAdmissions)
        plan = InstallationPlan.model_validate(example())
        values = await asyncio.gather(
            *(service.admit(plan, resume=False) for _ in range(2)), return_exceptions=True
        )
        assert sum(not isinstance(value, BaseException) for value in values) == 1
        assert [value.code for value in values if isinstance(value, InstallationError)] == [
            "INSTALLATION_IN_PROGRESS"
        ]
    finally:
        await context.stop()


async def test_operator_writes_use_native_encryption_catalog_and_default_without_membership(pg):
    import base64

    from flycanon.config import CanonSettings
    from flyquery.config import FlyquerySettings
    from pydantic import SecretStr
    from pyfly.container.scanner import scan_package

    from koinon.assistants.entities import AgentConfiguration, Provider
    from koinon.assistants.repositories import ProviderRepository
    from koinon.catalog.entities import AuditEvent, CatalogEntry, Membership
    from koinon.installation.writes import NativeInstallationWrites
    from koinon.knowledge.connections.entities import KnowledgeConnection
    from koinon.knowledge.connections.repositories import KnowledgeConnectionRepository
    from koinon.knowledge.connections.service import KnowledgeConnectionService
    from koinon.organization_chat.entities import OrganizationChatSetting
    from koinon.organization_chat.repositories import OrganizationChatRepository

    url, _ = pg
    engine = create_engine(str(url.set(drivername="postgresql+psycopg")))
    Base.metadata.create_all(
        engine,
        tables=[
            CatalogEntry.__table__,
            Membership.__table__,
            AuditEvent.__table__,
            Provider.__table__,
            AgentConfiguration.__table__,
            KnowledgeConnection.__table__,
            OrganizationChatSetting.__table__,
        ],
    )
    engine.dispose()
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
                            "url": str(url.set(drivername="postgresql+asyncpg")),
                        }
                    },
                },
                "koinon": {
                    "assistants": {
                        "master_key": base64.urlsafe_b64encode(b"k" * 32).decode(),
                        "allowed_provider_hosts": ["api.openai.com"],
                    }
                },
            }
        )
    )
    context.container.register_instance(CanonSettings, CanonSettings(answer_mode="rag"))
    context.container.register_instance(FlyquerySettings, FlyquerySettings())
    for package in (
        "koinon.catalog",
        "koinon.organization_knowledge",
        "koinon.organization_branding",
        "koinon.assistants",
    ):
        scan_package(package, context.container)
    for cls in (
        InstallationRepository,
        InstallationAdmissions,
        NativeInstallationWrites,
        KnowledgeConnectionRepository,
        KnowledgeConnectionService,
        OrganizationChatRepository,
    ):
        context.register_bean(cls)
    await context.start()
    try:
        plan = InstallationPlan.model_validate(example())
        admissions = context.get_bean(InstallationAdmissions)
        writes = context.get_bean(NativeInstallationWrites)
        permit = await admissions.admit(plan, resume=False)
        for provider in plan.providers:
            await writes.provider(permit, provider, SecretStr("protected-inert-credential"))
        first = await writes.provider(permit, plan.providers[0], SecretStr("ignored-replay-value"))
        for key in plan.catalog_order():
            await writes.catalog_node(permit, next(value for value in plan.catalog if value.key == key))
        await writes.connection(permit, plan.connections[0])
        await writes.agent(permit, plan.agent)
        await writes.default_agent(permit, plan.agent.key)
        await writes.default_agent(permit, plan.agent.key)
        stored = await context.get_bean(ProviderRepository).find_by_id(first["resource_id"])
        assert b"protected-inert-credential" not in stored.secret_ciphertext
        async with TransactionTemplate("primary").transaction():
            from koinon.catalog.repositories import AuditRepository, CatalogRepository, MembershipRepository

            rows = await context.get_bean(CatalogRepository).find_all(tenant_id="example")
            assert {row.system_key for row in rows} == {"space", "project", "folder"}
            assert all(
                row.created_by == "system:installation" and row.installation_run_id == permit.run_id
                for row in rows
            )
            assert not await context.get_bean(MembershipRepository).find_all(tenant_id="example")
            assert all(
                row.subject == "system:installation"
                for row in await context.get_bean(AuditRepository).find_all(tenant_id="example")
            )
        await admissions.finish(permit)
    finally:
        await context.stop()
