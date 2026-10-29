# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from pyfly.container import repository
from pyfly.data.relational.sqlalchemy import Repository
from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as postgres_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from koinon.organization_knowledge.entities import OrganizationKnowledgeSetting


@repository(name="organization_knowledge.repository")
class OrganizationKnowledgeRepository(Repository[OrganizationKnowledgeSetting, str]):
    async def current(self, tenant_id):
        return await self._require_session().scalar(
            select(OrganizationKnowledgeSetting)
            .where(OrganizationKnowledgeSetting.tenant_id == tenant_id)
            .execution_options(populate_existing=True)
        )

    async def compare_and_swap(self, tenant_id, documents, structured, revision, actor, at):
        session = self._require_session()
        values = dict(
            schema_version=1,
            documents=documents,
            structured=structured,
            revision=revision + 1,
            updated_by=actor,
            updated_at=at,
        )
        if revision == 0:
            insert = sqlite_insert if session.get_bind().dialect.name == "sqlite" else postgres_insert
            result = await session.execute(
                insert(OrganizationKnowledgeSetting)
                .values(tenant_id=tenant_id, **values)
                .on_conflict_do_nothing(index_elements=["tenant_id"])
                .returning(OrganizationKnowledgeSetting.tenant_id)
            )
        else:
            result = await session.execute(
                update(OrganizationKnowledgeSetting)
                .where(
                    OrganizationKnowledgeSetting.tenant_id == tenant_id,
                    OrganizationKnowledgeSetting.revision == revision,
                )
                .values(**values)
                .returning(OrganizationKnowledgeSetting.tenant_id)
            )
        return result.scalar_one_or_none() is not None
