# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Consume an exact server-side operation grant without inventing legacy tokens."""
from collections.abc import Mapping

from starlette.requests import Request

from flycanon.core.services.auth.agent_token_service import AgentScopeDenied
from flycanon.web.conventions.context import TenantContext, current_tenant_context


def verified_agent_context(request: Request, *, scope: str) -> TenantContext | None:
    grant = getattr(getattr(request, "state", None), "verified_legacy_agent_grant", None)
    if grant is None:
        return None
    context = getattr(request.state, "legacy_tenant_context", None)
    identity = getattr(request.state, "identity", None)
    scopes = grant.get("scopes") if isinstance(grant, Mapping) else None
    if (
        not isinstance(grant, Mapping)
        or not isinstance(context, TenantContext)
        or current_tenant_context() != context
        or grant.get("domain") != "canon"
        or grant.get("method") != request.method
        or grant.get("path") != request.url.path.removeprefix("/bff")
        or grant.get("tenant_id") != context.tenant_id
        or grant.get("workspace_id") != context.workspace_id
        or not context.actor
        or grant.get("subject") != context.actor
        or getattr(identity, "subject", None) != context.actor
        or not isinstance(scopes, tuple)
        or any(not isinstance(value, str) or "*" in value for value in scopes)
        or scope not in scopes
    ):
        raise AgentScopeDenied("The native operation grant does not match this request and trusted scope")
    return context
