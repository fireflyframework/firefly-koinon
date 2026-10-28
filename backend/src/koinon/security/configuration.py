# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Native security beans and explicit deployment defaults."""

from pyfly.container import Container, bean, configuration
from pyfly.container.exceptions import NoSuchBeanError
from pyfly.core import Config
from pyfly.security.http_security import HttpSecurity
from pyfly.security.oauth2 import (
    OAuth2AuthenticationSuccessHandler,
    OAuth2AuthorizationRequestCustomizer,
    OidcTokenValidatorFactory,
)
from pyfly.security.oauth2.client import InMemoryClientRegistrationRepository
from pyfly.security.oauth2.login import OAuth2LoginHandler
from pyfly.security.oauth2.resource_server import JWKSTokenValidator
from pyfly.session.concurrency import SessionConcurrencyController

from koinon.mcp_auth.service import McpOAuthService
from koinon.security.identity import MembershipAuthorizer, RequestAuthorization
from koinon.security.oidc import ApiBearerFilter, IdentityTokenValidator, VerifiedOidcLoginHandler
from koinon.security.settings import OidcSettings
from koinon.tokens.service import PersonalTokenService


def native_security_defaults(settings: OidcSettings) -> dict:
    return {
        "pyfly": {
            "session": {
                "enabled": True,
                "store": "postgres",
                "postgres": {"datasource": "primary"},
                "cookie": {"secure": settings.cookie_secure},
                "concurrency": {
                    "enabled": True,
                    "registry": "postgres",
                    "postgres": {"datasource": "primary"},
                },
            },
            "security": {
                "csrf": {"enabled": True, "cookie-secure": settings.cookie_secure, "cookie-gated": True},
                "oauth2": {
                    "resource-server": {"enabled": False},
                    "login": {"enabled": True},
                    "client": {
                        "enabled": True,
                        "registrations": {
                            "koinon": {
                                "client-id": settings.client_id,
                                "client-secret": settings.client_secret,
                                "issuer-uri": settings.issuer,
                                "jwks-uri": settings.jwks_uri,
                                "authorization-uri": settings.authorization_uri,
                                "token-uri": settings.token_uri,
                                "redirect-uri": settings.redirect_uri,
                                "scopes": "openid,profile,email",
                                "require-iss": settings.require_iss,
                                "use-pkce": True,
                            }
                        },
                    },
                },
            },
        }
    }


@configuration
class SecurityConfiguration:
    @bean
    def oidc_settings(self, config: Config) -> OidcSettings:
        return config.bind(OidcSettings)

    @bean
    def identity_token_validator(self, settings: OidcSettings) -> JWKSTokenValidator:
        return IdentityTokenValidator(
            settings.jwks_uri, issuer=settings.issuer, audiences=[settings.api_audience]
        )

    @bean
    def api_bearer_filter(
        self, validator: JWKSTokenValidator, tokens: PersonalTokenService | None = None,
        mcp_oauth: McpOAuthService | None = None,
    ) -> ApiBearerFilter:
        return ApiBearerFilter(validator, tokens, mcp_oauth)

    @bean
    def verified_login_handler(
        self, repository: InMemoryClientRegistrationRepository, container: Container, settings: OidcSettings
    ) -> OAuth2LoginHandler:
        try:
            concurrency = container.resolve(SessionConcurrencyController)
        except NoSuchBeanError:
            concurrency = None

        def optional(port):
            try:
                return container.resolve(port)
            except NoSuchBeanError:
                return None

        return VerifiedOidcLoginHandler(
            repository,
            concurrency=concurrency,
            success_uri=settings.success_uri,
            authorization_request_customizer=optional(OAuth2AuthorizationRequestCustomizer),
            authentication_success_handler=optional(OAuth2AuthenticationSuccessHandler),
            id_token_validator_factory=optional(OidcTokenValidatorFactory),
        )

    @bean
    def http_security(self) -> HttpSecurity:
        security = HttpSecurity()
        security.authorize_requests().request_matchers(
            "/health", "/ready", "/oauth2/**", "/login/oauth2/**", "/logout",
            "/.well-known/oauth-protected-resource/mcp",
            "/.well-known/oauth-authorization-server/oauth2/mcp",
        ).permit_all().request_matchers(
            "/api/**", "/bff/**", "/auth/me", "/mcp", "/mcp/**"
        ).authenticated().any_request().deny_all()
        return security

    @bean
    def request_authorization(self, authorizer: MembershipAuthorizer) -> RequestAuthorization:
        return RequestAuthorization(authorizer)
