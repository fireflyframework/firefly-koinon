# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from datetime import UTC, datetime, timedelta

from pyfly.container import repository
from pyfly.data.relational.sqlalchemy import Repository
from pyfly.kernel import ConflictException, ServiceUnavailableException
from sqlalchemy import and_, exists, func, literal, or_, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import aliased

from koinon.assistants.entities import Provider
from koinon.catalog.entities import CatalogEntry, Membership, Tenant
from koinon.jobs.entities import Job
from koinon.knowledge.bulk.entities import (
    BulkBatch,
    BulkItem,
    BulkQuota,
    BulkRecovery,
    BulkTableReservation,
    BulkUpload,
    BulkUploadState,
    now,
)
from koinon.knowledge.connections.entities import KnowledgeConnection
from koinon.knowledge.entities import DomainBinding
from koinon.tokens.entities import PersonalToken


@repository(name="knowledge.bulk.repository")
class BulkRepository(Repository[BulkBatch, str]):
    async def table_reservations(self, item_id: str) -> list[BulkTableReservation]:
        return list(
            (
                await self._require_session().scalars(
                    select(BulkTableReservation)
                    .where(BulkTableReservation.item_id == item_id)
                    .order_by(BulkTableReservation.ordinal)
                    .limit(17)
                )
            ).all()
        )

    async def add_table_reservation(self, row: BulkTableReservation) -> None:
        self._require_session().add(row)
        await self._require_session().flush()

    async def catalog_locks(self, tenant: str, identifiers: tuple[str, ...]) -> None:
        rows = await self._require_session().scalars(
            select(CatalogEntry)
            .where(CatalogEntry.tenant_id == tenant, CatalogEntry.id.in_(identifiers))
            .order_by(CatalogEntry.id)
            .with_for_update(read=True)
            .execution_options(populate_existing=True)
        )
        rows.all()

    async def authority_lock(self, tenant_id: str, subject: str, token_id: str | None) -> None:
        session = self._require_session()
        await session.scalar(select(Tenant).where(Tenant.id == tenant_id).with_for_update())
        await session.execute(
            select(Membership)
            .where(Membership.tenant_id == tenant_id, Membership.subject == subject)
            .order_by(Membership.id)
            .with_for_update(read=True)
            .execution_options(populate_existing=True)
        )
        if token_id:
            await session.scalar(
                select(PersonalToken)
                .where(PersonalToken.id == token_id)
                .with_for_update(read=True)
                .execution_options(populate_existing=True)
            )

    async def quota(self, identifier: str) -> BulkQuota:
        session = self._require_session()
        dialect = session.get_bind().dialect.name
        insert = pg_insert if dialect == "postgresql" else sqlite_insert if dialect == "sqlite" else None
        if insert is None:
            raise ServiceUnavailableException(
                "Bulk storage requires PostgreSQL or SQLite", code="BULK_DATABASE_UNSUPPORTED"
            )
        await session.execute(
            insert(BulkQuota)
            .values(id=identifier, reserved_bytes=0, active_uploads=0)
            .on_conflict_do_nothing(index_elements=["id"])
        )
        return (
            await session.scalars(
                select(BulkQuota)
                .where(BulkQuota.id == identifier)
                .with_for_update()
                .execution_options(populate_existing=True)
            )
        ).one()

    async def keyed(self, tenant: str, key: str) -> BulkBatch | None:
        return await self._require_session().scalar(
            select(BulkBatch)
            .where(BulkBatch.tenant_id == tenant, BulkBatch.key_hash == key)
            .execution_options(populate_existing=True)
        )

    async def admission_counts(self, tenant: str, subject: str) -> tuple[int, int, int]:
        session = self._require_session()
        history = int(
            await session.scalar(
                select(func.count()).select_from(BulkBatch).where(BulkBatch.tenant_id == tenant)
            )
            or 0
        )
        live_items = exists(
            select(BulkItem.id)
            .where(
                BulkItem.batch_id == BulkBatch.id, BulkItem.status.in_(["queued", "running", "reconciling"])
            )
            .correlate(BulkBatch)
        )
        active = and_(
            BulkBatch.tenant_id == tenant,
            BulkBatch.cancelled.is_(False),
            or_(and_(BulkBatch.submitted.is_(False), BulkBatch.expires_at > now()), live_items),
        )
        tenant_active = int(
            await session.scalar(select(func.count()).select_from(BulkBatch).where(active)) or 0
        )
        actor_active = int(
            await session.scalar(
                select(func.count()).select_from(BulkBatch).where(active, BulkBatch.subject == subject)
            )
            or 0
        )
        return history, tenant_active, actor_active

    async def scoped(
        self, tenant: str, subject: str, identifier: str, *, lock: bool = False
    ) -> BulkBatch | None:
        query = select(BulkBatch).where(
            BulkBatch.id == identifier, BulkBatch.tenant_id == tenant, BulkBatch.subject == subject
        )
        if lock:
            query = query.with_for_update()
        return await self._require_session().scalar(query.execution_options(populate_existing=True))

    async def item(self, batch_id: str, identifier: str, *, lock: bool = False) -> BulkItem | None:
        query = select(BulkItem).where(BulkItem.batch_id == batch_id, BulkItem.id == identifier)
        if lock:
            query = query.with_for_update()
        return await self._require_session().scalar(query.execution_options(populate_existing=True))

    async def all_items(self, batch_id: str) -> list[BulkItem]:
        return list(
            (
                await self._require_session().scalars(
                    select(BulkItem)
                    .where(BulkItem.batch_id == batch_id)
                    .order_by(BulkItem.ordinal, BulkItem.id)
                    .limit(101)
                )
            ).all()
        )

    async def counts(self, batch_id: str) -> dict[str, int]:
        return dict(
            (
                await self._require_session().execute(
                    select(BulkItem.status, func.count())
                    .where(BulkItem.batch_id == batch_id)
                    .group_by(BulkItem.status)
                )
            ).all()
        )

    async def page(self, batch_id: str, page: int, page_size: int) -> tuple[list[BulkItem], int]:
        session = self._require_session()
        where = BulkItem.batch_id == batch_id
        total = int(await session.scalar(select(func.count()).select_from(BulkItem).where(where)) or 0)
        rows = await session.scalars(
            select(BulkItem)
            .where(where)
            .order_by(BulkItem.ordinal, BulkItem.id)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return list(rows.all()), total

    async def visible_page(
        self,
        tenant: str,
        subject: str,
        token_id: str | None,
        page: int,
        page_size: int,
        *,
        allowed_workspaces,
        allowed_assets,
        allowed_resources,
    ) -> tuple[list[BulkBatch], int]:
        workspace, project, parent, source, asset = [aliased(CatalogEntry) for _ in range(5)]
        predicates = [
            BulkBatch.tenant_id == tenant,
            BulkBatch.subject == subject,
            BulkBatch.token_id == token_id,
        ]
        if allowed_workspaces is not None:
            predicates.append(BulkBatch.workspace_id.in_(allowed_workspaces))
        admitted = None
        if allowed_assets is not None:
            admitted = (
                select(CatalogEntry.id, literal(0).label("depth"))
                .where(CatalogEntry.tenant_id == tenant, CatalogEntry.id.in_(allowed_assets))
                .cte("bulk_admitted", recursive=True)
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

        valid_item = exists(
            select(asset.id)
            .select_from(asset)
            .join(source, source.id == asset.parent_id)
            .where(
                asset.id == BulkItem.asset_id,
                source.id == BulkItem.source_id,
                asset.kind == BulkItem.mode,
                source.kind == "source",
                source.parent_id == BulkBatch.parent_id,
                asset.workspace_id == BulkBatch.workspace_id,
                source.workspace_id == BulkBatch.workspace_id,
                asset.project_id == BulkBatch.project_id,
                source.project_id == BulkBatch.project_id,
                visible(source),
                visible(asset),
            )
            .correlate(BulkItem, BulkBatch)
        )
        denied_item = exists(
            select(BulkItem.id).where(BulkItem.batch_id == BulkBatch.id, ~valid_item).correlate(BulkBatch)
        )
        statement = (
            select(BulkBatch)
            .join(workspace, workspace.id == BulkBatch.workspace_id)
            .join(project, project.id == BulkBatch.project_id)
            .join(parent, parent.id == BulkBatch.parent_id)
            .where(
                *predicates,
                workspace.kind == "workspace",
                workspace.parent_id.is_(None),
                workspace.workspace_id == workspace.id,
                project.kind == "project",
                project.parent_id == workspace.id,
                project.workspace_id == workspace.id,
                project.project_id == project.id,
                parent.kind.in_(["collection", "corpus"]),
                parent.parent_id == project.id,
                parent.workspace_id == workspace.id,
                parent.project_id == project.id,
                visible(workspace),
                visible(project),
                visible(parent),
                ~denied_item,
            )
        )
        session = self._require_session()
        total = int(await session.scalar(select(func.count()).select_from(statement.subquery())) or 0)
        rows = await session.scalars(
            statement.order_by(BulkBatch.created_at.desc(), BulkBatch.id)
            .offset((page - 1) * page_size)
            .limit(page_size)
            .execution_options(populate_existing=True)
        )
        return list(rows.all()), total

    async def add_item(self, item: BulkItem) -> None:
        self._require_session().add(item)
        await self._require_session().flush()

    async def upload(self, item: str, key: str) -> BulkUpload | None:
        return await self._require_session().scalar(
            select(BulkUpload)
            .where(BulkUpload.item_id == item, BulkUpload.key_hash == key)
            .execution_options(populate_existing=True)
        )

    async def upload_count(self, item_id: str) -> int:
        return int(
            await self._require_session().scalar(
                select(func.count()).select_from(BulkUpload).where(BulkUpload.item_id == item_id)
            )
            or 0
        )

    async def clock(self) -> datetime:
        session = self._require_session()
        value = await session.scalar(
            select(
                func.clock_timestamp()
                if session.get_bind().dialect.name == "postgresql"
                else func.current_timestamp()
            )
        )
        if isinstance(value, str):
            value = datetime.fromisoformat(value)
        if not isinstance(value, datetime):
            raise ServiceUnavailableException("Primary clock is unavailable", code="BULK_DATABASE_CLOCK")
        return value.replace(tzinfo=UTC) if value.tzinfo is None else value

    async def expired_staging(self) -> list[tuple[str, str, int]]:
        timestamp = await self.clock()
        rows = await self._require_session().execute(
            select(BulkBatch.tenant_id, BulkUploadState.upload_id, BulkUploadState.generation)
            .select_from(BulkBatch)
            .join(BulkItem, BulkItem.batch_id == BulkBatch.id)
            .join(BulkUpload, BulkUpload.item_id == BulkItem.id)
            .join(BulkUploadState, BulkUploadState.upload_id == BulkUpload.id)
            .where(
                BulkUploadState.operation.in_(["writing", "verifying"]),
                BulkUploadState.lease_until <= timestamp,
            )
            .order_by(BulkUploadState.lease_until, BulkUploadState.upload_id)
            .limit(32)
        )
        return [(row[0], row[1], row[2]) for row in rows]

    async def upload_state(self, identifier: str, *, lock: bool = False) -> BulkUploadState | None:
        query = select(BulkUploadState).where(BulkUploadState.upload_id == identifier)
        if lock:
            query = query.with_for_update()
        return await self._require_session().scalar(query.execution_options(populate_existing=True))

    async def recovery(self, batch: str, key_hash: str) -> BulkRecovery | None:
        return await self._require_session().scalar(
            select(BulkRecovery)
            .where(BulkRecovery.batch_id == batch, BulkRecovery.key_hash == key_hash)
            .with_for_update()
            .execution_options(populate_existing=True)
        )

    async def recovery_by_id(self, identifier: str) -> BulkRecovery | None:
        return await self._require_session().scalar(
            select(BulkRecovery)
            .where(BulkRecovery.id == identifier)
            .with_for_update()
            .execution_options(populate_existing=True)
        )

    async def add_upload_state(self, state: BulkUploadState) -> None:
        self._require_session().add(state)
        await self._require_session().flush()

    async def add_recovery(self, row: BulkRecovery) -> None:
        self._require_session().add(row)
        await self._require_session().flush()

    async def upload_by_id(self, identifier: str, *, lock: bool = False) -> BulkUpload | None:
        query = select(BulkUpload).where(BulkUpload.id == identifier)
        if lock:
            query = query.with_for_update()
        return await self._require_session().scalar(query.execution_options(populate_existing=True))

    async def tenant_upload(self, tenant: str, identifier: str, *, lock: bool = False) -> BulkUpload | None:
        query = (
            select(BulkUpload)
            .join(BulkItem, BulkItem.id == BulkUpload.item_id)
            .join(BulkBatch, BulkBatch.id == BulkItem.batch_id)
            .where(BulkUpload.id == identifier, BulkBatch.tenant_id == tenant)
        )
        if lock:
            query = query.with_for_update(of=BulkUpload)
        return await self._require_session().scalar(query.execution_options(populate_existing=True))

    async def latest_upload(self, item_id: str) -> BulkUpload | None:
        return await self._require_session().scalar(
            select(BulkUpload)
            .where(BulkUpload.item_id == item_id)
            .order_by(BulkUpload.created_at.desc(), BulkUpload.id)
            .limit(1)
        )

    async def add_upload(self, row: BulkUpload) -> None:
        self._require_session().add(row)
        await self._require_session().flush()

    async def flush(self) -> None:
        await self._require_session().flush()

    async def connection(self, tenant: str, workspace: str, mode: str) -> dict:
        session = self._require_session()
        domain = "documents" if mode == "document" else "structured"
        role = "documents.embedding" if mode == "document" else "structured.embedding"
        selected = None
        for scope in [workspace, None]:
            selected = await session.scalar(
                select(KnowledgeConnection)
                .where(
                    KnowledgeConnection.tenant_id == tenant,
                    KnowledgeConnection.workspace_id == scope,
                    KnowledgeConnection.domain == domain,
                    KnowledgeConnection.role == role,
                )
                .with_for_update(read=True)
                .execution_options(populate_existing=True)
            )
            if selected is not None:
                break
        provider = (
            await session.scalar(
                select(Provider)
                .where(Provider.id == selected.provider_id, Provider.tenant_id == tenant)
                .with_for_update(read=True)
                .execution_options(populate_existing=True)
            )
            if selected
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
            or not selected.dimensions
            or not selected.embedding_fingerprint
        ):
            raise ServiceUnavailableException(
                "A current validated ingestion embedding connection is required",
                code="BULK_CONNECTION_REQUIRED",
            )
        return {
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

    async def workspace_matches(self, tenant: str, workspace: str, domain: str, native_id: str) -> bool:
        binding = await self._require_session().scalar(
            select(DomainBinding)
            .where(
                DomainBinding.tenant_id == tenant,
                DomainBinding.catalog_id == workspace,
                DomainBinding.domain == domain,
                DomainBinding.entity_kind == "workspace",
            )
            .with_for_update(read=True)
            .execution_options(populate_existing=True)
        )
        return (
            binding is not None
            and binding.workspace_id == workspace
            and binding.native_id == native_id
            and binding.native_workspace_id == native_id
        )

    async def claim(
        self, worker: str, lease_seconds: int, global_limit: int, tenant_limit: int
    ) -> tuple[Job, BulkItem, BulkBatch] | None:
        session = self._require_session()
        timestamp = now()
        await self.quota("global:workers")
        active = await session.scalar(
            select(func.count())
            .select_from(Job)
            .where(
                Job.kind.in_(["knowledge.bulk.intake", "knowledge.bulk.query"]),
                Job.status == "running",
                Job.lease_until > timestamp,
            )
        )
        if int(active or 0) >= global_limit:
            return None
        due = or_(
            and_(Job.status == "queued", Job.available_at <= timestamp),
            and_(Job.status == "running", Job.lease_until < timestamp),
        )
        ranked = (
            select(
                Job.id.label("id"),
                Job.tenant_id.label("tenant"),
                func.row_number()
                .over(partition_by=Job.tenant_id, order_by=(Job.available_at, Job.created_at, Job.id))
                .label("position"),
            )
            .join(BulkItem, BulkItem.job_id == Job.id)
            .join(BulkBatch, BulkBatch.id == BulkItem.batch_id)
            .where(
                Job.kind == "knowledge.bulk.intake",
                due,
                BulkBatch.cancelled.is_(False),
                BulkItem.status.in_(["queued", "running"]),
            )
            .subquery()
        )
        identifiers = (
            await session.execute(
                select(ranked.c.id, ranked.c.tenant)
                .where(ranked.c.position == 1)
                .order_by(ranked.c.id)
                .limit(100)
            )
        ).all()
        for identifier, tenant in identifiers:
            tenant_row = await session.scalar(
                select(Tenant).where(Tenant.id == tenant).with_for_update(skip_locked=True)
            )
            if tenant_row is None:
                continue
            target = await session.scalar(select(BulkItem).where(BulkItem.job_id == identifier))
            batch = (
                await session.scalar(
                    select(BulkBatch)
                    .where(BulkBatch.id == target.batch_id)
                    .with_for_update()
                    .execution_options(populate_existing=True)
                )
                if target
                else None
            )
            item = (
                await session.scalar(
                    select(BulkItem)
                    .where(BulkItem.id == target.id)
                    .with_for_update()
                    .execution_options(populate_existing=True)
                )
                if target
                else None
            )
            job = await session.scalar(
                select(Job)
                .where(Job.id == identifier, due)
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
            owned = await session.scalar(
                select(func.count())
                .select_from(Job)
                .where(
                    Job.kind.in_(["knowledge.bulk.intake", "knowledge.bulk.query"]),
                    Job.tenant_id == job.tenant_id,
                    Job.status == "running",
                    Job.lease_until > timestamp,
                )
            )
            if int(owned or 0) >= tenant_limit:
                continue
            if job.attempts >= job.max_attempts:
                job.status = "failed"
                job.lease_until = None
                job.worker_id = None
                item.status = "reconciling"
                item.error_code = "BULK_RECOVERY_REQUIRED"
                batch.revision += 1
                continue
            job.status = "running"
            job.worker_id = worker
            job.attempts += 1
            job.lease_until = timestamp + timedelta(seconds=lease_seconds)
            job.updated_at = timestamp
            item.status = "running"
            batch.revision += 1
            await session.flush()
            return job, item, batch
        return None

    async def job(self, identifier: str) -> Job | None:
        return await self._require_session().scalar(
            select(Job)
            .where(Job.id == identifier, Job.kind == "knowledge.bulk.intake")
            .with_for_update()
            .execution_options(populate_existing=True)
        )

    async def claimed(self, item_id: str, worker: str, attempt: int) -> tuple[Job, BulkItem, BulkBatch]:
        item = await self._require_session().scalar(select(BulkItem).where(BulkItem.id == item_id))
        batch = (
            await self._require_session().scalar(select(BulkBatch).where(BulkBatch.id == item.batch_id))
            if item
            else None
        )
        if batch is None:
            raise ConflictException("Bulk worker lost its claimed item", code="BULK_LEASE_LOST")
        return await self.fenced(batch.tenant_id, item_id, worker, attempt)

    async def fenced(
        self, tenant: str, item_id: str, worker: str, attempt: int
    ) -> tuple[Job, BulkItem, BulkBatch]:
        session = self._require_session()
        target = await session.scalar(
            select(BulkItem)
            .join(BulkBatch, BulkBatch.id == BulkItem.batch_id)
            .where(BulkItem.id == item_id, BulkBatch.tenant_id == tenant)
        )
        batch = (
            await session.scalar(
                select(BulkBatch)
                .where(BulkBatch.id == target.batch_id)
                .with_for_update()
                .execution_options(populate_existing=True)
            )
            if target
            else None
        )
        item = (
            await session.scalar(
                select(BulkItem)
                .where(BulkItem.id == item_id)
                .with_for_update()
                .execution_options(populate_existing=True)
            )
            if target
            else None
        )
        job = (
            await session.scalar(
                select(Job)
                .where(Job.id == item.job_id)
                .with_for_update()
                .execution_options(populate_existing=True)
            )
            if item
            else None
        )
        if (
            batch is None
            or item is None
            or job is None
            or batch.cancelled
            or item.status != "running"
            or job.kind != "knowledge.bulk.intake"
            or job.status != "running"
            or job.worker_id != worker
            or job.attempts != attempt
            or job.lease_until is None
            or job.lease_until <= now()
        ):
            raise ConflictException("Bulk worker lost the exact live attempt", code="BULK_LEASE_LOST")
        return job, item, batch
