# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Project verified native authority into the SDK's legacy session-owner boundary."""

import json
from datetime import UTC, datetime
from hashlib import sha256

from mcp.server.auth.middleware.bearer_auth import AuthenticatedUser, authorization_context
from mcp.server.auth.provider import AccessToken
from pyfly.kernel import UnauthorizedException
from pyfly.mcp import McpSessionPrincipal
from pyfly.security.context import SecurityContext
from starlette.authentication import AuthCredentials

from koinon.catalog.errors import AccessDenied
from koinon.knowledge.external_reviews.service import fingerprint
from koinon.tokens.authorization import TokenRestriction


def session_principal(request, context: SecurityContext, resource: str) -> McpSessionPrincipal:
    """Bind metadata to this request's freshly verified grant, never a cached bearer."""
    user = request.scope.get("user")
    if not isinstance(user, AuthenticatedUser) or not user.access_token.expires_at:
        raise UnauthorizedException("MCP bearer required", code="MCP_AUTH_REQUIRED")
    identity = authorization_context(user)
    if (
        not identity["client_id"]
        or identity["issuer"] != context.attributes.get("iss")
        or identity["subject"] != context.attributes.get("sub")
    ):
        raise UnauthorizedException("Invalid MCP identity", code="MCP_AUTH_REQUIRED")
    owner = sha256(json.dumps(identity, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return McpSessionPrincipal(owner, resource, datetime.fromtimestamp(user.access_token.expires_at, UTC))


async def transport_identity(context: SecurityContext, raw: str, restriction: TokenRestriction | None):
    issuer, subject = context.attributes.get("iss"), context.attributes.get("sub")
    if (
        restriction is None
        or not isinstance(issuer, str)
        or not issuer
        or not isinstance(subject, str)
        or not subject
    ):
        raise UnauthorizedException("An active MCP credential is required", code="MCP_AUTH_REQUIRED")
    try:
        grant = await restriction.grant(issuer + "|" + subject)
    except AccessDenied as error:
        raise UnauthorizedException(
            "An active MCP credential is required", code="MCP_AUTH_REQUIRED"
        ) from error
    if grant is None:
        raise UnauthorizedException("An active MCP credential is required", code="MCP_AUTH_REQUIRED")
    return AuthCredentials(grant.scopes), AuthenticatedUser(
        AccessToken(
            token=raw,
            client_id=fingerprint(grant),
            subject=subject,
            claims={"iss": issuer},
            scopes=grant.scopes,
            expires_at=int(grant.expires_at.timestamp()),
        )
    )
