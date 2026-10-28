# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Canonical index authority precedes every native inspection or provider operation."""

from pydantic import ValidationError
from pyfly.container import service
from pyfly.data.relational.sqlalchemy import LockMode, transactional
from pyfly.kernel import InvalidRequestException

from koinon.catalog.errors import AccessDenied
from koinon.knowledge.connections.service import KnowledgeConnectionService
from koinon.knowledge.indexes.adapters import NativeIndexAdapter, index_id
from koinon.knowledge.indexes.dtos import IndexPlanInput
from koinon.knowledge.indexes.mappers import index_dto
from koinon.knowledge.indexes.planner import IndexPlanner
from koinon.knowledge.indexes.repositories import KnowledgeIndexRepository
from koinon.knowledge.service import KnowledgeFacade


@service(name="knowledge.index_service")
class KnowledgeIndexService:
    def __init__(
        self,
        facade: KnowledgeFacade,
        adapter: NativeIndexAdapter,
        connections: KnowledgeConnectionService,
        planner: IndexPlanner,
        records: KnowledgeIndexRepository,
    ):
        self.facade, self.adapter, self.connections = facade, adapter, connections
        self.planner, self.records = planner, records

    async def authority(self, subject, tenant_id, workspace_id, *, write=False):
        chain = await self.facade._chain(subject, tenant_id, workspace_id)
        workspace = chain[0]
        if workspace.kind != "workspace" or workspace.id != workspace_id:
            raise AccessDenied("Select an active canonical workspace", code="ACCESS_DENIED")
        if self.facade.catalog.restriction and not write:
            grant = await self.facade.catalog.restriction.grant(subject)
            if grant is not None and grant.asset_ids is not None:
                raise AccessDenied(
                    "Workspace index inspection requires workspace-scoped access", code="TOKEN_SCOPE_DENIED"
                )
        if write:
            workspace = await self.facade.catalog.catalog_repository.find_by_id(
                workspace_id, lock=LockMode.PESSIMISTIC_READ
            )
            if workspace is None or workspace.tenant_id != tenant_id or workspace.status == "archived":
                raise AccessDenied("Select an active canonical workspace", code="ACCESS_DENIED")
            await self.facade.catalog.authorize(subject, tenant_id, "indexes:manage", workspace_id)
            if self.facade.catalog.restriction:
                await self.facade.catalog.restriction.resource(subject, workspace, write=True)
        return workspace

    async def choices(
        self,
        subject,
        tenant_id,
        *,
        workspace_id,
        domain,
        limit=50,
        offset=0,
        status=None,
        dimensions=None,
        model_id=None,
        provider_kind=None,
    ):
        self.validate_filters(domain, limit, offset, status, dimensions, model_id, provider_kind)
        workspace = await self.authority(subject, tenant_id, workspace_id)
        binding = await self.native_binding(subject, tenant_id, workspace, domain)
        if binding is None:
            return {"items": [], "total": 0, "limit": limit, "offset": offset}
        page = await self.adapter.discover(
            tenant_id=tenant_id,
            native_workspace_id=binding.native_workspace_id,
            catalog_workspace_id=workspace.id,
            domain=domain,
            actor=subject,
            limit=limit,
            offset=offset,
            status=status,
            dimensions=dimensions,
            model_id=model_id,
            provider_kind=provider_kind,
        )
        records = {
            row.native_id: row
            for row in await self.records.for_native_ids(
                tenant_id, domain, binding.native_workspace_id, [item["native_id"] for item in page["items"]]
            )
        }
        for item in page["items"]:
            item["tenant_id"] = tenant_id
            row = records.get(item["native_id"])
            if row is not None:
                item["managed_id"] = row.id
            item.pop("revision", None)
        try:
            await self.connections.authority(subject, tenant_id, workspace_id)
        except AccessDenied:
            for item in page["items"]:
                item.pop("provider_id", None)
        return {**page, "limit": limit, "offset": offset}

    async def list(
        self,
        subject,
        tenant_id,
        *,
        workspace_id,
        domain,
        limit=50,
        offset=0,
        status=None,
        dimensions=None,
        model_id=None,
        provider_kind=None,
    ):
        self.validate_filters(domain, limit, offset, status, dimensions, model_id, provider_kind)
        workspace = await self.authority(subject, tenant_id, workspace_id)
        binding = await self.native_binding(subject, tenant_id, workspace, domain)
        rows, total = await self.records.page(
            tenant_id,
            workspace_id,
            domain,
            limit=limit,
            offset=offset,
            status=status,
            dimensions=dimensions,
            model_id=model_id,
            provider_kind=provider_kind,
        )
        try:
            await self.connections.authority(subject, tenant_id, workspace_id)
            management = True
        except AccessDenied:
            management = False
        items = []
        for row in rows:
            value = index_dto(row, management=management)
            actual = (
                await self.adapter.get_native(
                    tenant_id=tenant_id,
                    native_workspace_id=binding.native_workspace_id,
                    catalog_workspace_id=workspace_id,
                    domain=domain,
                    actor=subject,
                    identifier=row.id,
                )
                if binding
                else None
            )
            if actual:
                value["native_status"] = actual["status"]
                for name in ("chunk_count", "vector_count", "indexed", "qualification"):
                    value[name] = actual[name]
                value["active"] = row.status == "active" and actual["active"]
            else:
                value["qualification"], value["active"] = "native_target_unavailable", False
            items.append(value)
        return {"items": items, "total": total, "limit": limit, "offset": offset}

    @staticmethod
    def validate_filters(
        domain, limit, offset, status=None, dimensions=None, model_id=None, provider_kind=None
    ):
        if (
            domain not in {"documents", "structured"}
            or type(limit) is not int
            or not 1 <= limit <= 100
            or type(offset) is not int
            or offset < 0
            or status
            not in {
                None,
                "legacy",
                "queued",
                "building",
                "awaiting_index",
                "ready",
                "activating",
                "active",
                "retired",
                "failed",
                "cancelled",
            }
            or (dimensions is not None and (type(dimensions) is not int or not 64 <= dimensions <= 4096))
            or (model_id is not None and (not isinstance(model_id, str) or not 1 <= len(model_id) <= 256))
            or (
                provider_kind is not None
                and (not isinstance(provider_kind, str) or not 1 <= len(provider_kind) <= 64)
            )
        ):
            raise InvalidRequestException(
                "Select supported index scope, filters and bounded pagination", code="INVALID_INDEX_QUERY"
            )

    async def choice(self, subject, tenant_id, identifier, *, workspace_id, domain):
        self.validate_filters(domain, 1, 0)
        workspace = await self.authority(subject, tenant_id, workspace_id)
        binding = await self.native_binding(subject, tenant_id, workspace, domain)
        value = (
            await self.adapter.get_native(
                tenant_id=tenant_id,
                native_workspace_id=binding.native_workspace_id,
                catalog_workspace_id=workspace_id,
                domain=domain,
                actor=subject,
                identifier=identifier,
            )
            if binding
            else None
        )
        if value is None or binding is None:
            raise AccessDenied("Native index choice is unavailable in this workspace", code="ACCESS_DENIED")
        value.pop("revision", None)
        value["tenant_id"] = tenant_id
        rows = await self.records.for_native_ids(
            tenant_id, domain, binding.native_workspace_id, [value["native_id"]]
        )
        if rows:
            value["managed_id"] = rows[0].id
        return value

    async def native_binding(self, subject, tenant_id, workspace, domain, *, write=False, create=False):
        native = "canon" if domain == "documents" else "structured"
        rows = await self.facade.bindings.find_all(
            tenant_id=tenant_id, catalog_id=workspace.id, domain=native
        )
        if not rows:
            return await self.facade._workspace(subject, tenant_id, workspace, native) if create else None
        binding = await self.facade.binding(tenant_id, workspace.id, native, entry=workspace)
        aliases = await self.facade.bindings.find_all(
            tenant_id=tenant_id,
            domain=native,
            entity_kind="workspace",
            native_id=binding.native_workspace_id,
        )
        for alias in sorted(aliases, key=lambda value: value.catalog_id):
            await self.authority(subject, tenant_id, alias.catalog_id, write=write)
            if write:
                await self.connections.authority(subject, tenant_id, alias.catalog_id)
        return binding

    @transactional
    async def plan(self, subject, tenant_id, values):
        try:
            data = IndexPlanInput.model_validate(values)
        except ValidationError as error:
            raise InvalidRequestException(
                "Provide valid index planning fields", code="INVALID_INDEX_PLAN"
            ) from error
        workspace = await self.authority(subject, tenant_id, data.workspace_id, write=True)
        await self.connections.authority(subject, tenant_id, workspace.id)
        binding = await self.native_binding(subject, tenant_id, workspace, data.domain, write=True)
        provider, profile = await self.planner.prepare(tenant_id, data)
        role = data.domain + ".embedding"
        current = await self.connections.selected(tenant_id, workspace.id, data.domain, role)
        overview = (
            await self.adapter.overview(
                tenant_id=tenant_id,
                workspace_id=binding.native_workspace_id,
                domain=data.domain,
                actor=subject,
            )
            if binding
            else {"active_native_id": None, "chunk_count": 0}
        )
        active = (
            index_id(tenant_id, workspace.id, data.domain, overview["active_native_id"])
            if overview["active_native_id"]
            else None
        )
        return {
            "tenant_id": tenant_id,
            **data.model_dump(exclude={"expected_dimensions"}),
            **profile,
            "provider_kind": provider.kind,
            "provider_revision": provider.revision,
            "expected_connection_revision": current.revision if current else None,
            "active_space_id": current.space_id if current else None,
            "active_index_id": active,
            "chunk_count": overview["chunk_count"],
            "warnings": [],
        }
