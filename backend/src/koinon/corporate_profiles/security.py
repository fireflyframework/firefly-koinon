# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from koinon.catalog.errors import AccessDenied
from koinon.profiles.security import require_personal_permission


def personal_identity(request, tenant_id, workspace_id=None, *, write=False):
    identity = require_personal_permission(request, "profile:write" if write else "profile:read")
    attributes = getattr(request.state.security_context, "attributes", {})
    if "koinon_token" in attributes:
        token = attributes["koinon_token"]
        workspaces = token.get("workspace_ids")
        if (
            token.get("tenant_id") != tenant_id
            or token.get("asset_ids") is not None
            or workspaces is not None
            and (
                not isinstance(workspaces, list)
                or any(not isinstance(item, str) for item in workspaces)
                or workspace_id not in workspaces
            )
        ):
            raise AccessDenied("Profile is outside the current organization scope", code="ACCESS_DENIED")
    return identity
