# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""A directory connection is optional; signed native login and local authority are not."""

import importlib.util
import time
from datetime import UTC, datetime, timedelta
from functools import partial
from pathlib import Path
from unittest.mock import AsyncMock
from urllib.parse import parse_qs, urlencode, urlsplit

import jwt
import pytest
from mcp.types import CLIENT_CAPABILITIES_META_KEY, PROTOCOL_VERSION_META_KEY
from pyfly.kernel import ServiceUnavailableException

from koinon.bootstrap.dtos import BootstrapSeedInput
from koinon.bootstrap.service import BootstrapGrants
from koinon.catalog.repositories import MembershipRepository
from koinon.corporate_identity.directory import NativeCorporateDirectory
from koinon.corporate_identity.dtos import IdentityProviderInput
from koinon.corporate_identity.entities import CorporateMapping
from koinon.corporate_identity.policy import DirectorySnapshot
from koinon.corporate_identity.repositories import (
    CorporateGrantRepository,
    CorporateMappingRepository,
    CorporateProviderRepository,
)
from koinon.corporate_identity.service import CorporateIdentityService
from koinon.security.oidc import VerifiedOidcLoginHandler

TID = "00000000-0000-4000-8000-000000000001"
ISSUER = f"https://login.microsoftonline.com/{TID}/v2.0"
spec = importlib.util.spec_from_file_location(
    "optional_directory_native_http", Path(__file__).parents[1] / "web/conftest.py"
)
assert spec and spec.loader
native = importlib.util.module_from_spec(spec)
spec.loader.exec_module(native)
native.ISSUER = ISSUER


@pytest.fixture
def client(tmp_path, monkeypatch, request):
    import koinon.app

    original = koinon.app.create_application

    def configured(values):
        values["koinon"]["knowledge"] = {"enabled": True}
        values["koinon"]["mcp"] = {
            "enabled": True,
            "public_url": "http://127.0.0.1:18781/mcp",
            "allowed_hosts": ["testserver"],
        }
        return original(values)

    monkeypatch.setattr(koinon.app, "create_application", configured)
    denied = AsyncMock(side_effect=AssertionError("No Graph grant or directory request in first start"))
    monkeypatch.setattr(NativeCorporateDirectory, "acquire", denied)
    monkeypatch.setattr(NativeCorporateDirectory, "_json", denied)
    yield from native.client.__wrapped__(tmp_path, monkeypatch, request)
    denied.assert_not_called()


def signed_login(client, monkeypatch, subject, oid):
    response = client.get("/oauth2/authorization/koinon", follow_redirects=False)
    assert response.status_code == 302, response.text
    query = parse_qs(urlsplit(response.headers["location"]).query)

    async def exchange(*args):
        return {
            "access_token": "inert-not-a-graph-credential",
            "id_token": jwt.encode(
                dict(
                    iss=ISSUER,
                    sub=subject,
                    tid=TID,
                    oid=oid,
                    aud="browser",
                    azp="browser",
                    nonce=query["nonce"][0],
                    exp=int(time.time()) + 300,
                ),
                native.KEY,
                algorithm="RS256",
                headers={"kid": "local-key"},
            ),
        }

    async def userinfo(*args):
        pytest.fail("Userinfo cannot supply native bootstrap identity")

    monkeypatch.setattr(VerifiedOidcLoginHandler, "_exchange_code", exchange)
    monkeypatch.setattr(VerifiedOidcLoginHandler, "_fetch_user_info", userinfo)
    response = client.get(
        "/login/oauth2/code/koinon?" + urlencode(dict(state=query["state"][0], code="inert", iss=ISSUER)),
        follow_redirects=False,
    )
    assert response.status_code == 302, response.text
    me = client.get("/auth/me")
    assert me.status_code == 200 and me.json()["subject"] == ISSUER + "|" + subject


def test_full_native_start_three_signed_admins_knowledge_chat_and_mcp_without_directory(client, monkeypatch):
    context = client.native_app.state.context
    assert client.get("/health").status_code == 200
    ready = client.get("/ready")
    assert ready.status_code == 200 and ready.json()["status"] == "ready"
    objects = [f"00000000-0000-4000-8000-{index:012}" for index in (2, 3, 4)]
    value = BootstrapSeedInput.model_validate(
        dict(
            issuer=ISSUER,
            client_id="browser",
            entra_tenant_id=TID,
            grants=[
                dict(object_id=oid, role="admin", expires_at=datetime.now(UTC) + timedelta(days=1))
                for oid in objects
            ],
        )
    )
    client.portal.call(context.get_bean(BootstrapGrants).seed, "new-org", "New organization", value)
    for index, oid in enumerate(objects):
        client.cookies.clear()
        signed_login(client, monkeypatch, f"pairwise-{index}", oid)
    rows = client.portal.call(partial(context.get_bean(MembershipRepository).find_all, tenant_id="new-org"))
    assert len(rows) == 3 and all(row.role == "admin" and row.active for row in rows)
    assert {row.subject for row in rows} == {ISSUER + f"|pairwise-{index}" for index in range(3)}
    assert not any(row.subject.endswith(oid) for row in rows for oid in objects)
    assert client.portal.call(context.get_bean(CorporateProviderRepository).find_all) == []
    client.cookies.clear()
    headers = native.bearer()
    assert client.get("/api/v1/context", headers=headers).status_code == 200
    assert client.get("/api/v1/tenants/north/catalog", headers=headers).status_code == 200
    member = client.post(
        "/api/v1/tenants/new-org/members",
        headers=native.bearer("pairwise-0"),
        json={
            "subject": ISSUER + "|manual-person",
            "role": "viewer",
        },
    )
    assert member.status_code == 201, member.text
    path = "/api/v1/tenants/new-org/members/" + member.json()["id"]
    assert client.patch(path, headers=native.bearer("pairwise-0"), json={"role": "editor"}).status_code == 200
    assert client.delete(path, headers=native.bearer("pairwise-0")).status_code == 204
    providers = client.get("/api/v1/tenants/north/communications/recipient-providers", headers=headers)
    assert providers.status_code == 200 and providers.json()["items"] == []
    unavailable = client.get("/api/v1/tenants/north/communications/recipients?q=Person", headers=headers)
    assert unavailable.status_code == 400 and "RECIPIENT_PROVIDER_REQUIRED" in unavailable.text
    chat = client.post("/api/v1/tenants/north/chat/threads", headers=headers, json={"title": "Local chat"})
    assert chat.status_code == 201, chat.text
    assert client.get("/api/v1/tenants/north/chat/threads", headers=headers).status_code == 200
    pat = client.post(
        "/api/v1/tokens",
        headers=headers,
        json={
            "name": "Owned MCP test",
            "tenant_id": "north",
            "scopes": ["catalog:read"],
            "expires_at": (datetime.now(UTC) + timedelta(hours=1)).isoformat(),
        },
    )
    assert pat.status_code == 201, pat.text
    client.cookies.clear()
    response = client.post(
        "/mcp",
        headers={
            "Accept": "application/json, text/event-stream",
            "Authorization": "Bearer " + pat.json()["token"],
            "MCP-Protocol-Version": "2026-07-28",
            "MCP-Method": "tools/call",
            "MCP-Name": "koinon_context",
        },
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": "koinon_context",
                "arguments": {},
                "_meta": {
                    PROTOCOL_VERSION_META_KEY: "2026-07-28",
                    CLIENT_CAPABILITIES_META_KEY: {},
                },
            },
        },
    )
    assert response.status_code == 200, response.text
    assert response.json()["result"]["isError"] is False


def test_draft_then_disabled_directory_never_becomes_login_or_local_access_prerequisite(client, monkeypatch):
    context = client.native_app.state.context
    service = context.get_bean(CorporateIdentityService)
    body = IdentityProviderInput.model_validate(
        dict(
            kind="entra",
            name="Optional directory",
            settings=dict(kind="entra", tenant_id=TID, client_id="browser", identity_mode="direct"),
        )
    )
    created = client.portal.call(service.create, ISSUER + "|admin", "north", body)
    assert created.status == "draft"
    signed_login(client, monkeypatch, "admin", "00000000-0000-4000-8000-000000000099")
    client.cookies.clear()
    assert client.get("/api/v1/context", headers=native.bearer()).status_code == 200
    disabled = client.portal.call(
        partial(service.disable, ISSUER + "|admin", "north", created.id, expected_revision=1)
    )
    assert disabled.status == "disabled"
    signed_login(client, monkeypatch, "admin", "00000000-0000-4000-8000-000000000099")


def test_later_active_directory_grants_fail_closed_when_graph_becomes_unavailable(client, monkeypatch):
    context = client.native_app.state.context
    providers = context.get_bean(CorporateProviderRepository)
    grants = context.get_bean(CorporateGrantRepository)

    async def configured_policy():
        # Stored fixture policy represents an already validated connection; no activation API is bypassed.
        service = context.get_bean(CorporateIdentityService)
        provider = await service.create(
            ISSUER + "|admin",
            "north",
            IdentityProviderInput.model_validate(
                dict(
                    kind="entra",
                    name="Previously validated directory",
                    settings=dict(kind="entra", tenant_id=TID, client_id="browser", identity_mode="direct"),
                )
            ),
        )
        row = await providers.find_by_id(provider.id)
        row.status = "active"
        await providers.save(row)
        await context.get_bean(CorporateMappingRepository).save(
            CorporateMapping(
                id="owned-directory-rule",
                tenant_id="north",
                provider_id=provider.id,
                group_id="research",
                group_name="Research",
                role="editor",
                enabled=True,
                revision=1,
            )
        )

    client.portal.call(configured_policy)
    directory = context.get_bean(NativeCorporateDirectory)
    acquire = AsyncMock(return_value="owned-fixture-no-real-graph-token")

    async def observe(settings, token, external):
        now = datetime.now(UTC)
        return DirectorySnapshot(external, frozenset({"research"}), True, now, now + timedelta(seconds=60))

    monkeypatch.setattr(directory, "acquire", acquire)
    monkeypatch.setattr(directory, "observe", observe)
    signed_login(client, monkeypatch, "researcher", "00000000-0000-4000-8000-000000000098")
    client.cookies.clear()
    response = client.get("/api/v1/context", headers=native.bearer("researcher"))
    assert response.status_code == 200 and any(row["id"] == "north" for row in response.json()["tenants"])

    async def expire():
        row = (await grants.find_all(subject=ISSUER + "|researcher"))[0]
        row.expires_at = datetime.now(UTC) - timedelta(seconds=1)
        await grants.save(row)

    client.portal.call(expire)
    acquire.side_effect = ServiceUnavailableException("Owned Graph403 fixture", code="DIRECTORY_UNAVAILABLE")
    response = client.get("/api/v1/context", headers=native.bearer("researcher"))
    assert response.status_code == 200 and response.json()["tenants"] == []
    assert all(not row.active for row in client.portal.call(grants.find_all))
    assert client.get("/api/v1/context", headers=native.bearer()).status_code == 200
    signed_login(client, monkeypatch, "admin", "00000000-0000-4000-8000-000000000099")
    client.cookies.clear()
    assert client.get("/api/v1/tenants/north/catalog", headers=native.bearer()).status_code == 200
    assert acquire.await_count >= 2
