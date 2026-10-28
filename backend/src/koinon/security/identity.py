# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Verified principal identity and uncached catalog authorization."""

from dataclasses import dataclass
from typing import Literal, Protocol, runtime_checkable

from pyfly.kernel.exceptions import UnauthorizedException
from pyfly.security.context import SecurityContext
from starlette.requests import Request


@dataclass(frozen=True, slots=True)
class RequestIdentity:
    subject: str
    authenticated: bool
    authentication_method: Literal["bearer", "oidc-session"]


def identity_from_request(request: Request) -> RequestIdentity:
    context = getattr(request.state, "security_context", None)
    if not isinstance(context, SecurityContext) or not context.is_authenticated:
        raise UnauthorizedException("Authentication required", code="AUTH_REQUIRED")
    issuer = context.attributes.get("iss")
    subject = context.attributes.get("sub")
    if not issuer or not subject or context.user_id != subject:
        raise UnauthorizedException("Verified issuer and subject required", code="INVALID_IDENTITY")
    method = "bearer" if request.url.path.startswith("/api/") else "oidc-session"
    return RequestIdentity(f"{issuer}|{subject}", True, method)


@runtime_checkable
class MembershipAuthorizer(Protocol):
    async def authorize(
        self, subject: str, tenant_id: str, permission: str, workspace_id: str | None = None
    ) -> None: ...


class RequestAuthorization:
    def __init__(self, authorizer: MembershipAuthorizer):
        self.authorizer = authorizer

    async def require_permission(
        self, request: Request, tenant_id: str, permission: str, workspace_id: str | None = None
    ) -> RequestIdentity:
        identity = identity_from_request(request)
        await self.authorizer.authorize(identity.subject, tenant_id, permission, workspace_id)
        return identity
