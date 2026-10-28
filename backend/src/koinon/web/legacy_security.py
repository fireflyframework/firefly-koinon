# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Verify durable membership before retained header-based endpoint contracts."""

import importlib
import re
from collections.abc import Awaitable, Callable
from contextlib import contextmanager
from dataclasses import dataclass
from json import JSONDecodeError
from types import MappingProxyType

from pyfly.container import component
from pyfly.container.ordering import HIGHEST_PRECEDENCE
from pyfly.kernel.exceptions import InvalidRequestException, PayloadTooLargeException, UnauthorizedException
from pyfly.web.adapters.starlette.errors import global_exception_handler
from pyfly.web.filters import OncePerRequestFilter
from pyfly.web.ports.filter import CallNext
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import compile_path

from koinon.catalog.errors import AccessDenied, InvalidHierarchy
from koinon.catalog.service import CatalogService
from koinon.security.identity import RequestIdentity, identity_from_request
from koinon.web.domain_errors import domain_problem

Verifier = Callable[[Request, RequestIdentity, str, str, dict], Awaitable[None]]


@dataclass(frozen=True)
class LegacyOperationPolicy:
    method: str
    pattern: re.Pattern[str]
    verifier: Verifier
    permission: str
    agent_scopes: tuple[str, ...] = ()


class LegacyOperationPolicies:
    def __init__(self):
        self.operations: list[LegacyOperationPolicy] = []

    def register(
        self,
        domain: str,
        method: str,
        path: str,
        verifier: Verifier,
        permission: str = "catalog:read",
        agent_scopes: tuple[str, ...] = (),
    ) -> None:
        if domain not in ("canon", "structured") or not path.startswith("/") or path.startswith("//"):
            raise ValueError("Use a known domain and explicit route template")
        if any(not isinstance(scope, str) or not scope or "*" in scope for scope in agent_scopes):
            raise ValueError("Declare exact operation scopes without wildcards")
        pattern, _, _ = compile_path(f"/api/v1/{domain}{path}")
        self.operations.append(
            LegacyOperationPolicy(method.upper(), pattern, verifier, permission, tuple(agent_scopes))
        )

    def resolve(self, method: str, path: str):
        for operation in self.operations:
            matched = operation.pattern.fullmatch(path)
            if operation.method == method and matched is not None:
                return operation, matched.groupdict()
        return None


def trusted_legacy_context(request: Request):
    value = getattr(request.state, "legacy_tenant_context", None)
    if value is None:
        raise UnauthorizedException("Verified legacy scope required", code="CONTEXT_REQUIRED")
    return value


@contextmanager
def bind_legacy_context(request: Request, path: str, identity: RequestIdentity, tenant: str, workspace: str):
    package = "flycanon" if path == "/api/v1/canon" or path.startswith("/api/v1/canon/") else "flyquery"
    module = importlib.import_module(package + ".web.conventions.context")
    value = module.TenantContext(
        tenant_id=tenant,
        workspace_id=workspace,
        actor=identity.subject,
        correlation_id=request.headers.get("x-correlation-id") or request.state.transaction_id,
    )
    token = module.set_tenant_context(value)
    request.state.legacy_tenant_context = value
    try:
        yield
    finally:
        token.var.reset(token.token)


@component
class LegacyMembershipFilter(OncePerRequestFilter):
    __pyfly_order__ = HIGHEST_PRECEDENCE + 300
    url_patterns = [
        "/api/v1/canon",
        "/api/v1/structured",
        "/bff/api/v1/canon",
        "/bff/api/v1/structured",
        "/api/v1/canon/*",
        "/api/v1/structured/*",
        "/bff/api/v1/canon/*",
        "/bff/api/v1/structured/*",
    ]

    def __init__(self, catalog: CatalogService, policies: LegacyOperationPolicies):
        self.catalog = catalog
        self.policies = policies

    async def do_filter(self, request: Request, call_next: CallNext):
        try:
            identity = identity_from_request(request)
            tenant = request.headers.get("x-tenant-id")
            workspace_id = request.headers.get("x-workspace-id")
            if not tenant or not workspace_id:
                raise InvalidHierarchy("Select a tenant and workspace", code="CONTEXT_REQUIRED")
            workspace = await self.catalog.get(identity.subject, tenant, workspace_id)
            if workspace.kind != "workspace":
                raise InvalidHierarchy("Select a workspace", code="INVALID_WORKSPACE")
            path = request.url.path.removeprefix("/bff")
            if "/agent-tokens" in path:
                permission = "members:write"
            elif "/audit" in path:
                permission = "audit:read"
            elif request.method in ("GET", "HEAD", "OPTIONS"):
                permission = "catalog:read"
            elif path.startswith("/api/v1/structured/") and any(
                segment in path for segment in ("/query", "/ask", "/conversations")
            ):
                permission = "query:execute"
            elif "/search" in path or "/answer" in path:
                permission = "knowledge:search"
            elif "/ingest" in path or "/sources" in path or "/files" in path:
                permission = "ingest:write"
            else:
                permission = "catalog:write"
            await self.catalog.authorize(identity.subject, tenant, permission, workspace_id)
            resolved = self.policies.resolve(request.method, path)
            if resolved is None:
                return JSONResponse(
                    {
                        "status": 503,
                        "code": "LEGACY_OPERATION_UNQUALIFIED",
                        "detail": "This compatibility operation requires resource-scope qualification",
                    },
                    status_code=503,
                )
            operation, parameters = resolved
            await self.catalog.authorize(identity.subject, tenant, operation.permission, workspace_id)
            request.state.verified_legacy_agent_grant = None
            request.state.verified_native_workspace_id = None
            try:
                await operation.verifier(request, identity, tenant, workspace_id, parameters)
            except (InvalidRequestException, PayloadTooLargeException) as error:
                return await global_exception_handler(request, error)
            except Exception as error:
                # Routing exception handlers do not wrap the outer request filters.
                for exception_type, handler in request.app.exception_handlers.items():
                    if handler is domain_problem and isinstance(error, exception_type):
                        return await domain_problem(request, error)
                raise
            native_workspace_id = getattr(request.state, "verified_native_workspace_id", None) or workspace_id
            if not isinstance(native_workspace_id, str) or not native_workspace_id:
                raise InvalidHierarchy("Verified native workspace is invalid", code="INVALID_WORKSPACE")
            if hasattr(request, "_body"):
                request.scope["pyfly.request_body"] = request._body
            request.state.identity = identity
            request.state.verified_tenant_id = tenant
            request.state.verified_workspace_id = workspace_id
            if operation.agent_scopes:
                request.state.verified_legacy_agent_grant = MappingProxyType(
                    {
                        "domain": "canon"
                        if path == "/api/v1/canon" or path.startswith("/api/v1/canon/")
                        else "structured",
                        "method": request.method.upper(),
                        "path": path,
                        "tenant_id": tenant,
                        "workspace_id": native_workspace_id,
                        "subject": identity.subject,
                        "scopes": operation.agent_scopes,
                    }
                )
        except JSONDecodeError:
            return JSONResponse(
                {"status": 400, "code": "INVALID_JSON", "detail": "Request body must be valid JSON"},
                status_code=400,
            )
        except (UnauthorizedException, AccessDenied, InvalidHierarchy) as error:
            status = (
                401
                if isinstance(error, UnauthorizedException)
                else 403
                if isinstance(error, AccessDenied)
                else 400
            )
            return JSONResponse(
                {"type": "about:blank", "status": status, "code": error.code, "detail": str(error)},
                status_code=status,
            )
        with bind_legacy_context(request, path, identity, tenant, native_workspace_id):
            return await call_next(request)
