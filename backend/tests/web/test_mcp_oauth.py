# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import base64
import hashlib
import re
from contextlib import contextmanager
from copy import copy
from urllib.parse import parse_qs, urlsplit

import pytest
from conftest import ISSUER, bearer
from conftest import client as native_client
from cryptography.fernet import Fernet
from pyfly.security.context import SecurityContext
from pyfly.session.ports.outbound import SessionStore


@pytest.fixture
def oauth(tmp_path, monkeypatch, request):
    import koinon.app

    original = koinon.app.create_application

    def configured(config):
        if "installation_brand" in request.fixturenames:
            config["koinon"]["branding"] = request.getfixturevalue("installation_brand")
        config["koinon"]["mcp"] = {
            "enabled": True,
            "public_url": "http://127.0.0.1:18781/mcp",
            "allowed_hosts": ["testserver"],
            "oauth": {
                "enabled": True,
                "encryption_key": Fernet.generate_key().decode(),
                "clients": [
                    {
                        "client_id": "test-chat-client",
                        "name": "Test Chat Client",
                        "redirect_uris": ["https://client.example/callback"],
                        "scopes": ["catalog:read", "knowledge:search"],
                    }
                ],
            },
        }
        return original(config)

    monkeypatch.setattr(koinon.app, "create_application", configured)
    with contextmanager(native_client.__wrapped__)(tmp_path, monkeypatch, request) as client:
        context = client.native_app.state.context
        store = context.get_bean(SessionStore)
        client.portal.call(
            store.save,
            "oauth-browser",
            {
                "SECURITY_CONTEXT": SecurityContext(
                    user_id="admin", attributes={"iss": ISSUER, "sub": "admin"}
                ),
            },
            1800,
        )
        client.cookies.set("PYFLY_SESSION", "oauth-browser", domain="testserver.local", path="/")
        client.application_factory = original
        yield client


def authorize(client, **overrides):
    verifier = "v" * 43
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    params = {
        "client_id": "test-chat-client",
        "redirect_uri": "https://client.example/callback",
        "response_type": "code",
        "resource": "http://127.0.0.1:18781/mcp",
        "scope": "catalog:read",
        "state": "client-state",
        "code_challenge": challenge,
        "code_challenge_method": "S256",
        **overrides,
    }
    return client.get("/oauth2/mcp/authorize", params=params, follow_redirects=False)


def consent(client):
    response = authorize(client)
    assert response.status_code == 200, response.text
    request_id = re.search(r'name="request_id" value="([^"]+)"', response.text)[1]
    return client.post(
        "/oauth2/mcp/authorize",
        data={
            "request_id": request_id,
            "decision": "allow",
            "tenant_id": "north",
            "workspace_id": client.workspace_id,
            "_csrf": client.cookies.get("XSRF-TOKEN"),
        },
        follow_redirects=False,
    )


def exchange(client, code, **overrides):
    # OAuth backchannel carries no ambient browser authority.
    cookies = [copy(cookie) for cookie in client.cookies.jar]
    client.cookies.clear()
    try:
        return client.post(
            "/oauth2/mcp/token",
            data={
                "grant_type": "authorization_code",
                "client_id": "test-chat-client",
                "code": code,
                "redirect_uri": "https://client.example/callback",
                "code_verifier": "v" * 43,
                "resource": "http://127.0.0.1:18781/mcp",
                **overrides,
            },
        )
    finally:
        client.cookies.clear()
        for cookie in cookies:
            client.cookies.jar.set_cookie(cookie)


def registered(oauth, *, client_type="public"):
    response = oauth.post(
        "/api/v1/tenants/north/mcp/oauth-clients",
        json={
            "name": "Organization research client",
            "client_type": client_type,
            "redirect_uris": ["https://client.example/callback"],
            "scopes": ["catalog:read", "knowledge:search"],
        },
        headers=bearer(),
    )
    assert response.status_code == 201, response.text
    assert "no-store" in response.headers["cache-control"]
    return response.json()


def organization_code(oauth, client_id):
    response = authorize(oauth, client_id=client_id)
    assert response.status_code == 200, response.text
    request_id = re.search(r'name="request_id" value="([^"]+)"', response.text)[1]
    granted = oauth.post(
        "/oauth2/mcp/authorize",
        data={
            "request_id": request_id,
            "decision": "allow",
            "tenant_id": "north",
            "workspace_id": oauth.workspace_id,
            "_csrf": oauth.cookies.get("XSRF-TOKEN"),
        },
        follow_redirects=False,
    )
    assert granted.status_code == 302, granted.text
    return parse_qs(urlsplit(granted.headers["location"]).query)["code"][0]


def test_org_admin_owns_public_client_without_exposing_installation_configuration(oauth):
    issued = registered(oauth)
    assert issued["client_secret"] is None
    client = issued["client"]
    assert client["tenant_id"] == "north" and client["revision"] == 1
    page = oauth.get("/api/v1/tenants/north/mcp/oauth-clients", headers=bearer())
    assert page.status_code == 200 and page.json()["items"] == [client]
    assert oauth.get("/api/v1/tenants/south/mcp/oauth-clients", headers=bearer()).status_code == 403
    readiness = oauth.get("/api/v1/tenants/north/mcp/oauth-clients/readiness", headers=bearer())
    assert readiness.status_code == 200 and readiness.json()["ready"] is True
    assert "encryption_key" not in readiness.text and "client_secret" not in page.text
    descriptor = oauth.get("/api/v1/tenants/north/mcp/connection", headers=bearer())
    assert descriptor.status_code == 200
    assert descriptor.json()["clients"] == [
        {
            "client_id": client["client_id"],
            "name": client["name"],
            "scopes": client["scopes"],
            "client_auth": "public",
        },
        {
            "client_id": "test-chat-client",
            "name": "Test Chat Client",
            "scopes": ["catalog:read", "knowledge:search"],
            "client_auth": "public",
        },
    ]
    assert oauth.get("/api/v1/tenants/south/mcp/connection", headers=bearer()).status_code == 403


def test_organization_client_can_exchange_only_with_current_registration(oauth):
    client = registered(oauth)["client"]
    code = organization_code(oauth, client["client_id"])
    updated = oauth.patch(
        f"/api/v1/tenants/north/mcp/oauth-clients/{client['id']}",
        json={"expected_revision": 1, "name": "Updated organization client"},
        headers=bearer(),
    )
    assert updated.status_code == 200 and updated.json()["revision"] == 2
    assert exchange(oauth, code, client_id=client["client_id"]).status_code == 400


def test_disabled_registration_invalidates_existing_opaque_and_canonical_application_credentials(oauth):
    from pyfly.kernel import UnauthorizedException

    from koinon.mcp_auth.service import McpOAuthService
    from koinon.tokens.service import PersonalTokenService

    client = registered(oauth)["client"]
    response = exchange(oauth, organization_code(oauth, client["client_id"]), client_id=client["client_id"])
    assert response.status_code == 200, response.text
    opaque = response.json()["access_token"]
    service = oauth.native_app.state.context.get_bean(McpOAuthService)
    canonical = oauth.portal.call(service.canonical_bearer, opaque)
    applications = oauth.get("/api/v1/authorized-applications", headers=bearer()).json()["items"]
    application_id = applications[0]["id"]
    updated = oauth.patch(
        f"/api/v1/tenants/north/mcp/oauth-clients/{client['id']}",
        json={"expected_revision": 1, "enabled": False},
        headers=bearer(),
    )
    assert updated.status_code == 200
    connections = oauth.get("/api/v1/authorized-applications", headers=bearer()).json()["items"]
    assert connections[0]["status"] == "revoked"
    with pytest.raises(UnauthorizedException):
        oauth.portal.call(service.authenticate, opaque)
    tokens = oauth.native_app.state.context.get_bean(PersonalTokenService)
    with pytest.raises(UnauthorizedException):
        oauth.portal.call(
            lambda: tokens.authenticate(canonical, purpose="application", application_id=application_id)
        )


def test_confidential_registration_secret_is_once_only_and_required_for_exchange(oauth):
    issued = registered(oauth, client_type="confidential")
    client, secret = issued["client"], issued["client_secret"]
    assert secret and secret not in str(client)
    detail = oauth.get(f"/api/v1/tenants/north/mcp/oauth-clients/{client['id']}", headers=bearer())
    assert secret not in detail.text and "client_secret" not in detail.text
    code = organization_code(oauth, client["client_id"])
    assert exchange(oauth, code, client_id=client["client_id"]).status_code == 401
    assert exchange(oauth, code, client_id=client["client_id"], client_secret=secret).status_code == 200


@pytest.mark.parametrize(
    "changes",
    [
        {"redirect_uris": ["https://*.example/callback"]},
        {"scopes": ["catalog:read", "ingest:write"]},
        {"name": "\n"},
        {"enabled": None},
    ],
)
def test_invalid_admin_patch_is_a_validation_error_without_changing_registration(oauth, changes):
    client = registered(oauth)["client"]
    response = oauth.patch(
        f"/api/v1/tenants/north/mcp/oauth-clients/{client['id']}",
        json={"expected_revision": 1, **changes},
        headers=bearer(),
    )
    assert response.status_code in {400, 422}, response.text
    unchanged = oauth.get(f"/api/v1/tenants/north/mcp/oauth-clients/{client['id']}", headers=bearer())
    assert unchanged.json() == client


def test_reenabling_a_registration_never_resurrects_previously_revoked_connections(oauth):
    from pyfly.kernel import UnauthorizedException

    from koinon.mcp_auth.service import McpOAuthService

    client = registered(oauth)["client"]
    response = exchange(oauth, organization_code(oauth, client["client_id"]), client_id=client["client_id"])
    opaque = response.json()["access_token"]
    path = f"/api/v1/tenants/north/mcp/oauth-clients/{client['id']}"
    for revision, enabled in ((1, False), (2, True)):
        assert (
            oauth.patch(
                path, json={"expected_revision": revision, "enabled": enabled}, headers=bearer()
            ).status_code
            == 200
        )
    service = oauth.native_app.state.context.get_bean(McpOAuthService)
    with pytest.raises(UnauthorizedException):
        oauth.portal.call(service.authenticate, opaque)
    connections = oauth.get("/api/v1/authorized-applications", headers=bearer()).json()["items"]
    assert connections[0]["status"] == "revoked"


def test_consent_for_managed_client_cannot_switch_to_another_membership_tenant(oauth):
    from koinon.catalog.entities import Membership, Tenant
    from koinon.catalog.repositories import MembershipRepository, TenantRepository
    from koinon.catalog.service import CatalogService

    context = oauth.native_app.state.context
    oauth.portal.call(context.get_bean(TenantRepository).save, Tenant(id="south", name="South"))
    oauth.portal.call(
        context.get_bean(MembershipRepository).save,
        Membership(
            id="south-admin",
            subject=ISSUER + "|admin",
            tenant_id="south",
            role="admin",
        ),
    )
    space = oauth.portal.call(
        lambda: context.get_bean(CatalogService).create(
            ISSUER + "|admin",
            "south",
            kind="workspace",
            name="South",
        )
    )
    client = registered(oauth)["client"]
    response = authorize(oauth, client_id=client["client_id"])
    assert space.id not in response.text
    request_id = re.search(r'name="request_id" value="([^"]+)"', response.text)[1]
    denied = oauth.post(
        "/oauth2/mcp/authorize",
        data={
            "request_id": request_id,
            "decision": "allow",
            "tenant_id": "south",
            "workspace_id": space.id,
            "_csrf": oauth.cookies.get("XSRF-TOKEN"),
        },
        follow_redirects=False,
    )
    assert denied.status_code == 403 and "location" not in denied.headers


def test_regular_member_discovers_safe_org_clients_but_cannot_manage_them(oauth):
    client = registered(oauth)["client"]
    response = oauth.get("/api/v1/tenants/north/mcp/connection", headers=bearer("viewer"))
    assert response.status_code == 200
    assert "no-store" in response.headers.get("cache-control", "")
    visible = next(value for value in response.json()["clients"] if value["client_id"] == client["client_id"])
    assert set(visible) == {"client_id", "name", "scopes", "client_auth"}
    assert oauth.get("/api/v1/tenants/north/mcp/oauth-clients", headers=bearer("viewer")).status_code == 403
    assert oauth.get("/api/v1/tenants/north/mcp/connection", headers=bearer("outsider")).status_code == 403


def test_delegated_token_cannot_manage_clients_and_descriptor_respects_its_tenant(oauth):
    from datetime import UTC, datetime, timedelta

    issued = oauth.post(
        "/api/v1/tokens",
        headers=bearer(),
        json={
            "name": "Scoped API",
            "tenant_id": "north",
            "scopes": ["catalog:read", "identity:manage"],
            "expires_at": (datetime.now(UTC) + timedelta(hours=1)).isoformat(),
        },
    )
    assert issued.status_code == 201, issued.text
    headers = {"Authorization": "Bearer " + issued.json()["token"]}
    assert oauth.get("/api/v1/tenants/north/mcp/oauth-clients", headers=headers).status_code == 403
    assert oauth.get("/api/v1/tenants/north/mcp/connection", headers=headers).status_code == 200
    assert oauth.get("/api/v1/tenants/south/mcp/connection", headers=headers).status_code == 403


def test_rotation_revokes_previous_secret_and_pending_authorization_code(oauth):
    issued = registered(oauth, client_type="confidential")
    client, old_secret = issued["client"], issued["client_secret"]
    code = organization_code(oauth, client["client_id"])
    rotated = oauth.post(
        f"/api/v1/tenants/north/mcp/oauth-clients/{client['id']}/rotate-secret",
        headers=bearer(),
        json={"expected_revision": 1},
    )
    assert rotated.status_code == 200, rotated.text
    secret = rotated.json()["client_secret"]
    assert secret != old_secret and rotated.json()["client"]["revision"] == 2
    assert exchange(oauth, code, client_id=client["client_id"], client_secret=old_secret).status_code == 401
    assert exchange(oauth, code, client_id=client["client_id"], client_secret=secret).status_code == 400


def test_code_only_discovery_uses_configured_urls_and_never_claims_registration(oauth):
    discovery = oauth.get("/.well-known/oauth-protected-resource/mcp")
    assert "set-cookie" not in discovery.headers
    resource = discovery.json()
    assert resource["resource"] == "http://127.0.0.1:18781/mcp"
    from koinon.mcp_auth.settings import MCP_SCOPES

    assert resource["scopes_supported"] == sorted(MCP_SCOPES)
    issuer = resource["authorization_servers"][0]
    metadata = oauth.get("/.well-known/oauth-authorization-server/oauth2/mcp").json()
    assert metadata["issuer"] == issuer
    assert metadata["grant_types_supported"] == ["authorization_code"]
    assert metadata["code_challenge_methods_supported"] == ["S256"]
    assert "registration_endpoint" not in metadata
    assert "client_id_metadata_document_supported" not in metadata
    assert "testserver" not in str(metadata)


def test_consent_code_exchange_and_existing_token_revocation(oauth):
    page = authorize(oauth)
    assert "Test Chat Client" in page.text and "Research" in page.text and "catalog:read" in page.text
    assert "Firefly Software Foundation" in page.text
    granted = consent(oauth)
    assert granted.status_code == 302, granted.text
    query = parse_qs(urlsplit(granted.headers["location"]).query)
    assert query["state"] == ["client-state"] and query["iss"]
    response = exchange(oauth, query["code"][0])
    assert response.status_code == 200, response.text
    body = response.json()
    assert "refresh_token" not in body
    opaque = body["access_token"]
    assert opaque.startswith("koinon_mcp_")
    assert oauth.get("/api/v1/context", headers={"Authorization": "Bearer " + opaque}).status_code == 401
    from koinon.mcp_auth.service import McpOAuthService

    service = oauth.native_app.state.context.get_bean(McpOAuthService)
    canonical = oauth.portal.call(service.canonical_bearer, opaque)
    assert oauth.get("/api/v1/context", headers={"Authorization": "Bearer " + canonical}).status_code == 401
    tokens = oauth.get("/api/v1/tokens", headers=bearer()).json()["items"]
    assert tokens == []
    row = oauth.get("/api/v1/authorized-applications", headers=bearer()).json()["items"][0]
    assert row["workspace_id"] == oauth.workspace_id and row["scopes"] == ["catalog:read"]
    assert opaque not in str(row) and canonical not in str(row)
    assert oauth.delete("/api/v1/authorized-applications/" + row["id"], headers=bearer()).status_code == 204
    from pyfly.kernel import UnauthorizedException

    with pytest.raises(UnauthorizedException):
        oauth.portal.call(service.canonical_bearer, opaque)
    assert exchange(oauth, query["code"][0]).status_code == 400


@pytest.mark.parametrize(
    "changes",
    [
        {"redirect_uri": "https://attacker.example/callback"},
        {"resource": "https://other.example/mcp"},
        {"scope": "members:write"},
        {"code_challenge_method": "plain"},
        {"code_challenge": "short"},
        {"code_challenge": "_" * 43},
    ],
)
def test_untrusted_authorization_requests_never_redirect(oauth, changes):
    response = authorize(oauth, **changes)
    assert response.status_code == 400 and "location" not in response.headers


def test_consent_requires_browser_session_and_csrf(oauth):
    assert authorize(oauth, access_token="forbidden").status_code == 400
    page = authorize(oauth)
    request_id = re.search(r'name="request_id" value="([^"]+)"', page.text)[1]
    assert (
        oauth.post(
            "/oauth2/mcp/authorize",
            data={
                "request_id": request_id,
                "decision": "allow",
                "tenant_id": "north",
                "workspace_id": oauth.workspace_id,
            },
        ).status_code
        == 403
    )
    oauth.cookies.clear()
    assert authorize(oauth).status_code == 302
    response = oauth.get("/oauth2/mcp/authorize", headers=bearer(), follow_redirects=False)
    assert response.status_code == 400


def test_consent_assets_load_with_a_restrictive_same_origin_policy(oauth):
    page = authorize(oauth)
    assert page.status_code == 200
    assert 'rel="stylesheet" href="/oauth2/mcp/style"' in page.text
    assert "style-src 'self'" in page.headers["content-security-policy"]
    assert "unsafe-inline" not in page.headers["content-security-policy"]
    for path, media_type in (("style", "text/css"), ("logo", "image/svg+xml"), ("font", "font/woff2")):
        response = oauth.get("/oauth2/mcp/" + path)
        assert response.status_code == 200
        assert response.headers["content-type"].startswith(media_type)


@pytest.mark.parametrize(
    "installation_brand", [{"product_name": "North <Knowledge>", "font_family": "Inter"}]
)
def test_headless_consent_uses_installation_identity_and_bundled_inter_without_relaxing_csp(
    oauth, installation_brand
):
    from importlib.resources import files

    page = authorize(oauth)
    assert page.status_code == 200
    assert "Connect to North &lt;Knowledge&gt;" in page.text
    assert "<Knowledge>" not in page.text
    assert 'alt="firefly koinon"' not in page.text
    assert "unsafe-inline" not in page.headers["content-security-policy"]
    assert "img-src 'self'" in page.headers["content-security-policy"]
    stylesheet = oauth.get("/oauth2/mcp/style")
    assert "Inter" in stylesheet.text
    font = oauth.get("/oauth2/mcp/font")
    assert font.content == files("koinon.organization_branding").joinpath("assets/inter.woff2").read_bytes()
    assert (
        oauth.get("/.well-known/oauth-protected-resource/mcp").json()["resource_name"] == "North <Knowledge>"
    )


def test_consent_keeps_client_and_space_text_inert():
    from koinon.mcp_auth.http import consent_page

    page = consent_page(
        'request"<',
        {"name": '<script>alert("client")</script>', "client_id": "configured-client"},
        ["catalog:read"],
        [{"tenant_id": 'tenant"', "workspace_id": "space", "tenant_name": "R&D", "name": "<img src=x>"}],
        'csrf"<',
    )
    assert "<script>" not in page and "<img src=x>" not in page
    assert "&lt;script&gt;" in page and "R&amp;D" in page
    assert 'name="request_id" value="request&quot;&lt;"' in page
    assert 'name="_csrf" value="csrf&quot;&lt;"' in page


def test_consent_identifies_the_current_browser_user_and_private_avatar(oauth):
    import io

    from PIL import Image

    from koinon.profiles.service import ProfileService

    service = oauth.native_app.state.context.get_bean(ProfileService)
    subject = ISSUER + "|admin"
    oauth.portal.call(service.update, subject, {"display_name": "Sam Rivera"})
    content = io.BytesIO()
    Image.new("RGB", (48, 48), "#ffb34a").save(content, format="PNG")
    oauth.portal.call(service.set_avatar, subject, content.getvalue())
    page = authorize(oauth)
    assert "Sam Rivera" in page.text and "Signed in as" in page.text
    assert "/oauth2/mcp/avatar" in page.text
    image = oauth.get("/oauth2/mcp/avatar")
    assert image.status_code == 200 and image.headers["content-type"].startswith("image/jpeg")
    assert "no-store" in image.headers["cache-control"]
    oauth.cookies.clear()
    assert oauth.get("/oauth2/mcp/avatar", follow_redirects=False).status_code in {401, 403}
    assert oauth.get("/oauth2/mcp/avatar", headers=bearer()).status_code == 400
    store = oauth.native_app.state.context.get_bean(SessionStore)
    oauth.portal.call(
        store.save,
        "oauth-viewer",
        {
            "SECURITY_CONTEXT": SecurityContext(
                user_id="viewer",
                attributes={
                    "iss": ISSUER,
                    "sub": "viewer",
                    "name": "Lee Morgan",
                    "email": "lee@example.test",
                    "email_verified": True,
                },
            ),
        },
        1800,
    )
    oauth.cookies.set("PYFLY_SESSION", "oauth-viewer", domain="testserver.local", path="/")
    assert oauth.get("/oauth2/mcp/avatar?subject=" + subject).status_code == 404
    other_page = authorize(oauth)
    assert "Lee Morgan" in other_page.text and "lee@example.test" in other_page.text
    assert "Sam Rivera" not in other_page.text


@pytest.mark.parametrize(
    "changes",
    [
        {"resource": "https://other.example/mcp"},
        {"redirect_uri": "https://client.example/other"},
        {"code_verifier": "x" * 43},
        {"code_verifier": "short"},
        {"client_id": "unknown-client"},
        {"grant_type": "refresh_token"},
        {"client_secret": "unexpected-secret"},
    ],
)
def test_invalid_exchange_keeps_code_available_for_the_bound_client(oauth, changes):
    redirect = consent(oauth)
    code = parse_qs(urlsplit(redirect.headers["location"]).query)["code"][0]
    response = exchange(oauth, code, **changes)
    assert response.status_code in {400, 401}
    assert exchange(oauth, code).status_code == 200


def test_consent_is_single_use(oauth):
    response = authorize(oauth)
    request_id = re.search(r'name="request_id" value="([^"]+)"', response.text)[1]
    form = {
        "request_id": request_id,
        "decision": "allow",
        "tenant_id": "north",
        "workspace_id": oauth.workspace_id,
        "_csrf": oauth.cookies.get("XSRF-TOKEN"),
    }
    assert oauth.post("/oauth2/mcp/authorize", data=form, follow_redirects=False).status_code == 302
    assert oauth.post("/oauth2/mcp/authorize", data=form, follow_redirects=False).status_code == 400


def test_cancel_returns_to_the_registered_client_without_creating_a_credential(oauth):
    page = authorize(oauth)
    request_id = re.search(r'name="request_id" value="([^"]+)"', page.text)[1]
    form = {
        "request_id": request_id,
        "decision": "deny",
        "_csrf": oauth.cookies.get("XSRF-TOKEN"),
    }
    response = oauth.post("/oauth2/mcp/authorize", data=form, follow_redirects=False)
    assert response.status_code == 302
    target = urlsplit(response.headers["location"])
    assert target.scheme == "https" and target.netloc == "client.example" and target.path == "/callback"
    params = parse_qs(target.query)
    assert params["error"] == ["access_denied"] and params["state"] == ["client-state"]
    assert "code" not in params
    tokens = oauth.get("/api/v1/tokens", headers=bearer()).json()["items"]
    assert not any(token["name"].startswith("MCP:") for token in tokens)
    assert oauth.post("/oauth2/mcp/authorize", data=form, follow_redirects=False).status_code == 400


def test_failure_during_token_mint_rolls_back_code_consumption(oauth, monkeypatch):
    from koinon.catalog.errors import AccessDenied
    from koinon.tokens.service import PersonalTokenService

    code = parse_qs(urlsplit(consent(oauth).headers["location"]).query)["code"][0]
    service = oauth.native_app.state.context.get_bean(PersonalTokenService)
    original = service.issue_application

    async def fail(*args, **kwargs):
        raise AccessDenied("Membership changed", code="ACCESS_DENIED")

    monkeypatch.setattr(service, "issue_application", fail)
    assert exchange(oauth, code).status_code == 403
    monkeypatch.setattr(service, "issue_application", original)
    assert exchange(oauth, code).status_code == 200


def test_encrypted_mcp_token_rejects_resource_expiry_and_removed_clients(oauth):
    import json

    from pyfly.kernel import UnauthorizedException

    from koinon.mcp_auth.service import MCP_PREFIX, McpOAuthService
    from koinon.mcp_auth.settings import McpOAuthSettings

    code = parse_qs(urlsplit(consent(oauth).headers["location"]).query)["code"][0]
    opaque = exchange(oauth, code).json()["access_token"]
    context = oauth.native_app.state.context
    service = context.get_bean(McpOAuthService)
    settings = context.get_bean(McpOAuthSettings)
    canonical = oauth.portal.call(service.canonical_bearer, opaque)
    assert oauth.portal.call(service.can_request_scopes, canonical, ("knowledge:search",)) is False
    assert oauth.portal.call(service.can_request_scopes, opaque, ("knowledge:search",)) is True
    assert oauth.portal.call(service.can_request_scopes, opaque, ("query:execute",)) is False
    assert oauth.portal.call(service.can_request_scopes, "invalid", ("knowledge:search",)) is False
    fernet = Fernet(settings.encryption_key.encode())
    payload = json.loads(fernet.decrypt(opaque[len(MCP_PREFIX) :].encode()))
    for key, value in (("aud", "https://other.example/mcp"), ("client_id", "unknown"), ("exp", 0)):
        invalid = MCP_PREFIX + fernet.encrypt(json.dumps({**payload, key: value}).encode()).decode()
        with pytest.raises(UnauthorizedException):
            oauth.portal.call(service.canonical_bearer, invalid)
    settings.clients[0]["scopes"] = []
    with pytest.raises(UnauthorizedException):
        oauth.portal.call(service.canonical_bearer, opaque)
    settings.clients.clear()
    with pytest.raises(UnauthorizedException):
        oauth.portal.call(service.canonical_bearer, opaque)


def test_code_expiry_is_rechecked_and_no_plaintext_code_is_persisted(oauth):
    from datetime import UTC, datetime, timedelta

    from koinon.mcp_auth.repositories import McpAuthorizationRepository
    from koinon.mcp_auth.service import digest

    code = parse_qs(urlsplit(consent(oauth).headers["location"]).query)["code"][0]

    async def expire():
        repository = oauth.native_app.state.context.get_bean(McpAuthorizationRepository)
        row = (await repository.find_all(code_hash=digest(code)))[0]
        assert code not in str(row.request_json) and code not in str(row.grant_json)
        assert row.code_hash != code and len(row.code_hash) == 64
        row.expires_at = datetime.now(UTC) - timedelta(seconds=1)
        await repository.save(row)

    oauth.portal.call(expire)
    assert exchange(oauth, code).status_code == 400


def test_confidential_client_requires_hashed_secret_and_rejects_bad_secret(oauth):
    from koinon.mcp_auth.service import digest
    from koinon.mcp_auth.settings import McpOAuthSettings

    settings = oauth.native_app.state.context.get_bean(McpOAuthSettings)
    secret = "c" * 48
    settings.clients[0]["client_secret_hash"] = digest(secret)
    code = parse_qs(urlsplit(consent(oauth).headers["location"]).query)["code"][0]
    assert exchange(oauth, code).status_code == 401
    assert exchange(oauth, code, client_secret="wrong").status_code == 401
    assert exchange(oauth, code, client_secret=secret).status_code == 200


def test_current_membership_revocation_blocks_oauth_canonical_calls(oauth):
    from koinon.catalog.repositories import MembershipRepository
    from koinon.mcp_auth.service import McpOAuthService

    code = parse_qs(urlsplit(consent(oauth).headers["location"]).query)["code"][0]
    opaque = exchange(oauth, code).json()["access_token"]
    context = oauth.native_app.state.context
    canonical = oauth.portal.call(context.get_bean(McpOAuthService).canonical_bearer, opaque)

    async def revoke():
        repository = context.get_bean(MembershipRepository)
        row = await repository.find_by_id("admin")
        row.active = False
        await repository.save(row)

    oauth.portal.call(revoke)
    response = oauth.get("/api/v1/tenants/north/catalog", headers={"Authorization": "Bearer " + canonical})
    assert response.status_code == 401
    authorized = oauth.portal.call(context.get_bean(McpOAuthService).authenticate, opaque)
    import pytest
    from pyfly.security.context_holder import SecurityContextHolder

    from koinon.catalog.errors import AccessDenied

    async def denied():
        with SecurityContextHolder.using(authorized):
            await context.get_bean(McpOAuthService).catalog.authorize(
                ISSUER + "|admin", "north", "catalog:read", oauth.workspace_id
            )

    with pytest.raises(AccessDenied):
        oauth.portal.call(denied)


def test_concurrent_exchange_issues_one_grant(oauth):
    import asyncio

    from koinon.mcp_auth.service import McpOAuthService, OAuthError
    from koinon.tokens.repositories import PersonalTokenRepository

    code = parse_qs(urlsplit(consent(oauth).headers["location"]).query)["code"][0]
    params = {
        "grant_type": "authorization_code",
        "client_id": "test-chat-client",
        "code": code,
        "resource": "http://127.0.0.1:18781/mcp",
        "redirect_uri": "https://client.example/callback",
        "code_verifier": "v" * 43,
    }
    context = oauth.native_app.state.context

    async def compete():
        service = context.get_bean(McpOAuthService)
        results = await asyncio.gather(
            service.exchange(params), service.exchange(params), return_exceptions=True
        )
        assert sum(isinstance(result, dict) for result in results) == 1
        assert sum(isinstance(result, OAuthError) for result in results) == 1
        rows = await context.get_bean(PersonalTokenRepository).find_all(
            name="Test Chat Client", purpose="application"
        )
        assert len(rows) == 1

    oauth.portal.call(compete)


@pytest.fixture
def installation_brand():
    from io import BytesIO

    from PIL import Image

    image = BytesIO()
    Image.new("RGB", (4, 4), "navy").save(image, format="PNG")
    raster = "data:image/png;base64," + base64.b64encode(image.getvalue()).decode("ascii")
    return {
        "product_name": "North knowledge",
        "font_family": "Inter",
        "logo_light": raster,
        "logo_dark": raster,
        "symbol": raster,
        "favicon": raster,
    }


def test_headless_installation_images_are_same_origin_sanitized_assets_not_organization_reads(
    oauth, installation_brand
):
    from unittest.mock import AsyncMock

    from koinon.organization_branding.service import OrganizationBrandingService

    branding = oauth.native_app.state.context.get_bean(OrganizationBrandingService)
    branding.get = AsyncMock(side_effect=AssertionError("Public presentation cannot fetch tenant overrides"))
    page = authorize(oauth)
    assert '<img src="/oauth2/mcp/logo" alt="North knowledge"' in page.text
    assert '<link rel="icon" href="/oauth2/mcp/icon">' in page.text
    for path, field in (("logo", "logo_light"), ("logo-dark", "logo_dark"), ("icon", "favicon")):
        response = oauth.get("/oauth2/mcp/" + path)
        assert response.status_code == 200
        assert response.headers["content-type"] == "image/png"
        assert response.headers["cache-control"] == "no-store"
        assert response.content == base64.b64decode(getattr(branding.defaults, field).split(",", 1)[1])
    branding.get.assert_not_called()
