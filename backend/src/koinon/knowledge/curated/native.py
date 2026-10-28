# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Compose retained native services through the one context and its named registry."""

from pydantic import TypeAdapter
from pyfly.container import Provider, service
from pyfly.data.relational.datasource_registry import DataSourceRegistry
from pyfly.data.transaction import infrastructure_unit
from pyfly.eda.adapters.database import DatabaseEventBus
from pyfly.eda.outbox import OutboxTables
from pyfly.kernel import ConflictException, ServiceUnavailableException
from sqlalchemy import select

from koinon.catalog.errors import AccessDenied
from koinon.knowledge.adapters import native_scope
from koinon.knowledge.curated.authority import CuratedAuthority, digest
from koinon.knowledge.curated.domain_entities import CuratedCommitRow, CuratedEvidenceRow, CuratedHeadRow
from koinon.knowledge.curated.dtos import (
    DocumentEvidence,
    KnowledgeCommitReceipt,
    KnowledgeEvidence,
    StructuredEvidence,
)
from koinon.knowledge.curated.intents import view
from koinon.knowledge.curated.native_unit import NativeKnowledgeTransaction, content
from koinon.knowledge.curated.ports import (
    NativeCatalogProjection,
    NativeKnowledgeCommitPort,
    NativeKnowledgeOperation,
)
from koinon.knowledge.curated.repositories import KnowledgeIntentRepository
from koinon.knowledge.service import KnowledgeFacade


def unavailable():
    return ServiceUnavailableException(
        "Configure the native document knowledge datasource and lifecycle",
        code="KNOWLEDGE_COMMIT_UNAVAILABLE",
    )


@service(name="knowledge.curated.native")
class NativeCuratedKnowledge(NativeKnowledgeCommitPort):
    def __init__(
        self,
        datasources: DataSourceRegistry,
        authority: CuratedAuthority,
        intents: KnowledgeIntentRepository,
        knowledge: Provider[KnowledgeFacade | None],
    ):
        self.datasources, self.authority, self.intents, self.knowledge = (
            datasources,
            authority,
            intents,
            knowledge,
        )
        self._publisher = None

    def facade(self):
        value = self.knowledge.get()
        if value is None:
            raise unavailable()
        return value

    def datasource(self):
        try:
            return self.datasources.get("canon")
        except KeyError:
            raise unavailable() from None

    async def workspace(self, subject, tenant_id, canonical_workspace_id, *, create=False):
        facade = self.facade()
        workspace = await facade.catalog.get(subject, tenant_id, canonical_workspace_id)
        if workspace.kind != "workspace" or workspace.status == "archived":
            raise AccessDenied("Select an active workspace", code="KNOWLEDGE_UNAVAILABLE")
        if create:
            return await facade._workspace(subject, tenant_id, workspace, "canon")
        return await facade.binding(tenant_id, canonical_workspace_id, "canon", entry=workspace)

    async def publisher(self):
        if self._publisher is None:
            bus = DatabaseEventBus(
                self.datasource(),
                tables=OutboxTables.named("canon_knowledge_outbox"),
                create_tables=False,
                notify=False,
                group="koinon.knowledge.curated",
            )
            await bus.outbox.start()
            self._publisher = bus
        return self._publisher

    async def sealed_workspace(self, row):
        """Bookkeeping uses the immutable alias, not renewed writer authority."""
        facade = self.facade()
        preview = view(row)
        workspace = await facade.catalog.catalog_repository.find_by_id(preview.destination.workspace_id)
        aliases = await facade.bindings.find_all(
            tenant_id=row.tenant_id, catalog_id=preview.destination.workspace_id, domain="canon"
        )
        if not aliases:
            return None
        alias = aliases[0]
        if (
            workspace is None
            or workspace.tenant_id != row.tenant_id
            or workspace.kind != "workspace"
            or alias.entity_kind != "workspace"
            or alias.workspace_id != workspace.id
            or alias.native_workspace_id != alias.native_id
        ):
            raise AccessDenied(
                "Committed workspace binding is unavailable", code="KNOWLEDGE_RECEIPT_MISMATCH"
            )
        return alias

    async def admitted(self, operation):
        preview = operation.preview
        row = await self.intents.find_by_id(preview.id)
        if (
            row is None
            or row.subject != preview.owner_subject
            or row.tenant_id != preview.tenant_id
            or row.status not in {"committing", "unresolved"}
            or not row.confirmation_key
            or row.authorization_digest != preview.authorization_digest
            or view(row).after != preview.after
            or view(row).evidence != preview.evidence
        ):
            raise AccessDenied(
                "An explicit matching user confirmation is required", code="KNOWLEDGE_CONFIRMATION_REQUIRED"
            )
        current = await self.authority.destination(row.subject, row.tenant_id, preview.destination.id)
        if current != preview.destination:
            raise ConflictException("Destination changed after review", code="KNOWLEDGE_DESTINATION_CHANGED")
        await self.authority.evidence(row.subject, row.tenant_id, preview.evidence)
        await self.authority.origins(
            row.subject,
            row.tenant_id,
            current.id,
            preview.evidence,
            row.originating_token_ids,
            write_token_ids=tuple(
                value for value in (row.preview_token_id, row.confirming_token_id) if value
            ),
        )
        return row

    async def commit(self, operation):
        from flycanon.core.services.knowledge import KnowledgeService

        row = await self.admitted(operation)
        preview = view(row)
        binding = await self.workspace(
            row.subject, row.tenant_id, preview.destination.workspace_id, create=True
        )
        lifecycle = self.facade().domains._resolve(KnowledgeService)
        transaction = NativeKnowledgeTransaction(
            self.datasource(), lifecycle, await self.publisher(), self.admitted
        )
        return await transaction.commit(
            NativeKnowledgeOperation(preview, tuple(row.originating_token_ids)),
            native_workspace_id=binding.native_id,
        )

    async def head(self, subject, tenant_id, item_id):
        from flycanon.models.entities.knowledge_item import KnowledgeItemRow
        from flycanon.models.entities.knowledge_version import KnowledgeVersionRow

        facade = self.facade()
        entry = await facade.catalog.get(subject, tenant_id, item_id)
        if entry.kind != "knowledge_item" or not entry.parent_id:
            raise AccessDenied("Select curated knowledge", code="KNOWLEDGE_UNAVAILABLE")
        await self.authority.destination(subject, tenant_id, entry.parent_id)
        binding = await facade.binding(tenant_id, item_id, "canon", entry=entry)
        with native_scope("canon", tenant_id, binding.native_workspace_id, subject):
            async with infrastructure_unit(self.datasource(), read_only=True) as session:
                head = await session.get(CuratedHeadRow, binding.native_id)
                item = await session.get(KnowledgeItemRow, binding.native_id)
                if (
                    head is None
                    or item is None
                    or (head.canonical_item_id, head.tenant_id, head.workspace_id, head.destination_id)
                    != (item_id, tenant_id, binding.native_workspace_id, entry.parent_id)
                ):
                    raise AccessDenied("Knowledge binding is unavailable", code="KNOWLEDGE_UNAVAILABLE")
                version = await session.scalar(
                    select(KnowledgeVersionRow).where(
                        KnowledgeVersionRow.knowledge_item_id == item.id,
                        KnowledgeVersionRow.version == item.current_version,
                        KnowledgeVersionRow.tenant_id == tenant_id,
                        KnowledgeVersionRow.workspace_id == binding.native_workspace_id,
                    )
                )
                rows = (
                    list(
                        await session.scalars(
                            select(CuratedEvidenceRow)
                            .where(CuratedEvidenceRow.native_version_id == version.id)
                            .order_by(CuratedEvidenceRow.ordinal)
                        )
                    )
                    if version
                    else []
                )
                if (
                    version is None
                    or not rows
                    or len(rows) > 500
                    or any(
                        row.ordinal != index or row.sha256 != digest(row.evidence_json)
                        for index, row in enumerate(rows, 1)
                    )
                ):
                    raise AccessDenied("Knowledge provenance is unavailable", code="KNOWLEDGE_UNAVAILABLE")
                evidence = TypeAdapter(tuple[KnowledgeEvidence, ...]).validate_python(
                    [row.evidence_json for row in rows]
                )
                value = content(version)
                commit = await session.get(CuratedCommitRow, rows[0].operation_id)
                receipt = (
                    KnowledgeCommitReceipt.model_validate(commit.receipt_json)
                    if commit and commit.receipt_json
                    else None
                )
                if (
                    receipt is None
                    or receipt.native_version_id != version.id
                    or receipt.content_sha256 != digest(value.model_dump(mode="json"))
                    or receipt.evidence_sha256 != digest([item.model_dump(mode="json") for item in evidence])
                ):
                    raise AccessDenied("Knowledge provenance is unavailable", code="KNOWLEDGE_UNAVAILABLE")
                await self.authority.evidence(subject, tenant_id, evidence, exact=False)
                return version.version, value

    async def receipt(self, subject, tenant_id, operation_id, authorization_digest):
        row = await self.intents.find_by_id(operation_id)
        if (
            row is None
            or row.subject != subject
            or row.tenant_id != tenant_id
            or row.authorization_digest != authorization_digest
        ):
            raise AccessDenied("Knowledge operation is unavailable", code="KNOWLEDGE_UNAVAILABLE")
        binding = await self.sealed_workspace(row)
        if binding is None:
            return None
        with native_scope("canon", tenant_id, binding.native_id, subject):
            async with infrastructure_unit(self.datasource(), read_only=True) as session:
                committed = await session.get(CuratedCommitRow, operation_id)
                if committed is None:
                    return None
                if (
                    committed.subject,
                    committed.tenant_id,
                    committed.workspace_id,
                    committed.authorization_digest,
                ) != (subject, tenant_id, binding.native_id, authorization_digest):
                    raise AccessDenied("Knowledge operation scope mismatch", code="KNOWLEDGE_UNAVAILABLE")
                return (
                    KnowledgeCommitReceipt.model_validate(committed.receipt_json)
                    if committed.receipt_json
                    else None
                )

    async def projection(self, subject, tenant_id, receipt):
        from flycanon.models.entities.knowledge_version import KnowledgeVersionRow

        row = await self.intents.find_by_id(receipt.operation_id)
        if row is None or (row.subject, row.tenant_id, row.authorization_digest) != (
            subject,
            tenant_id,
            receipt.authorization_digest,
        ):
            raise AccessDenied("Knowledge operation is unavailable", code="KNOWLEDGE_UNAVAILABLE")
        binding = await self.sealed_workspace(row)
        if binding is None:
            raise AccessDenied(
                "Committed workspace binding is unavailable", code="KNOWLEDGE_RECEIPT_MISMATCH"
            )
        with native_scope("canon", tenant_id, binding.native_id, subject):
            async with infrastructure_unit(self.datasource(), read_only=True) as session:
                committed = await session.get(CuratedCommitRow, receipt.operation_id)
                if committed is None or committed.receipt_json != receipt.model_dump(mode="json"):
                    raise AccessDenied(
                        "Native committed receipt is unavailable", code="KNOWLEDGE_RECEIPT_MISMATCH"
                    )
                display_version = receipt.serving_version or receipt.version
                version = await session.scalar(
                    select(KnowledgeVersionRow).where(
                        KnowledgeVersionRow.knowledge_item_id == receipt.native_item_id,
                        KnowledgeVersionRow.version == display_version,
                        KnowledgeVersionRow.tenant_id == tenant_id,
                        KnowledgeVersionRow.workspace_id == binding.native_id,
                    )
                )
                if version is None:
                    raise AccessDenied("Committed version is unavailable", code="KNOWLEDGE_RECEIPT_MISMATCH")
                rows = list(
                    await session.scalars(
                        select(CuratedEvidenceRow)
                        .where(
                            CuratedEvidenceRow.native_version_id == version.id,
                            CuratedEvidenceRow.tenant_id == tenant_id,
                            CuratedEvidenceRow.workspace_id == binding.native_id,
                        )
                        .order_by(CuratedEvidenceRow.ordinal)
                    )
                )
                if (
                    not rows
                    or len(rows) > 500
                    or any(
                        item.ordinal != index or item.sha256 != digest(item.evidence_json)
                        for index, item in enumerate(rows, 1)
                    )
                ):
                    raise AccessDenied(
                        "Committed provenance is unavailable", code="KNOWLEDGE_RECEIPT_MISMATCH"
                    )
                evidence = TypeAdapter(tuple[KnowledgeEvidence, ...]).validate_python(
                    [item.evidence_json for item in rows]
                )
                origin = await session.get(CuratedCommitRow, rows[0].operation_id)
                recorded = (
                    KnowledgeCommitReceipt.model_validate(origin.receipt_json)
                    if origin and origin.receipt_json
                    else None
                )
                if (
                    recorded is None
                    or recorded.native_version_id != version.id
                    or recorded.content_sha256 != digest(content(version).model_dump(mode="json"))
                    or recorded.evidence_sha256 != digest([item.model_dump(mode="json") for item in evidence])
                ):
                    raise AccessDenied(
                        "Committed provenance is unavailable", code="KNOWLEDGE_RECEIPT_MISMATCH"
                    )
                return NativeCatalogProjection(
                    native_workspace_id=binding.native_id,
                    title=version.title,
                    summary=version.summary,
                    serving_version_id=version.id if receipt.serving_version else None,
                    serving_operation_id=recorded.operation_id if receipt.serving_version else None,
                    source_asset_ids=tuple(
                        sorted(
                            {
                                item.source.asset_id
                                for item in evidence
                                if isinstance(item, DocumentEvidence | StructuredEvidence)
                            }
                        )
                    ),
                )
