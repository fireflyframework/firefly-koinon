# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Private metadata and model evidence share one current owner/thread authority."""

from hashlib import sha256

from pyfly.container import service
from pyfly.data.transaction import IllegalTransactionStateError
from pyfly.data.transaction.context import is_current_transaction_read_only, is_transaction_active
from pyfly.kernel import ConflictException, GoneException, InvalidRequestException

from koinon.assistants.repositories import ChatMessageRepository, ChatRunRepository
from koinon.catalog.errors import AccessDenied
from koinon.jobs.service import JobService
from koinon.knowledge.attachments.authority import AttachmentAuthority
from koinon.knowledge.attachments.data import AttachmentData
from koinon.knowledge.attachments.entities import ChatAttachmentLink, timestamp
from koinon.knowledge.attachments.mappers import from_snapshot, history_summary, reference, snapshot
from koinon.knowledge.attachments.ports import AttachmentBudget, AttachmentContent, ChatAttachmentAccess
from koinon.knowledge.attachments.repositories import (
    AttachmentChunkRepository,
    AttachmentLinkRepository,
    AttachmentRepository,
)
from koinon.knowledge.attachments.settings import AttachmentSettings
from koinon.knowledge.attachments.storage import AttachmentStorage


@service(name="knowledge.attachments.service")
class AttachmentService(ChatAttachmentAccess):
    def __init__(
        self,
        authority: AttachmentAuthority,
        data: AttachmentData,
        records: AttachmentRepository,
        chunks: AttachmentChunkRepository,
        links: AttachmentLinkRepository,
        storage: AttachmentStorage,
        settings: AttachmentSettings,
        runs: ChatRunRepository,
        messages: ChatMessageRepository,
        jobs: JobService,
    ):
        self.authority, self.data, self.records = authority, data, records
        self.chunks, self.links, self.storage, self.settings = chunks, links, storage, settings
        self.runs, self.messages, self.jobs = runs, messages, jobs

    @staticmethod
    def ready(row):
        if row.status == "deleted":
            raise GoneException("This attachment was removed", code="ATTACHMENT_REMOVED")
        if row.expires_at <= timestamp():
            raise GoneException("This private attachment expired; upload it again", code="ATTACHMENT_EXPIRED")
        if row.status != "ready":
            raise ConflictException("Wait for successful attachment extraction", code="ATTACHMENT_NOT_READY")

    def valid_ids(self, ids):
        if (
            not isinstance(ids, (list, tuple))
            or len(ids) > self.settings.max_selected
            or any(not isinstance(value, str) or not 1 <= len(value) <= 64 for value in ids)
            or len(set(ids)) != len(ids)
        ):
            raise InvalidRequestException(
                "Select up to ten distinct private files", code="INVALID_ATTACHMENT_SELECTION"
            )

    async def _rows(self, subject, tenant_id, thread_id, ids, *, lock=False):
        self.valid_ids(ids)
        await self.authority.thread(subject, tenant_id, thread_id, active=True)
        if not ids:
            return []
        async with self.data.scope(subject, tenant_id, thread_id):
            rows = await self.records.selected(tenant_id, subject, thread_id, ids, lock=lock)
        indexed = {row.id: row for row in rows}
        if set(indexed) != set(ids) or any(
            (row.subject, row.tenant_id, row.thread_id) != (subject, tenant_id, thread_id) for row in rows
        ):
            raise AccessDenied("Private attachment selection is unavailable", code="ATTACHMENT_UNAVAILABLE")
        result = [indexed[value] for value in ids]
        for row in result:
            self.ready(row)
        return result

    async def validate_selection(self, subject, tenant_id, thread_id, ids):
        return tuple(reference(row) for row in await self._rows(subject, tenant_id, thread_id, ids))

    async def _matching(self, subject, tenant_id, thread_id, refs):
        if any(
            (ref.subject, ref.tenant_id, ref.thread_id) != (subject, tenant_id, thread_id) for ref in refs
        ):
            raise AccessDenied("Private attachment reference is unavailable", code="ATTACHMENT_UNAVAILABLE")
        rows = await self._rows(subject, tenant_id, thread_id, [ref.id for ref in refs])
        if tuple(reference(row) for row in rows) != refs:
            raise AccessDenied("Private attachment reference changed", code="ATTACHMENT_REFERENCE_CHANGED")
        return rows

    async def authorize_evidence(self, subject, tenant_id, thread_id, refs):
        await self._matching(subject, tenant_id, thread_id, refs)

    async def content_for_model(
        self, subject, tenant_id, thread_id, refs, *, question, budget: AttachmentBudget
    ):
        rows = await self._matching(subject, tenant_id, thread_id, refs)
        if (
            type(budget.max_text_chars) is not int
            or not 1 <= budget.max_text_chars <= 24000
            or (
                type(budget.max_binary_bytes) is not int
                or not 0 <= budget.max_binary_bytes <= 16 * 1024 * 1024
            )
        ):
            raise ValueError("An explicit bounded native model context budget is required")
        result, texts, binary_bytes = [], [], 0

        async def fits(value):
            proposed = "\n\n".join([*texts, value])
            return len(proposed) <= budget.max_text_chars and await budget.fits_text(proposed)

        for row, ref in zip(rows, refs, strict=True):
            if row.kind == "image":
                mime = row.normalized_media_type or row.media_type
                if mime not in budget.allowed_media_types:
                    raise InvalidRequestException(
                        "Select a model that supports this image type; the current model cannot analyze it",
                        code="ATTACHMENT_MODEL_MODALITY_UNSUPPORTED",
                    )
                size = row.normalized_size_bytes or row.size_bytes
                if binary_bytes + size > budget.max_binary_bytes:
                    raise InvalidRequestException(
                        "Selected images exceed the native model input budget",
                        code="ATTACHMENT_CONTEXT_BUDGET_EXCEEDED",
                    )
                content = await self.storage.read(row, normalized=bool(row.normalized_sha256))
                binary_bytes += len(content)
                result.append(AttachmentContent(ref, data=content, media_type=mime, complete=True))
                continue
            header = f"Attachment {row.id}: {row.filename}\n"
            if row.text_char_count <= budget.max_text_chars:
                content = (await self.storage.read(row, normalized=True)).decode("utf-8")
                complete = header + "Complete extracted text (visual content is not analyzed):\n" + content
                if await fits(complete):
                    texts.append(complete)
                    result.append(
                        AttachmentContent(
                            ref,
                            text=complete,
                            complete=True,
                            total_chunks=row.chunk_count,
                            warnings=tuple(row.warnings),
                        )
                    )
                    continue
            if not isinstance(question, str) or len(question) > 8000:
                raise InvalidRequestException(
                    "Use a question up to 8000 characters for private file search",
                    code="ATTACHMENT_QUERY_TOO_LONG",
                )
            async with self.data.scope(subject, tenant_id, thread_id):
                chunks, _ = await self.chunks.page(
                    tenant_id, subject, thread_id, [row.id], page_size=16, q=question
                )
            excerpt = header + "Selected excerpts; the complete file has not been read:\n"
            chosen = []
            for chunk in chunks:
                if sha256(chunk.text.encode()).hexdigest() != chunk.sha256:
                    raise ConflictException(
                        "Private chunk integrity verification failed", code="ATTACHMENT_DIGEST_MISMATCH"
                    )
                candidate = (
                    excerpt + f"\n[chunk {chunk.id}; page {chunk.page or 'not paged'}]\n{chunk.text}\n"
                )
                if await fits(candidate):
                    excerpt, chosen = candidate, [*chosen, chunk.id]
            if not chosen:
                raise InvalidRequestException(
                    "No complete excerpt fits the remaining context; narrow the question or expand context",
                    code="ATTACHMENT_CONTEXT_BUDGET_EXCEEDED",
                )
            texts.append(excerpt)
            result.append(
                AttachmentContent(
                    ref,
                    text=excerpt,
                    chunk_ids=tuple(chosen),
                    total_chunks=row.chunk_count,
                    warnings=(*row.warnings, "EXCERPTS_ONLY"),
                )
            )
        await self._matching(subject, tenant_id, thread_id, refs)
        return tuple(result)

    async def pin_selection(self, subject, tenant_id, thread_id, refs, *, run_id, message_id):
        source = self.data.registry.primary
        if not is_transaction_active(source.name) or is_current_transaction_read_only():
            raise IllegalTransactionStateError(
                "Pin private files inside the existing native run admission transaction"
            )
        run = await self.runs.find_by_id(run_id)
        if run is None or (run.tenant_id, run.thread_id, run.user_message_id) != (
            tenant_id,
            thread_id,
            message_id,
        ):
            raise AccessDenied("Private attachment run is unavailable", code="ATTACHMENT_UNAVAILABLE")
        await self._matching(subject, tenant_id, thread_id, refs)
        async with self.data.scope(subject, tenant_id, thread_id, purpose="pin"):
            rows = await self.records.selected(
                tenant_id, subject, thread_id, [ref.id for ref in refs], lock=True
            )
            for row in rows:
                self.ready(row)
            if {row.id: reference(row) for row in rows} != {ref.id: ref for ref in refs}:
                raise ConflictException(
                    "Attachment changed before admission", code="ATTACHMENT_REFERENCE_CHANGED"
                )
            existing = await self.links.for_run(tenant_id, subject, thread_id, run_id)
            if existing:
                if tuple(from_snapshot(link.snapshot) for link in existing) != refs:
                    raise ConflictException(
                        "This run already pins different files", code="IDEMPOTENCY_CONFLICT"
                    )
                return
            for ordinal, ref in enumerate(refs):
                await self.links.save(
                    ChatAttachmentLink(
                        run_id=run_id,
                        message_id=message_id,
                        attachment_id=ref.id,
                        tenant_id=tenant_id,
                        subject=subject,
                        thread_id=thread_id,
                        ordinal=ordinal,
                        sha256=ref.sha256,
                        revision=ref.revision,
                        snapshot=snapshot(ref),
                    )
                )

    async def for_run(self, subject, tenant_id, thread_id, run_id):
        await self.authority.thread(subject, tenant_id, thread_id, active=True)
        run = await self.runs.find_by_id(run_id)
        if run is None or (run.tenant_id, run.thread_id) != (tenant_id, thread_id):
            raise AccessDenied("Private attachment run is unavailable", code="ATTACHMENT_UNAVAILABLE")
        # Private files can never be admitted on the portable catalog-only SQLite slice.
        if self.data.registry.primary.url.get_backend_name() != "postgresql":
            return ()
        async with self.data.scope(subject, tenant_id, thread_id):
            links = await self.links.for_run(tenant_id, subject, thread_id, run_id)
        refs = tuple(from_snapshot(link.snapshot) for link in links)
        await self.authorize_evidence(subject, tenant_id, thread_id, refs)
        return refs

    async def summaries_for_message(self, subject, tenant_id, thread_id, message_id):
        await self.authority.thread(subject, tenant_id, thread_id)
        message = await self.messages.find_by_id(message_id)
        if message is None or message.thread_id != thread_id:
            raise AccessDenied("Private message is unavailable", code="ATTACHMENT_UNAVAILABLE")
        if self.data.registry.primary.url.get_backend_name() != "postgresql":
            return ()
        async with self.data.scope(subject, tenant_id, thread_id):
            links = await self.links.for_message(tenant_id, subject, thread_id, message_id)
            rows = await self.records.selected(
                tenant_id, subject, thread_id, [link.attachment_id for link in links]
            )
        indexed = {row.id: row for row in rows}
        return tuple(
            history_summary(indexed[link.attachment_id]) for link in links if link.attachment_id in indexed
        )
