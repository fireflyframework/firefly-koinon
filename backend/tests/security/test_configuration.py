# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from contextlib import asynccontextmanager
from dataclasses import asdict

import pytest
from pyfly.container import bean, configuration
from pyfly.context import ApplicationContext
from pyfly.core import Config
from pyfly.security.context import SecurityContext
from pyfly.security.oauth2.login import OAuth2LoginHandler
from pyfly.security.oauth2.resource_server import JWKSTokenValidator
from pyfly.session.adapters.memory import InMemorySessionStore
from pyfly.session.concurrency import SessionConcurrencyController
from pyfly.session.ports.outbound import SessionStore
from pyfly.session.session import HttpSession
from pyfly.web.adapters.fastapi.app import create_app
from starlette.testclient import TestClient

from koinon.security.configuration import SecurityConfiguration, native_security_defaults
from koinon.security.controllers import AuthController
from koinon.security.identity import MembershipAuthorizer
from koinon.security.oidc import IdentityTokenValidator, VerifiedOidcLoginHandler
from koinon.security.settings import OidcSettings

ISSUER = "http://127.0.0.1:18784/realms/koinon"


def settings():
    return OidcSettings(
        issuer=ISSUER,
        jwks_uri=f"{ISSUER}/protocol/openid-connect/certs",
        client_id="koinon-browser",
        api_audience="koinon-api",
        authorization_uri=f"{ISSUER}/protocol/openid-connect/auth",
        token_uri=f"{ISSUER}/protocol/openid-connect/token",
        redirect_uri="http://127.0.0.1:18781/login/oauth2/code/koinon",
        cookie_secure=False,
    )


@pytest.mark.parametrize(
    "field,value",
    [
        ("issuer", "http://identity.example.test"),
        ("client_id", ""),
        ("api_audience", ""),
        ("redirect_uri", "https://user:secret@example.test/callback"),
    ],
)
def test_invalid_oidc_configuration(field, value):
    values = asdict(settings())
    values[field] = value
    with pytest.raises(ValueError):
        OidcSettings(**values)


def test_native_lifespan_session_csrf_and_logout():
    oidc = settings()
    store = InMemorySessionStore()

    class Catalog:
        async def authorize(self, subject, tenant_id, permission, workspace_id=None):
            pass

    @configuration
    class Fixtures:
        @bean
        def membership_authorizer(self) -> MembershipAuthorizer:
            return Catalog()

        @bean
        def sessions(self) -> SessionStore:
            return store

    values = native_security_defaults(oidc)
    values["pyfly"]["session"]["store"] = "memory"
    values["pyfly"]["session"]["concurrency"] = {"enabled": True, "max-sessions": 2, "registry": "memory"}
    values["koinon"] = {"security": asdict(oidc)}
    context = ApplicationContext(Config(values))
    for cls in (Fixtures, SecurityConfiguration, AuthController):
        context.register_bean(cls)

    @asynccontextmanager
    async def lifespan(app):
        await context.start()
        try:
            yield
        finally:
            await context.stop()

    app = create_app(context=context, lifespan=lifespan, actuator_enabled=False)
    with TestClient(app) as client:
        assert isinstance(context.get_bean(JWKSTokenValidator), IdentityTokenValidator)
        assert isinstance(context.get_bean(OAuth2LoginHandler), VerifiedOidcLoginHandler)
        assert context.get_bean(OAuth2LoginHandler)._concurrency is context.get_bean(
            SessionConcurrencyController
        )
        assert client.get("/auth/me").status_code == 401
        session = HttpSession("test-session", is_new=True)
        session.set_attribute(
            "SECURITY_CONTEXT", SecurityContext(user_id="user-1", attributes={"iss": ISSUER, "sub": "user-1"})
        )
        client.portal.call(store.save, session.id, session.get_data(), 1800)
        client.cookies.set("PYFLY_SESSION", session.id, domain="testserver.local", path="/")
        response = client.get("/auth/me")
        assert response.status_code == 200, response.text
        assert response.json()["subject"] == f"{ISSUER}|user-1"
        assert client.get("/api/missing").status_code == 401
        assert client.get("/auth/me", headers={"Authorization": "Bearer rejected"}).status_code == 400
        assert client.post("/logout").status_code == 403
        response = client.post(
            "/logout", headers={"X-XSRF-TOKEN": client.cookies.get("XSRF-TOKEN")}, follow_redirects=False
        )
        assert response.status_code == 302, response.text
        assert client.get("/auth/me").status_code == 401


def test_production_defaults_share_native_sessions_and_concurrency_on_primary():
    values = native_security_defaults(settings())
    session = values["pyfly"]["session"]
    assert session["store"] == "postgres"
    assert session["postgres"]["datasource"] == "primary"
    assert session["concurrency"]["registry"] == "postgres"
    assert session["concurrency"]["postgres"]["datasource"] == "primary"
