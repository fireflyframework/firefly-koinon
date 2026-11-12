# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Private account scheduling with exact checkpoint fences and bounded remote work."""

import asyncio
import hashlib
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Literal

from pyfly.container import service
from pyfly.kernel import ConflictException, ServiceUnavailableException
from sqlalchemy import select, text

from koinon.integrations.content_sources.account_operation_dtos import (
    AccountOperationBusy,
    AccountOperationIdentity,
    AccountOperationLease,
    AccountOperationRequest,
)
from koinon.integrations.content_sources.account_operation_repository import SourceAccountOperationRepository
from koinon.integrations.content_sources.entities import PersonalSourceConnection
from koinon.integrations.content_sources.errors import SourceError
from koinon.integrations.content_sources.lifecycle import SourceConnectionService, _no_remote_unit
from koinon.integrations.content_sources.transport import source_operation_deadline
from koinon.security.authority import primary_authority


def account_identity(connection: PersonalSourceConnection) -> AccountOperationIdentity:
    """Hash verified persisted claims; local grant ownership never partitions capacity."""
    if not connection.issuer or not connection.external_subject:
        raise SourceError("reconnect_required")
    family = {"onedrive": "microsoft", "sharepoint": "microsoft", "google_drive": "google"}.get(
        connection.provider
    )
    if family is None:
        raise SourceError("reconnect_required")
    digest = hashlib.sha256(b"koinon.source-account-operation.v1\x00")
    for value in (
        connection.tenant_id,
        family,
        connection.issuer,
        connection.external_tenant,
        connection.external_subject,
    ):
        if value is None:
            digest.update(b"\x00")
        else:
            encoded = value.encode("utf-8")
            digest.update(b"\x01" + len(encoded).to_bytes(4, "big") + encoded)
    return AccountOperationIdentity(tenant_id=connection.tenant_id, account_key=digest.digest())


class SourceAccountBusy(ServiceUnavailableException):
    def __init__(self, retry_after_seconds: int):
        super().__init__("Source account is busy; retry later", code="SOURCE_ACCOUNT_BUSY")
        self.retry_after_seconds = retry_after_seconds


@dataclass(frozen=True, slots=True)
class AccountOperationPermit:
    lease: AccountOperationLease = field(repr=False)
    deadline: float
    task: asyncio.Task = field(repr=False)
    completion: "_RemoteCompletion" = field(default_factory=lambda: _RemoteCompletion(), repr=False)


@dataclass(slots=True)
class _RemoteCompletion:
    settled: bool = False


def _owned(permit: AccountOperationPermit) -> None:
    if permit.task is not asyncio.current_task():
        raise ConflictException("Account operation belongs to another task", code="SOURCE_ACCOUNT_LEASE_LOST")


@service(name="content_sources.account_operations")
class SourceAccountOperations:
    def __init__(self, connections: SourceConnectionService):
        self.connections = connections

    async def acquire(
        self, tenant: str, request: AccountOperationRequest
    ) -> AccountOperationPermit | AccountOperationBusy:
        _no_remote_unit()
        # Claim latency spends the same local budget as remote work; no clock-skew conversion.
        started = asyncio.get_running_loop().time()
        await self.connections._authorize(request.owner, tenant)
        async with asyncio.timeout(5), primary_authority(read_only=False, fresh=True):
            session = self.connections.connections._require_session()
            await session.execute(text("SET LOCAL lock_timeout = '1s'"))
            await session.execute(text("SET LOCAL statement_timeout = '5s'"))
            records = SourceAccountOperationRepository(session=session)
            await records._tenant(tenant)
            await self.connections._member(request.owner, tenant)
            connection = await session.scalar(
                select(PersonalSourceConnection)
                .where(
                    PersonalSourceConnection.id == request.connection_id,
                    PersonalSourceConnection.tenant_id == tenant,
                    PersonalSourceConnection.owner == request.owner,
                )
                .with_for_update()
                .execution_options(populate_existing=True)
            )
            if connection is None or connection.status != "connected" or connection.secret_ciphertext is None:
                raise SourceError("access_denied")
            if connection.revision != request.connection_revision or connection.refresh_operation is not None:
                raise SourceError("authority_changed")
            if (
                self.connections.registrations.get(connection.provider).fingerprint
                != connection.config_fingerprint
            ):
                raise SourceError("reconnect_required")
            acquired = await records.try_acquire(account_identity(connection), request)
        if isinstance(acquired, AccountOperationBusy):
            return acquired
        task = asyncio.current_task()
        if task is None:
            raise RuntimeError("Account operations require an async task")
        return AccountOperationPermit(acquired, started + 120, task)

    @asynccontextmanager
    async def remote(self, permit: AccountOperationPermit):
        _owned(permit)
        _no_remote_unit()
        if asyncio.get_running_loop().time() >= permit.deadline:
            raise SourceError("timeout")
        permit.completion.settled = False
        boundary = None
        try:
            with source_operation_deadline(permit.deadline) as boundary:
                async with asyncio.timeout_at(permit.deadline):
                    yield
        except SourceError as error:
            # Typed read/authorization failures reach here after adapter contexts
            # close. Timeout and untyped cleanup failures cannot prove that closure.
            permit.completion.settled = (
                error.code in {"access_denied", "authority_changed", "version_changed", "scope_mismatch"}
                and boundary is not None
                and not boundary.transports
            )
            raise
        else:
            permit.completion.settled = boundary is not None and not boundary.transports
            if not permit.completion.settled:
                raise SourceError("unavailable")

    async def assert_current(self, permit: AccountOperationPermit, session) -> None:
        _owned(permit)
        await SourceAccountOperationRepository(session=session).assert_current(permit.lease)

    async def finish(
        self, permit: AccountOperationPermit, session, *, outcome: Literal["clean", "uncertain"] = "clean"
    ) -> bool:
        _owned(permit)
        finished = await SourceAccountOperationRepository(session=session).finish(
            permit.lease, outcome=outcome
        )
        if outcome == "clean" and not finished:
            raise ConflictException(
                "Account operation lease is no longer current", code="SOURCE_ACCOUNT_LEASE_LOST"
            )
        return finished

    async def abort(self, permit: AccountOperationPermit) -> None:
        """Conservatively quarantine failed slices; never shorten expiry after uncertain cleanup."""
        _owned(permit)
        _no_remote_unit()
        async with asyncio.timeout(5), primary_authority(read_only=False, fresh=True):
            session = self.connections.connections._require_session()
            # Cleanup is conditional and must not reject an already consumed or
            # superseded holder after the original operation failed.
            await SourceAccountOperationRepository(session=session).finish(
                permit.lease, outcome="clean" if permit.completion.settled else "uncertain"
            )
