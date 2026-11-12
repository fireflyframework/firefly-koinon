# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

from pyfly.container import Provider, service
from pyfly.data.relational.sqlalchemy import LockMode
from pyfly.kernel import (
    ConflictException,
    PayloadTooLargeException,
    ResourceNotFoundException,
    ServiceUnavailableException,
)

from koinon.assistants.memory.egress import MemoryEgress
from koinon.assistants.memory.egress_dtos import stored_snapshot
from koinon.catalog.errors import AccessDenied
from koinon.catalog.service import CatalogService
from koinon.evidence.access import EvidenceAccess
from koinon.evidence.dtos import ConversationIdentity, ConversationSnapshot, SourceReference
from koinon.evidence.entities import EvidenceReview
from koinon.evidence.ports import (
    ConversationOutputPort,
    ConversationSnapshotPort,
    SourceResolverPort,
    StoredResultPort,
)
from koinon.evidence.repositories import EvidenceReviewRepository
from koinon.evidence.settings import EvidenceSettings
from koinon.exports.dtos import MessageSelection, QueryResultExportInput
from koinon.integrations.content_sources.read_service import SourceReader, SourceReadOperation
from koinon.organization_branding.dtos import encode_branding
from koinon.organization_branding.service import OrganizationBrandingService
from koinon.security.authority import primary_authority


def digest(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()


@dataclass(frozen=True)
class PreparedReviewClaim:
    row: EvidenceReview
    operation: SourceReadOperation | None
    revision: str
    content_digest: str


@service(name="evidence.reviews")
class EvidenceReviews:
    def __init__(
        self,
        reviews: EvidenceReviewRepository,
        access: EvidenceAccess,
        catalog: CatalogService,
        settings: EvidenceSettings,
        snapshots: Provider[ConversationSnapshotPort | None],
        sources: Provider[SourceResolverPort | None],
        results: Provider[StoredResultPort | None],
        branding: Provider[OrganizationBrandingService | None],
        memory: Provider[MemoryEgress | None] | None = None,
        outputs: Provider[ConversationOutputPort | None] | None = None,
        source_reader: Provider[SourceReader | None] | None = None,
    ):
        self.reviews, self.access, self.catalog, self.settings = reviews, access, catalog, settings
        self.snapshots, self.sources, self.results = snapshots, sources, results
        self.branding = branding
        self.memory = memory
        self.outputs = outputs
        self.source_reader = source_reader

    async def source_operation(self, subject, tenant_id, review, *, operation=None):
        reader = self.source_reader.get() if self.source_reader is not None else None
        if reader is None:
            return operation
        sources = tuple(SourceReference.model_validate(value) for value in review.manifest_json)
        operation = await reader.sources(subject, tenant_id, sources, operation=operation)
        if review.snapshot_json.get("memory_bindings"):
            from koinon.assistants.memory.egress_dtos import MemoryEgressBinding

            bindings = tuple(
                MemoryEgressBinding.model_validate(value) for value in review.snapshot_json["memory_bindings"]
            )
            operation = await reader.memory(
                subject, tenant_id, bindings, operation=operation, owner=review.owner_subject
            )
        return operation

    async def preflight_review(self, subject, tenant_id, review_id, *, owner=None, operation=None):
        reader = self.source_reader.get() if self.source_reader is not None else None
        return (
            await reader.review(subject, tenant_id, review_id, owner=owner, operation=operation)
            if reader
            else operation
        )

    async def prepare_claim(self, subject, tenant_id, review_id, expected_revision, *, purpose):
        operation = await self.preflight_review(subject, tenant_id, review_id)
        async with primary_authority(fresh=True):
            rows = await self.reviews.find_all(id=review_id, tenant_id=tenant_id, owner_subject=subject)
            if not rows:
                raise AccessDenied("This review is unavailable", code="REVIEW_UNAVAILABLE")
            row = rows[0]
            self._claimable(row, expected_revision, purpose)
            original = digest(
                {"request": row.request_json, "snapshot": row.snapshot_json, "manifest": row.manifest_json}
            )
        operation = await self.source_operation(subject, tenant_id, row, operation=operation)
        if row.request_json.get("kind") == "query_result":
            if purpose != "export":
                raise ConflictException("Review this content before continuing", code="REVIEW_STALE")
            snapshot, _ = await self._result(
                subject, tenant_id, QueryResultExportInput.model_validate(row.request_json)
            )
        else:
            request = MessageSelection(
                thread_id=row.request_json["thread_id"], message_ids=row.request_json["message_ids"]
            )
            snapshot = await self._conversation(subject, tenant_id, request, purpose)
        payload = snapshot.model_dump(mode="json")
        if isinstance(snapshot, ConversationSnapshot):
            if "identity" in row.snapshot_json:
                recorded = stored_snapshot(row.snapshot_json).identity
                payload["identity"] = recorded.model_dump(mode="json") if recorded else None
            else:
                payload.pop("identity", None)
        if digest({"request": row.request_json, "snapshot": payload}) != row.revision:
            raise ConflictException(
                "The conversation or its sources changed; review it again", code="REVIEW_STALE"
            )
        if operation:
            await operation.release()
        return PreparedReviewClaim(row, operation, expected_revision, original)

    @staticmethod
    def _claimable(row, revision, purpose):
        if (
            row.kind != purpose
            or row.revision != revision
            or row.consumed_at is not None
            or row.expires_at <= datetime.now(UTC)
        ):
            raise ConflictException("Review the current content before continuing", code="REVIEW_STALE")

    async def claim_local(self, subject, tenant_id, prepared, *, purpose):
        row = await self.reviews.find_by_id(prepared.row.id, lock=LockMode.PESSIMISTIC_WRITE)
        if row is None or (row.tenant_id, row.owner_subject) != (tenant_id, subject):
            raise AccessDenied("This review is unavailable", code="REVIEW_UNAVAILABLE")
        self._claimable(row, prepared.revision, purpose)
        if (
            digest(
                {"request": row.request_json, "snapshot": row.snapshot_json, "manifest": row.manifest_json}
            )
            != prepared.content_digest
        ):
            raise ConflictException("Review content changed", code="REVIEW_STALE")
        sources = tuple(SourceReference.model_validate(value) for value in row.manifest_json)
        await self.access.check(
            subject, tenant_id, sources, permission="exports:write" if purpose == "export" else "shares:write"
        )
        grant = await self.catalog.restriction.grant(subject) if self.catalog.restriction else None
        row.creator_token_id = grant.id if grant else None
        row.consumed_at = datetime.now(UTC)
        await self.reviews.save(row)
        return row

    async def output_check(self, subject, tenant_id, snapshot):
        if not any(message.role == "assistant" for message in snapshot.messages):
            return
        port = self.outputs.get() if self.outputs else None
        if port is None:
            raise ServiceUnavailableException(
                "Regenerate this answer before transferring it", code="CONVERSATION_OUTPUT_UNAVAILABLE"
            )
        reader = self.source_reader.get() if self.source_reader is not None else None
        operation = await reader.sources(subject, tenant_id, snapshot.sources) if reader else None
        await port.authorize_output(
            snapshot.owner_subject,
            tenant_id,
            snapshot.thread_id,
            [message.id for message in snapshot.messages],
            snapshot=snapshot,
            **({"reader_subject": subject} if subject != snapshot.owner_subject else {}),
        )
        if operation is not None:
            await operation.release()

    async def memory_check(
        self,
        subject,
        tenant_id,
        snapshot,
        *,
        transfer=False,
        consent=False,
        reader_subject=None,
        permission=None,
        creator_token_id=None,
        creator_permission=None,
        release=None,
    ):
        bindings = getattr(snapshot, "memory_bindings", ())
        port = self.memory.get() if self.memory else None
        if bindings and port is None:
            raise ServiceUnavailableException(
                "Conversation authority is unavailable", code="MEMORY_UNAVAILABLE"
            )
        if port and not bindings:
            messages = tuple(message.id for message in snapshot.messages if message.role == "assistant")
            if messages and await port.repository.unbound_memory(
                subject, tenant_id, snapshot.thread_id, messages
            ):
                raise ConflictException(
                    "Review this answer again to bind its remembered context",
                    code="MEMORY_TRANSFER_REVIEW_REQUIRED",
                )

        async def release_check():
            if permission:
                await self.access.check(
                    reader_subject or subject,
                    tenant_id,
                    snapshot.sources,
                    permission=permission,
                    owner_subject=subject,
                    originating_token_ids=snapshot.originating_token_ids,
                    creator_token_id=creator_token_id,
                    creator_permission=creator_permission,
                )

        return (
            await port.authorize(
                subject,
                tenant_id,
                bindings,
                transfer=transfer,
                consent=consent,
                reader_subject=reader_subject,
                release_check=release_check,
                token_ids=(creator_token_id,) if creator_token_id else (),
                release=release,
            )
            if port
            else False
        )

    async def _identity(self, subject, tenant_id):
        service = self.branding.get()
        if service is None:
            raise ServiceUnavailableException(
                "Organization identity is unavailable", code="BRANDING_UNAVAILABLE"
            )
        value = await service.get(subject, tenant_id)
        return ConversationIdentity(
            product_name=value.branding.product_name,
            assistant_name=value.branding.assistant_name,
            branding_revision=value.revision,
            branding_origin=value.origin,
            branding_sha256=hashlib.sha256(encode_branding(value.branding).encode("ascii")).hexdigest(),
        )

    async def _conversation(self, subject, tenant_id, request, purpose):
        port = self.snapshots.get()
        if port is None:
            raise ServiceUnavailableException(
                "Conversation export is not configured", code="CONVERSATION_SNAPSHOT_UNAVAILABLE"
            )
        snapshot = await port.snapshot(subject, tenant_id, request.thread_id, request.message_ids)
        if (
            snapshot.owner_subject != subject
            or snapshot.tenant_id != tenant_id
            or snapshot.thread_id != request.thread_id
            or set(request.message_ids) != {m.id for m in snapshot.messages}
        ):
            raise AccessDenied("This conversation is unavailable", code="EVIDENCE_UNAVAILABLE")
        if purpose == "share":
            if any(message.private_derived for message in snapshot.messages):
                raise ConflictException(
                    "Answers derived from a private attachment cannot be shared",
                    code="PRIVATE_ATTACHMENT_SHARE_BLOCKED",
                )
            if not snapshot.source_manifest_complete:
                raise ConflictException(
                    "Review a complete source manifest before sharing", code="EVIDENCE_MANIFEST_INCOMPLETE"
                )
        reader = self.source_reader.get() if self.source_reader is not None else None
        source_operation = await reader.sources(subject, tenant_id, snapshot.sources) if reader else None
        await self.access.check(
            subject,
            tenant_id,
            snapshot.sources,
            permission="shares:write" if purpose == "share" else "exports:write",
            originating_token_ids=snapshot.originating_token_ids,
        )
        resolver = self.sources.get()
        if resolver is not None:
            snapshot = snapshot.model_copy(
                update={"sources": await resolver.resolve(subject, tenant_id, snapshot.sources)}
            )
        await self.memory_check(
            subject, tenant_id, snapshot, permission="shares:write" if purpose == "share" else "exports:write"
        )
        payload = snapshot.model_dump(mode="json")
        if len(json.dumps(payload, ensure_ascii=False).encode()) > self.settings.max_snapshot_bytes:
            raise PayloadTooLargeException(
                "Select fewer messages for this export or share", code="SNAPSHOT_TOO_LARGE"
            )
        if source_operation is not None:
            await source_operation.release()
        return snapshot

    async def _result(self, subject, tenant_id, request):
        reader = self.source_reader.get() if self.source_reader is not None else None
        source_operation = None
        if reader is not None:
            source_operation = await reader.sources(
                subject,
                tenant_id,
                (
                    SimpleNamespace(
                        id=request.query_id,
                        asset_id=request.dataset_id,
                        kind="dataset",
                        knowledge_version_id=None,
                        source_version_id=None,
                        extraction_id=None,
                        source_part_id=None,
                        snapshot_id=None,
                        query_id=request.query_id,
                    ),
                ),
            )
        port = self.results.get()
        if port is None:
            raise ServiceUnavailableException(
                "Stored result export is not configured", code="STORED_RESULT_UNAVAILABLE"
            )
        asset = await self.catalog.get(subject, tenant_id, request.dataset_id)
        if asset.kind != "dataset":
            raise AccessDenied("Select an authorized dataset result", code="EVIDENCE_UNAVAILABLE")
        await self.catalog.authorize(subject, tenant_id, "exports:write", asset.workspace_id)
        result = await port.describe(subject, tenant_id, request.dataset_id, request.query_id)
        if source_operation is not None:
            source_operation.validate_result(result)
        if result.asset_id != request.dataset_id or result.query_id != request.query_id:
            raise AccessDenied("This result is unavailable", code="EVIDENCE_UNAVAILABLE")
        if result.byte_size == 0:
            raise ResourceNotFoundException(
                "This empty execution stored no Parquet artifact or schema",
                code="RESULT_ARTIFACT_UNAVAILABLE",
            )
        if result.expires_at <= datetime.now(UTC):
            raise ConflictException(
                "This stored result expired; it will not be rerun automatically", code="RESULT_EXPIRED"
            )
        if result.byte_size > self.settings.max_download_bytes:
            raise PayloadTooLargeException(
                "Stored result exceeds the download limit", code="EXPORT_TOO_LARGE"
            )
        source = SourceReference(
            id=result.query_id, asset_id=asset.id, title=asset.name, kind="dataset", query_id=result.query_id
        )
        await self.access.check(subject, tenant_id, (source,), permission="exports:write")
        if source_operation:
            await source_operation.release()
        return result, (source,)

    async def query_result(self, subject, tenant_id, request: QueryResultExportInput):
        self.settings.validate()
        result, sources = await self._result(subject, tenant_id, request)
        grant = await self.catalog.restriction.grant(subject) if self.catalog.restriction else None
        payload, values = result.model_dump(mode="json"), request.model_dump(mode="json")
        now = datetime.now(UTC)
        row = EvidenceReview(
            id=str(uuid4()),
            tenant_id=tenant_id,
            owner_subject=subject,
            kind="export",
            title=sources[0].title,
            revision=digest({"request": values, "snapshot": payload}),
            request_json=values,
            snapshot_json=payload,
            manifest_json=[source.model_dump(mode="json") for source in sources],
            creator_token_id=grant.id if grant else None,
            created_at=now,
            expires_at=min(result.expires_at, now + timedelta(seconds=self.settings.review_ttl_seconds)),
            consumed_at=None,
        )
        await self._persist_review(subject, tenant_id, row)
        return row

    async def conversation(self, subject, tenant_id, request: MessageSelection, *, purpose):
        self.settings.validate()
        if purpose not in {"export", "share"}:
            raise ValueError("Unsupported review purpose")
        snapshot = await self._conversation(subject, tenant_id, request, purpose)
        snapshot = snapshot.model_copy(update={"identity": await self._identity(subject, tenant_id)})
        grant = await self.catalog.restriction.grant(subject) if self.catalog.restriction else None
        payload = snapshot.model_dump(mode="json")
        values = request.model_dump(mode="json")
        now = datetime.now(UTC)
        review = EvidenceReview(
            id=str(uuid4()),
            tenant_id=tenant_id,
            owner_subject=subject,
            kind=purpose,
            title=snapshot.title,
            revision=digest({"request": values, "snapshot": payload}),
            request_json=values,
            snapshot_json=payload,
            manifest_json=[source.model_dump(mode="json") for source in snapshot.sources],
            creator_token_id=grant.id if grant else None,
            created_at=now,
            expires_at=now + timedelta(seconds=self.settings.review_ttl_seconds),
            consumed_at=None,
        )
        await self.memory_check(
            subject,
            tenant_id,
            snapshot,
            permission="shares:write" if purpose == "share" else "exports:write",
            creator_token_id=review.creator_token_id,
            creator_permission="shares:write" if purpose == "share" else "exports:write",
        )
        await self._persist_review(subject, tenant_id, review)
        return review

    async def _persist_review(self, subject, tenant_id, review):
        operation = await self.source_operation(subject, tenant_id, review)
        async with operation.local_fence() if operation else primary_authority(read_only=False):
            await self.catalog._lock_tenant(tenant_id)
            if await self.reviews.active_count(subject, tenant_id) >= self.settings.max_active_reviews:
                raise ConflictException(
                    "Finish an existing review before creating another", code="REVIEW_LIMIT_REACHED"
                )
            await self.access.check(
                subject,
                tenant_id,
                tuple(SourceReference.model_validate(value) for value in review.manifest_json),
                permission="shares:write" if review.kind == "share" else "exports:write",
            )
            await self.reviews.save(review)
        if operation:
            await operation.release()

    async def claim(self, subject, tenant_id, review_id, expected_revision, *, purpose):
        prepared = await self.prepare_claim(subject, tenant_id, review_id, expected_revision, purpose=purpose)
        async with (
            prepared.operation.local_fence() if prepared.operation else primary_authority(read_only=False)
        ):
            row = await self.claim_local(subject, tenant_id, prepared, purpose=purpose)
        if prepared.operation:
            await prepared.operation.release()
        return row
