# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Application policy over native pyfly OIDC validation and filters."""

from collections.abc import Callable
from typing import Any, cast

from pyfly.context.request_context import RequestContext
from pyfly.kernel.exceptions import SecurityException, UnauthorizedException
from pyfly.security.context_holder import SecurityContextHolder
from pyfly.security.oauth2 import (
    OAuth2AuthenticationSuccessHandler,
    OAuth2AuthorizationRequestCustomizer,
    OidcTokenValidatorFactory,
)
from pyfly.security.oauth2.client import ClientRegistration
from pyfly.security.oauth2.login import OAuth2LoginHandler
from pyfly.security.oauth2.resource_server import ClaimMappings, JWKSTokenValidator
from pyfly.web.adapters.starlette.filters.oauth2_resource_filter import OAuth2ResourceServerFilter
from pyfly.web.ports.filter import CallNext
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from koinon.mcp_auth.service import McpOAuthService
from koinon.tokens.service import PREFIX, PersonalTokenService

IDENTITY_CLAIMS = ClaimMappings(
    principal_claims=("sub",),
    attribute_claims=(
        "iss",
        "sub",
        "name",
        "locale",
        "picture",
        "sid",
        "koinon_identity_provider",
        "koinon_external_subject",
        "koinon_external_issuer",
        "koinon_external_tid",
        "koinon_external_oid",
        "koinon_google_hd",
    ),
    raw_attribute_claims=("auth_time", "amr", "groups", "hasgroups", "_claim_names", "koinon_groups_overage"),
    authority_claims=(),
    scope_claims=("scope", "scp"),
)


class IdentityTokenValidator(JWKSTokenValidator):
    def __init__(self, jwks_uri: str, **kwargs: Any):
        kwargs["claim_mappings"] = IDENTITY_CLAIMS
        super().__init__(jwks_uri, **kwargs)

    def validate(self, token: str, *, timeout: float | None = None) -> dict[str, Any]:
        claims = super().validate(token, timeout=timeout)
        if not all(isinstance(claims.get(key), str) and claims[key] for key in ("iss", "sub")):
            raise SecurityException("Verified issuer and subject required", code="INVALID_TOKEN")
        return claims


class ApiBearerFilter(OAuth2ResourceServerFilter):
    """Bearer authority on /api; preserve sessions on browser routes."""

    def __init__(self, validator: JWKSTokenValidator, tokens: PersonalTokenService | None = None,
                 mcp_oauth: McpOAuthService | None = None):
        super().__init__(validator, error_mode="401")
        self.tokens = tokens
        self.mcp_oauth = mcp_oauth

    async def do_filter(self, request: Request, call_next: CallNext) -> Response:
        path = request.url.path
        if path == "/mcp" or path.startswith("/mcp/"):
            if request.headers.get("cookie"):
                return JSONResponse({"code": "MCP_COOKIES_FORBIDDEN"}, status_code=400)
            token = self._extract_token(request.headers.get("authorization", ""))
            try:
                if not token or self.tokens is None or self.mcp_oauth is None:
                    raise UnauthorizedException("MCP bearer required", code="AUTH_REQUIRED")
                canonical = await self.mcp_oauth.canonical_bearer(token)
                context = await self.tokens.authenticate(canonical)
            except UnauthorizedException:
                challenge = 'Bearer error="invalid_token"'
                if self.mcp_oauth is not None and self.mcp_oauth.settings.enabled:
                    challenge += ', resource_metadata="' + self.mcp_oauth.resource_metadata_url + '"'
                    challenge += ', scope="catalog:read"'
                return JSONResponse({"code": "MCP_AUTH_REQUIRED"}, status_code=401,
                                    headers={"WWW-Authenticate": challenge})
            request.state.security_context = context
            request_context = RequestContext.current()
            if request_context is not None:
                request_context.security_context = context
            with SecurityContextHolder.using(context):
                return await call_next(request)
        if path == "/api" or path.startswith("/api/"):
            token = self._extract_token(request.headers.get("authorization", ""))
            if token and token.startswith(PREFIX):
                try:
                    if self.tokens is None:
                        raise UnauthorizedException("API tokens unavailable", code="INVALID_TOKEN")
                    context = await self.tokens.authenticate(token)
                except UnauthorizedException:
                    return JSONResponse(
                        {"status": 401, "code": "INVALID_TOKEN", "detail": "API token is invalid or expired"},
                        status_code=401,
                        headers={"WWW-Authenticate": 'Bearer error="invalid_token"'},
                    )
                claims = cast(dict[str, Any], context.attributes["koinon_token"])
                if (
                    path in {"/api/v1/context", "/api/v1/capabilities"}
                    and "catalog:read" not in claims["scopes"]
                ):
                    return JSONResponse({"code": "TOKEN_SCOPE_DENIED"}, status_code=403)
                if (
                    path.startswith(("/api/v1/canon", "/api/v1/structured"))
                    and claims["asset_ids"] is not None
                ):
                    return JSONResponse({"code": "TOKEN_COMPATIBILITY_SCOPE_UNQUALIFIED"}, status_code=403)
                request.state.security_context = context
                request_context = RequestContext.current()
                if request_context is not None:
                    request_context.security_context = context
                with SecurityContextHolder.using(context):
                    return await call_next(request)
            return await super().do_filter(request, call_next)
        if (path == "/bff" or path.startswith("/bff/") or path == "/auth/me") and request.headers.get(
            "authorization"
        ):
            # The native CSRF filter exempts Bearer headers; browser endpoints must never use that bypass.
            return JSONResponse({"code": "BROWSER_AUTHORIZATION_HEADER_FORBIDDEN"}, status_code=400)
        return await call_next(request)


class _IdentityValidatorFactory(OidcTokenValidatorFactory):
    def __init__(self, factory: Callable):
        self.factory = factory

    def create(self, registration: ClientRegistration) -> JWKSTokenValidator:
        return self.factory(registration)


class VerifiedOidcLoginHandler(OAuth2LoginHandler):
    """Configure application policy through the framework-owned OIDC flow."""

    def __init__(
        self,
        client_repository: Any,
        *,
        validator_factory: Callable | None = None,
        concurrency=None,
        success_uri: str = "/",
        authorization_request_customizer: OAuth2AuthorizationRequestCustomizer | None = None,
        authentication_success_handler: OAuth2AuthenticationSuccessHandler | None = None,
        id_token_validator_factory: OidcTokenValidatorFactory | None = None,
    ):
        self.validator_factory = validator_factory or self._validator
        super().__init__(
            client_repository,
            concurrency=concurrency,
            success_uri=success_uri,
            authorization_request_customizer=authorization_request_customizer,
            authentication_success_handler=authentication_success_handler,
            id_token_validator_factory=id_token_validator_factory
            or _IdentityValidatorFactory(lambda registration: self.validator_factory(registration)),
            claim_mappings=IDENTITY_CLAIMS,
            require_oidc_id_token=True,
        )

    @staticmethod
    def _validator(registration: ClientRegistration) -> IdentityTokenValidator:
        return IdentityTokenValidator(
            registration.jwks_uri, issuer=registration.issuer_uri, audiences=[registration.client_id]
        )
