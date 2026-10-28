# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""One registry-owned canon unit commits content, evidence, serving state and outbox."""

from datetime import UTC, datetime
from hashlib import sha256
from uuid import NAMESPACE_URL, uuid5

from flycanon.interfaces.dtos.knowledge import Citation, CreateKnowledgeRequest, UpdateKnowledgeRequest
from flycanon.interfaces.enums import Domain
from flycanon.models.entities.knowledge_chunk import KnowledgeChunkRow
from flycanon.models.entities.knowledge_item import KnowledgeItemRow
from flycanon.models.entities.knowledge_version import KnowledgeVersionRow
from pyfly.data.transaction import infrastructure_unit
from pyfly.kernel import ConflictException
from sqlalchemy import select
from sqlalchemy.exc import DBAPIError, IntegrityError

from koinon.catalog.errors import AccessDenied
from koinon.knowledge.adapters import native_scope
from koinon.knowledge.curated.authority import digest
from koinon.knowledge.curated.domain_entities import (
    CuratedCommitRow,
    CuratedEvidenceRow,
    CuratedHeadRow,
    CuratedVersionChunkRow,
)
from koinon.knowledge.curated.dtos import DocumentEvidence, KnowledgeCommitReceipt, KnowledgeContent
from koinon.knowledge.curated.ports import NativeCommitUncertain


def content(row):
    return KnowledgeContent(
        title=row.title,
        body=row.body,
        summary=row.summary,
        domain=row.domain,
        tags=tuple(row.tags_json or []),
    )


def unavailable():
    return AccessDenied("Native knowledge is unavailable in this scope", code="KNOWLEDGE_UNAVAILABLE")


class NativeKnowledgeTransaction:
    def __init__(self, datasource, lifecycle, publisher, authorize):
        self.datasource, self.lifecycle, self.publisher, self.authorize = (
            datasource,
            lifecycle,
            publisher,
            authorize,
        )

    async def head(self, tenant_id, workspace_id, canonical_item_id):
        async with infrastructure_unit(self.datasource, read_only=True) as session:
            head = await session.scalar(
                select(CuratedHeadRow).where(
                    CuratedHeadRow.tenant_id == tenant_id,
                    CuratedHeadRow.workspace_id == workspace_id,
                    CuratedHeadRow.canonical_item_id == canonical_item_id,
                )
            )
            if head is None:
                raise unavailable()
            item = await session.get(KnowledgeItemRow, head.native_item_id)
            row = (
                await session.scalar(
                    select(KnowledgeVersionRow).where(
                        KnowledgeVersionRow.knowledge_item_id == head.native_item_id,
                        KnowledgeVersionRow.version == item.current_version,
                    )
                )
                if item
                else None
            )
            if row is None or (row.tenant_id, row.workspace_id) != (tenant_id, workspace_id):
                raise unavailable()
            return row.version, content(row)

    async def claim(self, session, operation, workspace_id):
        preview = operation.preview
        row = CuratedCommitRow(
            operation_id=preview.id,
            canonical_item_id=preview.target_item_id,
            subject=preview.owner_subject,
            tenant_id=preview.tenant_id,
            workspace_id=workspace_id,
            authorization_digest=preview.authorization_digest,
            originating_token_ids=list(operation.originating_token_ids),
        )
        try:
            async with session.begin_nested():
                session.add(row)
                await session.flush()
        except IntegrityError:
            row = await session.get(CuratedCommitRow, preview.id, with_for_update=True)
            if row is None:
                raise
        if (
            row.subject,
            row.tenant_id,
            row.workspace_id,
            row.authorization_digest,
            row.canonical_item_id,
            row.originating_token_ids,
        ) != (
            preview.owner_subject,
            preview.tenant_id,
            workspace_id,
            preview.authorization_digest,
            preview.target_item_id,
            list(operation.originating_token_ids),
        ):
            raise ConflictException(
                "Operation already binds a different authorization", code="KNOWLEDGE_IDEMPOTENCY_CONFLICT"
            )
        return row

    async def citations(self, session, operation, workspace_id):
        citations = []
        for evidence in operation.preview.evidence:
            if not isinstance(evidence, DocumentEvidence):
                continue
            reference = evidence.source
            if reference.source_part_id:
                # Immutable version evidence owns these refs; they are not canon_chunks citations.
                continue
            chunk = await session.get(KnowledgeChunkRow, reference.chunk_id)
            if (
                chunk is None
                or (chunk.tenant_id, chunk.workspace_id) != (operation.preview.tenant_id, workspace_id)
                or reference.used_revision != "chunk-sha256:" + sha256(chunk.content.encode()).hexdigest()
                or (reference.quote is not None and reference.quote not in chunk.content)
            ):
                raise ConflictException(
                    "Document evidence changed; review again", code="KNOWLEDGE_SOURCE_CHANGED"
                )
            citations.append(
                Citation(
                    source_id=chunk.source_id,
                    chunk_id=chunk.id,
                    quote=reference.quote if reference.quote and len(reference.quote) <= 4000 else None,
                    page=reference.page,
                )
            )
        return citations

    async def commit(self, operation, *, native_workspace_id):
        preview = operation.preview
        await self.authorize(operation)
        try:
            with native_scope("canon", preview.tenant_id, native_workspace_id, preview.owner_subject):
                async with infrastructure_unit(self.datasource) as session:
                    claim = await self.claim(session, operation, native_workspace_id)
                    if claim.receipt_json is not None:
                        receipt = KnowledgeCommitReceipt.model_validate(claim.receipt_json)
                    else:
                        receipt = await self.write(session, operation, native_workspace_id, claim)
            return receipt
        except DBAPIError as error:
            if error.connection_invalidated:
                raise NativeCommitUncertain() from None
            raise

    async def write(self, session, operation, workspace_id, claim):
        preview = operation.preview
        head = await session.scalar(
            select(CuratedHeadRow)
            .where(
                CuratedHeadRow.tenant_id == preview.tenant_id,
                CuratedHeadRow.workspace_id == workspace_id,
                CuratedHeadRow.canonical_item_id == preview.target_item_id,
            )
            .with_for_update()
        )
        publishing = preview.action in {"create_published", "update_published", "publish_draft"}
        creating = preview.action in {"create_draft", "create_published"}
        previous_serving = head.serving_version if head else None
        if creating and head is not None:
            raise ConflictException("Knowledge identity already exists", code="KNOWLEDGE_VERSION_CONFLICT")
        if not creating:
            if (
                head is None
                or head.destination_id != preview.destination.id
                or head.canonical_workspace_id != preview.destination.workspace_id
            ):
                raise unavailable()
            item = await session.get(KnowledgeItemRow, head.native_item_id, with_for_update=True)
            if item is None or item.current_version != preview.expected_version or item.status == "retired":
                raise ConflictException("Review the current version", code="KNOWLEDGE_VERSION_CONFLICT")
            previous = await session.scalar(
                select(KnowledgeVersionRow).where(
                    KnowledgeVersionRow.knowledge_item_id == item.id,
                    KnowledgeVersionRow.version == item.current_version,
                )
            )
            if previous is None or content(previous) != preview.before:
                raise ConflictException("Knowledge content changed", code="KNOWLEDGE_VERSION_CONFLICT")
            if preview.action == "publish_draft" and (
                previous.status != "draft" or content(previous) != preview.after
            ):
                raise ConflictException("Review the exact draft", code="KNOWLEDGE_VERSION_CONFLICT")
        await self.authorize(operation)
        citations = await self.citations(session, operation, workspace_id)
        arguments = dict(
            title=preview.after.title,
            summary=preview.after.summary,
            body=preview.after.body,
            domain=Domain(preview.after.domain),
            tags=list(preview.after.tags),
            citations=citations,
            publish=publishing,
            actor=preview.owner_subject,
            metadata={"_koinon_operation_id": preview.id},
        )
        if creating:
            version = await self.lifecycle.create(
                CreateKnowledgeRequest.model_validate(arguments),
                tenant_id=preview.tenant_id,
                workspace_id=workspace_id,
                correlation_id=preview.id,
                event_publisher=self.publisher,
            )
            head = CuratedHeadRow(
                tenant_id=preview.tenant_id,
                workspace_id=workspace_id,
                native_item_id=version.knowledge_item_id,
                canonical_item_id=preview.target_item_id,
                canonical_workspace_id=preview.destination.workspace_id,
                destination_id=preview.destination.id,
                serving_version=None,
                operation_id=preview.id,
            )
            session.add(head)
        else:
            if head is None:
                raise unavailable()
            version = await self.lifecycle.update(
                head.native_item_id,
                UpdateKnowledgeRequest.model_validate(arguments),
                tenant_id=preview.tenant_id,
                workspace_id=workspace_id,
                correlation_id=preview.id,
                event_publisher=self.publisher,
                clear_summary=preview.after.summary is None,
            )
        await self.verify_content(session, preview, version, workspace_id)
        if head is None:
            raise unavailable()
        if publishing:
            head.serving_version = version.version
        elif previous_serving is not None:
            serving = await session.scalar(
                select(KnowledgeVersionRow).where(
                    KnowledgeVersionRow.knowledge_item_id == head.native_item_id,
                    KnowledgeVersionRow.version == previous_serving,
                )
            )
            if serving is None:
                raise unavailable()
            serving.status, serving.superseded_by_version = "published", None
        head.operation_id = preview.id
        return await self.persist(session, operation, workspace_id, claim, head, version, publishing)

    async def verify_content(self, session, preview, version, workspace_id):
        await session.flush()
        persisted = await session.scalar(
            select(KnowledgeVersionRow)
            .where(
                KnowledgeVersionRow.id == version.id,
                KnowledgeVersionRow.knowledge_item_id == version.knowledge_item_id,
                KnowledgeVersionRow.tenant_id == preview.tenant_id,
                KnowledgeVersionRow.workspace_id == workspace_id,
            )
            .execution_options(populate_existing=True)
        )
        actual = (
            {
                "title": persisted.title,
                "body": persisted.body,
                "summary": persisted.summary,
                "domain": persisted.domain,
                "tags": list(persisted.tags_json or []),
            }
            if persisted is not None
            else None
        )
        if digest(actual) != digest(preview.after.model_dump(mode="json")):
            raise ConflictException(
                "Persisted knowledge differs from the authorized content",
                code="KNOWLEDGE_CONTENT_MISMATCH",
            )

    async def persist(self, session, operation, workspace_id, claim, head, version, publishing):
        preview = operation.preview
        for ordinal, evidence in enumerate(preview.evidence, 1):
            data = evidence.model_dump(mode="json")
            session.add(
                CuratedEvidenceRow(
                    tenant_id=preview.tenant_id,
                    workspace_id=workspace_id,
                    native_version_id=version.id,
                    ordinal=ordinal,
                    operation_id=preview.id,
                    kind=evidence.kind,
                    sha256=digest(data),
                    evidence_json=data,
                )
            )
        for ordinal, start in enumerate(range(0, len(version.body), 4800)):
            text = version.body[start : start + 4800]
            session.add(
                CuratedVersionChunkRow(
                    id=str(uuid5(NAMESPACE_URL, f"koinon:knowledge:{version.id}:{ordinal}")),
                    native_version_id=version.id,
                    canonical_item_id=preview.target_item_id,
                    tenant_id=preview.tenant_id,
                    workspace_id=workspace_id,
                    ordinal=ordinal,
                    content=text,
                    sha256=sha256(text.encode()).hexdigest(),
                    char_start=start,
                    char_end=start + len(text),
                )
            )
        await session.flush()
        receipt = KnowledgeCommitReceipt(
            operation_id=preview.id,
            intent_id=preview.id,
            intent_revision=preview.revision,
            authorization_digest=preview.authorization_digest,
            item_id=preview.target_item_id,
            native_item_id=version.knowledge_item_id,
            native_version_id=version.id,
            version=version.version,
            serving_version=head.serving_version,
            action=preview.action,
            content_sha256=digest(preview.after.model_dump(mode="json")),
            evidence_sha256=digest([value.model_dump(mode="json") for value in preview.evidence]),
            committed_at=datetime.now(UTC),
            retrieval_state="lexical_ready" if publishing else "not_published",
        )
        await self.publisher.publish(
            destination="koinon.knowledge",
            event_type="KnowledgeCommitted",
            payload={
                "operation_id": preview.id,
                "tenant_id": preview.tenant_id,
                "workspace_id": workspace_id,
                "canonical_item_id": preview.target_item_id,
                "native_item_id": version.knowledge_item_id,
                "version": version.version,
                "serving_version": head.serving_version,
            },
        )
        claim.receipt_json = receipt.model_dump(mode="json")
        await session.flush()
        await self.verify_content(session, preview, version, workspace_id)
        return receipt
