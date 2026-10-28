# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from types import SimpleNamespace
from unittest.mock import AsyncMock

from koinon.corporate_identity.broker import CorporateBrokerPolicy
from koinon.corporate_identity.settings import IdentitySettings


async def test_broker_inspection_is_explicit_and_never_calls_remote_without_deployment_credentials():
    directory = SimpleNamespace(_json=AsyncMock())
    probe = CorporateBrokerPolicy(IdentitySettings(), SimpleNamespace(), directory)
    brokered = SimpleNamespace(broker_alias="north-entra")
    result = await probe.check(brokered)
    assert result["status"] == "blocked" and result["verified"] is False
    directory._json.assert_not_called()
    result = await probe.check(SimpleNamespace(broker_alias=None))
    assert result["verified"] is True and result["status"] == "passed"


async def test_broker_auto_link_or_missing_protected_mapper_cannot_pass(monkeypatch):
    import koinon.corporate_identity.broker as module

    calls = []

    class OAuth:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def client_credentials(self, **kwargs):
            return SimpleNamespace(access_token="controlled-token")

    monkeypatch.setattr(module, "OAuth2Client", OAuth)

    async def request(url, token, **kwargs):
        calls.append(url)
        if url.endswith("/executions"):
            return [
                {"providerId": "idp-auto-link", "requirement": "REQUIRED"},
                {"providerId": "idp-username-password-form", "requirement": "REQUIRED"},
            ]
        return {
            "enabled": True,
            "providerId": "oidc",
            "firstBrokerLoginFlowAlias": "Explicit account proof",
            "config": {"clientId": "corporate", "issuer": "https://login.microsoftonline.com/tenant/v2.0"},
        }

    directory = SimpleNamespace(
        keycloak_origin=lambda issuer: ("https://identity.test", "koinon"), _json=request
    )
    probe = CorporateBrokerPolicy(
        IdentitySettings(broker_admin_client_id="read-only", broker_admin_secret="synthetic"),
        SimpleNamespace(issuer="https://identity.test/realms/koinon", client_id="app"),
        directory,
    )
    provider = SimpleNamespace(
        broker_alias="north-entra",
        kind="entra",
        settings_json={"client_id": "corporate", "tenant_id": "tenant"},
    )
    result = await probe.check(provider)
    assert result["verified"] is False and result["status"] == "blocked"
    assert len(calls) == 2 and "synthetic" not in str(result) and "controlled-token" not in str(result)
