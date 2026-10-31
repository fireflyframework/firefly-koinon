# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest
from pyfly.client import HttpxClientAdapter

from koinon.corporate_identity.directory import NativeCorporateDirectory
from koinon.corporate_identity.dtos import EntraSettings, GoogleWorkspaceSettings, KeycloakSettings
from koinon.corporate_identity.settings import IdentitySettings
from koinon.corporate_profiles.directory import CorporateProfileDirectory
from koinon.corporate_profiles.dtos import CorporateProfileSyncPolicy, KeycloakProfileAttributes
from koinon.corporate_profiles.settings import CorporateProfileSettings


@pytest.mark.parametrize(
    "url",
    [
        "https://photos.example.evil/people/user.png",
        "https://photos.example/people/../admin",
        "https://photos.example/people/%2e%2e/admin",
        "https://photos.example/people/%252e%252e/admin",
        "https://user:password@photos.example/people/user.png",
        "https://photos.example/people/user.png#fragment",
        "http://photos.example/people/user.png",
        "https://photos.example/people/user.png?token=secret",
    ],
)
def test_photo_policy_denies_unadmitted_urls(url):
    settings = CorporateProfileSettings(photo_origins={"https://photos.example": ["/people/"]})
    assert not settings.photo_url(url)


@pytest.mark.asyncio
async def test_keycloak_photo_uses_separate_anonymous_bounded_nonredirect_client(monkeypatch):
    from koinon.corporate_profiles import directory as module

    recorded = []

    def upstream(request):
        assert request.headers["authorization"] == "Bearer inert-directory-token"
        return httpx.Response(
            200,
            json={
                "id": "user",
                "enabled": True,
                "firstName": "Company",
                "attributes": {"picture": ["https://photos.example/people/user.png"]},
            },
        )

    def photo(request):
        recorded.append(request)
        assert "authorization" not in request.headers
        assert "cookie" not in request.headers
        return httpx.Response(200, content=b"bounded bytes", headers={"Set-Cookie": "ignored=value"})

    native = NativeCorporateDirectory.__new__(NativeCorporateDirectory)
    native.settings = IdentitySettings(allowed_provider_origins=["https://identity.example"])
    native.http = HttpxClientAdapter(
        transport=httpx.MockTransport(upstream), owns_transport=True, trust_env=False
    )
    native.acquire = AsyncMock(return_value="inert-directory-token")

    def anonymous(**kwargs):
        assert kwargs["trust_env"] is False and kwargs["follow_redirects"] is False
        return HttpxClientAdapter(transport=httpx.MockTransport(photo), owns_transport=True, trust_env=False)

    monkeypatch.setattr(module, "HttpxClientAdapter", anonymous)
    try:
        service = CorporateProfileDirectory(
            native, CorporateProfileSettings(photo_origins={"https://photos.example": ["/people/"]})
        )
        settings = KeycloakSettings(
            kind="keycloak", issuer="https://identity.example/realms/company", client_id="client"
        )
        result = await service.observe(
            settings,
            None,
            CorporateProfileSyncPolicy(keycloak_attributes=KeycloakProfileAttributes(picture="picture")),
            "user",
        )
        assert result.fields["avatar"].value == b"bounded bytes"
        assert len(recorded) == 1
    finally:
        await native.http.stop()


@pytest.mark.asyncio
async def test_entra_never_attempts_app_only_manager_endpoint_or_follows_photo_redirect():
    paths = []
    oid = "22222222-2222-4222-8222-222222222222"

    def respond(request):
        paths.append(request.url.path)
        if request.url.path.endswith("/photo/$value"):
            return httpx.Response(302, headers={"Location": "https://untrusted.example/image"})
        return httpx.Response(
            200,
            json={
                "id": oid,
                "accountEnabled": True,
                "displayName": "Company",
                "jobTitle": None,
                "department": None,
            },
        )

    native = SimpleNamespace(
        http=HttpxClientAdapter(transport=httpx.MockTransport(respond), owns_transport=True, trust_env=False),
        acquire=AsyncMock(return_value="inert"),
    )
    try:
        settings = EntraSettings(
            kind="entra", tenant_id="11111111-1111-4111-8111-111111111111", client_id="client"
        )
        result = await CorporateProfileDirectory(native, CorporateProfileSettings()).observe(
            settings, None, CorporateProfileSyncPolicy(manager_source="directory"), oid
        )
        assert result.fields["manager"].status == "unsupported"
        assert result.fields["avatar"].status == "unavailable"
        assert len(paths) == 2 and all("/manager" not in path for path in paths)
    finally:
        await native.http.stop()


@pytest.mark.asyncio
async def test_google_manager_resolution_cannot_cross_directory_customer():
    def respond(request):
        if request.url.path.endswith("/photos/thumbnail"):
            return httpx.Response(404)
        if request.url.path.endswith("/user"):
            return httpx.Response(
                200,
                json={
                    "id": "user",
                    "customerId": "C001",
                    "suspended": False,
                    "name": {"fullName": "Company"},
                    "organizations": [],
                    "relations": [{"type": "manager", "value": "manager@example.org"}],
                },
            )
        return httpx.Response(200, json={"id": "manager", "customerId": "C002", "suspended": False})

    native = SimpleNamespace(
        http=HttpxClientAdapter(transport=httpx.MockTransport(respond), owns_transport=True, trust_env=False),
        acquire=AsyncMock(return_value="inert"),
    )
    try:
        settings = GoogleWorkspaceSettings(
            kind="google_workspace", client_id="client", hosted_domains=["example.org"], customer_id="C001"
        )
        result = await CorporateProfileDirectory(native, CorporateProfileSettings()).observe(
            settings, None, CorporateProfileSyncPolicy(manager_source="directory"), "user"
        )
        assert result.fields["manager"].status == "unavailable"
        assert result.fields["manager"].value is None
        assert result.fields["avatar"].status == "empty"
    finally:
        await native.http.stop()
