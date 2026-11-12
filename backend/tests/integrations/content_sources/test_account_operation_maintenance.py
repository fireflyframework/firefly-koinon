# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Account cleanup remains available without provider or validation activity."""

import asyncio
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from pyfly.context import ApplicationContext
from pyfly.core import Config
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from test_account_operation_postgres import account_database as account_database
from test_account_operation_postgres import operation

from koinon.catalog.entities import Tenant
from koinon.integrations.content_sources.account_operation_dtos import AccountOperationIdentity
from koinon.integrations.content_sources.account_operation_entities import SourceAccountOperation as Header
from koinon.integrations.content_sources.account_operation_entities import SourceAccountWaiter as Waiter
from koinon.integrations.content_sources.account_operation_maintenance import SourceAccountMaintenance
from koinon.integrations.content_sources.account_operation_repository import SourceAccountOperationRepository
from koinon.integrations.content_sources.configuration import register_source_accounts
from koinon.integrations.content_sources.credentials import SourceCredentialVault
from koinon.integrations.content_sources.lifecycle import SourceConnectionService
from koinon.security.authority import primary_authority
from koinon.workers.admission import WorkAdmission, WorkAdmissionSettings


def test_disabled_worker_resolves_account_cleanup_without_credentials():
    values = {"koinon": {"process": {"role": "worker"}, "content_sources": {"enabled": False}}}
    context = ApplicationContext(Config(values))
    admission = WorkAdmission(WorkAdmissionSettings())
    context.container.register_instance(WorkAdmission, admission)
    register_source_accounts(context, values, controllers=False)

    cleanup = context.get_bean_by_name("content_sources.account_maintenance")
    assert cleanup.admission is admission
    assert not context.container.contains_type(SourceCredentialVault)
    assert not context.container.contains_type(SourceConnectionService)


def test_api_process_does_not_register_account_cleanup():
    values = {"koinon": {"process": {"role": "api"}}}
    context = ApplicationContext(Config(values))
    register_source_accounts(context, values, controllers=True)
    assert not context.container.contains_type(SourceAccountMaintenance)


@pytest.fixture
async def maintenance(account_database):
    url = account_database.set(drivername="postgresql+asyncpg").render_as_string(hide_password=False)
    context = ApplicationContext(
        Config(
            {
                "pyfly": {
                    "banner": {"mode": "off"},
                    "data": {"relational": {"enabled": True, "ddl-auto": "none", "url": url}},
                }
            }
        )
    )
    context.register_bean(SourceAccountOperationRepository)
    await context.start()
    engine = create_async_engine(url)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    cleanup = SourceAccountMaintenance(
        context.get_bean(SourceAccountOperationRepository), WorkAdmission(WorkAdmissionSettings())
    )
    try:
        yield cleanup, sessions
    finally:
        await context.stop()
        await engine.dispose()


async def seed_tenant(sessions, *, suffix="", count=1):
    tenant = "maintenance_" + uuid4().hex + suffix
    async with sessions.begin() as session:
        session.add(Tenant(id=tenant, name="Maintenance test"))
        await session.flush()
        session.add_all(
            [
                Header(tenant_id=tenant, account_key=n.to_bytes(32), last_used_at=datetime.now(UTC))
                for n in range(count)
            ]
        )
    return tenant


@pytest.mark.integration
async def test_cleanup_reclaims_idle_accounts_without_validation_rows_and_preserves_live_holder(maintenance):
    cleanup, sessions = maintenance
    tenant = await seed_tenant(sessions, count=2)
    identity = AccountOperationIdentity(tenant_id=tenant, account_key=(0).to_bytes(32))
    async with sessions.begin() as session:
        lease = await SourceAccountOperationRepository(session=session).try_acquire(
            identity, operation("live")
        )
    await cleanup.cleanup()
    async with sessions() as session:
        rows = (await session.scalars(select(Header).where(Header.tenant_id == tenant))).all()
        assert len(rows) == 1 and rows[0].token == lease.token
        assert (
            await session.scalar(select(func.count()).select_from(Waiter).where(Waiter.tenant_id == tenant))
            == 1
        )


@pytest.mark.integration
async def test_cleanup_transaction_changes_at_most_one_thousand_rows(maintenance):
    cleanup, sessions = maintenance
    tenant = await seed_tenant(sessions, count=1001)
    async with primary_authority(read_only=False):
        assert await cleanup.records.cleanup_tenant(tenant) == 1000
    async with sessions() as session:
        assert (
            await session.scalar(select(func.count()).select_from(Header).where(Header.tenant_id == tenant))
            == 1
        )


@pytest.mark.integration
async def test_locked_tenant_does_not_starve_next_tenant_and_cursor_wraps(maintenance, caplog):
    cleanup, sessions = maintenance
    first, second = sorted([await seed_tenant(sessions), await seed_tenant(sessions)])
    cleanup._after = first[:-1]
    async with sessions.begin() as locked:
        await locked.scalar(select(Tenant).where(Tenant.id == first).with_for_update())
        await cleanup.cleanup()
        assert sum(record.message == "source_account_tenant_cleanup_failed" for record in caplog.records) == 1
        async with sessions() as session:
            assert await session.scalar(select(Header.tenant_id).where(Header.tenant_id == first)) == first
            assert await session.scalar(select(Header.tenant_id).where(Header.tenant_id == second)) is None
    await cleanup.cleanup()
    async with sessions() as session:
        assert await session.scalar(select(Header.tenant_id).where(Header.tenant_id == first)) is None


@pytest.mark.integration
async def test_expired_holder_keeps_quarantine_during_cleanup(maintenance):
    cleanup, sessions = maintenance
    tenant = await seed_tenant(sessions)
    identity = AccountOperationIdentity(tenant_id=tenant, account_key=(0).to_bytes(32))
    expiry = datetime.now(UTC) - timedelta(seconds=1)
    async with sessions.begin() as session:
        records = SourceAccountOperationRepository(session=session)
        await records.try_acquire(identity, operation("expired"))
        row = await session.get(Header, (tenant, identity.account_key))
        row.expires_at, row.started_at = expiry, expiry - timedelta(seconds=150)
    await cleanup.cleanup()
    async with sessions() as session:
        row = await session.get(Header, (tenant, identity.account_key))
        assert row is not None and row.token is None
        assert row.quarantine_until == expiry + timedelta(seconds=30)
        assert (
            await session.scalar(select(func.count()).select_from(Waiter).where(Waiter.tenant_id == tenant))
            == 0
        )


@pytest.mark.integration
async def test_cancellation_during_admission_leaves_data_and_releases_overlap_guard(maintenance):
    cleanup, sessions = maintenance
    tenant = await seed_tenant(sessions)
    holding, release = asyncio.Event(), asyncio.Event()

    async def occupy_capacity():
        async with cleanup.admission.hold("bulk"):
            holding.set()
            await release.wait()

    holder = asyncio.create_task(occupy_capacity())
    await holding.wait()
    task = asyncio.create_task(cleanup.cleanup())
    started = asyncio.Event()
    asyncio.get_running_loop().call_soon(started.set)
    await started.wait()
    try:
        assert cleanup.admission.worker_waiting == 1
        assert await cleanup.cleanup() == 0
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert cleanup.admission.worker_waiting == 0
        async with sessions() as session:
            assert await session.scalar(select(Header.tenant_id).where(Header.tenant_id == tenant)) == tenant
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        release.set()
        await holder
    await cleanup.cleanup()
    async with sessions() as session:
        assert await session.scalar(select(Header.tenant_id).where(Header.tenant_id == tenant)) is None


@pytest.mark.integration
async def test_total_deadline_includes_waiting_for_admission(maintenance, monkeypatch):
    cleanup, sessions = maintenance
    tenant = await seed_tenant(sessions)
    holding, release = asyncio.Event(), asyncio.Event()

    async def occupy_capacity():
        async with cleanup.admission.hold("bulk"):
            holding.set()
            await release.wait()

    holder = asyncio.create_task(occupy_capacity())
    await holding.wait()
    real_timeout = asyncio.timeout

    def elapsed_deadline(delay):
        timer = real_timeout(delay)
        # Advance the external timer deterministically after entry; no real-time sleep.
        asyncio.get_running_loop().call_soon(timer.reschedule, asyncio.get_running_loop().time() - 1)
        return timer

    try:
        with monkeypatch.context() as timing:
            timing.setattr(asyncio, "timeout", elapsed_deadline)
            assert await cleanup.cleanup() == 0
        assert cleanup.admission.worker_waiting == 0
        async with sessions() as session:
            assert await session.scalar(select(Header.tenant_id).where(Header.tenant_id == tenant)) == tenant
    finally:
        release.set()
        await holder


@pytest.mark.integration
async def test_tenant_round_continues_after_ten_candidates_and_restart_is_safe(maintenance):
    cleanup, sessions = maintenance
    tenants = sorted([await seed_tenant(sessions) for _ in range(12)])
    cleanup._after = tenants[0][:-1]
    # Keep these tenants present; only the final one is eligible for deletion.
    async with sessions.begin() as session:
        for tenant in tenants[:-1]:
            await SourceAccountOperationRepository(session=session).try_acquire(
                AccountOperationIdentity(tenant_id=tenant, account_key=(0).to_bytes(32)), operation("live")
            )
    await cleanup.cleanup()
    async with sessions() as session:
        assert (
            await session.scalar(select(Header.tenant_id).where(Header.tenant_id == tenants[-1]))
            == tenants[-1]
        )
    await cleanup.cleanup()
    async with sessions() as session:
        assert await session.scalar(select(Header.tenant_id).where(Header.tenant_id == tenants[-1])) is None
        assert (
            await session.scalar(
                select(func.count()).select_from(Header).where(Header.tenant_id.in_(tenants))
            )
            == 11
        )
    restarted = SourceAccountMaintenance(cleanup.records, cleanup.admission)
    await restarted.cleanup()
    async with sessions() as session:
        assert (
            await session.scalar(
                select(func.count()).select_from(Header).where(Header.tenant_id.in_(tenants))
            )
            == 11
        )
