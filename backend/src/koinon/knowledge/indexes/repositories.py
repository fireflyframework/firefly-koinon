# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from pyfly.container import repository
from pyfly.data.relational.sqlalchemy import Repository
from sqlalchemy import and_, func, or_, select

from koinon.catalog.entities import CatalogEntry
from koinon.jobs.entities import Job
from koinon.knowledge.entities import DomainBinding
from koinon.knowledge.indexes.entities import KnowledgeIndex


@repository(name="knowledge.index_repository")
class KnowledgeIndexRepository(Repository[KnowledgeIndex, str]):
    @staticmethod
    def mode_scope(tenant_id, parent_id, status=None):
        return (
            KnowledgeIndex.tenant_id == tenant_id,
            or_(
                KnowledgeIndex.transition["parent_mode_transition_id"].as_string() == parent_id,
                and_(
                    KnowledgeIndex.transition["parent_mode_transition_id"].as_string().is_(None),
                    Job.tenant_id == tenant_id,
                    Job.kind == "knowledge.index",
                    Job.payload["parent_mode_transition_id"].as_string() == parent_id,
                ),
            ),
            *((KnowledgeIndex.status == status,) if status is not None else ()),
        )

    async def mode_children(self, tenant_id, parent_id, *, status=None, lock=False, limit=200, after_id=None):
        if type(limit) is not int or not 1 <= limit <= 200:
            raise ValueError("Index child pages contain 1 to 200 records")
        statement = (
            select(KnowledgeIndex)
            .outerjoin(Job, KnowledgeIndex.job_id == Job.id)
            .where(*self.mode_scope(tenant_id, parent_id, status))
            .order_by(KnowledgeIndex.id)
            .limit(limit)
            .execution_options(populate_existing=True)
        )
        if after_id is not None:
            statement = statement.where(KnowledgeIndex.id > after_id)
        if lock:
            statement = statement.with_for_update(of=KnowledgeIndex)
        return list(await self._require_session().scalars(statement))

    async def count_mode_recoveries(self, tenant_id, parent_id):
        return int(
            await self._require_session().scalar(
                select(func.count())
                .select_from(KnowledgeIndex)
                .outerjoin(Job, KnowledgeIndex.job_id == Job.id)
                .where(*self.mode_scope(tenant_id, parent_id, "activating"))
            )
            or 0
        )

    async def mode_ready_candidates(
        self, tenant_id, workspace_id, native_workspace_id, *, provider_id, model_id, after=None
    ):
        statement = select(KnowledgeIndex).where(
            KnowledgeIndex.tenant_id == tenant_id,
            KnowledgeIndex.workspace_id == workspace_id,
            KnowledgeIndex.native_workspace_id == native_workspace_id,
            KnowledgeIndex.domain == "documents",
            KnowledgeIndex.provider_id == provider_id,
            KnowledgeIndex.model_id == model_id,
            KnowledgeIndex.status.in_(("ready", "retired")),
        )
        if after is not None:
            statement = statement.where(KnowledgeIndex.id > after)
        return list(
            await self._require_session().scalars(
                statement.order_by(KnowledgeIndex.id).limit(1).execution_options(populate_existing=True)
            )
        )

    async def find_initial_workspace_effects(self, tenant_id, workspace_id, run_id, index_id) -> bool:
        catalog = (
            select(CatalogEntry.id)
            .where(
                CatalogEntry.tenant_id == tenant_id,
                CatalogEntry.workspace_id == workspace_id,
                or_(
                    CatalogEntry.installation_run_id.is_distinct_from(run_id),
                    CatalogEntry.kind.not_in(("workspace", "project", "collection", "corpus")),
                    CatalogEntry.created_by != "system:installation",
                ),
            )
            .exists()
        )
        bindings = (
            select(DomainBinding.id)
            .where(
                DomainBinding.tenant_id == tenant_id,
                DomainBinding.workspace_id == workspace_id,
            )
            .exists()
        )
        indexes = (
            select(KnowledgeIndex.id)
            .where(
                KnowledgeIndex.tenant_id == tenant_id,
                KnowledgeIndex.workspace_id == workspace_id,
                KnowledgeIndex.id != index_id,
            )
            .exists()
        )
        return bool(await self._require_session().scalar(select(or_(catalog, bindings, indexes))))

    async def page(
        self,
        tenant_id,
        workspace_id,
        domain,
        *,
        limit,
        offset,
        status=None,
        dimensions=None,
        model_id=None,
        provider_kind=None,
    ):
        scope = (
            KnowledgeIndex.tenant_id == tenant_id,
            KnowledgeIndex.workspace_id == workspace_id,
            KnowledgeIndex.domain == domain,
        )
        scope = (
            *scope,
            *(
                getattr(KnowledgeIndex, key) == value
                for key, value in (
                    ("status", status),
                    ("dimensions", dimensions),
                    ("model_id", model_id),
                    ("provider_kind", provider_kind),
                )
                if value is not None
            ),
        )
        session = self._require_session()
        count = await session.scalar(select(func.count()).select_from(KnowledgeIndex).where(*scope))
        rows = await session.scalars(
            select(KnowledgeIndex)
            .where(*scope)
            .order_by(KnowledgeIndex.created_at.desc(), KnowledgeIndex.id)
            .limit(limit)
            .offset(offset)
        )
        return list(rows), count or 0

    async def for_native_ids(self, tenant_id, domain, workspace_id, native_ids):
        if not native_ids:
            return []
        return list(
            await self._require_session().scalars(
                select(KnowledgeIndex).where(
                    KnowledgeIndex.tenant_id == tenant_id,
                    KnowledgeIndex.domain == domain,
                    KnowledgeIndex.native_workspace_id == workspace_id,
                    KnowledgeIndex.native_id.in_(native_ids),
                )
            )
        )
