# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import json
import time
from dataclasses import asdict

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from starlette.testclient import TestClient

from koinon.catalog.entities import Membership, Tenant
from koinon.catalog.repositories import MembershipRepository, TenantRepository
from koinon.catalog.service import CatalogService
from koinon.security.oidc import IdentityTokenValidator
from koinon.security.settings import OidcSettings

ISSUER = "https://identity.example.test/realms/koinon"
KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)


def bearer(subject="admin"):
    return {
        "Authorization": "Bearer "
        + jwt.encode(
            {"iss": ISSUER, "sub": subject, "aud": "koinon-api", "exp": int(time.time()) + 300},
            KEY,
            algorithm="RS256",
            headers={"kid": "local-key"},
        )
    }


@pytest.fixture
def client(tmp_path, monkeypatch, request):
    from koinon.app import create_application

    jwk = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(KEY.public_key()))
    jwk.update(kid="local-key", alg="RS256", use="sig")
    original = IdentityTokenValidator.__init__

    def local_validator(self, uri, **kwargs):
        kwargs["jwks_fetcher"] = lambda uri, **limits: json.dumps({"keys": [jwk]}).encode()
        original(self, uri, **kwargs)

    monkeypatch.setattr(IdentityTokenValidator, "__init__", local_validator)
    oidc = OidcSettings(
        issuer=ISSUER,
        jwks_uri=f"{ISSUER}/certs",
        client_id="browser",
        api_audience="koinon-api",
        authorization_uri=f"{ISSUER}/auth",
        token_uri=f"{ISSUER}/token",
        redirect_uri="http://127.0.0.1:18781/login/oauth2/code/koinon",
        cookie_secure=False,
    )
    app = create_application(
        {
            "koinon": {
                "security": asdict(oidc),
                "legacy": {"enabled": False},
                "knowledge": {"enabled": False},
            },
            "pyfly": {
                "data": {
                    "relational": {
                        "enabled": True,
                        "ddl-auto": "create",
                        "url": f"sqlite+aiosqlite:///{tmp_path / 'app.db'}",
                    }
                }
            },
        }
    )
    if hasattr(request, "param"):
        from koinon.web.projection import register_controller

        controller, domain = request.param if isinstance(request.param, tuple) else (request.param, "canon")
        register_controller(app.state.context, controller, domain)
    with TestClient(app) as browser:

        async def seed():
            context = app.state.context
            for tenant in ("north", "south"):
                await context.get_bean(TenantRepository).save(Tenant(id=tenant, name=tenant.title()))
            for subject, tenant, role in (
                ("admin", "north", "admin"),
                ("editor", "north", "editor"),
                ("viewer", "north", "viewer"),
                ("analyst", "north", "analyst"),
                ("outsider", "south", "admin"),
            ):
                await context.get_bean(MembershipRepository).save(
                    Membership(
                        id=subject,
                        subject=f"{ISSUER}|{subject}",
                        tenant_id=tenant,
                        role=role,
                    )
                )
            service = context.get_bean(CatalogService)
            workspace = await service.create(f"{ISSUER}|admin", "north", kind="workspace", name="Research")
            return workspace.id

        browser.workspace_id = browser.portal.call(seed)
        browser.native_app = app
        yield browser
