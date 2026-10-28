# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from pyfly.container import rest_controller
from pyfly.kernel import InvalidRequestException, PayloadTooLargeException
from pyfly.web import (
    Body,
    PathVar,
    QueryParam,
    Valid,
    delete_mapping,
    get_mapping,
    patch_mapping,
    post_mapping,
    request_mapping,
)
from starlette.requests import Request
from starlette.responses import Response

from koinon.profiles.dtos import ProfileInput
from koinon.profiles.images import MAX_AVATAR_BYTES
from koinon.profiles.security import require_directory_identity, require_personal_permission
from koinon.profiles.service import ProfileService


def browser_urls(value: dict, request: Request) -> dict:
    if request.url.path.startswith("/bff/"):
        for row in value.get("items", [value]):
            if isinstance(row.get("avatar_url"), str) and row["avatar_url"].startswith("/api/v1/"):
                row["avatar_url"] = "/bff" + row["avatar_url"]
    return value


def image_response(content: bytes, request: Request) -> Response:
    from hashlib import sha256

    etag = '"' + sha256(content).hexdigest() + '"'
    headers = {"Cache-Control": "private, no-cache", "ETag": etag, "X-Content-Type-Options": "nosniff"}
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304, headers=headers)
    return Response(content, media_type="image/jpeg", headers=headers)


@rest_controller(name="profiles.controller")
@request_mapping("/api/v1")
class ProfileController:
    def __init__(self, profiles: ProfileService):
        self.profiles = profiles

    @get_mapping("/profile")
    async def get(self, request: Request) -> dict:
        identity = require_personal_permission(request, "profile:read")
        defaults = request.state.security_context.attributes
        return browser_urls(await self.profiles.get(identity.subject, defaults), request)

    @patch_mapping("/profile")
    async def update(self, body: Valid[Body[ProfileInput]], request: Request) -> dict:
        identity = require_personal_permission(request, "profile:write")
        values = body.model_dump(exclude_unset=True)
        await self.profiles.get(identity.subject, request.state.security_context.attributes)
        return browser_urls(await self.profiles.update(identity.subject, values), request)

    @get_mapping("/profile/avatar")
    async def avatar(self, request: Request) -> Response:
        identity = require_personal_permission(request, "profile:read")
        return image_response(await self.profiles.avatar(identity.subject), request)

    @post_mapping("/profile/avatar")
    async def set_avatar(self, request: Request) -> dict:
        identity = require_personal_permission(request, "profile:write")
        if request.headers.get("content-type", "").split(";")[0].strip() not in {
            "image/jpeg",
            "image/png",
            "image/webp",
        }:
            raise InvalidRequestException("Upload raw PNG, JPEG or WebP image bytes", code="INVALID_AVATAR")
        content = bytearray()
        async for chunk in request.stream():
            if len(content) + len(chunk) > MAX_AVATAR_BYTES:
                raise PayloadTooLargeException("Avatar must contain at most 2 MiB", code="AVATAR_TOO_LARGE")
            content.extend(chunk)
        await self.profiles.get(identity.subject, request.state.security_context.attributes)
        return browser_urls(await self.profiles.set_avatar(identity.subject, bytes(content)), request)

    @delete_mapping("/profile/avatar")
    async def delete_avatar(self, request: Request) -> dict:
        identity = require_personal_permission(request, "profile:write")
        return browser_urls(await self.profiles.delete_avatar(identity.subject), request)

    @get_mapping("/tenants/{tenant_id}/people")
    async def people(
        self,
        tenant_id: PathVar[str],
        request: Request,
        workspace_id: QueryParam[str | None] = None,
        q: QueryParam[str] = "",
        limit: QueryParam[int] = 20,
        after: QueryParam[str] = "",
    ) -> dict:
        identity = require_directory_identity(request, tenant_id, workspace_id)
        return browser_urls(
            await self.profiles.people(
                identity.subject, tenant_id, workspace_id=workspace_id, q=q, limit=limit, after=after
            ),
            request,
        )

    @get_mapping("/tenants/{tenant_id}/people/{profile_id}/avatar")
    async def person_avatar(
        self,
        tenant_id: PathVar[str],
        profile_id: PathVar[str],
        request: Request,
        workspace_id: QueryParam[str | None] = None,
    ) -> Response:
        identity = require_directory_identity(request, tenant_id, workspace_id)
        content = await self.profiles.directory_avatar(
            identity.subject, tenant_id, profile_id, workspace_id=workspace_id
        )
        return image_response(content, request)
