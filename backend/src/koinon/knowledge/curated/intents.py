# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from pyfly.container import Provider, service
from pyfly.data.relational.sqlalchemy import LockMode, transactional
from pyfly.kernel import ConflictException, InvalidRequestException, ServiceUnavailableException
from pyfly.security.context_holder import SecurityContextHolder

from koinon.catalog.errors import AccessDenied
from koinon.knowledge.curated.acknowledgement import CatalogAcknowledgement
from koinon.knowledge.curated.authority import CuratedAuthority, digest
from koinon.knowledge.curated.dtos import (
    CommittedKnowledge,
    ExternalProposalOrigin,
    KnowledgeCommitReceipt,
    KnowledgeConfirmation,
    KnowledgeIntent,
    KnowledgeIntentInput,
    PendingKnowledgeCommit,
)
from koinon.knowledge.curated.entities import KnowledgeIntentRow
from koinon.knowledge.curated.ports import (
    NativeCommitUncertain,
    NativeKnowledgeCommitPort,
    NativeKnowledgeOperation,
)
from koinon.knowledge.curated.repositories import KnowledgeIntentRepository


def view(row):
    request = KnowledgeIntentInput.model_validate(row.request_json)
    return KnowledgeIntent(
        id=row.id,
        revision=row.revision,
        tenant_id=row.tenant_id,
        owner_subject=row.subject,
        action=request.action,
        destination=row.destination_json,
        target_item_id=row.target_item_id,
        expected_version=request.expected_version,
        before=row.before_json,
        after=request.content,
        evidence=row.evidence_json,
        authorization_digest=row.authorization_digest,
        status=row.status,
        created_at=row.created_at,
        expires_at=row.expires_at,
        receipt=row.receipt_json,
    )


def current_token_id():
    context = SecurityContextHolder.get_context()
    value = context.attributes.get("koinon_token_id") if context else None
    return value if isinstance(value, str) else None


@service(name="knowledge.curated.intents_service")
class KnowledgeIntents:
    def __init__(
        self,
        intents: KnowledgeIntentRepository,
        authority: CuratedAuthority,
        native: Provider[NativeKnowledgeCommitPort | None],
        acknowledgement: CatalogAcknowledgement,
    ):
        self.intents, self.authority, self.native = intents, authority, native
        self.acknowledgement = acknowledgement

    def committer(self):
        value = self.native.get()
        if value is None:
            raise ServiceUnavailableException(
                "Native knowledge lifecycle is not configured", code="KNOWLEDGE_COMMIT_UNAVAILABLE"
            )
        return value

    async def load(self, subject, tenant_id, identifier, *, lock=False):
        row = await self.intents.find_by_id(identifier, lock=LockMode.PESSIMISTIC_WRITE if lock else None)
        if row is None or row.tenant_id != tenant_id or row.subject != subject:
            raise AccessDenied(
                "This private knowledge preview is unavailable", code="KNOWLEDGE_INTENT_UNAVAILABLE"
            )
        return row

    @transactional
    async def preview(self, subject, tenant_id, values):
        request = KnowledgeIntentInput.model_validate(values)
        destination = await self.authority.destination(subject, tenant_id, request.destination_id)
        recorded_at = datetime.now(UTC)
        evidence, origins = await self.authority.observe(subject, tenant_id, request, recorded_at)
        preview_token = current_token_id()
        expires_at = recorded_at + timedelta(hours=24)
        if isinstance(request.origin, ExternalProposalOrigin):
            grant = await self.authority.catalog.restriction.grant(subject)
            expires_at = min(grant.expires_at, recorded_at + timedelta(minutes=15))
        await self.authority.origins(
            subject,
            tenant_id,
            request.destination_id,
            evidence,
            origins,
            write_token_ids=(preview_token,) if preview_token else (),
        )
        before = None
        if request.target_item_id is not None:
            version, before = await self.committer().head(subject, tenant_id, request.target_item_id)
            if version != request.expected_version:
                raise ConflictException(
                    "Review the current knowledge version", code="KNOWLEDGE_VERSION_CONFLICT"
                )
        row = KnowledgeIntentRow(
            id=str(uuid4()),
            tenant_id=tenant_id,
            subject=subject,
            revision=1,
            status="preview",
            request_json=request.model_dump(mode="json"),
            destination_json=destination.model_dump(mode="json"),
            evidence_json=[value.model_dump(mode="json") for value in evidence],
            before_json=before.model_dump(mode="json") if before else None,
            target_item_id=request.target_item_id or str(uuid4()),
            originating_token_ids=list(origins),
            preview_token_id=preview_token,
            created_at=recorded_at,
            expires_at=expires_at,
        )
        row.authorization_digest = digest(
            {
                "id": row.id,
                "revision": row.revision,
                "subject": subject,
                "tenant_id": tenant_id,
                "request": row.request_json,
                "destination": row.destination_json,
                "evidence": row.evidence_json,
                "before": row.before_json,
                "target": row.target_item_id,
                "origins": row.originating_token_ids,
                "expires_at": row.expires_at.isoformat(),
            }
        )
        return view(await self.intents.save(row))

    async def authorized(self, subject, tenant_id, row, *, committed=None):
        committed = row.status == "committed" if committed is None else committed
        preview = view(row)
        destination = await self.authority.destination(
            subject, tenant_id, preview.destination.id, write=not committed
        )
        if (
            (destination.id, destination.workspace_id, destination.project_id)
            != (preview.destination.id, preview.destination.workspace_id, preview.destination.project_id)
            or not committed
            and destination != preview.destination
        ):
            raise ConflictException(
                "The destination changed; review a new preview", code="KNOWLEDGE_DESTINATION_CHANGED"
            )
        await self.authority.evidence(subject, tenant_id, preview.evidence, exact=not committed)
        if not committed:
            await self.authority.origins(
                subject,
                tenant_id,
                preview.destination.id,
                preview.evidence,
                row.originating_token_ids,
                write_token_ids=tuple(
                    value for value in (row.preview_token_id, row.confirming_token_id) if value
                ),
            )
        return preview

    async def get(self, subject, tenant_id, identifier):
        row = await self.load(subject, tenant_id, identifier)
        preview = await self.authorized(
            subject, tenant_id, row, committed=row.status in {"committing", "unresolved", "committed"}
        )
        if row.status not in {"committing", "unresolved"}:
            return preview
        native = self.native.get()
        if native is None:
            return await self.authorized(subject, tenant_id, row, committed=False)
        try:
            receipt = await native.receipt(subject, tenant_id, identifier, preview.authorization_digest)
        except NativeCommitUncertain:
            return await self.authorized(subject, tenant_id, row, committed=False)
        if receipt is not None:
            await self.acknowledge(subject, tenant_id, identifier, receipt)
            return view(await self.load(subject, tenant_id, identifier))
        return await self.authorized(subject, tenant_id, row, committed=False)

    @transactional
    async def admit(
        self, subject, tenant_id, identifier, confirmation, request_key, *, _external_approval=None
    ):
        row = await self.load(subject, tenant_id, identifier, lock=True)
        if row.request_json.get("origin", {}).get("kind") == "external_proposal":
            from koinon.knowledge.external_reviews.approval import require_approval

            require_approval(_external_approval, row, request_key, current_token_id())
        if (
            confirmation.expected_revision != row.revision
            or confirmation.authorization_digest != row.authorization_digest
        ):
            raise ConflictException(
                "Confirm the exact reviewed knowledge change", code="KNOWLEDGE_INTENT_CONFLICT"
            )
        preview = await self.authorized(subject, tenant_id, row, committed=row.status != "preview")
        if row.status == "committed":
            if row.confirmation_key != request_key:
                raise ConflictException(
                    "This review already has a confirmation key", code="KNOWLEDGE_IDEMPOTENCY_CONFLICT"
                )
            return preview, tuple(row.originating_token_ids), None
        if row.status not in {"preview", "committing", "unresolved"} or (
            row.status == "preview" and row.expires_at <= datetime.now(UTC)
        ):
            raise ConflictException("Review a fresh knowledge preview", code="KNOWLEDGE_INTENT_EXPIRED")
        if row.confirmation_key is not None and row.confirmation_key != request_key:
            raise ConflictException(
                "Reuse the exact original confirmation key", code="KNOWLEDGE_IDEMPOTENCY_CONFLICT"
            )
        native = self.committer()
        if row.status == "preview":
            row.confirming_token_id = current_token_id()
            if row.confirming_token_id:
                row.originating_token_ids = sorted(set(row.originating_token_ids) | {row.confirming_token_id})
        row.status, row.confirmation_key = "committing", request_key
        await self.intents.save(row)
        return view(row), tuple(row.originating_token_ids), native

    @transactional
    async def acknowledge(self, subject, tenant_id, identifier, receipt, *, _reconcile=False):
        row = await self.load(subject, tenant_id, identifier, lock=True)
        preview = view(row)
        receipt = KnowledgeCommitReceipt.model_validate(receipt)
        if (
            receipt.operation_id,
            receipt.intent_id,
            receipt.intent_revision,
            receipt.authorization_digest,
            receipt.item_id,
            receipt.action,
            receipt.content_sha256,
            receipt.evidence_sha256,
        ) != (
            preview.id,
            preview.id,
            preview.revision,
            preview.authorization_digest,
            preview.target_item_id,
            preview.action,
            digest(preview.after.model_dump(mode="json")),
            digest([value.model_dump(mode="json") for value in preview.evidence]),
        ):
            raise AccessDenied(
                "Native knowledge receipt does not match this authorization",
                code="KNOWLEDGE_RECEIPT_MISMATCH",
            )
        if not _reconcile:
            await self.authorized(subject, tenant_id, row, committed=True)
        if row.receipt_json is not None and row.receipt_json != receipt.model_dump(mode="json"):
            raise ConflictException("Native knowledge receipt changed", code="KNOWLEDGE_RECEIPT_MISMATCH")
        projection = await self.committer().projection(subject, tenant_id, receipt)
        await self.acknowledgement.apply(preview, receipt, projection)
        row.status, row.receipt_json = "committed", receipt.model_dump(mode="json")
        await self.intents.save(row)
        return CommittedKnowledge(receipt=receipt)

    async def reconcile(self, subject, tenant_id, identifier):
        row = await self.load(subject, tenant_id, identifier)
        if row.status not in {"committing", "unresolved"}:
            return False
        receipt = await self.committer().receipt(subject, tenant_id, identifier, row.authorization_digest)
        if receipt is None:
            return False
        await self.acknowledge(subject, tenant_id, identifier, receipt, _reconcile=True)
        return True

    @transactional
    async def unresolved(self, subject, tenant_id, identifier):
        row = await self.load(subject, tenant_id, identifier, lock=True)
        if row.status != "committed":
            row.status = "unresolved"
            await self.intents.save(row)
        return PendingKnowledgeCommit(operation_id=row.id, intent_id=row.id)

    @transactional
    async def stale(self, subject, tenant_id, identifier):
        row = await self.load(subject, tenant_id, identifier, lock=True)
        if row.status in {"committing", "unresolved"} and row.receipt_json is None:
            row.status = "stale"
            await self.intents.save(row)

    async def confirm(self, subject, tenant_id, identifier, values, request_key, *, _external_approval=None):
        confirmation = KnowledgeConfirmation.model_validate(values)
        if not isinstance(request_key, str) or not 1 <= len(request_key) <= 160:
            raise InvalidRequestException(
                "Provide a confirmation Idempotency-Key", code="KNOWLEDGE_IDEMPOTENCY_REQUIRED"
            )
        preview, origins, native = await self.admit(
            subject, tenant_id, identifier, confirmation, request_key, _external_approval=_external_approval
        )
        if preview.receipt is not None:
            return CommittedKnowledge(receipt=preview.receipt)
        if native is None:
            raise ServiceUnavailableException(
                "Native knowledge lifecycle is unavailable", code="KNOWLEDGE_COMMIT_UNAVAILABLE"
            )
        try:
            receipt = await native.receipt(subject, tenant_id, preview.id, preview.authorization_digest)
            if receipt is None:
                if preview.expires_at <= datetime.now(UTC):
                    raise ConflictException(
                        "Review a fresh knowledge preview", code="KNOWLEDGE_INTENT_EXPIRED"
                    )
                await self.authorized(
                    subject, tenant_id, await self.load(subject, tenant_id, identifier), committed=False
                )
                try:
                    receipt = await native.commit(NativeKnowledgeOperation(preview, origins))
                except ConflictException as error:
                    if error.code in {
                        "KNOWLEDGE_SOURCE_CHANGED",
                        "KNOWLEDGE_VERSION_CONFLICT",
                        "KNOWLEDGE_DESTINATION_CHANGED",
                    }:
                        await self.stale(subject, tenant_id, identifier)
                    raise
            return await self.acknowledge(subject, tenant_id, identifier, receipt)
        except NativeCommitUncertain:
            return await self.unresolved(subject, tenant_id, identifier)

    @transactional
    async def cancel(self, subject, tenant_id, identifier, expected_revision, *, _external_approval=None):
        row = await self.load(subject, tenant_id, identifier, lock=True)
        if row.request_json.get("origin", {}).get("kind") == "external_proposal":
            from koinon.knowledge.external_reviews.approval import require_approval

            require_approval(_external_approval, row, row.confirmation_key, current_token_id())
        preview = await self.authorized(subject, tenant_id, row)
        if row.status == "cancelled" and row.revision == expected_revision + 1:
            return preview
        if row.status != "preview" or row.revision != expected_revision:
            raise ConflictException(
                "Refresh this knowledge operation before cancelling", code="KNOWLEDGE_INTENT_CONFLICT"
            )
        row.status, row.revision = "cancelled", row.revision + 1
        return view(await self.intents.save(row))
