# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from datetime import timedelta

from pyfly.container import repository
from pyfly.data.relational.sqlalchemy import Repository
from pyfly.kernel import ConflictException, ServiceUnavailableException
from sqlalchemy import and_, exists, func, literal, or_, select
from sqlalchemy.orm import aliased

from koinon.assistants.entities import Provider
from koinon.catalog.entities import CatalogEntry, Tenant
from koinon.jobs.entities import Job
from koinon.knowledge.bulk.entities import now
from koinon.knowledge.bulk.repositories import BulkRepository
from koinon.knowledge.bulk_queries.entities import QueryBatch, QueryBatchItem, QueryBatchReference
from koinon.knowledge.connections.entities import KnowledgeConnection
from koinon.knowledge.entities import DomainBinding


@repository(name="knowledge.bulk_queries.repository")
class QueryBatchRepository(Repository[QueryBatch, str]):
    async def flush(self) -> None:
        await self._require_session().flush()

    async def keyed(self, tenant: str, key_hash: str) -> QueryBatch | None:
        return await self._require_session().scalar(
            select(QueryBatch)
            .where(QueryBatch.tenant_id == tenant, QueryBatch.key_hash == key_hash)
            .execution_options(populate_existing=True)
        )

    async def scoped(
        self, tenant: str, subject: str, token: str | None, batch_id: str, *, lock: bool = False
    ) -> QueryBatch | None:
        statement = select(QueryBatch).where(
            QueryBatch.id == batch_id,
            QueryBatch.tenant_id == tenant,
            QueryBatch.subject == subject,
            QueryBatch.token_id == token,
        )
        if lock:
            statement = statement.with_for_update()
        return await self._require_session().scalar(statement.execution_options(populate_existing=True))

    async def item(self, batch_id: str, item_id: str, *, lock: bool = False) -> QueryBatchItem | None:
        statement = select(QueryBatchItem).where(
            QueryBatchItem.id == item_id, QueryBatchItem.batch_id == batch_id
        )
        if lock:
            statement = statement.with_for_update()
        return await self._require_session().scalar(statement.execution_options(populate_existing=True))

    async def items(self, batch_id: str) -> list[QueryBatchItem]:
        return list(
            (
                await self._require_session().scalars(
                    select(QueryBatchItem)
                    .where(QueryBatchItem.batch_id == batch_id)
                    .order_by(QueryBatchItem.ordinal, QueryBatchItem.id)
                    .limit(21)
                    .execution_options(populate_existing=True)
                )
            ).all()
        )

    async def add_item(self, item: QueryBatchItem) -> None:
        self._require_session().add(item)
        await self.flush()

    async def references(self, item_id: str) -> list[QueryBatchReference]:
        return list(
            (
                await self._require_session().scalars(
                    select(QueryBatchReference)
                    .where(QueryBatchReference.item_id == item_id)
                    .order_by(QueryBatchReference.catalog_id)
                    .limit(129)
                )
            ).all()
        )

    async def add_reference(self, value: QueryBatchReference) -> None:
        self._require_session().add(value)
        await self.flush()

    async def aliases(
        self, tenant: str, workspace: str, dataset: str, native_workspace: str, native_table: str
    ) -> list[CatalogEntry]:
        return list(
            (
                await self._require_session().scalars(
                    select(CatalogEntry)
                    .join(DomainBinding, DomainBinding.catalog_id == CatalogEntry.id)
                    .where(
                        DomainBinding.tenant_id == tenant,
                        DomainBinding.domain == "structured",
                        DomainBinding.entity_kind == "table",
                        DomainBinding.native_id == native_table,
                        DomainBinding.native_workspace_id == native_workspace,
                        DomainBinding.workspace_id == workspace,
                        CatalogEntry.tenant_id == tenant,
                        CatalogEntry.workspace_id == workspace,
                        CatalogEntry.parent_id == dataset,
                        CatalogEntry.kind == "table",
                        CatalogEntry.status != "archived",
                    )
                    .order_by(CatalogEntry.id)
                    .limit(2)
                    .with_for_update(read=True)
                    .execution_options(populate_existing=True)
                )
            ).all()
        )

    async def binding(self, tenant: str, catalog_id: str, *, lock: bool = False) -> DomainBinding | None:
        statement = select(DomainBinding).where(
            DomainBinding.tenant_id == tenant,
            DomainBinding.catalog_id == catalog_id,
            DomainBinding.domain == "structured",
        )
        if lock:
            statement = statement.with_for_update(read=True)
        return await self._require_session().scalar(statement.execution_options(populate_existing=True))

    async def counts(self, batch_id: str) -> dict[str, int]:
        return dict(
            (
                await self._require_session().execute(
                    select(QueryBatchItem.status, func.count())
                    .where(QueryBatchItem.batch_id == batch_id)
                    .group_by(QueryBatchItem.status)
                )
            ).all()
        )

    async def admission_counts(self, tenant: str, subject: str) -> tuple[int, int, int]:
        session = self._require_session()
        total = int(
            await session.scalar(
                select(func.count()).select_from(QueryBatch).where(QueryBatch.tenant_id == tenant)
            )
            or 0
        )
        live = exists(
            select(QueryBatchItem.id).where(
                QueryBatchItem.batch_id == QueryBatch.id, QueryBatchItem.status.in_(["queued", "running"])
            )
        )
        active = select(func.count()).select_from(QueryBatch).where(QueryBatch.tenant_id == tenant, live)
        return (
            total,
            int(await session.scalar(active) or 0),
            int(await session.scalar(active.where(QueryBatch.subject == subject)) or 0),
        )

    async def page(self, batch_id: str, page: int, page_size: int) -> tuple[list[QueryBatchItem], int]:
        session = self._require_session()
        where = QueryBatchItem.batch_id == batch_id
        total = int(await session.scalar(select(func.count()).select_from(QueryBatchItem).where(where)) or 0)
        rows = await session.scalars(
            select(QueryBatchItem)
            .where(where)
            .order_by(QueryBatchItem.ordinal, QueryBatchItem.id)
            .offset((page - 1) * page_size)
            .limit(page_size)
            .execution_options(populate_existing=True)
        )
        return list(rows.all()), total

    async def visible_page(
        self,
        tenant: str,
        subject: str,
        token: str | None,
        page: int,
        page_size: int,
        *,
        allowed_workspaces,
        allowed_assets,
        allowed_resources,
    ) -> tuple[list[QueryBatch], int]:
        workspace, project, parent, source, dataset, reference = [aliased(CatalogEntry) for _ in range(6)]
        dataset_binding, workspace_binding, table_binding = [aliased(DomainBinding) for _ in range(3)]
        predicates = [
            QueryBatch.tenant_id == tenant,
            QueryBatch.subject == subject,
            QueryBatch.token_id == token,
        ]
        if allowed_workspaces is not None:
            predicates.append(QueryBatch.workspace_id.in_(allowed_workspaces))
        admitted = None
        if allowed_assets is not None:
            admitted = (
                select(CatalogEntry.id, literal(0).label("depth"))
                .where(CatalogEntry.tenant_id == tenant, CatalogEntry.id.in_(allowed_assets))
                .cte("query_admitted", recursive=True)
            )
            child = aliased(CatalogEntry)
            admitted = admitted.union_all(
                select(child.id, admitted.c.depth + 1)
                .join(admitted, child.parent_id == admitted.c.id)
                .where(child.tenant_id == tenant, admitted.c.depth < 15)
            )

        def visible(entry):
            condition = and_(entry.tenant_id == tenant, entry.status != "archived")
            if admitted is not None:
                condition = and_(
                    condition, or_(entry.id.in_(allowed_resources or []), entry.id.in_(select(admitted.c.id)))
                )
            return condition

        valid_ref = exists(
            select(reference.id)
            .join(table_binding, table_binding.catalog_id == reference.id)
            .where(
                reference.id == QueryBatchReference.catalog_id,
                reference.kind == "table",
                reference.parent_id == QueryBatchItem.dataset_id,
                reference.workspace_id == QueryBatch.workspace_id,
                table_binding.tenant_id == tenant,
                table_binding.domain == "structured",
                table_binding.entity_kind == "table",
                table_binding.workspace_id == QueryBatch.workspace_id,
                table_binding.native_workspace_id == QueryBatchItem.native_workspace_id,
                table_binding.native_id == QueryBatchReference.native_table_id,
                visible(reference),
            )
            .correlate(QueryBatchReference, QueryBatchItem, QueryBatch)
        )
        invalid_ref = exists(
            select(QueryBatchReference.item_id)
            .where(QueryBatchReference.item_id == QueryBatchItem.id, ~valid_ref)
            .correlate(QueryBatchItem, QueryBatch)
        )
        valid_item = exists(
            select(dataset.id)
            .join(source, source.id == dataset.parent_id)
            .join(parent, parent.id == source.parent_id)
            .join(project, project.id == parent.parent_id)
            .join(dataset_binding, dataset_binding.catalog_id == dataset.id)
            .join(workspace_binding, workspace_binding.catalog_id == QueryBatch.workspace_id)
            .where(
                dataset.id == QueryBatchItem.dataset_id,
                dataset.kind == "dataset",
                dataset.status == "ready",
                dataset_binding.tenant_id == tenant,
                dataset_binding.domain == "structured",
                dataset_binding.entity_kind == "dataset",
                dataset_binding.workspace_id == QueryBatch.workspace_id,
                dataset_binding.native_workspace_id == QueryBatchItem.native_workspace_id,
                dataset_binding.native_id == QueryBatchItem.native_dataset_id,
                workspace_binding.tenant_id == tenant,
                workspace_binding.domain == "structured",
                workspace_binding.entity_kind == "workspace",
                workspace_binding.workspace_id == QueryBatch.workspace_id,
                workspace_binding.native_id == QueryBatchItem.native_workspace_id,
                workspace_binding.native_workspace_id == workspace_binding.native_id,
                source.kind == "source",
                parent.kind.in_(["collection", "corpus"]),
                project.kind == "project",
                project.parent_id == QueryBatch.workspace_id,
                project.project_id == project.id,
                *(
                    entry.workspace_id == QueryBatch.workspace_id
                    for entry in [dataset, source, parent, project]
                ),
                *(entry.project_id == project.id for entry in [dataset, source, parent]),
                *(visible(entry) for entry in [dataset, source, parent, project]),
                ~invalid_ref,
            )
            .correlate(QueryBatchItem, QueryBatch)
        )
        invalid_item = exists(
            select(QueryBatchItem.id)
            .where(QueryBatchItem.batch_id == QueryBatch.id, ~valid_item)
            .correlate(QueryBatch)
        )
        statement = (
            select(QueryBatch)
            .join(workspace, workspace.id == QueryBatch.workspace_id)
            .where(
                *predicates,
                workspace.kind == "workspace",
                workspace.workspace_id == workspace.id,
                workspace.parent_id.is_(None),
                visible(workspace),
                ~invalid_item,
            )
        )
        session = self._require_session()
        total = int(await session.scalar(select(func.count()).select_from(statement.subquery())) or 0)
        rows = await session.scalars(
            statement.order_by(QueryBatch.created_at.desc(), QueryBatch.id)
            .offset((page - 1) * page_size)
            .limit(page_size)
            .execution_options(populate_existing=True)
        )
        return list(rows.all()), total

    async def connections(
        self, tenant: str, workspace: str, roles: tuple[str, ...], *, lock: bool = True
    ) -> dict:
        session = self._require_session()
        result = {}
        for role in roles:
            selected = None
            for scope in [workspace, None]:
                statement = select(KnowledgeConnection).where(
                    KnowledgeConnection.tenant_id == tenant,
                    KnowledgeConnection.workspace_id == scope,
                    KnowledgeConnection.domain == "structured",
                    KnowledgeConnection.role == role,
                )
                if lock:
                    statement = statement.with_for_update(read=True)
                selected = await session.scalar(statement.execution_options(populate_existing=True))
                if selected is not None:
                    break
            statement = (
                select(Provider).where(Provider.tenant_id == tenant, Provider.id == selected.provider_id)
                if selected
                else None
            )
            if statement is not None and lock:
                statement = statement.with_for_update(read=True)
            provider = (
                await session.scalar(statement.execution_options(populate_existing=True))
                if statement is not None
                else None
            )
            if (
                selected is None
                or not selected.enabled
                or selected.mode != "provider"
                or provider is None
                or not provider.enabled
                or provider.validated_revision != provider.revision
                or selected.model_id not in provider.model_ids
                or (
                    role == "structured.embedding"
                    and (not selected.dimensions or not selected.embedding_fingerprint)
                )
            ):
                raise ServiceUnavailableException(
                    "Each query role needs a current explicit validated provider",
                    code="BULK_QUERY_CONNECTION_REQUIRED",
                )
            result[role] = {
                "connection_id": selected.id,
                "revision": selected.revision,
                "provider_id": provider.id,
                "provider_revision": provider.revision,
                "model_id": selected.model_id,
                "model_options": selected.model_options,
                "dimensions": selected.dimensions,
                "storage_dimensions": selected.storage_dimensions,
                "embedding_fingerprint": selected.embedding_fingerprint,
            }
        return result

    async def job(self, job_id: str) -> Job | None:
        return await self._require_session().scalar(
            select(Job)
            .where(Job.id == job_id, Job.kind == "knowledge.bulk.query")
            .with_for_update()
            .execution_options(populate_existing=True)
        )

    async def fenced(
        self, tenant: str, item_id: str, worker: str, attempt: int
    ) -> tuple[Job, QueryBatchItem, QueryBatch]:
        session = self._require_session()
        candidate = await session.scalar(select(QueryBatchItem).where(QueryBatchItem.id == item_id))
        batch = (
            await session.scalar(
                select(QueryBatch)
                .where(QueryBatch.id == candidate.batch_id, QueryBatch.tenant_id == tenant)
                .with_for_update()
                .execution_options(populate_existing=True)
            )
            if candidate
            else None
        )
        item = await self.item(batch.id, item_id, lock=True) if batch else None
        job = await self.job(item.job_id) if item else None
        if (
            batch is None
            or item is None
            or job is None
            or batch.cancelled
            or batch.expires_at <= now()
            or job.resource_id != item.dataset_id
            or job.payload != {"batch_id": batch.id, "item_id": item.id}
            or item.status != "running"
            or job.status != "running"
            or job.worker_id != worker
            or job.attempts != attempt
            or job.lease_until is None
            or job.lease_until <= now()
        ):
            raise ConflictException("Query worker lost its current lease", code="BULK_LEASE_LOST")
        return job, item, batch

    async def claimed(
        self, item_id: str, worker: str, attempt: int
    ) -> tuple[Job, QueryBatchItem, QueryBatch]:
        candidate = await self._require_session().scalar(
            select(QueryBatchItem).where(QueryBatchItem.id == item_id)
        )
        batch = (
            await self._require_session().scalar(
                select(QueryBatch).where(QueryBatch.id == candidate.batch_id)
            )
            if candidate
            else None
        )
        if batch is None:
            raise ConflictException("Query lease unavailable", code="BULK_LEASE_LOST")
        return await self.fenced(batch.tenant_id, item_id, worker, attempt)

    async def claim(
        self, worker: str, lease_seconds: int, global_limit: int, tenant_limit: int, shared: BulkRepository
    ) -> tuple[Job, QueryBatchItem, QueryBatch] | None:
        session = self._require_session()
        clock = now()
        await shared.quota("global:workers")
        running = and_(
            Job.kind.in_(["knowledge.bulk.intake", "knowledge.bulk.query"]),
            Job.status == "running",
            Job.lease_until > clock,
        )
        if (
            int(await session.scalar(select(func.count()).select_from(Job).where(running)) or 0)
            >= global_limit
        ):
            return None
        due = or_(
            and_(Job.status == "queued", Job.available_at <= clock),
            and_(Job.status == "running", Job.lease_until < clock),
        )
        ranked = select(
            Job.id.label("id"),
            Job.tenant_id.label("tenant"),
            func.row_number()
            .over(partition_by=Job.tenant_id, order_by=(Job.available_at, Job.created_at, Job.id))
            .label("position"),
        ).join(QueryBatchItem, QueryBatchItem.job_id == Job.id)
        ranked = (
            ranked.join(QueryBatch, QueryBatch.id == QueryBatchItem.batch_id)
            .where(
                Job.kind == "knowledge.bulk.query",
                due,
                QueryBatch.cancelled.is_(False),
                QueryBatchItem.status.in_(["queued", "running"]),
            )
            .subquery()
        )
        candidates = (
            await session.execute(
                select(ranked.c.id, ranked.c.tenant)
                .where(ranked.c.position == 1)
                .order_by(ranked.c.id)
                .limit(100)
            )
        ).all()
        for job_id, tenant in candidates:
            if (
                await session.scalar(
                    select(Tenant).where(Tenant.id == tenant).with_for_update(skip_locked=True)
                )
                is None
            ):
                continue
            candidate = await session.scalar(select(QueryBatchItem).where(QueryBatchItem.job_id == job_id))
            batch = (
                await session.scalar(
                    select(QueryBatch)
                    .where(QueryBatch.id == candidate.batch_id)
                    .with_for_update()
                    .execution_options(populate_existing=True)
                )
                if candidate
                else None
            )
            item = await self.item(batch.id, candidate.id, lock=True) if batch and candidate else None
            job = await session.scalar(
                select(Job)
                .where(Job.id == job_id, due)
                .with_for_update(skip_locked=True)
                .execution_options(populate_existing=True)
            )
            if (
                batch is None
                or item is None
                or job is None
                or batch.cancelled
                or item.status not in {"queued", "running"}
            ):
                continue
            if batch.expires_at <= clock or job.attempts >= job.max_attempts:
                item.status = "reconciling" if item.status == "running" else "failed"
                item.error_code = (
                    "BULK_QUERY_RECOVERY_REQUIRED" if item.status == "reconciling" else "BULK_QUERY_EXPIRED"
                )
                job.status = "failed"
                job.worker_id = None
                job.lease_until = None
                batch.revision += 1
                continue
            if (
                int(
                    await session.scalar(
                        select(func.count()).select_from(Job).where(running, Job.tenant_id == tenant)
                    )
                    or 0
                )
                >= tenant_limit
            ):
                continue
            job.status = "running"
            job.worker_id = worker
            job.attempts += 1
            job.lease_until = clock + timedelta(seconds=lease_seconds)
            job.updated_at = clock
            item.status = "running"
            batch.revision += 1
            await self.flush()
            return job, item, batch
        return None
