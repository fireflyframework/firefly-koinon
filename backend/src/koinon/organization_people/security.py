# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from koinon.catalog.errors import AccessDenied
from koinon.profiles.security import require_personal_permission
from koinon.security.identity import identity_from_request


def organization_identity(request, tenant_id, workspace_id=None, *, write=False):
    identity = identity_from_request(request)
    attributes = getattr(request.state.security_context, "attributes", {})
    if "koinon_token" not in attributes:
        return identity
    token = attributes["koinon_token"]
    permissions = {"members:write"} if write else {"members:write", "catalog:read"}
    if not isinstance(token, dict):
        raise AccessDenied("Directory is outside the token scope", code="ACCESS_DENIED")
    scopes = token.get("scopes")
    workspaces = token.get("workspace_ids")
    if (
        not isinstance(scopes, list)
        or any(not isinstance(scope, str) for scope in scopes)
        or not permissions.intersection(scopes)
        or token.get("tenant_id") != tenant_id
        or token.get("asset_ids") is not None
        or workspaces is not None
        and (
            not isinstance(workspaces, list)
            or any(not isinstance(value, str) for value in workspaces)
            or workspace_id not in workspaces
        )
    ):
        raise AccessDenied("Directory is outside the token scope", code="ACCESS_DENIED")
    return identity


def own_identity(request):
    return require_personal_permission(request, "profile:read")
