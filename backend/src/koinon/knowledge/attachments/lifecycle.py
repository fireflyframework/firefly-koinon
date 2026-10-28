# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Durable private original reservations and native extraction/purge intents."""

from datetime import timedelta
from hashlib import sha256
from json import dumps
from typing import get_args
from uuid import uuid4

from pyfly.container import service
from pyfly.data.relational.sqlalchemy import LockMode, transactional
from pyfly.kernel import (
    ConflictException,
    InvalidRequestException,
    PayloadTooLargeException,
    ServiceUnavailableException,
)
from pyfly.security.context_holder import SecurityContextHolder

from koinon.catalog.errors import AccessDenied
from koinon.knowledge.attachments.dtos import AttachmentKind, AttachmentStatus, PrivateChunkView
from koinon.knowledge.attachments.entities import ChatAttachment, timestamp
from koinon.knowledge.attachments.mappers import attachment_dto
from koinon.knowledge.attachments.service import AttachmentService


@service(name="knowledge.attachments.lifecycle")
class AttachmentLifecycle:
    def __init__(self, reader: AttachmentService):
        self.reader = reader

    async def row(self, subject, tenant_id, thread_id, attachment_id, *, active=False, lock=False):
        await self.reader.authority.thread(subject, tenant_id, thread_id, active=active)
        async with self.reader.data.scope(subject, tenant_id, thread_id):
            row = await self.reader.records.find_by_id(
                attachment_id, lock=LockMode.PESSIMISTIC_WRITE if lock else None
            )
            if row is None or (row.subject, row.tenant_id, row.thread_id) != (subject, tenant_id, thread_id):
                raise AccessDenied("Private file is unavailable", code="ATTACHMENT_UNAVAILABLE")
            return row

    async def view(self, row):
        job = await self.reader.jobs.repository.find_by_id(row.job_id) if row.job_id else None
        return attachment_dto(row, job)

    async def get(self, subject, tenant_id, thread_id, attachment_id):
        return await self.view(await self.row(subject, tenant_id, thread_id, attachment_id))

    @staticmethod
    def page_input(page, page_size, q=""):
        if (
            type(page) is not int
            or not 1 <= page <= 1000000
            or type(page_size) is not int
            or not 1 <= page_size <= 100
            or (not isinstance(q, str) or len(q) > 255)
        ):
            raise InvalidRequestException(
                "Select bounded private file pagination and filters", code="INVALID_ATTACHMENT_PAGE"
            )

    async def list(
        self, subject, tenant_id, thread_id, *, page=1, page_size=25, q="", status=None, kind=None
    ):
        self.page_input(page, page_size, q)
        if (
            status is not None
            and status not in get_args(AttachmentStatus)
            or kind is not None
            and kind not in get_args(AttachmentKind)
        ):
            raise InvalidRequestException(
                "Choose a supported private file filter", code="INVALID_ATTACHMENT_FILTER"
            )
        await self.reader.authority.thread(subject, tenant_id, thread_id)
        async with self.reader.data.scope(subject, tenant_id, thread_id):
            rows, total = await self.reader.records.page(
                tenant_id, subject, thread_id, page=page, page_size=page_size, q=q, status=status, kind=kind
            )
        return {
            "items": [await self.view(row) for row in rows],
            "total": total,
            "page": page,
            "page_size": page_size,
            "pages": (total + page_size - 1) // page_size,
        }

    async def chunks(self, subject, tenant_id, thread_id, attachment_id, *, page=1, page_size=25, q=""):
        self.page_input(page, page_size, q)
        row = await self.row(subject, tenant_id, thread_id, attachment_id)
        self.reader.ready(row)
        async with self.reader.data.scope(subject, tenant_id, thread_id):
            rows, total = await self.reader.chunks.page(
                tenant_id, subject, thread_id, [attachment_id], page=page, page_size=page_size, q=q
            )
        return {
            "items": [
                PrivateChunkView(
                    id=value.id,
                    attachment_id=value.attachment_id,
                    index=value.ordinal,
                    text=value.text,
                    page=value.page,
                    section_path=value.section_path,
                    char_start=value.char_start,
                    char_end=value.char_end,
                    sha256=value.sha256,
                )
                for value in rows
            ],
            "total": total,
            "page": page,
            "page_size": page_size,
            "pages": (total + page_size - 1) // page_size,
        }

    async def original(self, subject, tenant_id, thread_id, attachment_id):
        row = await self.row(subject, tenant_id, thread_id, attachment_id)
        if row.status == "deleted" or row.expires_at <= timestamp():
            self.reader.ready(row)
        return row, await self.reader.storage.read(row)

    @staticmethod
    def request_key(subject, thread_id, key):
        if not isinstance(key, str) or not 1 <= len(key) <= 255:
            raise InvalidRequestException(
                "Supply an Idempotency-Key up to255 characters", code="INVALID_IDEMPOTENCY_KEY"
            )
        return sha256(dumps([subject, thread_id, key], separators=(",", ":")).encode()).hexdigest()

    async def upload(self, subject, tenant_id, thread_id, *, filename, content, media_type, idempotency_key):
        settings = self.reader.settings
        settings.validate()
        await self.reader.authority.thread(subject, tenant_id, thread_id, active=True)
        if (
            not filename
            or len(filename) > 255
            or any(ord(value) < 32 or value in "/\\" for value in filename)
        ):
            raise InvalidRequestException(
                "Choose a filename without paths or control characters", code="INVALID_ATTACHMENT_NAME"
            )
        if not content or len(content) > settings.max_file_bytes:
            raise PayloadTooLargeException(
                "The file is empty or exceeds the attachment limit", code="ATTACHMENT_TOO_LARGE"
            )
        if media_type is not None and (
            not isinstance(media_type, str)
            or len(media_type) > 128
            or any(ord(value) < 32 for value in media_type)
        ):
            raise InvalidRequestException(
                "Choose a valid declared media type", code="INVALID_ATTACHMENT_MEDIA"
            )
        if media_type and media_type.startswith("image/") and len(content) > settings.max_image_bytes:
            raise PayloadTooLargeException(
                "The image exceeds the attachment limit", code="ATTACHMENT_IMAGE_TOO_LARGE"
            )
        self.reader.storage.configured()
        key = self.request_key(subject, thread_id, idempotency_key)
        digest = sha256(content).hexdigest()
        request_hash = sha256(
            dumps([filename, digest, len(content), media_type], separators=(",", ":")).encode()
        ).hexdigest()
        row = await self.reserve(
            subject, tenant_id, thread_id, filename, media_type, key, request_hash, digest, len(content)
        )
        if row.expires_at <= timestamp() or row.status == "deleted":
            self.reader.ready(row)
        if (
            row.status == "storing"
            or row.status == "failed"
            and row.error_code == "ATTACHMENT_STORAGE_FAILED"
        ):
            try:
                await self.reader.storage.put(row, content)
            except OSError as error:
                await self.storage_failed(subject, tenant_id, thread_id, row.id)
                raise ServiceUnavailableException(
                    "Private storage could not retain this original; retry the same upload key",
                    code="ATTACHMENT_STORAGE_FAILED",
                ) from error
            row = await self.stored(subject, tenant_id, thread_id, row.id)
        return await self.view(row)

    @transactional
    async def reserve(
        self, subject, tenant_id, thread_id, filename, media_type, key, request_hash, digest, size
    ):
        await self.reader.authority.thread(subject, tenant_id, thread_id, active=True)
        await self.reader.authority.threads.find_by_id(thread_id, lock=LockMode.PESSIMISTIC_WRITE)
        async with self.reader.data.scope(subject, tenant_id, thread_id):
            existing = await self.reader.records.find_all(
                tenant_id=tenant_id, subject=subject, thread_id=thread_id, request_key=key
            )
            if existing:
                if existing[0].request_hash != request_hash:
                    raise ConflictException(
                        "This upload key belongs to different bytes or metadata", code="IDEMPOTENCY_CONFLICT"
                    )
                return existing[0]
            count, used = await self.reader.records.quota(tenant_id, subject, thread_id)
            settings = self.reader.settings
            if count >= settings.max_thread_files or used + size > settings.max_thread_bytes:
                raise ConflictException(
                    "Remove an existing file or use a new conversation", code="ATTACHMENT_QUOTA_EXCEEDED"
                )
            context = SecurityContextHolder.get_context()
            row = await self.reader.records.save(
                ChatAttachment(
                    id=str(uuid4()),
                    tenant_id=tenant_id,
                    subject=subject,
                    thread_id=thread_id,
                    request_key=key,
                    request_hash=request_hash,
                    filename=filename,
                    declared_media_type=media_type,
                    size_bytes=size,
                    sha256=digest,
                    expires_at=timestamp() + timedelta(seconds=settings.ttl_seconds),
                    access_token_id=context.attributes.get("koinon_token_id") if context else None,
                )
            )
            expiry = await self.reader.jobs.submit(
                tenant_id,
                thread_id,
                "chat.attachment.expire",
                self.payload(row),
                "attachment-expiry-" + row.id,
            )
            expiry.available_at = row.expires_at
            await self.reader.jobs.repository.save(expiry)
            row.expiry_job_id = expiry.id
            return await self.reader.records.save(row)

    @staticmethod
    def payload(row):
        return {
            "attachment_id": row.id,
            "subject": row.subject,
            "thread_id": row.thread_id,
            "sha256": row.sha256,
        }

    @transactional
    async def storage_failed(self, subject, tenant_id, thread_id, attachment_id):
        row = await self.row(subject, tenant_id, thread_id, attachment_id, lock=True)
        if row.status != "storing":
            return
        async with self.reader.data.scope(subject, tenant_id, thread_id):
            row.status, row.error_code = "failed", "ATTACHMENT_STORAGE_FAILED"
            row.error = "The original was not stored; retry the same upload key with identical bytes"
            row.revision += 1
            row.updated_at = timestamp()
            await self.reader.records.save(row)

    @transactional
    async def stored(self, subject, tenant_id, thread_id, attachment_id):
        row = await self.row(subject, tenant_id, thread_id, attachment_id, active=True, lock=True)
        if row.job_id and row.status in {"queued", "extracting", "ready", "failed"}:
            return row
        if row.status != "storing" and not (
            row.status == "failed" and row.error_code == "ATTACHMENT_STORAGE_FAILED"
        ):
            if row.status == "deleted":
                await self.reader.storage.purge(row)
            raise ConflictException(
                "The upload no longer owns this reservation", code="ATTACHMENT_STATE_CONFLICT"
            )
        async with self.reader.data.scope(subject, tenant_id, thread_id):
            job = await self.reader.jobs.submit(
                tenant_id,
                thread_id,
                "chat.attachment.extract",
                self.payload(row),
                "attachment-extract-" + row.id,
            )
            row.job_id, row.status = job.id, "queued"
            row.error_code, row.error = None, None
            row.revision += 1
            row.updated_at = timestamp()
            return await self.reader.records.save(row)

    @transactional
    async def change(
        self, subject, tenant_id, thread_id, attachment_id, expected_revision, *, action, key=""
    ):
        row = await self.row(subject, tenant_id, thread_id, attachment_id, active=action != "delete")
        job = await self.reader.jobs._locked(tenant_id, row.job_id) if row.job_id else None
        row = await self.row(
            subject, tenant_id, thread_id, attachment_id, active=action != "delete", lock=True
        )
        if action == "retry":
            retry_key = self.request_key(subject, thread_id, key)
            previous = await self.reader.jobs.repository.find_all(
                tenant_id=tenant_id, idempotency_key=retry_key
            )
            if previous:
                original = previous[0]
                if (
                    original.id != row.job_id
                    or original.payload.get("attachment_id") != row.id
                    or original.payload.get("retry_revision") != expected_revision
                ):
                    raise ConflictException(
                        "This retry key belongs to another request", code="IDEMPOTENCY_CONFLICT"
                    )
                return await self.view(row)
        if type(expected_revision) is not int or row.revision != expected_revision:
            raise ConflictException("Reload the attachment revision", code="ATTACHMENT_REVISION_CONFLICT")
        async with self.reader.data.scope(subject, tenant_id, thread_id):
            if action in {"delete", "cancel"}:
                if action == "cancel" and row.status not in {"storing", "queued", "extracting"}:
                    raise ConflictException(
                        "This extraction cannot be cancelled", code="ATTACHMENT_STATE_CONFLICT"
                    )
                if job is not None and job.status not in {"failed", "succeeded", "cancelled"}:
                    await self.reader.jobs.cancel(tenant_id, job.id)
                row.status = "deleted" if action == "delete" else "cancelled"
                if action == "delete":
                    await self.reader.jobs.submit(
                        tenant_id,
                        thread_id,
                        "chat.attachment.purge",
                        self.payload(row),
                        "attachment-purge-" + row.id + "-" + str(row.revision),
                    )
            elif action == "retry":
                if row.status not in {"failed", "cancelled"} or row.expires_at <= timestamp():
                    raise ConflictException(
                        "Retry a nonexpired failed or cancelled extraction", code="ATTACHMENT_STATE_CONFLICT"
                    )
                if row.error_code == "ATTACHMENT_STORAGE_FAILED":
                    raise ConflictException(
                        "Retry the original upload with its existing key and identical bytes",
                        code="ATTACHMENT_ORIGINAL_UNAVAILABLE",
                    )
                job = await self.reader.jobs.submit(
                    tenant_id,
                    thread_id,
                    "chat.attachment.extract",
                    {**self.payload(row), "retry_revision": row.revision},
                    self.request_key(subject, thread_id, key),
                )
                row.job_id, row.status = job.id, "queued"
                context = SecurityContextHolder.get_context()
                row.access_token_id = context.attributes.get("koinon_token_id") if context else None
                row.error_code, row.error = None, None
            else:
                raise ValueError("Unsupported private attachment transition")
            row.revision += 1
            row.updated_at = timestamp()
            await self.reader.records.save(row)
        return await self.view(row)
