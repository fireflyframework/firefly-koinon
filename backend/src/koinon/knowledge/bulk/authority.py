# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from pyfly.container import service
from pyfly.security.context_holder import SecurityContextHolder

from koinon.catalog.errors import AccessDenied
from koinon.catalog.service import ROLE_PERMISSIONS, CatalogService
from koinon.knowledge.bulk.dataset_dtos import DatasetReservation
from koinon.knowledge.bulk.dtos import BulkDestination
from koinon.knowledge.bulk.repositories import BulkRepository


def token_identity() -> str | None:
    context = SecurityContextHolder.get_context()
    token = context.attributes.get("koinon_token_id") if context else None
    if token is not None and (not isinstance(token, str) or not 1 <= len(token) <= 64):
        raise AccessDenied("Original token cannot be verified", code="TOKEN_UNAVAILABLE")
    return token


@service(name="knowledge.bulk.authority")
class BulkAuthority:
    def __init__(self, catalog: CatalogService, records: BulkRepository):
        self.catalog, self.records = catalog, records

    async def read_bounds(self, subject: str, tenant: str) -> dict:
        if token_identity() and self.catalog.restriction is None:
            raise AccessDenied("Original token cannot be verified", code="TOKEN_UNAVAILABLE")
        memberships = [
            member
            for member in await self.catalog.memberships(subject)
            if member.tenant_id == tenant and "catalog:read" in ROLE_PERMISSIONS.get(member.role, ())
        ]
        if not memberships:
            raise AccessDenied("Bulk history is unavailable", code="ACCESS_DENIED")
        allowed = (
            None
            if any(m.workspace_id is None for m in memberships)
            else [m.workspace_id for m in memberships]
        )
        grant = await self.catalog.restriction.grant(subject) if self.catalog.restriction else None
        if grant is not None:
            if grant.tenant_id != tenant or "catalog:read" not in grant.scopes:
                raise AccessDenied("Bulk history exceeds token scope", code="TOKEN_SCOPE_DENIED")
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

    async def destination(self, subject: str, tenant: str, target: BulkDestination, *, write: bool) -> None:
        token = token_identity()
        if token and self.catalog.restriction is None:
            raise AccessDenied("Original token cannot be verified", code="TOKEN_UNAVAILABLE")
        if write:
            await self.records.authority_lock(tenant, subject, token)
            await self.records.catalog_locks(
                tenant, (target.workspace_id, target.project_id, target.parent_id)
            )
        chain = []
        for identifier in [target.parent_id, target.project_id, target.workspace_id]:
            row = await self.catalog.get(subject, tenant, identifier)
            if row.status == "archived":
                raise AccessDenied("Bulk destination is unavailable", code="ACCESS_DENIED")
            chain.append(row)
        parent, project, workspace = chain
        if (
            [row.kind for row in chain]
            not in [["collection", "project", "workspace"], ["corpus", "project", "workspace"]]
            or parent.parent_id != project.id
            or project.parent_id != workspace.id
            or workspace.parent_id is not None
            or any(row.workspace_id != workspace.id for row in chain)
            or any(row.project_id != project.id for row in chain[:-1])
        ):
            raise AccessDenied("Bulk destination ancestry differs", code="ACCESS_DENIED")
        if write:
            for permission in ["catalog:write", "ingest:write"]:
                await self.catalog.authorize(subject, tenant, permission, workspace.id)
        if self.catalog.restriction:
            await self.catalog.restriction.resource(subject, parent, write=write)

    async def item(
        self, subject: str, tenant: str, source_id: str, asset_id: str, target: BulkDestination, digest: str
    ) -> None:
        await self.records.catalog_locks(tenant, (source_id, asset_id))
        source = await self.catalog.get(subject, tenant, source_id)
        asset = await self.catalog.get(subject, tenant, asset_id)
        if (
            source.kind != "source"
            or source.parent_id != target.parent_id
            or asset.parent_id != source.id
            or asset.kind not in {"document", "dataset"}
            or any(
                row.workspace_id != target.workspace_id
                or row.project_id != target.project_id
                or row.status == "archived"
                for row in [source, asset]
            )
            or source.metadata_json.get("sha256") != digest
            or asset.metadata_json.get("sha256") != digest
        ):
            raise AccessDenied(
                "Reserved intake source changed or was archived", code="BULK_DESTINATION_CHANGED"
            )
        if self.catalog.restriction:
            await self.catalog.restriction.resource(subject, asset, write=True)

    async def dataset(self, subject: str, tenant: str, item, target: BulkDestination) -> None:
        reservation = DatasetReservation.stored(item.reservation_json)
        tables = await self.records.table_reservations(item.id)
        if len(tables) > reservation.max_tables:
            raise AccessDenied("Reserved tables exceed admission", code="BULK_DESTINATION_CHANGED")
        await self.records.catalog_locks(
            tenant, (reservation.catalog_file_version_id, *(row.catalog_table_id for row in tables))
        )
        version = await self.catalog.get(subject, tenant, reservation.catalog_file_version_id)
        if (
            version.kind != "index_version"
            or version.parent_id != item.asset_id
            or version.workspace_id != target.workspace_id
            or version.project_id != target.project_id
            or version.status == "archived"
            or version.metadata_json.get("bulk_item_id") != item.id
            or version.metadata_json.get("sha256") != item.sha256
            or version.metadata_json.get("bytes") != item.size_bytes
        ):
            raise AccessDenied("Reserved file version changed", code="BULK_DESTINATION_CHANGED")
        for row in tables:
            table = await self.catalog.get(subject, tenant, row.catalog_table_id)
            if (
                table.kind != "table"
                or table.parent_id != item.asset_id
                or table.name != row.name
                or table.workspace_id != target.workspace_id
                or table.project_id != target.project_id
                or table.status == "archived"
                or table.metadata_json.get("bulk_item_id") != item.id
                or table.metadata_json.get("snapshot_id") != row.snapshot_id
            ):
                raise AccessDenied("Reserved table changed", code="BULK_DESTINATION_CHANGED")
            if self.catalog.restriction:
                await self.catalog.restriction.resource(subject, table, write=True)
        if self.catalog.restriction:
            await self.catalog.restriction.resource(subject, version, write=True)
