# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from datetime import timedelta
from uuid import uuid4

from pydantic import ValidationError
from pyfly.container import service
from pyfly.data.relational.sqlalchemy import Isolation, Propagation, transactional
from pyfly.kernel import (
    ConflictException,
    InvalidRequestException,
    RateLimitException,
    ServiceUnavailableException,
)

from koinon.catalog.errors import AccessDenied
from koinon.jobs.service import JobService
from koinon.knowledge.bulk.authority import token_identity
from koinon.knowledge.bulk.dtos import aggregate_status
from koinon.knowledge.bulk.entities import now
from koinon.knowledge.bulk.service import key_digest
from koinon.knowledge.bulk.settings import BulkSettings
from koinon.knowledge.bulk_queries.authority import QueryBatchAuthority, query_roles
from koinon.knowledge.bulk_queries.dtos import (
    BatchQueryOutcome,
    QueryBatchAction,
    QueryBatchCancellation,
    QueryBatchCapabilities,
    QueryBatchCreate,
    QueryBatchItemPage,
    QueryBatchItemView,
    QueryBatchPage,
    QueryBatchResult,
    QueryBatchView,
)
from koinon.knowledge.bulk_queries.entities import QueryBatch, QueryBatchItem
from koinon.knowledge.bulk_queries.native import BulkQueryNative
from koinon.knowledge.bulk_queries.queue import QueryBatchQueue, canonical_digest
from koinon.knowledge.bulk_queries.repositories import QueryBatchRepository
from koinon.security.authority import PRIMARY_POLICY_UNIT


@service(name="knowledge.bulk_queries.service")
class QueryBatches:
    def __init__(
        self,
        records: QueryBatchRepository,
        authority: QueryBatchAuthority,
        jobs: JobService,
        queue: QueryBatchQueue,
        native: BulkQueryNative,
        settings: BulkSettings,
    ):
        self.records, self.authority, self.jobs, self.queue, self.native, self.settings = (
            records,
            authority,
            jobs,
            queue,
            native,
            settings,
        )

    async def _policy(self, subject: str, tenant: str):
        settings = self.authority.facade().knowledge_settings
        if settings is None:
            raise ServiceUnavailableException(
                "Effective query policy unavailable", code="BULK_QUERY_POLICY_REQUIRED"
            )
        return await settings.snapshot(subject, tenant)

    @transactional(
        datasource="primary",
        name=PRIMARY_POLICY_UNIT,
        propagation=Propagation.REQUIRES_NEW,
        isolation=Isolation.SERIALIZABLE,
        read_only=True,
        read_from_primary=True,
    )
    async def capabilities(self, subject: str, tenant: str, workspace: str) -> QueryBatchCapabilities:
        await self.authority.workspace(subject, tenant, workspace)
        configured = False
        try:
            policy = await self._policy(subject, tenant)
            await self.records.connections(tenant, workspace, query_roles(policy), lock=False)
            configured = True
        except ServiceUnavailableException:
            pass
        return QueryBatchCapabilities(configured=configured)

    async def _scope(
        self, subject: str, tenant: str, batch_id: str, *, write: bool = False, resources: bool = True
    ) -> QueryBatch:
        row = await self.records.scoped(tenant, subject, token_identity(), batch_id)
        if row is None:
            raise AccessDenied("Private query batch unavailable", code="ACCESS_DENIED")
        await self.authority.workspace(subject, tenant, row.workspace_id, write=write)
        if write:
            row = await self.records.scoped(tenant, subject, token_identity(), batch_id, lock=True)
            if row is None:
                raise AccessDenied("Private query batch unavailable", code="ACCESS_DENIED")
        if resources:
            for item in await self.records.items(row.id):
                await self.authority.item(subject, tenant, row.workspace_id, item, write=write)
        return row

    async def _view(self, row: QueryBatch) -> QueryBatchView:
        counts = await self.records.counts(row.id)
        status = aggregate_status([state for state, count in counts.items() if count])
        if status == "staging" or status == "expired":
            raise ConflictException(
                "Query outcome state cannot be verified", code="BULK_QUERY_RECEIPT_CONFLICT"
            )
        return QueryBatchView(
            id=row.id,
            tenant_id=row.tenant_id,
            workspace_id=row.workspace_id,
            status=status,
            revision=row.revision,
            total_items=sum(counts.values()),
            counts=counts,
            cancellation_requested=row.cancelled,
            created_at=row.created_at,
            expires_at=row.expires_at,
        )

    @transactional(propagation=Propagation.REQUIRES_NEW)
    async def create(self, subject: str, tenant: str, request: QueryBatchCreate, key: str) -> QueryBatchView:
        request = QueryBatchCreate.model_validate(request.model_dump(mode="python")).model_copy(deep=True)
        self.settings.validate()
        await self.authority.workspace(subject, tenant, request.workspace_id, write=True)
        key_hash = key_digest(key)
        request_hash = canonical_digest([subject, token_identity(), request.model_dump(mode="json")])
        previous = await self.records.keyed(tenant, key_hash)
        if previous is not None:
            if previous.request_hash != request_hash:
                raise ConflictException(
                    "Key belongs to a different query admission", code="IDEMPOTENCY_CONFLICT"
                )
            return await self._view(await self._scope(subject, tenant, previous.id))
        history, active, actor_active = await self.records.admission_counts(tenant, subject)
        if history >= self.settings.max_batches_per_tenant:
            raise RateLimitException(
                "Retained query history reached its bound", code="BULK_QUERY_HISTORY_LIMIT"
            )
        if (
            active >= self.settings.max_active_batches_per_tenant
            or actor_active >= self.settings.max_active_batches_per_subject
        ):
            raise RateLimitException("Active query batch admission is full", code="BULK_QUERY_BATCH_LIMIT")
        policy = await self._policy(subject, tenant)
        connections = await self.records.connections(tenant, request.workspace_id, query_roles(policy))
        bindings = []
        for item in request.items:
            bindings.append(
                await self.authority.dataset(
                    subject, tenant, request.workspace_id, item.dataset_id, write=True
                )
            )
        row = await self.records.save(
            QueryBatch(
                id=str(uuid4()),
                tenant_id=tenant,
                workspace_id=request.workspace_id,
                subject=subject,
                token_id=token_identity(),
                key_hash=key_hash,
                request_hash=request_hash,
                request_json=request.model_dump(mode="json"),
                revision=1,
                created_at=now(),
                expires_at=now() + timedelta(hours=24),
            )
        )
        for ordinal, (item, binding) in enumerate(zip(request.items, bindings, strict=True)):
            item_id = str(uuid4())
            job = await self.jobs.submit(
                tenant,
                item.dataset_id,
                "knowledge.bulk.query",
                {"batch_id": row.id, "item_id": item_id},
                "bulk-query:" + item_id,
            )
            await self.records.add_item(
                QueryBatchItem(
                    id=item_id,
                    batch_id=row.id,
                    ordinal=ordinal,
                    client_item_id=item.client_item_id,
                    dataset_id=item.dataset_id,
                    question=item.question,
                    native_workspace_id=binding.native_workspace_id,
                    native_dataset_id=binding.native_id,
                    connection_json=connections,
                    policy_json=policy.model_dump(mode="json"),
                    job_id=job.id,
                    status="queued",
                )
            )
        await self.records.flush()
        return await self._view(row)

    @staticmethod
    def _page(page: int, size: int) -> None:
        if type(page) is not int or not 1 <= page <= 1000000 or type(size) is not int or not 1 <= size <= 100:
            raise InvalidRequestException("Use bounded query pagination", code="BULK_QUERY_PAGE_INVALID")

    @transactional(
        datasource="primary",
        name=PRIMARY_POLICY_UNIT,
        propagation=Propagation.REQUIRES_NEW,
        isolation=Isolation.SERIALIZABLE,
        read_only=True,
        read_from_primary=True,
    )
    async def _guard(self, subject: str, tenant: str, batch_id: str) -> None:
        await self._scope(subject, tenant, batch_id)

    @transactional(
        datasource="primary",
        name=PRIMARY_POLICY_UNIT,
        propagation=Propagation.REQUIRES_NEW,
        isolation=Isolation.SERIALIZABLE,
        read_only=True,
        read_from_primary=True,
    )
    async def _get(self, subject: str, tenant: str, batch_id: str) -> QueryBatchView:
        return await self._view(await self._scope(subject, tenant, batch_id))

    async def get(self, subject: str, tenant: str, batch_id: str) -> QueryBatchView:
        result = await self._get(subject, tenant, batch_id)
        await self._guard(subject, tenant, batch_id)
        return result

    @transactional(
        datasource="primary",
        name=PRIMARY_POLICY_UNIT,
        propagation=Propagation.REQUIRES_NEW,
        isolation=Isolation.SERIALIZABLE,
        read_only=True,
        read_from_primary=True,
    )
    async def _list(self, subject: str, tenant: str, page: int, page_size: int) -> QueryBatchPage:
        bounds = await self.authority.read_bounds(subject, tenant)
        rows, total = await self.records.visible_page(
            tenant, subject, token_identity(), page, page_size, **bounds
        )
        return QueryBatchPage(
            items=[await self._view(row) for row in rows],
            total=total,
            page=page,
            page_size=page_size,
            pages=(total + page_size - 1) // page_size,
        )

    @transactional(
        datasource="primary",
        name=PRIMARY_POLICY_UNIT,
        propagation=Propagation.REQUIRES_NEW,
        isolation=Isolation.SERIALIZABLE,
        read_only=True,
        read_from_primary=True,
    )
    async def _list_guard(self, subject: str, tenant: str) -> None:
        await self.authority.read_bounds(subject, tenant)

    async def list(self, subject: str, tenant: str, *, page: int = 1, page_size: int = 25) -> QueryBatchPage:
        self._page(page, page_size)
        first = await self._list(subject, tenant, page, page_size)
        result = await self._list(subject, tenant, page, page_size)
        if first != result:
            raise ConflictException("Query page changed; reload", code="BULK_QUERY_PAGE_CHANGED")
        for row in result.items:
            await self._guard(subject, tenant, row.id)
        await self._list_guard(subject, tenant)
        return result

    @transactional(
        datasource="primary",
        name=PRIMARY_POLICY_UNIT,
        propagation=Propagation.REQUIRES_NEW,
        isolation=Isolation.SERIALIZABLE,
        read_only=True,
        read_from_primary=True,
    )
    async def _items(
        self, subject: str, tenant: str, batch_id: str, page: int, page_size: int
    ) -> QueryBatchItemPage:
        await self._scope(subject, tenant, batch_id)
        rows, total = await self.records.page(batch_id, page, page_size)
        return QueryBatchItemPage(
            items=[
                QueryBatchItemView(
                    id=row.id,
                    client_item_id=row.client_item_id,
                    dataset_id=row.dataset_id,
                    question=row.question,
                    status=row.status,
                    job_id=row.job_id,
                    error_code=row.error_code,
                    query_id=(row.result_json or {}).get("query_id"),
                )
                for row in rows
            ],
            total=total,
            page=page,
            page_size=page_size,
            pages=(total + page_size - 1) // page_size,
        )

    async def items(
        self, subject: str, tenant: str, batch_id: str, *, page: int = 1, page_size: int = 25
    ) -> QueryBatchItemPage:
        self._page(page, page_size)
        result = await self._items(subject, tenant, batch_id, page, page_size)
        await self._guard(subject, tenant, batch_id)
        return result

    @transactional(
        datasource="primary",
        name=PRIMARY_POLICY_UNIT,
        propagation=Propagation.REQUIRES_NEW,
        isolation=Isolation.SERIALIZABLE,
        read_only=True,
        read_from_primary=True,
    )
    async def _result(self, subject: str, tenant: str, batch_id: str, item_id: str) -> QueryBatchResult:
        await self._scope(subject, tenant, batch_id)
        item = await self.records.item(batch_id, item_id)
        if item is None:
            raise AccessDenied("Private query item unavailable", code="ACCESS_DENIED")
        try:
            outcome = (
                BatchQueryOutcome.model_validate(item.result_json) if item.result_json is not None else None
            )
        except ValidationError:
            raise ConflictException(
                "Saved query result cannot be verified", code="BULK_QUERY_RECEIPT_CONFLICT"
            ) from None
        return QueryBatchResult(
            batch_id=batch_id, item_id=item_id, status=item.status, result=outcome, error_code=item.error_code
        )

    async def result(self, subject: str, tenant: str, batch_id: str, item_id: str) -> QueryBatchResult:
        result = await self._result(subject, tenant, batch_id, item_id)
        await self._guard(subject, tenant, batch_id)
        return result

    def _action(self, row: QueryBatch, action: str, body: QueryBatchAction, key: str) -> bool:
        key_hash = key_digest(key)
        expected = canonical_digest([action, body.model_dump(), token_identity()])
        previous = row.actions_json.get(key_hash)
        if previous is not None:
            if previous != expected:
                raise ConflictException("Key belongs to another query action", code="IDEMPOTENCY_CONFLICT")
            return False
        if row.revision != body.expected_revision:
            raise ConflictException("Query batch revision changed", code="BULK_QUERY_REVISION_CONFLICT")
        if len(row.actions_json) >= 256:
            raise RateLimitException(
                "Query action receipts reached their bound", code="BULK_QUERY_ACTION_LIMIT"
            )
        row.actions_json = {**row.actions_json, key_hash: expected}
        return True

    @transactional(propagation=Propagation.REQUIRES_NEW)
    async def cancel(
        self, subject: str, tenant: str, batch_id: str, body: QueryBatchAction, key: str
    ) -> QueryBatchCancellation:
        row = await self._scope(subject, tenant, batch_id, write=True, resources=False)
        if self._action(row, "cancel", body, key):
            row.cancelled = True
            for item in await self.records.items(row.id):
                if item.result_json is not None or item.status in {"failed", "cancelled"}:
                    continue
                job = await self.records.job(item.job_id)
                if job is None:
                    raise ConflictException("Query job unavailable", code="BULK_QUERY_RECEIPT_CONFLICT")
                if job.attempts == 0:
                    item.status = "cancelled"
                else:
                    try:
                        lease = self.queue.lease(job, item, row)
                        status, receipt = await self.native.inspect(lease)
                        if status == "committed" and receipt is not None:
                            await self.native.acknowledge_committed(lease, receipt)
                            continue
                        item.status = "cancelled" if status == "absent" else "reconciling"
                        item.error_code = None if status == "absent" else "BULK_QUERY_OUTCOME_UNRESOLVED"
                    except Exception:
                        item.status = "reconciling"
                        item.error_code = "BULK_QUERY_CANCEL_UNKNOWN"
                if job.status in {"queued", "running"}:
                    await self.jobs.cancel(tenant, job.id)
            row.revision += 1
            await self.records.flush()
        return QueryBatchCancellation(batch_id=row.id, revision=row.revision)

    @transactional(propagation=Propagation.REQUIRES_NEW)
    async def reconcile(
        self, subject: str, tenant: str, batch_id: str, item_id: str, body: QueryBatchAction, key: str
    ) -> QueryBatchView:
        row = await self._scope(subject, tenant, batch_id, write=True)
        if not self._action(row, "reconcile:" + item_id, body, key):
            return await self._view(row)
        item = await self.records.item(batch_id, item_id, lock=True)
        if item is None:
            raise AccessDenied("Private query item unavailable", code="ACCESS_DENIED")
        if item.result_json is not None:
            return await self._view(row)
        job = await self.records.job(item.job_id)
        if job is None:
            raise ConflictException("Query job unavailable", code="BULK_QUERY_RECEIPT_CONFLICT")
        lease = self.queue.lease(job, item, row)
        status, receipt = await self.native.inspect(lease)
        if status == "committed" and receipt is not None:
            await self.native.acknowledge_committed(lease, receipt)
        elif status == "absent":
            item.status = "cancelled" if row.cancelled else "failed"
            item.error_code = None if row.cancelled else "BULK_QUERY_NOT_STARTED"
            job.status = "cancelled" if row.cancelled else "failed"
            job.lease_until = None
            job.worker_id = None
        else:
            item.status = "reconciling"
            item.error_code = "BULK_QUERY_OUTCOME_UNRESOLVED"
            job.status = "failed"
            job.lease_until = None
            job.worker_id = None
        row.revision += 1
        await self.records.flush()
        return await self._view(row)
