# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import asyncio
from hashlib import sha256

from pyfly.container import rest_controller
from pyfly.kernel import PayloadTooLargeException
from pyfly.web import (
    Body,
    PathVar,
    QueryParam,
    Valid,
    get_mapping,
    post_mapping,
    put_mapping,
    request_mapping,
)
from starlette.requests import Request

from koinon.knowledge.bulk.dtos import (
    BulkAction,
    FileBatchCapabilities,
    FileBatchCreate,
    FileBatchPage,
    FileBatchView,
    FileItemPage,
    StagedFileReceipt,
)
from koinon.knowledge.bulk.service import FileBatches, key_digest
from koinon.security.identity import identity_from_request


def action_key(request: Request) -> str:
    value = request.headers.get("Idempotency-Key", "")
    key_digest(value)
    return value


@rest_controller(name="knowledge.bulk.controller")
@request_mapping("/api/v1/tenants/{tenant_id}")
class FileBatchController:
    def __init__(self, files: FileBatches):
        self.files = files

    @get_mapping("/source-batch-capabilities")
    async def capabilities(
        self, tenant_id: PathVar[str], request: Request, workspace_id: QueryParam[str]
    ) -> FileBatchCapabilities:
        return await self.files.capabilities(identity_from_request(request).subject, tenant_id, workspace_id)

    @post_mapping("/sources/batches", status_code=201)
    async def create(
        self, tenant_id: PathVar[str], body: Valid[Body[FileBatchCreate]], request: Request
    ) -> FileBatchView:
        return await self.files.create(
            identity_from_request(request).subject, tenant_id, body, action_key(request)
        )

    @get_mapping("/sources/batches")
    async def list(
        self,
        tenant_id: PathVar[str],
        request: Request,
        page: QueryParam[int] = 1,
        page_size: QueryParam[int] = 25,
    ) -> FileBatchPage:
        return await self.files.list(
            identity_from_request(request).subject, tenant_id, page=page, page_size=page_size
        )

    @get_mapping("/sources/batches/{batch_id}")
    async def get(self, tenant_id: PathVar[str], batch_id: PathVar[str], request: Request) -> FileBatchView:
        return await self.files.get(identity_from_request(request).subject, tenant_id, batch_id)

    @get_mapping("/sources/batches/{batch_id}/items")
    async def items(
        self,
        tenant_id: PathVar[str],
        batch_id: PathVar[str],
        request: Request,
        page: QueryParam[int] = 1,
        page_size: QueryParam[int] = 25,
    ) -> FileItemPage:
        return await self.files.items(
            identity_from_request(request).subject, tenant_id, batch_id, page=page, page_size=page_size
        )

    @put_mapping("/sources/batches/{batch_id}/items/{item_id}/content")
    async def content(
        self, tenant_id: PathVar[str], batch_id: PathVar[str], item_id: PathVar[str], request: Request
    ) -> StagedFileReceipt:
        subject = identity_from_request(request).subject
        ticket = await self.files.reserve_stream(subject, tenant_id, batch_id, item_id, action_key(request))
        try:
            received = 0
            digest = sha256()
            buffer = bytearray() if ticket.write else None
            async with asyncio.timeout(60):
                async for part in request.stream():
                    received += len(part)
                    if received > ticket.size_bytes:
                        raise PayloadTooLargeException(
                            "Body exceeds its admitted original size", code="BULK_CONTENT_LIMIT"
                        )
                    digest.update(part)
                    if buffer is not None:
                        buffer.extend(part)
            return await self.files.finish_stream(
                subject,
                tenant_id,
                batch_id,
                item_id,
                ticket,
                bytes(buffer) if buffer is not None else None,
                received,
                digest.hexdigest(),
            )
        except BaseException:
            await self.files.abort_stream(tenant_id, ticket)
            raise

    @get_mapping("/sources/batches/{batch_id}/items/{item_id}/receipt")
    async def receipt(
        self, tenant_id: PathVar[str], batch_id: PathVar[str], item_id: PathVar[str], request: Request
    ) -> StagedFileReceipt:
        return await self.files.receipt(identity_from_request(request).subject, tenant_id, batch_id, item_id)

    @post_mapping("/sources/batches/{batch_id}/submit", status_code=202)
    async def submit(
        self, tenant_id: PathVar[str], batch_id: PathVar[str], body: Valid[Body[BulkAction]], request: Request
    ) -> FileBatchView:
        return await self.files.submit(
            identity_from_request(request).subject, tenant_id, batch_id, body, action_key(request)
        )

    @post_mapping("/sources/batches/{batch_id}/cancel")
    async def cancel(
        self, tenant_id: PathVar[str], batch_id: PathVar[str], body: Valid[Body[BulkAction]], request: Request
    ) -> FileBatchView:
        return await self.files.cancel(
            identity_from_request(request).subject, tenant_id, batch_id, body, action_key(request)
        )

    @post_mapping("/sources/batches/{batch_id}/items/{item_id}/reconcile")
    async def reconcile(
        self,
        tenant_id: PathVar[str],
        batch_id: PathVar[str],
        item_id: PathVar[str],
        body: Valid[Body[BulkAction]],
        request: Request,
    ) -> FileBatchView:
        return await self.files.reconcile(
            identity_from_request(request).subject, tenant_id, batch_id, item_id, body, action_key(request)
        )

    @post_mapping("/sources/batches/{batch_id}/items/{item_id}/original/reconcile")
    async def recover_original(
        self,
        tenant_id: PathVar[str],
        batch_id: PathVar[str],
        item_id: PathVar[str],
        body: Valid[Body[BulkAction]],
        request: Request,
    ) -> FileBatchView:
        return await self.files.recover_original(
            identity_from_request(request).subject, tenant_id, batch_id, item_id, body, action_key(request)
        )
