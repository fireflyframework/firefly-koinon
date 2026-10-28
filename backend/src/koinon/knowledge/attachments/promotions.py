# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Explicit publication reuses original domain flows with durable, reconcilable effect intents."""

from hashlib import sha256
from json import dumps
from uuid import uuid4

from pyfly.container import service
from pyfly.data.relational.sqlalchemy import LockMode, transactional
from pyfly.kernel import ConflictException

from koinon.catalog.errors import InvalidHierarchy
from koinon.catalog.mappers import entry_dto
from koinon.knowledge.attachments.dtos import AttachmentPromotionView
from koinon.knowledge.attachments.entities import ChatAttachmentPromotion, timestamp
from koinon.knowledge.attachments.lifecycle import AttachmentLifecycle
from koinon.knowledge.attachments.repositories import AttachmentPromotionRepository
from koinon.knowledge.content import ContentUpdates


@service(name="knowledge.attachments.promotion_service")
class AttachmentPromotions:
    def __init__(
        self, lifecycle: AttachmentLifecycle, records: AttachmentPromotionRepository, content: ContentUpdates
    ):
        self.lifecycle, self.reader, self.records, self.content = (
            lifecycle,
            lifecycle.reader,
            records,
            content,
        )
        self.knowledge = content.knowledge

    async def authority(self, subject, tenant_id, values):
        if values["action"] == "add":
            chain = await self.content._writable(subject, tenant_id, values["parent_id"])
            parent, workspace = chain[0], chain[-1]
            if (
                parent.kind not in {"collection", "corpus"}
                or workspace.id != values["workspace_id"]
                or parent.project_id != values["project_id"]
            ):
                raise InvalidHierarchy(
                    "Select a matching collection, project and workspace", code="INVALID_PARENT"
                )
        elif values["action"] == "replace_document":
            _, binding, _ = await self.content._document_scope(subject, tenant_id, values["document_id"])
            self.content._document_precondition(
                values["expected_sha256"], values["acknowledge_chunk_invalidation"]
            )
            await self.content._document_revision_precondition(subject, tenant_id, binding,
                values.get("expected_source_version_id"), values.get("expected_extraction_id"))
        else:
            await self.content._table_scope(subject, tenant_id, values["dataset_id"], values["table_id"])

    async def promote(self, subject, tenant_id, thread_id, attachment_id, values, key):
        await self.reader.authority.thread(subject, tenant_id, thread_id, active=True)
        await self.authority(subject, tenant_id, values)
        row = await self.lifecycle.row(subject, tenant_id, thread_id, attachment_id, active=True)
        self.reader.ready(row)
        intent, created = await self.plan(subject, tenant_id, thread_id, attachment_id, values, key)
        if not created:
            result = await self.reconcile(subject, tenant_id, intent)
            return self.response(intent, result)
        try:
            original = await self.reader.storage.read(row)

            async def retained(entry):
                current = await self.lifecycle.row(subject, tenant_id, thread_id, attachment_id, active=True)
                self.reader.ready(current)
                if current.revision != values["expected_revision"]:
                    raise ConflictException(
                        "Private original changed before publication", code="ATTACHMENT_REVISION_CONFLICT"
                    )
                await self.bind_intent(
                    subject, tenant_id, thread_id, intent.id, entry.id, version=values["action"] != "add"
                )

            if values["action"] == "add":
                result = await self.knowledge.upload(
                    subject,
                    tenant_id,
                    **{name: values[name] for name in ("workspace_id", "project_id", "parent_id", "mode")},
                    filename=row.filename,
                    content=original,
                    _on_source=retained,
                )
            elif values["action"] == "replace_document":
                result = await self.content.document(
                    subject,
                    tenant_id,
                    values["document_id"],
                    filename=row.filename,
                    content=original,
                    expected_sha256=values["expected_sha256"],
                    acknowledge_chunk_invalidation=values["acknowledge_chunk_invalidation"],
                    expected_source_version_id=values.get("expected_source_version_id"),
                    expected_extraction_id=values.get("expected_extraction_id"),
                    _on_version=retained,
                )
            else:
                result = await self.content.table(
                    subject,
                    tenant_id,
                    values["dataset_id"],
                    values["table_id"],
                    filename=row.filename,
                    content=original,
                    expected_snapshot_id=values["expected_snapshot_id"],
                    _on_version=retained,
                )
            await self.finished(subject, tenant_id, thread_id, intent.id, result)
            return self.response(intent, result)
        except Exception as error:
            await self.failed(
                subject,
                tenant_id,
                thread_id,
                intent.id,
                str(getattr(error, "code", None) or "ATTACHMENT_PROMOTION_FAILED")[:64],
            )
            raise

    @staticmethod
    def response(intent, result):
        return AttachmentPromotionView.model_validate(
            {
                "promotion_id": intent.id,
                "attachment_id": intent.attachment_id,
                "action": intent.action,
                **result,
            }
        )

    @transactional
    async def plan(self, subject, tenant_id, thread_id, attachment_id, values, key):
        await self.reader.authority.threads.find_by_id(thread_id, lock=LockMode.PESSIMISTIC_WRITE)
        request_key = self.lifecycle.request_key(subject, thread_id, key)
        digest = sha256(
            dumps([attachment_id, values], sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        async with self.reader.data.scope(subject, tenant_id, thread_id):
            previous = await self.records.find_all(
                tenant_id=tenant_id, subject=subject, thread_id=thread_id, request_key=request_key
            )
            if previous:
                if previous[0].request_hash != digest:
                    raise ConflictException(
                        "This publication key belongs to another action", code="IDEMPOTENCY_CONFLICT"
                    )
                return previous[0], False
            row = await self.reader.records.find_by_id(attachment_id, lock=LockMode.PESSIMISTIC_WRITE)
            self.reader.ready(row)
            if row.revision != values["expected_revision"]:
                raise ConflictException(
                    "Reload the private attachment revision", code="ATTACHMENT_REVISION_CONFLICT"
                )
            intent = await self.records.save(
                ChatAttachmentPromotion(
                    id=str(uuid4()),
                    attachment_id=row.id,
                    tenant_id=tenant_id,
                    subject=subject,
                    thread_id=thread_id,
                    request_key=request_key,
                    request_hash=digest,
                    action=values["action"],
                    values_json=values,
                    status="running",
                )
            )
            return intent, True

    @transactional
    async def bind_intent(self, subject, tenant_id, thread_id, intent_id, catalog_id, *, version):
        async with self.reader.data.scope(subject, tenant_id, thread_id):
            intent = await self.records.find_by_id(intent_id, lock=LockMode.PESSIMISTIC_WRITE)
            if version:
                intent.content_version_id = catalog_id
            else:
                intent.source_catalog_id = catalog_id
            intent.revision += 1
            intent.updated_at = timestamp()
            await self.records.save(intent)

    @transactional
    async def finished(self, subject, tenant_id, thread_id, intent_id, result):
        async with self.reader.data.scope(subject, tenant_id, thread_id):
            intent = await self.records.find_by_id(intent_id, lock=LockMode.PESSIMISTIC_WRITE)
            intent.status, intent.result_json = "completed", result
            intent.revision += 1
            intent.updated_at = timestamp()
            await self.records.save(intent)

    @transactional
    async def failed(self, subject, tenant_id, thread_id, intent_id, code):
        async with self.reader.data.scope(subject, tenant_id, thread_id):
            intent = await self.records.find_by_id(intent_id, lock=LockMode.PESSIMISTIC_WRITE)
            intent.status, intent.error_code = "failed", code
            intent.error = (
                "Publication did not finish; inspect the retained source/version before a new explicit action"
            )
            intent.revision += 1
            intent.updated_at = timestamp()
            await self.records.save(intent)

    async def reconcile(self, subject, tenant_id, intent):
        # A crash may follow the original effect but precede the final private metadata write.
        # Reconstruct only a proven completed original operation; never blindly ingest twice.
        if intent.status == "completed":
            return intent.result_json
        result = None
        if intent.action == "add" and intent.source_catalog_id:
            source = await self.knowledge.catalog.get(subject, tenant_id, intent.source_catalog_id)
            if source.status == "ready":
                assets = await self.knowledge.catalog.list(
                    subject, tenant_id, parent_id=source.id, kind=intent.values_json["mode"]
                )
                if len(assets) == 1 and assets[0].status == "ready":
                    await self.knowledge._chain(subject, tenant_id, assets[0].id)
                    result = {"source": entry_dto(source), "assets": [entry_dto(assets[0])]}
        elif intent.content_version_id:
            version = await self.knowledge.catalog.get(subject, tenant_id, intent.content_version_id)
            if version.status == "ready":
                values = intent.values_json
                domain = "canon" if intent.action == "replace_document" else "structured"
                await self.knowledge.binding(tenant_id, version.id, domain, entry=version)
                result = {"version": entry_dto(version), "effects": version.metadata_json.get("effects", {})}
                if intent.action == "replace_document":
                    chain = await self.knowledge._chain(subject, tenant_id, values["document_id"])
                    result.update(asset=entry_dto(chain[0]), source=entry_dto(chain[1]))
                else:
                    chain = await self.knowledge._chain(subject, tenant_id, values["table_id"])
                    result.update(table=entry_dto(chain[0]), asset=entry_dto(chain[1]))
        if result is None:
            raise ConflictException(
                "Inspect the retained source/version; automatic replay would risk duplicate effects",
                code="ATTACHMENT_PROMOTION_UNRESOLVED",
            )
        await self.finished(subject, tenant_id, intent.thread_id, intent.id, result)
        return result
