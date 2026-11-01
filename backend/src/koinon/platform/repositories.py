# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Bounded tenant metadata projections exclude names, payloads and credential configuration."""

from dataclasses import dataclass

from pyfly.container import repository
from pyfly.data.relational.sqlalchemy import Repository
from pyfly.data.transaction import transactional
from sqlalchemy import and_, exists, select

from koinon.assistants.entities import AgentConfiguration, Provider
from koinon.catalog.entities import CatalogEntry
from koinon.knowledge.entities import DomainBinding
from koinon.knowledge.indexes.entities import KnowledgeIndex
from koinon.organization_chat.entities import OrganizationChatSetting


@dataclass(frozen=True, slots=True)
class StatusWindow:
    states: tuple[str, ...]
    complete: bool


@dataclass(frozen=True, slots=True)
class IndexTarget:
    id: str
    workspace_id: str
    native_workspace_id: str
    native_id: str
    domain: str
    status: str
    dimensions: int


@repository
class PlatformRepository(Repository[CatalogEntry, str]):
    @transactional(read_only=True, read_from_primary=True)
    async def catalog_states(self, tenant_id: str, kind: str, *, limit: int = 1000) -> StatusWindow:
        if kind not in {"document", "dataset"} or not 1 <= limit <= 1000:
            raise ValueError("Select a bounded native knowledge category")
        rows = (
            (
                await self._require_session().execute(
                    select(CatalogEntry.status)
                    .where(
                        CatalogEntry.tenant_id == tenant_id,
                        CatalogEntry.kind == kind,
                        CatalogEntry.status != "archived",
                    )
                    .order_by(CatalogEntry.id)
                    .limit(limit + 1)
                )
            )
            .scalars()
            .all()
        )
        return StatusWindow(tuple(rows[:limit]), len(rows) <= limit)

    @transactional(read_only=True, read_from_primary=True)
    async def index_targets(
        self, tenant_id: str, *, limit: int = 100
    ) -> tuple[tuple[IndexTarget, ...], bool]:
        if not 1 <= limit <= 100:
            raise ValueError("Select a bounded index sample")
        rows = (
            await self._require_session().execute(
                select(
                    KnowledgeIndex.id,
                    KnowledgeIndex.workspace_id,
                    KnowledgeIndex.native_workspace_id,
                    KnowledgeIndex.native_id,
                    KnowledgeIndex.domain,
                    KnowledgeIndex.status,
                    KnowledgeIndex.dimensions,
                )
                .join(
                    CatalogEntry,
                    and_(
                        CatalogEntry.id == KnowledgeIndex.workspace_id,
                        CatalogEntry.tenant_id == KnowledgeIndex.tenant_id,
                    ),
                )
                .where(KnowledgeIndex.tenant_id == tenant_id, CatalogEntry.status != "archived")
                .order_by(KnowledgeIndex.id)
                .limit(limit + 1)
            )
        ).all()
        return tuple(IndexTarget(*row) for row in rows[:limit]), len(rows) <= limit

    @transactional(read_only=True, read_from_primary=True)
    async def workspaces(
        self, tenant_id: str, domain: str, *, limit: int = 32
    ) -> tuple[tuple[str, str], ...]:
        if domain not in {"canon", "structured"} or not 1 <= limit <= 32:
            raise ValueError("Select a bounded native workspace scope")
        rows = (
            await self._require_session().execute(
                select(DomainBinding.workspace_id, DomainBinding.native_workspace_id)
                .join(
                    CatalogEntry,
                    and_(
                        CatalogEntry.id == DomainBinding.catalog_id,
                        CatalogEntry.tenant_id == DomainBinding.tenant_id,
                    ),
                )
                .where(
                    DomainBinding.tenant_id == tenant_id,
                    DomainBinding.domain == domain,
                    CatalogEntry.status != "archived",
                )
                .distinct()
                .order_by(DomainBinding.workspace_id, DomainBinding.native_workspace_id)
                .limit(limit + 1)
            )
        ).all()
        return tuple((row[0], row[1]) for row in rows)

    @transactional(read_only=True, read_from_primary=True)
    async def model_default_configured(self, tenant_id: str) -> bool:
        selected = select(OrganizationChatSetting.tenant_id).join(
            AgentConfiguration,
            and_(
                AgentConfiguration.tenant_id == OrganizationChatSetting.tenant_id,
                AgentConfiguration.id == OrganizationChatSetting.default_agent_id,
            ),
        )
        selected = selected.join(
            Provider,
            and_(
                Provider.tenant_id == AgentConfiguration.tenant_id,
                Provider.id == AgentConfiguration.provider_id,
            ),
        )
        selected = selected.where(
            OrganizationChatSetting.tenant_id == tenant_id,
            AgentConfiguration.enabled.is_(True),
            Provider.enabled.is_(True),
            AgentConfiguration.model_id != "",
        )
        return bool(await self._require_session().scalar(select(exists(selected))))
