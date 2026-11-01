# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from starlette.requests import Request

from koinon.catalog.errors import AccessDenied
from koinon.security.identity import RequestIdentity, identity_from_request


def require_personal_permission(request: Request, permission: str) -> RequestIdentity:
    identity = identity_from_request(request)
    context = getattr(request.state, "security_context", None)
    attributes = getattr(context, "attributes", {})
    token = attributes.get("koinon_token")
    if "koinon_token" in attributes:
        scopes = token.get("scopes") if isinstance(token, dict) else None
        if not isinstance(scopes, list) or any(not isinstance(scope, str) for scope in scopes):
            raise AccessDenied("Personal token has no profile permission", code="ACCESS_DENIED")
        granted = set(scopes)
        if "profile:write" in granted:
            granted.add("profile:read")
        if "notifications:write" in granted:
            granted.add("notifications:read")
        if permission not in granted:
            raise AccessDenied("Personal token has no profile permission", code="ACCESS_DENIED")
    return identity


def require_directory_identity(request: Request, tenant_id: str, workspace_id: str | None) -> RequestIdentity:
    identity = require_personal_permission(request, "members:write")
    token = getattr(request.state.security_context, "attributes", {}).get("koinon_token")
    if token is not None:
        workspaces = token.get("workspace_ids")
        if workspaces is not None and (
            not isinstance(workspaces, list) or any(not isinstance(item, str) for item in workspaces)
        ):
            raise AccessDenied("Directory is outside the personal token scope", code="ACCESS_DENIED")
        if token.get("tenant_id") != tenant_id or (workspaces is not None and workspace_id not in workspaces):
            raise AccessDenied("Directory is outside the personal token scope", code="ACCESS_DENIED")
    return identity
