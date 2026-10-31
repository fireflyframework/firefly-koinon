# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from flycanon.core.services.sources.async_ingest_service import AsyncIngestService
from flyquery.core.services.ingestion.workers import IngestWorker

from koinon.app import create_application


def config(enabled=True):
    return {
        "koinon": {
            "legacy": {"enabled": False},
            "knowledge": {"enabled": enabled},
            "mcp": {"enabled": False},
            "security": {
                "issuer": "https://identity.invalid",
                "jwks_uri": "https://identity.invalid/keys",
                "client_id": "browser",
                "api_audience": "api",
                "authorization_uri": "https://identity.invalid/authorize",
                "token_uri": "https://identity.invalid/token",
                "redirect_uri": "http://127.0.0.1/callback",
                "cookie_secure": False,
            },
        }
    }


def test_production_disables_legacy_http_without_disabling_native_core():
    application = create_application(config())
    context = application.state.context
    assert context.container.contains_type(AsyncIngestService)
    assert context.container.contains_type(IngestWorker)
    assert not any(
        route.path.startswith(("/api/v1/canon/", "/api/v1/structured/")) for route in application.routes
    )


def test_worker_has_native_core_without_any_registered_controller_or_http_application():
    application = create_application(config(), role="worker")
    context = application.state.context
    assert context.container.contains_type(AsyncIngestService) and context.container.contains_type(
        IngestWorker
    )
    assert not any(
        getattr(kind, "__pyfly_stereotype__", "") in {"controller", "rest_controller"}
        for kind in context.container.registered_types()
    )
    assert not hasattr(application, "router")


def test_explicit_knowledge_disable_leaves_native_core_and_capability_absent():
    application = create_application(config(False))
    assert not application.state.context.container.contains_type(AsyncIngestService)
    assert not application.state.context.container.contains_type(IngestWorker)
    assert all(not value["registered"] for value in application.state.capability_registry.domains.values())


def test_complete_worker_never_enables_shared_http_mcp_session_storage():
    values = config()
    values["koinon"]["mcp"] = {"enabled": True, "public_url": "https://knowledge.example.test/mcp"}
    application = create_application(values, role="worker")
    assert application.state.context.config.get("pyfly.mcp.sessions.enabled") is False
    assert not hasattr(application, "router")
