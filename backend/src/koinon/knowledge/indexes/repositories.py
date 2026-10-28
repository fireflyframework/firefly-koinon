# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from pyfly.container import repository
from pyfly.data.relational.sqlalchemy import Repository
from sqlalchemy import func, select

from koinon.knowledge.indexes.entities import KnowledgeIndex


@repository(name="knowledge.index_repository")
class KnowledgeIndexRepository(Repository[KnowledgeIndex, str]):
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
