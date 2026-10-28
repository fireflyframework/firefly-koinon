# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""A monotonic primary-store acknowledgement of an already committed native operation."""

from uuid import NAMESPACE_URL, uuid5

from pyfly.container import service
from pyfly.data.relational.datasource_registry import DataSourceRegistry
from pyfly.data.transaction import infrastructure_unit
from sqlalchemy import select

from koinon.catalog.entities import AuditEvent, CatalogEntry
from koinon.catalog.errors import AccessDenied
from koinon.knowledge.curated.entities import CuratedCatalogState, CuratedSourceRoot
from koinon.knowledge.entities import DomainBinding


def identifier(value):
    return str(uuid5(NAMESPACE_URL, "koinon:curated:" + value))


def mismatch():
    return AccessDenied(
        "Committed knowledge binding disagrees with its scope", code="KNOWLEDGE_RECEIPT_MISMATCH"
    )


@service(name="knowledge.curated.acknowledgement")
class CatalogAcknowledgement:
    def __init__(self, datasources: DataSourceRegistry):
        self.datasources = datasources

    async def apply(self, preview, receipt, projection):
        async with infrastructure_unit(self.datasources.get("primary")) as session:
            destination = await session.get(CatalogEntry, preview.destination.id, with_for_update=True)
            if destination is None or (
                destination.tenant_id,
                destination.workspace_id,
                destination.project_id,
            ) != (preview.tenant_id, preview.destination.workspace_id, preview.destination.project_id):
                raise mismatch()
            workspace = await session.scalar(
                select(DomainBinding).where(
                    DomainBinding.tenant_id == preview.tenant_id,
                    DomainBinding.catalog_id == preview.destination.workspace_id,
                    DomainBinding.domain == "canon",
                )
            )
            if (
                workspace is None
                or workspace.entity_kind != "workspace"
                or workspace.native_id != projection.native_workspace_id
                or workspace.native_workspace_id != projection.native_workspace_id
            ):
                raise mismatch()
            state = await session.get(CuratedCatalogState, receipt.item_id, with_for_update=True)
            if state is not None:
                if (state.tenant_id, state.workspace_id, state.native_item_id, state.native_workspace_id) != (
                    preview.tenant_id,
                    preview.destination.workspace_id,
                    receipt.native_item_id,
                    projection.native_workspace_id,
                ):
                    raise mismatch()
                if state.head_version >= receipt.version:
                    if state.head_version == receipt.version and (
                        state.head_version_id,
                        state.head_operation_id,
                    ) != (receipt.native_version_id, receipt.operation_id):
                        raise mismatch()
                    return
            item = await session.get(CatalogEntry, receipt.item_id)
            if item is None:
                item = CatalogEntry(
                    id=receipt.item_id,
                    tenant_id=preview.tenant_id,
                    workspace_id=preview.destination.workspace_id,
                    project_id=preview.destination.project_id,
                    parent_id=preview.destination.id,
                    kind="knowledge_item",
                    name=projection.title,
                    created_by=preview.owner_subject,
                    created_at=receipt.committed_at,
                )
                session.add(item)
                await session.flush()
            elif (item.tenant_id, item.workspace_id, item.project_id, item.parent_id, item.kind) != (
                preview.tenant_id,
                preview.destination.workspace_id,
                preview.destination.project_id,
                preview.destination.id,
                "knowledge_item",
            ):
                raise mismatch()
            binding = await session.scalar(
                select(DomainBinding).where(
                    DomainBinding.tenant_id == preview.tenant_id,
                    DomainBinding.catalog_id == item.id,
                    DomainBinding.domain == "canon",
                )
            )
            if binding is None:
                session.add(
                    DomainBinding(
                        id=identifier("binding:" + item.id),
                        tenant_id=preview.tenant_id,
                        catalog_id=item.id,
                        workspace_id=preview.destination.workspace_id,
                        domain="canon",
                        entity_kind="knowledge_item",
                        native_id=receipt.native_item_id,
                        native_workspace_id=projection.native_workspace_id,
                        created_by=preview.owner_subject,
                    )
                )
            elif (
                binding.native_id,
                binding.native_workspace_id,
                binding.entity_kind,
                binding.workspace_id,
            ) != (
                receipt.native_item_id,
                projection.native_workspace_id,
                "knowledge_item",
                preview.destination.workspace_id,
            ):
                raise mismatch()
            if bool(receipt.serving_version) != bool(
                projection.serving_version_id and projection.serving_operation_id
            ):
                raise mismatch()
            roots = tuple(sorted(set(projection.source_asset_ids)))
            sources = (
                list(await session.scalars(select(CatalogEntry).where(CatalogEntry.id.in_(roots))))
                if roots
                else []
            )
            if len(sources) != len(roots) or any(
                source.tenant_id != preview.tenant_id or source.kind not in {"document", "dataset"}
                for source in sources
            ):
                raise mismatch()
            if state is None:
                state = CuratedCatalogState(
                    item_id=item.id,
                    tenant_id=preview.tenant_id,
                    workspace_id=preview.destination.workspace_id,
                    native_item_id=receipt.native_item_id,
                    native_workspace_id=projection.native_workspace_id,
                )
                session.add(state)
            state.head_version, state.head_version_id, state.head_operation_id = (
                receipt.version,
                receipt.native_version_id,
                receipt.operation_id,
            )
            state.serving_version, state.serving_version_id, state.serving_operation_id = (
                receipt.serving_version,
                projection.serving_version_id,
                projection.serving_operation_id,
            )
            state.root_count = len(roots)
            await session.flush()
            active_version = projection.serving_version_id or receipt.native_version_id
            for source_id in roots:
                key = identifier(f"root:{item.id}:{active_version}:{source_id}")
                if await session.get(CuratedSourceRoot, key) is None:
                    session.add(
                        CuratedSourceRoot(
                            id=key,
                            tenant_id=preview.tenant_id,
                            item_id=item.id,
                            native_version_id=active_version,
                            source_asset_id=source_id,
                        )
                    )
            item.name, item.description = projection.title, projection.summary or ""
            item.status = "published" if receipt.serving_version else "draft"
            item.updated_by, item.updated_at = preview.owner_subject, receipt.committed_at
            item.metadata_json = {
                "head_version": receipt.version,
                "serving_version": receipt.serving_version,
                "dense_status": "not_recorded",
            }
            session.add(
                AuditEvent(
                    id=identifier("audit:" + receipt.operation_id),
                    tenant_id=preview.tenant_id,
                    subject=preview.owner_subject,
                    action="knowledge." + receipt.action,
                    resource_id=item.id,
                    details={
                        "operation_id": receipt.operation_id,
                        "version": receipt.version,
                        "serving_version": receipt.serving_version,
                        "content_sha256": receipt.content_sha256,
                    },
                    created_at=receipt.committed_at,
                )
            )
            await session.flush()
