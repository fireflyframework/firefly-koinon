# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Native leased private parsing with short publication transactions and cancellation fences."""

import base64
import logging
from datetime import timedelta
from hashlib import sha256
from uuid import uuid4

from pyfly.container import service
from pyfly.data.relational.sqlalchemy import LockMode, transactional
from pyfly.kernel import ConflictException
from pyfly.scheduling import scheduled
from pyfly.security.context import SecurityContext
from pyfly.security.context_holder import SecurityContextHolder
from sqlalchemy import and_, delete, or_, select

from koinon.jobs.entities import Job
from koinon.knowledge.attachments.capabilities import AttachmentProcessingState
from koinon.knowledge.attachments.entities import ChatAttachmentChunk, timestamp
from koinon.knowledge.attachments.extraction import ExtractionFailure
from koinon.knowledge.attachments.lifecycle import AttachmentLifecycle
from koinon.knowledge.attachments.parser import PrivateAttachmentParser

logger = logging.getLogger(__name__)
KINDS = ("chat.attachment.extract", "chat.attachment.expire", "chat.attachment.purge")


@service(name="knowledge.attachments.worker")
class AttachmentWorker:
    def __init__(
        self,
        lifecycle: AttachmentLifecycle,
        parser: PrivateAttachmentParser,
        processing: AttachmentProcessingState,
    ):
        self.lifecycle, self.reader, self.parser = lifecycle, lifecycle.reader, parser
        self.processing = processing
        self.worker_id = "private-files-" + uuid4().hex

    @scheduled(fixed_delay=timedelta(seconds=1))
    async def tick(self):
        if not self.reader.settings.worker_enabled:
            return
        self.reader.settings.validate()
        job_id = await self.claim()
        self.processing.last_tick = timestamp()
        if job_id is None:
            return
        try:
            job = await self.reader.jobs.repository.find_by_id(job_id)
            row = await self.start(job)
            if job.kind != "chat.attachment.extract":
                await self.reader.storage.purge(row)
                await self.purged(job)
                return
            attributes = {"koinon_token_id": row.access_token_id} if row.access_token_id else {}
            with SecurityContextHolder.using(SecurityContext(user_id=row.subject, attributes=attributes)):
                await self.reader.authority.thread(row.subject, row.tenant_id, row.thread_id, active=True)
                content = await self.reader.storage.read(row)
                result = await self.parser.parse(row, content)
                normalized = (
                    base64.b64decode(result["data"], validate=True)
                    if result.get("data")
                    else result["text"].encode()
                )
                await self.reader.storage.put(row, normalized, normalized=True)
                await self.publish(job, result, normalized)
        except Exception as error:
            code = str(getattr(error, "code", None) or "ATTACHMENT_EXTRACTION_FAILED")[:64]
            logger.warning(
                "Private attachment work failed",
                extra={"job_id": job_id, "error_code": code, "error_type": type(error).__name__},
            )
            try:
                await self.failed(job_id, code, str(error) if isinstance(error, ExtractionFailure) else None)
            except Exception as failure:
                if getattr(failure, "code", None) not in {"JOB_LEASE_LOST", "ATTACHMENT_LEASE_LOST"}:
                    raise

    @transactional
    async def claim(self):
        now = timestamp()
        session = self.reader.jobs.repository._require_session()
        job = await session.scalar(
            select(Job)
            .where(
                Job.kind.in_(KINDS),
                or_(
                    and_(Job.status == "queued", Job.available_at <= now),
                    and_(Job.status == "running", Job.lease_until < now),
                ),
            )
            .order_by(Job.available_at, Job.created_at, Job.id)
            .limit(1)
            .with_for_update(skip_locked=True)
        )
        if job is None:
            return None
        if job.attempts >= job.max_attempts:
            job.status, job.error, job.lease_until = (
                "failed",
                "Private file worker retry budget exhausted",
                None,
            )
            await self.reader.jobs.repository.save(job)
            async with self.reader.data.scope(job.payload["subject"], job.tenant_id, job.resource_id):
                row = await self.reader.records.find_by_id(
                    job.payload["attachment_id"], lock=LockMode.PESSIMISTIC_WRITE
                )
                if row is not None and row.job_id == job.id and row.status in {"queued", "extracting"}:
                    row.status, row.error_code = "failed", "ATTACHMENT_WORKER_EXHAUSTED"
                    row.error = "Private extraction stopped; retry this original before its expiry"
                    row.revision += 1
                    await self.reader.records.save(row)
            return None
        job.status, job.worker_id = "running", self.worker_id
        job.lease_until = now + timedelta(seconds=self.reader.settings.extraction_timeout_seconds + 60)
        job.attempts += 1
        await self.reader.jobs.repository.save(job)
        return job.id

    async def fence(self, job):
        current = await self.reader.jobs._locked(job.tenant_id, job.id, self.worker_id)
        if current.kind not in KINDS or current.resource_id != current.payload.get("thread_id"):
            raise ConflictException("Private work has no trusted target", code="ATTACHMENT_LEASE_LOST")
        row = await self.reader.records.find_by_id(
            current.payload["attachment_id"], lock=LockMode.PESSIMISTIC_WRITE
        )
        if row is None or (row.tenant_id, row.subject, row.thread_id, row.sha256) != (
            current.tenant_id,
            current.payload["subject"],
            current.resource_id,
            current.payload["sha256"],
        ):
            raise ConflictException("Private work lost its immutable target", code="ATTACHMENT_LEASE_LOST")
        if current.kind == "chat.attachment.extract" and (
            row.job_id != current.id or row.status not in {"queued", "extracting"}
        ):
            raise ConflictException("Private extraction lost its lease", code="ATTACHMENT_LEASE_LOST")
        return current, row

    @transactional
    async def start(self, job):
        async with self.reader.data.scope(
            job.payload["subject"],
            job.tenant_id,
            job.resource_id,
            purpose="extract" if job.kind == "chat.attachment.extract" else "purge",
        ):
            _, row = await self.fence(job)
            if job.kind == "chat.attachment.extract":
                if row.expires_at <= timestamp():
                    raise ConflictException("Private file has expired", code="ATTACHMENT_EXPIRED")
                row.status = "extracting"
                row.updated_at = timestamp()
                await self.reader.records.save(row)
            elif row.status != "deleted" and row.expires_at > timestamp():
                raise ConflictException(
                    "Private file is not eligible for cleanup", code="ATTACHMENT_LEASE_LOST"
                )
            return row

    @transactional
    async def publish(self, job, result, normalized):
        await self.reader.authority.thread(
            job.payload["subject"], job.tenant_id, job.resource_id, active=True
        )
        async with self.reader.data.scope(
            job.payload["subject"], job.tenant_id, job.resource_id, purpose="extract"
        ) as session:
            _, row = await self.fence(job)
            if row.expires_at <= timestamp():
                raise ConflictException("Private file has expired", code="ATTACHMENT_EXPIRED")
            await session.execute(
                delete(ChatAttachmentChunk).where(ChatAttachmentChunk.attachment_id == row.id)
            )
            for ordinal, value in enumerate(result["chunks"]):
                if result["text"][value["char_start"] : value["char_end"]] != value["text"]:
                    raise ExtractionFailure(
                        "Parser provenance did not match normalized text", "ATTACHMENT_PROVENANCE_INVALID"
                    )
                await self.reader.chunks.save(
                    ChatAttachmentChunk(
                        id=str(uuid4()),
                        attachment_id=row.id,
                        tenant_id=row.tenant_id,
                        subject=row.subject,
                        thread_id=row.thread_id,
                        ordinal=ordinal,
                        **value,
                    )
                )
            row.kind, row.media_type = result["kind"], result["media_type"]
            row.normalized_media_type = result["normalized_media_type"]
            row.normalized_sha256, row.normalized_size_bytes = sha256(normalized).hexdigest(), len(normalized)
            row.chunk_count, row.text_char_count = len(result["chunks"]), len(result["text"])
            row.page_count, row.warnings = result.get("page_count"), result.get("warnings", [])
            row.image_width, row.image_height = result.get("image_width"), result.get("image_height")
            row.status, row.error, row.error_code = "ready", None, None
            row.revision += 1
            row.updated_at = timestamp()
            await self.reader.records.save(row)
            await self.reader.jobs.complete(
                job.tenant_id,
                job.id,
                self.worker_id,
                {"attachment_id": row.id, "status": "ready", "chunk_count": row.chunk_count},
            )

    @transactional
    async def purged(self, job):
        async with self.reader.data.scope(
            job.payload["subject"], job.tenant_id, job.resource_id, purpose="purge"
        ) as session:
            _, row = await self.fence(job)
            if row.status != "deleted" and row.expires_at > timestamp():
                raise ConflictException("Private cleanup lost its authority", code="ATTACHMENT_LEASE_LOST")
            await session.execute(
                delete(ChatAttachmentChunk).where(ChatAttachmentChunk.attachment_id == row.id)
            )
            row.status = "deleted" if row.status == "deleted" else "expired"
            row.revision += 1
            row.updated_at = timestamp()
            await self.reader.records.save(row)
            await self.reader.jobs.complete(
                job.tenant_id, job.id, self.worker_id, {"attachment_id": row.id, "status": row.status}
            )

    @transactional
    async def failed(self, job_id, code, message):
        job = await self.reader.jobs.repository.find_by_id(job_id)
        async with self.reader.data.scope(job.payload["subject"], job.tenant_id, job.resource_id):
            job, row = await self.fence(job)
            if job.kind == "chat.attachment.extract":
                row.status, row.error_code = "failed", code
                row.error = (
                    message or "Extraction failed; verify current access and format prerequisites, then retry"
                )[:500]
                row.revision += 1
                row.updated_at = timestamp()
                await self.reader.records.save(row)
                job.status, job.error, job.lease_until = "failed", code, None
                await self.reader.jobs.repository.save(job)
            else:
                await self.reader.jobs.fail(job.tenant_id, job.id, self.worker_id, code)
