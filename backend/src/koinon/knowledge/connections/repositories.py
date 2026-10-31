# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from pyfly.container import repository
from pyfly.data.relational.sqlalchemy import Repository
from sqlalchemy import select

from koinon.catalog.entities import AuditEvent, Tenant
from koinon.knowledge.connections.entities import KnowledgeConnection


@repository(name="knowledge.connection_repository")
class KnowledgeConnectionRepository(Repository[KnowledgeConnection, str]):
    """Tenant defaults and canonical workspace overrides; credentials remain in providers."""

    async def lock_tenant(self, tenant_id: str) -> None:
        await self._require_session().scalar(select(Tenant).where(Tenant.id == tenant_id).with_for_update())

    async def find_conflicting_embedding_history(self, tenant_id, role, spaces, fingerprint):
        statement = (
            select(AuditEvent.id)
            .where(
                AuditEvent.tenant_id == tenant_id,
                AuditEvent.action == "knowledge.connection.saved",
                AuditEvent.details["role"].as_string() == role,
                AuditEvent.details["space_id"].as_string().in_(tuple(spaces)),
                AuditEvent.details["embedding_fingerprint"].as_string() != fingerprint,
            )
            .limit(1)
        )
        return await self._require_session().scalar(statement)

    async def pending_index(self, tenant_id, domain, workspace_id):
        from sqlalchemy import text

        session = self._require_session()
        if session.get_bind().dialect.name == "postgresql":
            exists = await session.scalar(text("SELECT to_regclass('public.koinon_knowledge_indexes')"))
        else:
            exists = await session.scalar(
                text("SELECT name FROM sqlite_master WHERE type='table' AND name='koinon_knowledge_indexes'")
            )
        if not exists:
            return None
        return await session.scalar(
            text(
                "SELECT id FROM koinon_knowledge_indexes WHERE tenant_id=:tenant AND domain=:doma"
                "in AND native_workspace_id=:workspace AND status='activating' LIMIT 1"
            ),
            {"tenant": tenant_id, "domain": domain, "workspace": workspace_id},
        )
