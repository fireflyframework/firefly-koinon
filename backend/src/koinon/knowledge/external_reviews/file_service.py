# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import base64
import binascii
import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from pyfly.container import Provider, service
from pyfly.data.relational.sqlalchemy import LockMode, transactional
from pyfly.kernel import ConflictException, InvalidRequestException, ServiceUnavailableException

from koinon.catalog.errors import AccessDenied
from koinon.catalog.mappers import entry_dto
from koinon.knowledge.curated.authority import CuratedAuthority, digest
from koinon.knowledge.curated.dtos import KnowledgeDestination
from koinon.knowledge.external_reviews.dtos import ExternalReviewDecision
from koinon.knowledge.external_reviews.entities import ExternalFileReviewRow
from koinon.knowledge.external_reviews.file_cleanup import ExternalFileCleanup
from koinon.knowledge.external_reviews.file_dtos import (
    CHUNK_BYTES,
    MAX_FILE_BYTES,
    ExternalFileChunkInput,
    ExternalFileCleanupResult,
    ExternalFileReceipt,
    ExternalFileReviewChallenge,
    ExternalFileReviewInput,
    ExternalFileReviewView,
)
from koinon.knowledge.external_reviews.file_queue import ExternalFileQueue
from koinon.knowledge.external_reviews.file_storage import ExternalReviewFileStorage
from koinon.knowledge.external_reviews.repositories import ExternalFileReviewRepository
from koinon.knowledge.external_reviews.service import ExternalKnowledgeReviews, fingerprint, key
from koinon.knowledge.external_reviews.settings import ExternalReviewSettings
from koinon.knowledge.service import KnowledgeFacade


@service(name="knowledge.external_reviews.file_service")
class ExternalFileReviews:
    def __init__(
        self,
        rows: ExternalFileReviewRepository,
        reviews: ExternalKnowledgeReviews,
        authority: CuratedAuthority,
        storage: ExternalReviewFileStorage,
        knowledge: Provider[KnowledgeFacade | None],
        settings: ExternalReviewSettings,
        cleanup: ExternalFileCleanup,
        queue: ExternalFileQueue | None = None,
    ):
        self.rows, self.reviews, self.authority = rows, reviews, authority
        self.storage, self.knowledge = storage, knowledge
        self.settings = settings
        self.cleaner = cleanup
        self.queue = queue

    def facade(self) -> KnowledgeFacade:
        value = self.knowledge.get()
        if value is None:
            raise ServiceUnavailableException(
                "Configure canonical knowledge ingestion", code="EXTERNAL_INTAKE_UNAVAILABLE"
            )
        return value

    def capacity(self) -> int:
        self.settings.validate()
        _, storage_limit = self.storage.configured()
        intake_limit = self.facade().settings.max_upload_bytes
        if self.queue is not None and self.storage.file_transport():
            intake_limit = max(intake_limit, self.queue.capacity())
        return min(
            MAX_FILE_BYTES, self.settings.max_file_bytes, intake_limit, storage_limit,
            self.storage.scratch.capacity_bytes // 2,
        )

    async def load(
        self, subject: str, tenant_id: str, identifier: str, *, lock=False
    ) -> ExternalFileReviewRow:
        grant = await self.reviews.grant(subject, tenant_id)
        row = await self.rows.find_by_id(identifier, lock=LockMode.PESSIMISTIC_WRITE if lock else None)
        if row is None or (
            row.subject,
            row.tenant_id,
            row.credential_id,
            row.application_id,
            row.credential_sha256,
        ) != (subject, tenant_id, grant.id, grant.authorized_application_id, fingerprint(grant)):
            raise AccessDenied("This private file review is unavailable", code="EXTERNAL_REVIEW_UNAVAILABLE")
        return row

    async def authorize(
        self, subject: str, tenant_id: str, row: ExternalFileReviewRow
    ) -> KnowledgeDestination:
        expected = KnowledgeDestination.model_validate(row.destination_json)
        destination = await self.authority.destination(
            subject, tenant_id, expected.id, write=row.status not in {"committed", "cancelled"}
        )
        if row.status not in {"committed", "cancelled"} and destination != expected:
            raise ConflictException(
                "The destination changed; review again", code="KNOWLEDGE_DESTINATION_CHANGED"
            )
        if (destination.id, destination.workspace_id, destination.project_id) != (
            expected.id,
            expected.workspace_id,
            expected.project_id,
        ):
            raise AccessDenied("The file destination changed", code="EXTERNAL_REVIEW_UNAVAILABLE")
        return expected

    async def view(self, subject: str, tenant_id: str, row: ExternalFileReviewRow) -> ExternalFileReviewView:
        destination = await self.authorize(subject, tenant_id, row)
        request = ExternalFileReviewInput.model_validate(row.request_json)
        intake_status = None
        if row.source_id:
            source = await self.authority.catalog.get(subject, tenant_id, row.source_id)
            if source.parent_id != destination.id or source.workspace_id != destination.workspace_id:
                raise AccessDenied("Recorded intake scope changed", code="EXTERNAL_REVIEW_UNAVAILABLE")
            intake_status = source.status
        return ExternalFileReviewView.model_validate(
            dict(
                id=row.id,
                tenant_id=row.tenant_id,
                revision=row.revision,
                authorization_digest=row.authorization_digest,
                status=row.status,
                **request.model_dump(exclude={"destination_id"}),
                destination=destination,
                received_chunks=len(row.chunks_json),
                total_chunks=(request.size_bytes + CHUNK_BYTES - 1) // CHUNK_BYTES,
                expires_at=row.expires_at,
                submitted_by=row.subject,
                credential_id=row.credential_id,
                application_id=row.application_id,
                source_id=row.source_id,
                intake_status=intake_status,
                receipt=ExternalFileReceipt.model_validate(row.receipt_json) if row.receipt_json else None,
            )
        )

    def fresh(self, row: ExternalFileReviewRow, statuses: set[str]) -> None:
        if row.status not in statuses or row.expires_at <= datetime.now(UTC):
            raise ConflictException("Review a fresh file proposal", code="EXTERNAL_REVIEW_EXPIRED")

    @transactional
    async def stage(
        self, subject: str, tenant_id: str, values: object, request_key: str
    ) -> ExternalFileReviewView:
        request_key = key(request_key)
        request = ExternalFileReviewInput.model_validate(values)
        grant = await self.reviews.grant(subject, tenant_id)
        self.settings.validate()
        await self.authority.catalog.tenant_repository.find_by_id(tenant_id, lock=LockMode.PESSIMISTIC_WRITE)
        if request.size_bytes > self.capacity():
            raise InvalidRequestException(
                "The file exceeds its configured upload bound", code="EXTERNAL_FILE_TOO_LARGE"
            )
        destination = await self.authority.destination(subject, tenant_id, request.destination_id)
        existing = await self.rows.find_all(
            tenant_id=tenant_id, subject=subject, credential_id=grant.id, stage_key=request_key
        )
        if existing:
            row = await self.load(subject, tenant_id, existing[0].id, lock=True)
            if row.request_json != request.model_dump(mode="json"):
                raise ConflictException(
                    "This key already identifies another file", code="EXTERNAL_REVIEW_IDEMPOTENCY_CONFLICT"
                )
            return await self.view(subject, tenant_id, row)
        count, total = await self.rows.staging_totals(tenant_id, subject)
        if (
            count >= self.settings.max_active_files
            or total + request.size_bytes > self.settings.max_staged_bytes
        ):
            raise ConflictException(
                "Finish an existing review or ask an administrator to clean up expired or cancelled uploads",
                code="EXTERNAL_STAGING_LIMIT",
            )
        now = datetime.now(UTC)
        row = ExternalFileReviewRow(
            id=str(uuid4()),
            tenant_id=tenant_id,
            subject=subject,
            credential_id=grant.id,
            application_id=grant.authorized_application_id,
            credential_sha256=fingerprint(grant),
            stage_key=request_key,
            request_json=request.model_dump(mode="json"),
            destination_json=destination.model_dump(mode="json"),
            revision=1,
            status="uploading",
            chunks_json={},
            created_at=now,
            expires_at=min(grant.expires_at, now + timedelta(seconds=self.settings.ttl_seconds)),
        )
        row.authorization_digest = digest(
            {
                "id": row.id,
                "tenant_id": tenant_id,
                "subject": subject,
                "credential": row.credential_sha256,
                "revision": row.revision,
                "request": row.request_json,
                "destination": row.destination_json,
                "expires_at": row.expires_at.isoformat(),
                "origin": "external_proposal",
                "authority": "unverified",
            }
        )
        return await self.view(subject, tenant_id, await self.rows.save(row))

    async def get(self, subject: str, tenant_id: str, identifier: str) -> ExternalFileReviewView:
        row = await self.load(subject, tenant_id, identifier)
        if row.status in {"ingesting", "unresolved"} and row.source_id:
            await self.reconcile(subject, tenant_id, identifier)
            row = await self.load(subject, tenant_id, identifier)
        return await self.view(subject, tenant_id, row)

    @transactional
    async def chunk(
        self, subject: str, tenant_id: str, identifier: str, values: object
    ) -> ExternalFileReviewView:
        values = ExternalFileChunkInput.model_validate(values)
        row = await self.load(subject, tenant_id, identifier, lock=True)
        self.fresh(row, {"uploading"})
        await self.authorize(subject, tenant_id, row)
        request = ExternalFileReviewInput.model_validate(row.request_json)
        remaining = request.size_bytes - values.index * CHUNK_BYTES
        try:
            content = base64.b64decode(values.data_base64, validate=True)
        except (binascii.Error, ValueError):
            raise InvalidRequestException(
                "Use valid Base64 file bytes", code="EXTERNAL_FILE_CHUNK_INVALID"
            ) from None
        if (
            remaining <= 0
            or len(content) != min(CHUNK_BYTES, remaining)
            or hashlib.sha256(content).hexdigest() != values.sha256
        ):
            raise ConflictException(
                "The chunk differs from its admitted index, size or digest",
                code="EXTERNAL_FILE_CHUNK_INVALID",
            )
        entry = {"size": len(content), "sha256": values.sha256}
        previous = row.chunks_json.get(str(values.index))
        if previous is not None and previous != entry:
            raise ConflictException(
                "This chunk already contains different bytes", code="EXTERNAL_FILE_CHUNK_CONFLICT"
            )
        if previous is None:
            await self.storage.put(row, f"chunks/{values.index}", content, values.sha256)
            row.chunks_json = {**row.chunks_json, str(values.index): entry}
            await self.rows.save(row)
        else:
            await self.storage.read(row, f"chunks/{values.index}", len(content), values.sha256)
        return await self.view(subject, tenant_id, row)

    @transactional
    async def seal(self, subject: str, tenant_id: str, identifier: str) -> ExternalFileReviewView:
        row = await self.load(subject, tenant_id, identifier, lock=True)
        self.fresh(row, {"uploading", "preview"})
        await self.authorize(subject, tenant_id, row)
        request = ExternalFileReviewInput.model_validate(row.request_json)
        count = (request.size_bytes + CHUNK_BYTES - 1) // CHUNK_BYTES
        if set(row.chunks_json) != {str(index) for index in range(count)}:
            raise ConflictException("Upload every expected file chunk", code="EXTERNAL_FILE_INCOMPLETE")
        try:
            async with self.storage.spool(request.size_bytes):
                reference = await self.storage.seal_file(row, request.size_bytes, request.sha256)
        except ValueError:
            raise ConflictException(
                "File digest differs from the reviewed manifest", code="EXTERNAL_FILE_DIGEST_MISMATCH"
            ) from None
        self.fresh(row, {"uploading", "preview"})
        row.blob_key, row.status = self.storage.key(row, "original"), "preview"
        row.blob_reference_json = reference.to_dict() if reference else None
        await self.rows.save(row)
        return await self.view(subject, tenant_id, row)

    @transactional
    async def challenge(self, subject: str, tenant_id: str, identifier: str) -> ExternalFileReviewChallenge:
        row = await self.load(subject, tenant_id, identifier, lock=True)
        self.fresh(row, {"uploading", "preview"})
        view = await self.view(subject, tenant_id, row)
        nonce = secrets.token_urlsafe(32)
        row.nonce_sha256 = hashlib.sha256(nonce.encode()).hexdigest()
        await self.rows.save(row)
        return ExternalFileReviewChallenge(review=view, nonce=nonce)

    def decision(self, row: ExternalFileReviewRow, values: object) -> None:
        values = ExternalReviewDecision.model_validate(values)
        if (values.expected_revision, values.authorization_digest) != (
            row.revision,
            row.authorization_digest,
        ):
            raise ConflictException("Approve the exact reviewed file", code="EXTERNAL_REVIEW_CHANGED")
        if not row.nonce_sha256 or not secrets.compare_digest(
            row.nonce_sha256, hashlib.sha256(values.nonce.encode()).hexdigest()
        ):
            raise AccessDenied("Use the private application review", code="EXTERNAL_REVIEW_NONCE_INVALID")

    @transactional
    async def admit(
        self, subject: str, tenant_id: str, identifier: str, values: object, request_key: str
    ) -> bool:
        request_key = key(request_key)
        row = await self.load(subject, tenant_id, identifier, lock=True)
        self.decision(row, values)
        await self.authorize(subject, tenant_id, row)
        if row.status in {"ingesting", "unresolved", "committed"}:
            if row.confirmation_key != request_key:
                raise ConflictException(
                    "Reuse the original approval key", code="EXTERNAL_REVIEW_IDEMPOTENCY_CONFLICT"
                )
            return False
        self.fresh(row, {"preview"})
        row.status, row.confirmation_key, row.decided_at = "ingesting", request_key, datetime.now(UTC)
        await self.rows.save(row)
        return True

    @transactional
    async def source(self, subject, tenant_id, identifier, source):
        row = await self.load(subject, tenant_id, identifier, lock=True)
        destination = await self.authorize(subject, tenant_id, row)
        request = ExternalFileReviewInput.model_validate(row.request_json)
        if row.status != "ingesting" or (
            source.parent_id,
            source.workspace_id,
            source.project_id,
            source.tenant_id,
            source.kind,
            source.status,
            source.name,
            source.created_by,
            source.metadata_json.get("sha256"),
            source.metadata_json.get("bytes"),
            source.metadata_json.get("mode"),
        ) != (
            destination.id,
            destination.workspace_id,
            destination.project_id,
            tenant_id,
            "source",
            "pending",
            request.filename,
            subject,
            request.sha256,
            request.size_bytes,
            request.mode,
        ):
            raise AccessDenied(
                "Intake source differs from the approved destination", code="EXTERNAL_INTAKE_MISMATCH"
            )
        if row.source_id is not None and row.source_id != source.id:
            raise ConflictException(
                "This operation already owns another source", code="EXTERNAL_INTAKE_MISMATCH"
            )
        row.source_id = source.id
        source.metadata_json = {
            **source.metadata_json,
            "_koinon_external_review": {
                "review_id": row.id,
                "authorization_digest": row.authorization_digest,
                "credential_id": row.credential_id,
                "application_id": row.application_id,
                "submitted_by": row.subject,
                "authority": "unverified",
                "provider": None,
                "model": None,
            },
        }
        await self.authority.catalog.catalog_repository.save(source)
        await self.rows.save(row)

    @transactional
    async def finish(self, subject, tenant_id, identifier, result=None):
        row = await self.load(subject, tenant_id, identifier, lock=True)
        if result is not None:
            receipt = ExternalFileReceipt.model_validate(result)
            request = ExternalFileReviewInput.model_validate(row.request_json)
            destination = KnowledgeDestination.model_validate(row.destination_json)
            source = receipt.source
            if (
                (
                    source.id,
                    source.tenant_id,
                    source.parent_id,
                    source.workspace_id,
                    source.project_id,
                    source.kind,
                    source.status,
                    source.metadata.get("sha256"),
                    source.metadata.get("bytes"),
                    source.metadata.get("mode"),
                    source.name,
                    source.created_by,
                )
                != (
                    row.source_id,
                    tenant_id,
                    destination.id,
                    destination.workspace_id,
                    destination.project_id,
                    "source",
                    "ready",
                    request.sha256,
                    request.size_bytes,
                    request.mode,
                    request.filename,
                    subject,
                )
                or len(receipt.assets) != 1
                or any(
                    (
                        asset.tenant_id,
                        asset.workspace_id,
                        asset.project_id,
                        asset.parent_id,
                        asset.kind,
                        asset.status,
                        asset.name,
                        asset.created_by,
                        asset.metadata.get("sha256"),
                    )
                    != (
                        tenant_id,
                        destination.workspace_id,
                        destination.project_id,
                        source.id,
                        request.mode,
                        "ready",
                        request.filename,
                        subject,
                        request.sha256,
                    )
                    for asset in receipt.assets
                )
            ):
                raise ConflictException(
                    "Intake receipt differs from the approved file", code="EXTERNAL_INTAKE_MISMATCH"
                )
            row.receipt_json, row.status = receipt.model_dump(mode="json"), "committed"
        elif row.status != "committed":
            row.status = "unresolved"
        await self.rows.save(row)

    async def approve(
        self, subject: str, tenant_id: str, identifier: str, values: object, request_key: str
    ) -> ExternalFileReviewView:
        first = await self.admit(subject, tenant_id, identifier, values, request_key)
        if first:
            row = await self.load(subject, tenant_id, identifier)
            request = ExternalFileReviewInput.model_validate(row.request_json)
            destination = await self.authorize(subject, tenant_id, row)
            try:
                if request.size_bytes > self.facade().settings.max_upload_bytes:
                    if self.queue is None:
                        raise ServiceUnavailableException(
                            "Configure queued file ingestion", code="EXTERNAL_INTAKE_UNAVAILABLE"
                        )
                    await self.queue.enqueue(self, subject, tenant_id, identifier)
                    return await self.get(subject, tenant_id, identifier)
                content = await self.storage.read(row, "original", request.size_bytes, request.sha256)
                row = await self.load(subject, tenant_id, identifier)
                destination = await self.authorize(subject, tenant_id, row)
                result = await self.facade().upload(
                    subject,
                    tenant_id,
                    workspace_id=destination.workspace_id,
                    project_id=destination.project_id,
                    parent_id=destination.id,
                    mode=request.mode,
                    filename=request.filename,
                    content=content,
                    _on_source=lambda source: self.source(subject, tenant_id, identifier, source),
                )
                await self.finish(subject, tenant_id, identifier, result)
            except Exception as error:
                await self.finish(subject, tenant_id, identifier)
                if isinstance(error, AccessDenied):
                    raise
        return await self.get(subject, tenant_id, identifier)

    @transactional
    async def reconcile(self, subject: str, tenant_id: str, identifier: str) -> None:
        row = await self.load(subject, tenant_id, identifier, lock=True)
        if row.status not in {"ingesting", "unresolved"} or not row.source_id:
            return
        destination = await self.authorize(subject, tenant_id, row)
        request = ExternalFileReviewInput.model_validate(row.request_json)
        source = await self.authority.catalog.get(subject, tenant_id, row.source_id)
        marker = source.metadata_json.get("_koinon_external_review", {})
        if source.status != "ready" or (
            marker.get("review_id"),
            marker.get("authorization_digest"),
            source.parent_id,
        ) != (row.id, row.authorization_digest, destination.id):
            return
        assets = await self.authority.catalog.list(subject, tenant_id, parent_id=source.id, kind=request.mode)
        if len(assets) != 1 or assets[0].status != "ready":
            return
        facade = self.facade()
        domain = "canon" if request.mode == "document" else "structured"
        await facade.binding(tenant_id, source.id, domain, entry=source)
        await facade.binding(tenant_id, assets[0].id, domain, entry=assets[0])
        await self.finish(
            subject, tenant_id, identifier, {"source": entry_dto(source), "assets": [entry_dto(assets[0])]}
        )

    @transactional
    async def cancel(
        self, subject: str, tenant_id: str, identifier: str, values: object
    ) -> ExternalFileReviewView:
        row = await self.load(subject, tenant_id, identifier, lock=True)
        self.decision(row, values)
        if row.status != "cancelled":
            self.fresh(row, {"uploading", "preview"})
            await self.authorize(subject, tenant_id, row)
            row.status, row.decided_at = "cancelled", datetime.now(UTC)
            await self.rows.save(row)
        return await self.view(subject, tenant_id, row)

    async def cleanup(self, subject: str, tenant_id: str, values: object) -> ExternalFileCleanupResult:
        return await self.cleaner.cleanup(subject, tenant_id, values)
