# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Native bodies with immutable receipts and current source-root authorization."""

from math import ceil

from pydantic import TypeAdapter
from pyfly.container import service
from pyfly.data.relational.datasource_registry import DataSourceRegistry
from pyfly.data.transaction import infrastructure_unit
from pyfly.kernel import InvalidRequestException, ServiceUnavailableException
from sqlalchemy import select

from koinon.catalog.errors import AccessDenied
from koinon.knowledge.adapters import native_scope
from koinon.knowledge.curated.authority import CuratedAuthority, digest
from koinon.knowledge.curated.domain_entities import CuratedCommitRow, CuratedEvidenceRow, CuratedHeadRow
from koinon.knowledge.curated.dtos import (
    KnowledgeCommitReceipt,
    KnowledgeEvidence,
    KnowledgeItemPage,
    KnowledgeItemSummary,
    KnowledgeItemView,
    KnowledgeVersionView,
)
from koinon.knowledge.curated.entities import CuratedCatalogState
from koinon.knowledge.curated.native import NativeCuratedKnowledge
from koinon.knowledge.curated.native_unit import content
from koinon.knowledge.entities import DomainBinding


def unavailable():
    return AccessDenied("This committed knowledge version is unavailable", code="KNOWLEDGE_UNAVAILABLE")


@service(name="knowledge.curated.reads")
class CuratedKnowledgeReads:
    def __init__(
        self, authority: CuratedAuthority, native: NativeCuratedKnowledge, datasources: DataSourceRegistry
    ):
        self.authority, self.native, self.datasources = authority, native, datasources

    async def scope(self, subject, tenant_id, item_id):
        entry = await self.authority.catalog.get(subject, tenant_id, item_id)
        if entry.kind != "knowledge_item" or not entry.parent_id:
            raise unavailable()
        await self.authority.destination(subject, tenant_id, entry.parent_id, write=False)
        async with infrastructure_unit(self.datasources.get("primary"), read_only=True) as session:
            state = await session.get(CuratedCatalogState, item_id)
            binding = await session.scalar(
                select(DomainBinding).where(
                    DomainBinding.tenant_id == tenant_id,
                    DomainBinding.catalog_id == item_id,
                    DomainBinding.domain == "canon",
                )
            )
            workspace = await session.scalar(
                select(DomainBinding).where(
                    DomainBinding.tenant_id == tenant_id,
                    DomainBinding.catalog_id == entry.workspace_id,
                    DomainBinding.domain == "canon",
                )
            )
            if (
                state is None
                or binding is None
                or workspace is None
                or (
                    state.tenant_id,
                    state.workspace_id,
                    state.native_item_id,
                    state.native_workspace_id,
                    binding.native_workspace_id,
                    binding.entity_kind,
                    workspace.native_id,
                )
                != (
                    tenant_id,
                    entry.workspace_id,
                    binding.native_id,
                    workspace.native_id,
                    workspace.native_id,
                    "knowledge_item",
                    state.native_workspace_id,
                )
            ):
                raise unavailable()
            return entry, state

    async def recorded(self, session, tenant_id, state, selected):
        from flycanon.models.entities.knowledge_version import KnowledgeVersionRow

        row = await session.scalar(
            select(KnowledgeVersionRow).where(
                KnowledgeVersionRow.knowledge_item_id == state.native_item_id,
                KnowledgeVersionRow.version == selected,
                KnowledgeVersionRow.tenant_id == tenant_id,
                KnowledgeVersionRow.workspace_id == state.native_workspace_id,
            )
        )
        if row is None:
            raise unavailable()
        rows = list(
            await session.scalars(
                select(CuratedEvidenceRow)
                .where(
                    CuratedEvidenceRow.native_version_id == row.id,
                    CuratedEvidenceRow.tenant_id == tenant_id,
                    CuratedEvidenceRow.workspace_id == state.native_workspace_id,
                )
                .order_by(CuratedEvidenceRow.ordinal)
            )
        )
        if (
            not rows
            or len(rows) > 500
            or any(
                item.ordinal != ordinal or item.sha256 != digest(item.evidence_json)
                for ordinal, item in enumerate(rows, 1)
            )
        ):
            raise unavailable()
        commit = await session.get(CuratedCommitRow, rows[0].operation_id)
        receipt = (
            KnowledgeCommitReceipt.model_validate(commit.receipt_json)
            if commit and commit.receipt_json
            else None
        )
        evidence = TypeAdapter(tuple[KnowledgeEvidence, ...]).validate_python(
            [item.evidence_json for item in rows]
        )
        body = content(row)
        if (
            receipt is None
            or commit is None
            or commit.tenant_id != tenant_id
            or commit.workspace_id != state.native_workspace_id
            or receipt.item_id != state.item_id
            or receipt.native_item_id != state.native_item_id
            or receipt.native_version_id != row.id
            or receipt.version != selected
            or receipt.content_sha256 != digest(body.model_dump(mode="json"))
            or receipt.evidence_sha256 != digest([item.model_dump(mode="json") for item in evidence])
        ):
            raise unavailable()
        return row, commit, receipt, evidence, body

    async def version(self, subject, tenant_id, item_id, version=None):
        entry, state = await self.scope(subject, tenant_id, item_id)
        selected = version if version is not None else state.serving_version or state.head_version
        if type(selected) is not int or selected < 1 or selected > state.head_version:
            raise InvalidRequestException(
                "Choose an acknowledged knowledge version", code="INVALID_KNOWLEDGE_VERSION"
            )
        with native_scope("canon", tenant_id, state.native_workspace_id, subject):
            async with infrastructure_unit(self.native.datasource(), read_only=True) as session:
                row, commit, receipt, evidence, body = await self.recorded(
                    session, tenant_id, state, selected
                )
                published = receipt.serving_version == selected
                if not published:
                    await self.authority.destination(subject, tenant_id, entry.parent_id)
                await self.authority.evidence(subject, tenant_id, evidence, exact=False)
                head = await session.get(CuratedHeadRow, state.native_item_id)
                serving = selected == state.serving_version
                if serving and (
                    head is None or head.serving_version != selected or row.id != state.serving_version_id
                ):
                    raise ServiceUnavailableException(
                        "Reconcile the committed operation before reading its serving version",
                        code="KNOWLEDGE_ACK_PENDING",
                    )
                result = KnowledgeVersionView(
                    item_id=item_id,
                    version=selected,
                    version_id=row.id,
                    publication="published" if published else "draft",
                    serving=serving,
                    content=body,
                    evidence=evidence,
                    content_sha256=receipt.content_sha256,
                    evidence_sha256=receipt.evidence_sha256,
                    operation_id=receipt.operation_id,
                    author_subject=commit.subject,
                    committed_at=receipt.committed_at,
                )
                return KnowledgeItemView(
                    id=item_id,
                    tenant_id=tenant_id,
                    workspace_id=entry.workspace_id,
                    project_id=entry.project_id,
                    destination_id=entry.parent_id,
                    head_version=state.head_version,
                    serving_version=state.serving_version,
                    selected_version=result,
                )

    async def page(
        self,
        subject,
        tenant_id,
        *,
        workspace_id=None,
        project_id=None,
        destination_id=None,
        q="",
        page=1,
        page_size=25,
    ):
        result = await self.authority.catalog.page(
            subject,
            tenant_id,
            kind="knowledge_item",
            workspace_id=workspace_id,
            project_id=project_id,
            parent_id=destination_id,
            q=q,
            page=page,
            page_size=page_size,
        )
        items = tuple(
            KnowledgeItemSummary(
                id=row.id,
                tenant_id=row.tenant_id,
                workspace_id=row.workspace_id,
                project_id=row.project_id,
                destination_id=row.parent_id,
                title=row.name,
                summary=row.description,
                head_version=row.metadata_json["head_version"],
                serving_version=row.metadata_json["serving_version"],
            )
            for row in result["items"]
        )
        return KnowledgeItemPage(
            items=items,
            total=result["total"],
            page=result["page"],
            page_size=result["page_size"],
            pages=ceil(result["total"] / result["page_size"]),
            has_next=result["page"] * result["page_size"] < result["total"],
            has_previous=result["page"] > 1,
        )
