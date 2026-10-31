# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import json
import time
from dataclasses import asdict
from types import SimpleNamespace
from unittest.mock import AsyncMock

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
    monkeypatch.setenv("FLYCANON_ALLOW_IN_MEMORY_ADAPTERS", "true")
    monkeypatch.setenv("FLYQUERY_ALLOW_IN_MEMORY_ADAPTERS", "true")
    from flycanon.config import CanonSettings
    from flycanon.core import configuration as canon_configuration
    from flycanon.core.services.retrieval import CorpusContext
    from flyquery.config import FlyquerySettings

    from koinon.app import create_application

    jwk = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(KEY.public_key()))
    jwk.update(kid="local-key", alg="RS256", use="sig")
    original = IdentityTokenValidator.__init__

    def local_validator(self, uri, **kwargs):
        kwargs["jwks_fetcher"] = lambda uri, **limits: json.dumps({"keys": [jwk]}).encode()
        original(self, uri, **kwargs)

    monkeypatch.setattr(IdentityTokenValidator, "__init__", local_validator)
    monkeypatch.setattr(
        canon_configuration,
        "build_corpus_context",
        lambda **kwargs: CorpusContext(
            corpus=SimpleNamespace(initialise=AsyncMock(), close=AsyncMock()),
            vector_store=SimpleNamespace(initialise=AsyncMock(), close=AsyncMock()),
            backend="pgvector",
        ),
    )
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
                "storage": {
                    "documents": {"root": str(tmp_path / "documents")},
                    "structured": {"root": str(tmp_path / "structured")},
                },
            },
            "pyfly": {
                "data": {
                    "relational": {
                        "enabled": True,
                        "ddl-auto": "create",
                        "url": f"sqlite+aiosqlite:///{tmp_path / 'app.db'}",
                        "datasources": {
                            name: {
                                "url": f"sqlite+aiosqlite:///{tmp_path / (name + '.db')}",
                                "ddl-auto": "none",
                            }
                            for name in ("canon", "canon_admin", "structured", "structured_admin")
                        },
                    }
                }
            },
        }
    )
    (tmp_path / "documents").mkdir()
    (tmp_path / "structured").mkdir()
    from flycanon.core.services.sources.async_ingest_service import AsyncIngestService

    if not app.state.context.container.contains_type(AsyncIngestService):
        app.state.context.container.register_instance(
            CanonSettings,
            CanonSettings(answer_mode="rag", object_store_localfs_root=str(tmp_path / "documents")),
        )
        app.state.context.container.register_instance(
            FlyquerySettings, FlyquerySettings(object_store_base=str(tmp_path / "structured"))
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
