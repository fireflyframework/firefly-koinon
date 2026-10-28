# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from urllib.parse import quote

from pyfly.container import rest_controller
from pyfly.kernel import InvalidRequestException, PayloadTooLargeException
from pyfly.web import (
    Body,
    PathVar,
    QueryParam,
    Valid,
    delete_mapping,
    get_mapping,
    post_mapping,
    request_mapping,
)
from starlette.datastructures import UploadFile
from starlette.requests import Request
from starlette.responses import Response

from koinon.knowledge.attachments.capabilities import AttachmentCapabilityService
from koinon.knowledge.attachments.dtos import (
    AttachmentCapabilities,
    AttachmentPage,
    AttachmentPromotionInput,
    AttachmentPromotionView,
    AttachmentRevision,
    AttachmentView,
    PrivateChunkPage,
)
from koinon.knowledge.attachments.lifecycle import AttachmentLifecycle
from koinon.knowledge.attachments.promotions import AttachmentPromotions
from koinon.security.identity import identity_from_request


@rest_controller(name="knowledge.attachments.controller")
@request_mapping("/api/v1/tenants/{tenant_id}/chat/threads/{thread_id}/attachments")
class ChatAttachmentsController:
    def __init__(
        self,
        lifecycle: AttachmentLifecycle,
        capabilities: AttachmentCapabilityService,
        promotions: AttachmentPromotions,
    ):
        self.lifecycle, self.capabilities_service = lifecycle, capabilities
        self.promotions = promotions

    @get_mapping("/capabilities")
    async def capabilities(
        self, tenant_id: PathVar[str], thread_id: PathVar[str], request: Request
    ) -> AttachmentCapabilities:
        return await self.capabilities_service.for_thread(
            identity_from_request(request).subject, tenant_id, thread_id
        )

    @post_mapping("", status_code=202)
    async def upload(
        self, tenant_id: PathVar[str], thread_id: PathVar[str], request: Request
    ) -> AttachmentView:
        subject = identity_from_request(request).subject
        await self.lifecycle.reader.authority.thread(subject, tenant_id, thread_id, active=True)
        limit = self.lifecycle.reader.settings.max_file_bytes
        received = 0

        async def bounded_receive():
            nonlocal received
            message = await request.receive()
            received += len(message.get("body", b""))
            if received > limit + 65536:
                raise PayloadTooLargeException(
                    "Multipart request exceeds the private file limit", code="ATTACHMENT_TOO_LARGE"
                )
            return message

        bounded = Request(request.scope, bounded_receive)
        async with bounded.form(max_files=1, max_fields=0, max_part_size=4096) as form:
            file = form.get("file")
            if not isinstance(file, UploadFile) or set(form) != {"file"}:
                raise InvalidRequestException("Supply one private file", code="INVALID_ATTACHMENT_UPLOAD")
            content = bytearray()
            while chunk := await file.read(65536):
                content.extend(chunk)
                if len(content) > limit:
                    raise PayloadTooLargeException(
                        "The file exceeds the private file limit", code="ATTACHMENT_TOO_LARGE"
                    )
            return await self.lifecycle.upload(
                subject,
                tenant_id,
                thread_id,
                filename=file.filename,
                content=bytes(content),
                media_type=file.content_type,
                idempotency_key=request.headers.get("idempotency-key"),
            )

    @get_mapping("")
    async def list_files(
        self,
        tenant_id: PathVar[str],
        thread_id: PathVar[str],
        request: Request,
        page: QueryParam[int] = 1,
        page_size: QueryParam[int] = 25,
        q: QueryParam[str] = "",
        status: QueryParam[str | None] = None,
        kind: QueryParam[str | None] = None,
    ) -> AttachmentPage:
        return AttachmentPage.model_validate(
            await self.lifecycle.list(
                identity_from_request(request).subject,
                tenant_id,
                thread_id,
                page=page,
                page_size=page_size,
                q=q,
                status=status,
                kind=kind,
            )
        )

    @get_mapping("/{attachment_id}")
    async def get(
        self, tenant_id: PathVar[str], thread_id: PathVar[str], attachment_id: PathVar[str], request: Request
    ) -> AttachmentView:
        return await self.lifecycle.get(
            identity_from_request(request).subject, tenant_id, thread_id, attachment_id
        )

    @get_mapping("/{attachment_id}/original")
    async def original(
        self, tenant_id: PathVar[str], thread_id: PathVar[str], attachment_id: PathVar[str], request: Request
    ) -> Response:
        row, content = await self.lifecycle.original(
            identity_from_request(request).subject, tenant_id, thread_id, attachment_id
        )
        return Response(
            content,
            media_type="application/octet-stream",
            headers={
                "Content-Disposition": "attachment; filename*=UTF-8''" + quote(row.filename, safe=""),
                "X-Content-Type-Options": "nosniff",
                "Cache-Control": "private, no-store",
                "ETag": '"' + row.sha256 + '"',
            },
        )

    @get_mapping("/{attachment_id}/chunks")
    async def chunks(
        self,
        tenant_id: PathVar[str],
        thread_id: PathVar[str],
        attachment_id: PathVar[str],
        request: Request,
        page: QueryParam[int] = 1,
        page_size: QueryParam[int] = 25,
        q: QueryParam[str] = "",
    ) -> PrivateChunkPage:
        return PrivateChunkPage.model_validate(
            await self.lifecycle.chunks(
                identity_from_request(request).subject,
                tenant_id,
                thread_id,
                attachment_id,
                page=page,
                page_size=page_size,
                q=q,
            )
        )

    @post_mapping("/{attachment_id}/cancel")
    async def cancel(
        self,
        tenant_id: PathVar[str],
        thread_id: PathVar[str],
        attachment_id: PathVar[str],
        body: Valid[Body[AttachmentRevision]],
        request: Request,
    ) -> AttachmentView:
        return await self.lifecycle.change(
            identity_from_request(request).subject,
            tenant_id,
            thread_id,
            attachment_id,
            body.expected_revision,
            action="cancel",
        )

    @post_mapping("/{attachment_id}/retry", status_code=202)
    async def retry(
        self,
        tenant_id: PathVar[str],
        thread_id: PathVar[str],
        attachment_id: PathVar[str],
        body: Valid[Body[AttachmentRevision]],
        request: Request,
    ) -> AttachmentView:
        return await self.lifecycle.change(
            identity_from_request(request).subject,
            tenant_id,
            thread_id,
            attachment_id,
            body.expected_revision,
            action="retry",
            key=request.headers.get("idempotency-key"),
        )

    @delete_mapping("/{attachment_id}", status_code=204)
    async def delete(
        self,
        tenant_id: PathVar[str],
        thread_id: PathVar[str],
        attachment_id: PathVar[str],
        expected_revision: QueryParam[int],
        request: Request,
    ) -> Response:
        await self.lifecycle.change(
            identity_from_request(request).subject,
            tenant_id,
            thread_id,
            attachment_id,
            expected_revision,
            action="delete",
        )
        return Response(status_code=204)

    @post_mapping("/{attachment_id}/knowledge", status_code=201)
    async def knowledge(
        self,
        tenant_id: PathVar[str],
        thread_id: PathVar[str],
        attachment_id: PathVar[str],
        body: Valid[Body[AttachmentPromotionInput]],
        request: Request,
    ) -> AttachmentPromotionView:
        return await self.promotions.promote(
            identity_from_request(request).subject,
            tenant_id,
            thread_id,
            attachment_id,
            body.root.model_dump(),
            request.headers.get("idempotency-key"),
        )
