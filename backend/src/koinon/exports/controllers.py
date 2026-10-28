# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from hashlib import sha256

from pyfly.container import rest_controller
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
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from koinon.evidence.http import private_json
from koinon.exports.dtos import ExportCreate, ExportReviewRequest
from koinon.exports.service import KnowledgeExports
from koinon.security.identity import identity_from_request


@rest_controller
@request_mapping("/api/v1/tenants/{tenant_id}/exports")
class ExportController:
    def __init__(self, exports: KnowledgeExports):
        self.exports = exports

    @post_mapping("/reviews", status_code=201)
    async def review(
        self, tenant_id: PathVar[str], body: Valid[Body[ExportReviewRequest]], request: Request
    ) -> JSONResponse:
        return private_json(
            await self.exports.preview(identity_from_request(request).subject, tenant_id, body.root),
            status=201,
        )

    @post_mapping("", status_code=201)
    async def create(
        self, tenant_id: PathVar[str], body: Valid[Body[ExportCreate]], request: Request
    ) -> JSONResponse:
        return private_json(
            await self.exports.create(identity_from_request(request).subject, tenant_id, body), status=201
        )

    @get_mapping("")
    async def list(
        self,
        tenant_id: PathVar[str],
        request: Request,
        q: QueryParam[str] = "",
        status: QueryParam[str] = "all",
        page: QueryParam[int] = 1,
        page_size: QueryParam[int] = 25,
    ) -> JSONResponse:
        return private_json(
            await self.exports.page(
                identity_from_request(request).subject,
                tenant_id,
                q=q,
                status=status,
                page=page,
                page_size=page_size,
            )
        )

    @get_mapping("/{export_id}")
    async def get(self, tenant_id: PathVar[str], export_id: PathVar[str], request: Request) -> JSONResponse:
        return private_json(
            await self.exports.get(identity_from_request(request).subject, tenant_id, export_id)
        )

    @get_mapping("/{export_id}/download")
    async def download(self, tenant_id: PathVar[str], export_id: PathVar[str], request: Request) -> Response:
        rendered = await self.exports.download(identity_from_request(request).subject, tenant_id, export_id)
        return Response(
            rendered.content,
            media_type=rendered.content_type,
            headers={
                **dict(rendered.headers),
                "Content-Disposition": f'attachment; filename="{rendered.filename}"',
                "Cache-Control": "no-store",
                "X-Content-Type-Options": "nosniff",
                "ETag": '"' + sha256(rendered.content).hexdigest() + '"',
            },
        )

    @delete_mapping("/{export_id}", status_code=204)
    async def cancel(self, tenant_id: PathVar[str], export_id: PathVar[str], request: Request) -> None:
        await self.exports.cancel(identity_from_request(request).subject, tenant_id, export_id)
