# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Native account routes enforce browser consent and owner-only metadata access."""

import base64
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from urllib.parse import unquote

import pytest
from conftest import ISSUER, bearer
from conftest import client as native_client
from pyfly.security.context import SecurityContext
from pyfly.session.ports.outbound import SessionStore


@pytest.fixture
def sources(tmp_path, monkeypatch, request):
    import koinon.app

    original = koinon.app.create_application

    def configured(config):
        config["koinon"]["content_sources"] = {
            "enabled": True,
            "master_key": base64.b64encode(bytes(range(32))).decode(),
            "providers": {
                "google_drive": {
                    "client_id": "source-client",
                    "client_secret": "synthetic-secret",
                    "redirect_uri": "https://app.example.test/sources/callback",
                }
            },
        }
        return original(config)

    monkeypatch.setattr(koinon.app, "create_application", configured)
    with contextmanager(native_client.__wrapped__)(tmp_path, monkeypatch, request) as client:
        store = client.native_app.state.context.get_bean(SessionStore)
        client.portal.call(
            store.save,
            "source-browser",
            {
                "SECURITY_CONTEXT": SecurityContext(
                    user_id="admin", attributes={"iss": ISSUER, "sub": "admin"}
                )
            },
            1800,
        )
        client.cookies.set("PYFLY_SESSION", "source-browser", domain="testserver.local", path="/")
        yield client


def test_source_consent_requires_session_and_csrf_then_lists_only_owner(sources):
    root = "/api/v1/tenants/north/content-sources"
    body = {"provider": "google_drive"}
    sources.cookies.clear()
    assert sources.post(root + "/authorizations", headers=bearer(), json=body).status_code == 403
    sources.cookies.set("PYFLY_SESSION", "source-browser", domain="testserver.local", path="/")
    browser = "/bff" + root
    assert sources.get(browser + "/connections").status_code == 200
    assert sources.post(browser + "/authorizations", json=body).status_code == 403
    csrf = {"X-XSRF-TOKEN": unquote(sources.cookies.get("XSRF-TOKEN"))}
    response = sources.post(browser + "/authorizations", headers=csrf, json=body)
    assert response.status_code == 201, response.text
    identifier = response.json()["connection_id"]
    page = sources.get(root + "/connections", headers=bearer()).json()
    assert page["synchronization_available"] is False
    assert [row["id"] for row in page["items"]] == [identifier]
    assert sources.get(root + "/connections", headers=bearer("viewer")).json()["items"] == []
    assert sources.get(root + "/connections/" + identifier, headers=bearer("viewer")).status_code == 403
    assert sources.get(root.replace("north", "south") + "/connections", headers=bearer()).status_code == 403
    assert sources.get(root + "/connections?limit=101", headers=bearer()).status_code == 400
    path = browser + "/connections/" + identifier + "/disconnect"
    assert sources.post(path, json={"expected_revision": 1}).status_code == 403
    disconnected = sources.post(path, headers=csrf, json={"expected_revision": 1})
    assert disconnected.status_code == 200 and disconnected.json()["status"] == "disconnected"


def test_disabled_sources_are_not_exposed(client):
    assert (
        client.get("/api/v1/tenants/north/content-sources/connections", headers=bearer()).status_code == 404
    )


def test_invalid_browse_parameters_are_client_errors_before_reading_credentials(sources, monkeypatch):
    from koinon.integrations.content_sources.browse import PersonalSourceBrowser
    from koinon.integrations.content_sources.dtos import Account

    browser = sources.native_app.state.context.get_bean(PersonalSourceBrowser)
    credential_reads = []

    async def reader(*args):
        credential_reads.append(args)
        return Account("sharepoint", "verified-admin", "external-tenant"), object()

    monkeypatch.setattr(browser, "_reader", reader)
    root = "/api/v1/tenants/north/content-sources/connections/connection"
    cases = [
        ("sites", "q", {}, 256),
        ("drives", "site_id", {}, 1024),
        ("children", "drive_id", {}, 1024),
        ("children", "folder_id", {"drive_id": "drive"}, 1024),
    ]
    for operation, parameter, valid, limit in cases:
        invalid = ("", "bad\nvalue", "x" * (limit + 1))
        if parameter != "q":
            invalid += ("..", "another/path")
        for value in invalid:
            response = sources.get(
                root + "/" + operation, headers=bearer(), params={**valid, parameter: value}
            )
            assert response.status_code == 400, (operation, parameter, response.text)
            assert response.json()["code"] == "SOURCE_INVALID_PARAMETER"
    assert credential_reads == []


def test_personal_token_cannot_manage_or_browse_sources(sources):
    response = sources.post(
        "/api/v1/tokens",
        headers=bearer(),
        json={
            "name": "Source boundary",
            "tenant_id": "north",
            "scopes": ["catalog:read"],
            "expires_at": (datetime.now(UTC) + timedelta(hours=1)).isoformat(),
        },
    )
    assert response.status_code == 201, response.text
    headers = {"Authorization": "Bearer " + response.json()["token"]}
    root = "/api/v1/tenants/north/content-sources"
    for path in (
        "/connections",
        "/connections/unknown",
        "/connections/unknown/drives",
        "/connections/unknown/sites?q=report",
        "/connections/unknown/children?drive_id=drive",
    ):
        denied = sources.get(root + path, headers=headers)
        assert denied.status_code == 403 and denied.json()["code"] == "SOURCE_INTERACTIVE_IDENTITY_REQUIRED"
    for path, body in (
        ("/authorizations", {"provider": "google_drive"}),
        ("/authorizations/complete", {"challenge_id": "id", "state": "state", "code": "code"}),
        ("/connections/unknown/disconnect", {"expected_revision": 1}),
    ):
        assert sources.post(root + path, headers=headers, json=body).status_code == 403


@pytest.mark.parametrize("invalid", [{"master_key": "invalid"}, {"providers": {"google_drive": {}}}])
def test_invalid_enabled_source_configuration_fails_before_exposure(invalid):
    from pyfly.context import ApplicationContext
    from pyfly.core import Config
    from pyfly.kernel import ServiceUnavailableException

    from koinon.integrations.content_sources.configuration import register_source_accounts
    from koinon.integrations.content_sources.errors import SourceError

    values = {"enabled": True, "master_key": base64.b64encode(bytes(range(32))).decode(), **invalid}
    with pytest.raises((ServiceUnavailableException, SourceError)):
        register_source_accounts(
            ApplicationContext(Config({})), {"koinon": {"content_sources": values}}, controllers=True
        )
