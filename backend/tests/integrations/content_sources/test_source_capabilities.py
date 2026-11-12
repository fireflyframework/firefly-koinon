# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Installation capabilities stay available independently from personal grants."""

import httpx
import pytest
from pyfly.context import ApplicationContext
from pyfly.core import Config
from pyfly.kernel import PyFlyException
from pyfly.security.context import SecurityContext
from pyfly.web.adapters.starlette.app import create_app
from pyfly.web.adapters.starlette.errors import global_exception_handler
from starlette.middleware.base import BaseHTTPMiddleware
from test_connection_lifecycle import lifecycle as lifecycle
from test_source_migration_postgres import source_database as source_database

pytestmark = pytest.mark.integration


@pytest.mark.parametrize("enabled", [False, True])
@pytest.mark.parametrize("lifecycle", ["postgres"], indirect=True)
async def test_capabilities_http_reports_configuration_without_exposing_grants(lifecycle, enabled):
    _, settings, _, context = lifecycle
    settings.enabled = enabled
    settings.synchronization_enabled = enabled
    settings.sync_min_interval_seconds = 1800
    settings.sync_max_interval_seconds = 7200
    settings.sync_max_scan_items = 200
    settings.sync_validation_max_active_per_owner = 1
    settings.sync_validation_max_active_per_tenant = 3
    settings.sync_validation_max_records_per_tenant = 17
    settings.sync_validation_max_retained_bytes_per_tenant = 32 * 1024 * 1024
    app = create_app(context=context, actuator_enabled=False)
    app.add_exception_handler(PyFlyException, global_exception_handler)

    async def identity(request, next_handler):
        request.state.security_context = SecurityContext(
            user_id="alice", attributes={"iss": "issuer", "sub": "alice"}
        )
        return await next_handler(request)

    app.add_middleware(BaseHTTPMiddleware, dispatch=identity)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        result = await client.get("/api/v1/tenants/tenant/content-sources/capabilities")
        assert result.status_code == 200, result.text
        body = result.json()
        assert body["accounts_available"] is enabled
        assert body["inbound_only"] is True and body["synchronization_available"] is False
        providers = {provider["provider"]: provider for provider in body["providers"]}
        assert providers["google_drive"]["consent_available"] is enabled
        assert providers["google_drive"]["display_name"] == "Google Drive"
        assert providers["onedrive"]["unavailable_reason"] == ("not_configured" if enabled else "disabled")
        assert body["schedule"]["min_interval_seconds"] == 1800
        assert body["schedule"]["max_interval_seconds"] == 7200
        assert body["validation_limits"] == {
            "max_scan_items": 200,
            "max_active_per_owner": 1,
            "max_active_per_tenant": 3,
            "max_records_per_tenant": 17,
            "max_retained_bytes_per_tenant": 32 * 1024 * 1024,
            "max_lifetime_seconds": 8 * 60 * 60,
            "lifetime_limited_by_session": True,
        }
        assert {"extension": ".txt", "mode": "document"} in body["formats"]
        assert not any(
            secret in result.text
            for secret in ("synthetic-secret", "source-client", "redirect_uri", "authorization_url")
        )
        assert (await client.get("/api/v1/tenants/other/content-sources/capabilities")).status_code == 403
        schema = (await client.get("/openapi.json")).json()
        assert "SourceCapabilitiesOutput" in schema["components"]["schemas"]


def test_disabled_registration_exposes_capabilities_without_credential_services():
    from koinon.integrations.content_sources.configuration import register_source_accounts
    from koinon.integrations.content_sources.controllers import SourceCapabilitiesController
    from koinon.integrations.content_sources.credentials import SourceCredentialVault
    from koinon.integrations.content_sources.lifecycle import SourceConnectionService

    context = ApplicationContext(Config({}))
    register_source_accounts(context, {}, controllers=True)
    assert context.container.contains_type(SourceCapabilitiesController)
    assert not context.container.contains_type(SourceCredentialVault)
    assert not context.container.contains_type(SourceConnectionService)
