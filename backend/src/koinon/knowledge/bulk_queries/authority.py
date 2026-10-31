# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from uuid import UUID

from pyfly.container import Provider, service
from pyfly.kernel import ConflictException, ServiceUnavailableException

from koinon.catalog.entities import CatalogEntry
from koinon.catalog.errors import AccessDenied
from koinon.catalog.service import ROLE_PERMISSIONS
from koinon.knowledge.bulk.authority import token_identity
from koinon.knowledge.bulk.repositories import BulkRepository
from koinon.knowledge.bulk_queries.entities import QueryBatchItem
from koinon.knowledge.bulk_queries.native_values import QuerySnapshotReference
from koinon.knowledge.bulk_queries.repositories import QueryBatchRepository
from koinon.knowledge.entities import DomainBinding
from koinon.knowledge.service import KnowledgeFacade
from koinon.organization_knowledge.dtos import OrganizationKnowledgeSnapshot


def query_roles(snapshot: OrganizationKnowledgeSnapshot) -> tuple[str, ...]:
    roles = ("structured.embedding", "structured.grounding", "structured.generation", "structured.explainer")
    return (*roles, "structured.critic") if snapshot.structured.max_refine_retries > 0 else roles


@service(name="knowledge.bulk_queries.authority")
class QueryBatchAuthority:
    def __init__(
        self, facades: Provider[KnowledgeFacade | None], shared: BulkRepository, records: QueryBatchRepository
    ):
        self.facades, self.shared, self.records = facades, shared, records

    def facade(self) -> KnowledgeFacade:
        value = self.facades.get()
        if value is None:
            raise ServiceUnavailableException(
                "Canonical queries are unavailable", code="BULK_QUERY_NATIVE_REQUIRED"
            )
        if token_identity() and value.catalog.restriction is None:
            raise AccessDenied("Original token cannot be verified", code="TOKEN_UNAVAILABLE")
        return value

    async def workspace(self, subject: str, tenant: str, workspace_id: str, *, write: bool = False) -> None:
        facade = self.facade()
        if write:
            await self.shared.authority_lock(tenant, subject, token_identity())
            await self.shared.catalog_locks(tenant, (workspace_id,))
        workspace = await facade.catalog.get(subject, tenant, workspace_id)
        if workspace.kind != "workspace" or workspace.status == "archived":
            raise AccessDenied("Query workspace unavailable", code="ACCESS_DENIED")
        await facade.catalog.authorize(subject, tenant, "query:execute", workspace_id)
        if facade.catalog.restriction:
            await facade.catalog.restriction.resource(subject, workspace)

    async def dataset(
        self, subject: str, tenant: str, workspace_id: str, dataset_id: str, *, write: bool = False
    ) -> DomainBinding:
        facade = self.facade()
        chain = await facade._chain(subject, tenant, dataset_id, "query:execute")
        if write:
            await self.shared.catalog_locks(tenant, tuple(row.id for row in chain))
            chain = await facade._chain(subject, tenant, dataset_id, "query:execute")
        dataset = chain[0]
        if dataset.kind != "dataset" or dataset.workspace_id != workspace_id:
            raise AccessDenied("Query dataset differs from workspace", code="BULK_QUERY_SCOPE_CHANGED")
        facade._ready_dataset(dataset)
        binding = await self.records.binding(tenant, dataset_id, lock=write)
        workspace = await self.records.binding(tenant, workspace_id, lock=write)
        if (
            binding is None
            or workspace is None
            or binding.entity_kind != "dataset"
            or workspace.entity_kind != "workspace"
            or binding.workspace_id != workspace_id
            or workspace.workspace_id != workspace_id
            or binding.native_workspace_id != workspace.native_id
            or workspace.native_id != workspace.native_workspace_id
        ):
            raise ConflictException("Current native query binding required", code="BULK_QUERY_SCOPE_CHANGED")
        try:
            UUID(binding.native_workspace_id)
            UUID(binding.native_id)
        except (ValueError, TypeError, AttributeError):
            raise ConflictException(
                "Native query identities cannot be verified", code="BULK_QUERY_SCOPE_CHANGED"
            ) from None
        return binding

    async def item(
        self, subject: str, tenant: str, workspace_id: str, item: QueryBatchItem, *, write: bool = False
    ) -> None:
        binding = await self.dataset(subject, tenant, workspace_id, item.dataset_id, write=write)
        if (
            binding.native_id != item.native_dataset_id
            or binding.native_workspace_id != item.native_workspace_id
        ):
            raise ConflictException("Admitted native dataset changed", code="BULK_QUERY_SCOPE_CHANGED")
        references = await self.records.references(item.id)
        if len(references) > 128:
            raise AccessDenied("Query references exceed their bound", code="BULK_QUERY_SCOPE_CHANGED")
        if write:
            await self.shared.catalog_locks(tenant, tuple(ref.catalog_id for ref in references))
        facade = self.facade()
        for reference in references:
            chain = await facade._chain(subject, tenant, reference.catalog_id, "query:execute")
            table = chain[0]
            if (
                table.kind != "table"
                or table.parent_id != item.dataset_id
                or table.workspace_id != workspace_id
            ):
                raise AccessDenied("Saved query table unavailable", code="BULK_QUERY_SCOPE_CHANGED")
            binding = await self.records.binding(tenant, table.id, lock=write)
            if (
                binding is None
                or binding.entity_kind != "table"
                or binding.native_id != reference.native_table_id
                or binding.native_workspace_id != item.native_workspace_id
            ):
                raise AccessDenied("Saved query binding changed", code="BULK_QUERY_SCOPE_CHANGED")

    async def snapshot_alias(
        self,
        subject: str,
        tenant: str,
        workspace_id: str,
        item: QueryBatchItem,
        reference: QuerySnapshotReference,
    ) -> CatalogEntry:
        aliases = await self.records.aliases(
            tenant, workspace_id, item.dataset_id, item.native_workspace_id, str(reference.table_id)
        )
        if len(aliases) != 1:
            raise AccessDenied(
                "A unique current query table binding is required", code="BULK_QUERY_SCOPE_CHANGED"
            )
        table = aliases[0]
        chain = await self.facade()._chain(subject, tenant, table.id, "query:execute")
        if chain[0].parent_id != item.dataset_id or chain[0].workspace_id != workspace_id:
            raise AccessDenied("Query table scope differs", code="BULK_QUERY_SCOPE_CHANGED")
        return table

    async def read_bounds(self, subject: str, tenant: str) -> dict:
        catalog = self.facade().catalog
        members = [
            row
            for row in await catalog.memberships(subject)
            if row.tenant_id == tenant and "query:execute" in ROLE_PERMISSIONS.get(row.role, ())
        ]
        if not members:
            raise AccessDenied("Query history unavailable", code="ACCESS_DENIED")
        allowed = (
            None
            if any(row.workspace_id is None for row in members)
            else [row.workspace_id for row in members]
        )
        grant = await catalog.restriction.grant(subject) if catalog.restriction else None
        if grant is not None:
            if grant.tenant_id != tenant or not {"catalog:read", "query:execute"}.issubset(grant.scopes):
                raise AccessDenied("Query history exceeds token scope", code="TOKEN_SCOPE_DENIED")
            if grant.workspace_ids is not None:
                allowed = (
                    grant.workspace_ids
                    if allowed is None
                    else sorted(set(allowed) & set(grant.workspace_ids))
                )
        return {
            "allowed_workspaces": allowed,
            "allowed_assets": grant.asset_ids if grant else None,
            "allowed_resources": grant.resource_ids if grant else None,
        }
