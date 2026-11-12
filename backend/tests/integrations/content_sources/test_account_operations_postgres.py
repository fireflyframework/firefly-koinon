# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Shared account capacity surrounds actual worker pages and checkpoint writes."""

import asyncio
from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest
from pyfly.kernel import ConflictException
from test_sync_worker import empty_listing as empty_listing
from test_sync_worker import lifecycle as lifecycle
from test_sync_worker import review as review
from test_sync_worker import source_database as source_database
from test_sync_worker import worker as worker

from koinon.integrations.content_sources.account_operation_dtos import (
    AccountOperationBusy,
    AccountOperationRequest,
)
from koinon.integrations.content_sources.account_operation_entities import SourceAccountOperation
from koinon.integrations.content_sources.account_operations import AccountOperationPermit, SourceAccountBusy
from koinon.integrations.content_sources.errors import SourceError
from koinon.integrations.content_sources.lifecycle import _no_remote_unit
from koinon.integrations.content_sources.mapping_entities import SourceMapping
from koinon.integrations.content_sources.sync_entities import SourceSyncRun
from koinon.security.authority import primary_authority

pytestmark = pytest.mark.integration


async def request_for(worker, name):
    async with primary_authority(fresh=True):
        session = worker.mappings.controls._require_session()
        run = await session.get(SourceSyncRun, worker.run_id)
        mapping = await session.get(SourceMapping, worker.mapping_id)
        return AccountOperationRequest(
            kind="validation",
            operation_id=name,
            revision=1,
            connection_id=mapping.connection_id,
            connection_revision=run.connection_revision,
            owner="issuer|alice",
            process_instance_id=name,
        )


@pytest.mark.parametrize("lifecycle", ["postgres"], indirect=True)
async def test_busy_account_does_not_enumerate_or_advance_worker_checkpoint(worker):
    accounts = worker.worker.accounts
    holder = await accounts.acquire("tenant", await request_for(worker, "validation"))
    assert isinstance(holder, AccountOperationPermit)
    worker.pages.append(worker.page(0, 1))
    try:
        with pytest.raises(SourceAccountBusy) as failure:
            await worker.worker.run_once("tenant", "issuer|alice", worker.run_id)
        assert 1 <= failure.value.retry_after_seconds <= 30
        assert worker.calls == []
        async with primary_authority(fresh=True):
            session = worker.mappings.controls._require_session()
            run = await session.get(SourceSyncRun, worker.run_id)
            assert run.page_sequence == 0 and not run.enumeration_complete
    finally:
        await accounts.abort(holder)


@pytest.mark.parametrize("lifecycle", ["postgres"], indirect=True)
async def test_expired_clean_finish_rolls_back_checkpoint_after_initial_fence(worker):
    accounts = worker.worker.accounts
    holder = await accounts.acquire("tenant", await request_for(worker, "expiry"))
    assert isinstance(holder, AccountOperationPermit)
    async with accounts.remote(holder):
        _no_remote_unit()
    failure = None
    try:
        try:
            async with primary_authority(read_only=False, fresh=True):
                session = worker.mappings.controls._require_session()
                await accounts.assert_current(holder, session)
                run = await session.get(SourceSyncRun, worker.run_id)
                run.page_sequence += 1
                header = await session.get(
                    SourceAccountOperation,
                    (holder.lease.identity.tenant_id, holder.lease.identity.account_key),
                )
                # Persist an exact expired holder without a wall-clock sleep.
                expires = datetime.now(UTC) - timedelta(seconds=1)
                started = expires - timedelta(seconds=150)
                header.started_at, header.expires_at = started, expires
                await session.flush()
                expired = replace(
                    holder,
                    lease=holder.lease.model_copy(
                        update={
                            "started_at": started,
                            "expires_at": expires,
                        }
                    ),
                )
                await accounts.finish(expired, session)
        except ConflictException as error:
            failure = error.code
        async with primary_authority(fresh=True):
            session = worker.mappings.controls._require_session()
            run = await session.get(SourceSyncRun, worker.run_id)
            assert run.page_sequence == 0, "Expired account finish committed the page checkpoint"
        assert failure == "SOURCE_ACCOUNT_LEASE_LOST"
    finally:
        await accounts.abort(holder)


@pytest.mark.parametrize("lifecycle", ["postgres"], indirect=True)
@pytest.mark.parametrize("code", ["access_denied", "timeout", "transport_error", "unavailable"])
async def test_only_confirmed_read_failure_releases_account_without_quarantine(worker, code):
    accounts = worker.worker.accounts
    request = await request_for(worker, "validation")
    holder = await accounts.acquire("tenant", request)
    assert isinstance(holder, AccountOperationPermit)
    with pytest.raises(SourceError) as failure:
        async with accounts.remote(holder):
            raise SourceError(code)
    assert failure.value.code == code
    await accounts.abort(holder)
    following = await accounts.acquire("tenant", request.model_copy(update={"operation_id": "next"}))
    if code == "access_denied":
        assert isinstance(following, AccountOperationPermit)
        await accounts.abort(following)
    else:
        assert isinstance(following, AccountOperationBusy)


@pytest.mark.parametrize("lifecycle", ["postgres"], indirect=True)
async def test_account_permit_is_task_bound_and_checkpoint_finish_is_atomic(worker):
    accounts = worker.worker.accounts
    request = await request_for(worker, "validation")
    holder = await accounts.acquire("tenant", request)
    assert isinstance(holder, AccountOperationPermit)
    async with accounts.remote(holder):
        _no_remote_unit()

    async def foreign_task():
        with pytest.raises(ConflictException) as failure:
            async with accounts.remote(holder):
                pytest.fail("Foreign task obtained remote admission")
        return failure.value.code

    assert await asyncio.create_task(foreign_task()) == "SOURCE_ACCOUNT_LEASE_LOST"
    try:
        with pytest.raises(RuntimeError, match="rollback"):
            async with primary_authority(read_only=False, fresh=True):
                session = worker.mappings.controls._require_session()
                await accounts.assert_current(holder, session)
                assert await accounts.finish(holder, session)
                raise RuntimeError("rollback")
        contender = request.model_copy(update={"operation_id": "second"})
        assert isinstance(await accounts.acquire("tenant", contender), AccountOperationBusy)
        async with primary_authority(read_only=False, fresh=True):
            session = worker.mappings.controls._require_session()
            await accounts.assert_current(holder, session)
            assert await accounts.finish(holder, session)
        next_holder = await accounts.acquire("tenant", contender)
        assert isinstance(next_holder, AccountOperationPermit)
        assert next_holder.lease.fence > holder.lease.fence
        await accounts.abort(next_holder)
    finally:
        await accounts.abort(holder)
