# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import hashlib
import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import datetime

from pydantic import ValidationError
from pyfly.container import service
from pyfly.data.relational.datasource_registry import DataSourceRegistry
from pyfly.data.relational.sqlalchemy import Propagation, transactional
from pyfly.data.transaction import infrastructure_unit
from pyfly.kernel import ConflictException, InvalidRequestException
from pyfly.security.context import SecurityContext
from pyfly.security.context_holder import SecurityContextHolder

from koinon.knowledge.bulk.repositories import BulkRepository
from koinon.knowledge.bulk.settings import BulkSettings
from koinon.knowledge.bulk_queries.authority import QueryBatchAuthority, query_roles
from koinon.knowledge.bulk_queries.repositories import QueryBatchRepository
from koinon.organization_knowledge.dtos import OrganizationKnowledgeSnapshot


def canonical_digest(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode()
    ).hexdigest()


@dataclass(frozen=True)
class QueryLease:
    job_id: str
    item_id: str
    batch_id: str
    tenant_id: str
    subject: str
    token_id: str | None
    worker_id: str
    attempt: int
    workspace_id: str
    dataset_id: str
    native_workspace_id: str
    native_dataset_id: str
    question: str
    policy: OrganizationKnowledgeSnapshot
    connections_sha256: str
    expires_at: datetime | None


@service(name="knowledge.bulk_queries.queue")
class QueryBatchQueue:
    def __init__(
        self,
        records: QueryBatchRepository,
        shared: BulkRepository,
        authority: QueryBatchAuthority,
        settings: BulkSettings,
        datasources: DataSourceRegistry,
    ):
        self.records, self.shared, self.authority, self.settings, self.datasources = (
            records,
            shared,
            authority,
            settings,
            datasources,
        )

    @staticmethod
    def lease(job, item, batch) -> QueryLease:
        try:
            policy = OrganizationKnowledgeSnapshot.model_validate(item.policy_json)
        except ValidationError:
            raise ConflictException(
                "Admitted query policy cannot be verified", code="BULK_QUERY_POLICY_CHANGED"
            ) from None
        return QueryLease(
            job_id=job.id,
            item_id=item.id,
            batch_id=batch.id,
            tenant_id=batch.tenant_id,
            subject=batch.subject,
            token_id=batch.token_id,
            worker_id=job.worker_id or "",
            attempt=job.attempts,
            workspace_id=batch.workspace_id,
            dataset_id=item.dataset_id,
            native_workspace_id=item.native_workspace_id,
            native_dataset_id=item.native_dataset_id,
            question=item.question,
            policy=policy,
            connections_sha256=canonical_digest(item.connection_json),
            expires_at=job.lease_until,
        )

    @transactional(propagation=Propagation.REQUIRES_NEW)
    async def claim(self, worker_id: str) -> QueryLease | None:
        self.settings.validate()
        if not worker_id or len(worker_id) > 64:
            raise InvalidRequestException("Use a bounded query worker identity", code="INVALID_WORKER")
        result = await self.records.claim(
            worker_id,
            self.settings.lease_seconds,
            self.settings.max_workers_global,
            self.settings.max_workers_per_tenant,
            self.shared,
        )
        return self.lease(*result) if result is not None else None

    async def _check(self, lease: QueryLease) -> None:
        with SecurityContextHolder.using(
            SecurityContext(
                user_id=lease.subject,
                attributes={"koinon_token_id": lease.token_id} if lease.token_id else {},
            )
        ):
            await self.authority.workspace(lease.subject, lease.tenant_id, lease.workspace_id, write=True)
            candidate = await self.records.item(lease.batch_id, lease.item_id)
            if candidate is None:
                raise ConflictException("Query lease unavailable", code="BULK_LEASE_LOST")
            await self.authority.item(
                lease.subject, lease.tenant_id, lease.workspace_id, candidate, write=True
            )
            _, item, batch = await self.records.fenced(
                lease.tenant_id, lease.item_id, lease.worker_id, lease.attempt
            )
            current = self.lease(await self.records.job(item.job_id), item, batch)
            if current != lease:
                raise ConflictException("Admitted query lease changed", code="BULK_LEASE_LOST")
            if item.connection_json != await self.records.connections(
                lease.tenant_id, lease.workspace_id, query_roles(lease.policy)
            ):
                raise ConflictException(
                    "Admitted query connection changed", code="BULK_QUERY_CONNECTION_CHANGED"
                )

    @transactional(propagation=Propagation.REQUIRES_NEW)
    async def check(self, lease: QueryLease) -> None:
        await self._check(lease)

    @transactional(propagation=Propagation.REQUIRES_NEW)
    async def load_claimed(self, item_id: str, worker_id: str, attempt: int) -> QueryLease:
        lease = self.lease(*await self.records.claimed(item_id, worker_id, attempt))
        await self._check(lease)
        return lease

    @asynccontextmanager
    async def publication(self, lease: QueryLease) -> AsyncIterator[None]:
        async with infrastructure_unit(self.datasources.get("primary")):
            await self._check(lease)
            yield
            await self.records.fenced(lease.tenant_id, lease.item_id, lease.worker_id, lease.attempt)

    @transactional(propagation=Propagation.REQUIRES_NEW)
    async def failed(self, lease: QueryLease, *, code: str, unknown: bool) -> None:
        job, item, batch = await self.records.fenced(
            lease.tenant_id, lease.item_id, lease.worker_id, lease.attempt
        )
        item.status = "reconciling" if unknown else "failed"
        item.error_code = (
            code
            if code.isascii() and code.replace("_", "").isalnum() and len(code) <= 64
            else "BULK_QUERY_FAILED"
        )
        job.status = "failed"
        job.error = item.error_code
        job.worker_id = None
        job.lease_until = None
        batch.revision += 1
        await self.records.flush()
