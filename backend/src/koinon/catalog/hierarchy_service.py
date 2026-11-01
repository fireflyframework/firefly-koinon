# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Move organizational folders while retaining their native knowledge identities."""

from datetime import UTC, datetime

from pyfly.container import service
from pyfly.data.relational.sqlalchemy import transactional
from pyfly.kernel import ConflictException

from koinon.catalog.ancestry import MAX_ANCESTRY, MAX_FOLDER_ANCESTRY, validated_ancestry
from koinon.catalog.entities import CatalogEntry
from koinon.catalog.errors import AccessDenied, InvalidHierarchy
from koinon.catalog.service import PARENTS, CatalogService


@service
class CatalogHierarchyService:
    def __init__(self, catalog: CatalogService):
        self.catalog = catalog

    @transactional
    async def move(
        self,
        subject: str,
        tenant_id: str,
        entry_id: str,
        *,
        parent_id: str,
        expected_parent_id: str,
        expected_updated_at: datetime,
    ) -> CatalogEntry:
        catalog = self.catalog
        await catalog._lock_tenant(tenant_id)
        entry = await catalog._scoped_entry(tenant_id, entry_id, lock=True)
        await catalog.authorize(subject, tenant_id, "catalog:write", entry.workspace_id)
        if catalog.restriction:
            await catalog.restriction.resource(subject, entry, write=True)
            grant = await catalog.restriction.grant(subject)
            if grant is not None and grant.asset_ids is not None:
                raise AccessDenied("Folder moves require knowledge-space access", code="TOKEN_SCOPE_DENIED")
        if entry.system_key is not None:
            raise ConflictException("System knowledge spaces cannot be moved", code="SYSTEM_SPACE_PROTECTED")
        if entry.kind not in {"collection", "corpus"}:
            raise InvalidHierarchy("Select an organizational folder to move", code="INVALID_MOVE_KIND")
        if entry.parent_id != expected_parent_id or entry.updated_at != expected_updated_at:
            raise ConflictException(
                "This folder changed. Refresh it before moving it", code="CATALOG_CHANGED"
            )
        destination = await catalog._scoped_entry(tenant_id, parent_id, lock=True)
        await catalog.authorize(subject, tenant_id, "catalog:write", destination.workspace_id)
        if catalog.restriction:
            await catalog.restriction.resource(subject, destination, write=True)
        if (entry.workspace_id, entry.project_id) != (destination.workspace_id, destination.project_id):
            raise InvalidHierarchy(
                "Moving between knowledge spaces or projects requires a controlled transfer",
                code="KNOWLEDGE_TRANSFER_REQUIRED",
            )
        if destination.kind not in PARENTS[entry.kind]:
            raise InvalidHierarchy("Select a compatible destination folder", code="INVALID_PARENT")

        async def read(identifier: str) -> CatalogEntry:
            return await catalog._scoped_entry(tenant_id, identifier)

        await validated_ancestry(entry, read, PARENTS)
        chain = await validated_ancestry(destination, read, PARENTS)
        if entry.id in {node.id for node in chain}:
            raise InvalidHierarchy("A folder move cannot create a cycle", code="INVALID_ANCESTRY")
        facts = await catalog.catalog_repository.subtree_facts(tenant_id, entry)
        if (
            facts["max_depth"] + len(chain) >= MAX_ANCESTRY
            or facts["folder_depth"] + len(chain) >= MAX_FOLDER_ANCESTRY
            or facts["invalid_scope"]
        ):
            raise InvalidHierarchy(
                "The moved hierarchy is too deep or has invalid scope", code="INVALID_ANCESTRY"
            )
        if facts["pending"]:
            raise ConflictException(
                "Wait for processing to finish before moving this folder", code="FOLDER_BUSY"
            )
        if entry.parent_id == parent_id:
            return entry
        previous = entry.parent_id
        entry.parent_id, entry.updated_at, entry.updated_by = parent_id, datetime.now(UTC), subject
        await catalog.catalog_repository.save(entry)
        await catalog._audit(
            subject,
            tenant_id,
            "catalog.moved",
            entry.id,
            {"from_parent_id": previous, "to_parent_id": parent_id},
        )
        return entry
