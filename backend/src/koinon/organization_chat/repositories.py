# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from pyfly.container import repository
from pyfly.data.relational.sqlalchemy import Repository
from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as postgres_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from koinon.organization_chat.entities import OrganizationChatSetting


@repository(name="organization_chat.repository")
class OrganizationChatRepository(Repository[OrganizationChatSetting, str]):
    async def current(self, tenant_id):
        return await self._require_session().scalar(
            select(OrganizationChatSetting)
            .where(OrganizationChatSetting.tenant_id == tenant_id)
            .execution_options(populate_existing=True)
        )

    async def compare_and_swap(self, tenant_id, agent_id, revision, actor, at):
        session = self._require_session()
        values = dict(default_agent_id=agent_id, revision=revision + 1, updated_by=actor, updated_at=at)
        if revision == 0:
            # Atomic insert covers the absent-row race on PostgreSQL and SQLite.
            insert = sqlite_insert if session.get_bind().dialect.name == "sqlite" else postgres_insert
            result = await session.execute(
                insert(OrganizationChatSetting)
                .values(tenant_id=tenant_id, **values)
                .on_conflict_do_nothing(index_elements=["tenant_id"])
                .returning(OrganizationChatSetting.tenant_id)
            )
        else:
            result = await session.execute(
                update(OrganizationChatSetting)
                .where(
                    OrganizationChatSetting.tenant_id == tenant_id,
                    OrganizationChatSetting.revision == revision,
                )
                .values(**values)
                .returning(OrganizationChatSetting.tenant_id)
            )
        return result.scalar_one_or_none() is not None
