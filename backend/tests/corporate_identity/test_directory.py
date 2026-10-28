# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from types import SimpleNamespace

import pytest
from pyfly.kernel import ServiceUnavailableException

from koinon.corporate_identity.directory import NativeCorporateDirectory
from koinon.corporate_identity.dtos import EntraSettings, KeycloakSettings
from koinon.corporate_identity.settings import IdentitySettings


class Response:
    status_code = 200

    def __init__(self, value):
        self.value = value

    def json(self):
        return self.value


async def test_keycloak_complete_pages_use_stable_subject_and_exact_allowlisted_origin():
    directory = NativeCorporateDirectory(IdentitySettings(allowed_provider_hosts=["identity.example.test"]))
    calls = []

    async def request(method, url, **kwargs):
        calls.append((method, url, kwargs))
        if url.endswith("/users/stable%2Fsubject"):
            return Response({"id": "stable/subject", "enabled": True})
        return Response([{"id": "group-1", "name": "Researchers"}])

    directory.http = SimpleNamespace(request_bounded=request)
    settings = KeycloakSettings(
        kind="keycloak",
        issuer="https://identity.example.test/realms/corp",
        client_id="ui",
        directory_client_id="directory",
    )
    result = await directory.observe(settings, "offline-token", "stable/subject")
    assert result.external_subject == "stable/subject" and result.complete is True
    assert result.groups == frozenset({"group-1"})
    assert calls[1][2]["params"] == {"first": 0, "max": 100, "briefRepresentation": "false"}
    assert all(
        call[2]["follow_redirects"] is False and call[2]["max_response_bytes"] == 524288 for call in calls
    )
    assert calls[0][2]["headers"]["Authorization"] == "Bearer offline-token"
    with pytest.raises(ServiceUnavailableException):
        await directory.observe(
            settings.model_copy(update={"issuer": "https://other.test/realms/corp"}),
            "offline-token",
            "stable/subject",
        )
    assert len(calls) == 2


async def test_graph_uses_tenant_bound_stable_object_and_rejects_foreign_next_links():
    directory = NativeCorporateDirectory(IdentitySettings())
    calls = []

    async def request(method, url, **kwargs):
        calls.append(url)
        if "/memberOf/" not in url:
            return Response({"id": "22222222-2222-2222-2222-222222222222", "accountEnabled": True})
        return Response({"value": [{"id": "group-1"}], "@odata.nextLink": "https://evil.test/groups"})

    directory.http = SimpleNamespace(request_bounded=request)
    settings = EntraSettings(kind="entra", tenant_id="11111111-1111-1111-1111-111111111111", client_id="ui")
    with pytest.raises(ServiceUnavailableException):
        await directory.observe(settings, "offline-token", "22222222-2222-2222-2222-222222222222")
    assert len(calls) == 2 and all(url.startswith("https://graph.microsoft.com/v1.0/users/") for url in calls)


async def test_partial_or_disabled_directory_is_not_a_successful_unknown_snapshot():
    directory = NativeCorporateDirectory(IdentitySettings(allowed_provider_hosts=["identity.example.test"]))
    settings = KeycloakSettings(
        kind="keycloak", issuer="https://identity.example.test/realms/corp", client_id="ui"
    )

    async def disabled(method, url, **kwargs):
        return Response({"id": "stable", "enabled": False})

    directory.http = SimpleNamespace(request_bounded=disabled)
    snapshot = await directory.observe(settings, "offline-token", "stable")
    assert snapshot.complete is True and snapshot.groups == frozenset()

    async def unavailable(method, url, **kwargs):
        response = Response({"access_token": "must-not-leak"})
        response.status_code = 403
        return response

    directory.http = SimpleNamespace(request_bounded=unavailable)
    with pytest.raises(ServiceUnavailableException) as caught:
        await directory.observe(settings, "offline-token", "stable")
    assert "must-not-leak" not in str(caught.value)


async def test_directory_group_picker_uses_provider_pagination_and_real_group_names():
    directory = NativeCorporateDirectory(IdentitySettings(allowed_provider_hosts=["identity.example.test"]))
    settings = KeycloakSettings(
        kind="keycloak", issuer="https://identity.example.test/realms/corp", client_id="ui"
    )
    calls = []

    async def request(method, url, **kwargs):
        calls.append(kwargs["params"])
        return Response(
            [
                {"id": f"group-{index}", "name": f"Research team {index}", "path": f"/Research/{index}"}
                for index in range(3)
            ]
        )

    directory.http = SimpleNamespace(request_bounded=request)
    page = await directory.groups(settings, "offline-token", q="Research", limit=2)
    assert len(page["items"]) == 2 and page["next_cursor"] == "2"
    assert page["items"][0]["name"] == "Research team 0"
    assert calls == [
        {
            "search": "Research",
            "first": 0,
            "max": 3,
            "briefRepresentation": "false",
            "populateHierarchy": "false",
        }
    ]


def test_hostname_allowlist_does_not_grant_arbitrary_ports_or_loopback_origins():
    directory = NativeCorporateDirectory(
        IdentitySettings(allowed_provider_hosts=["identity.example.test", "127.0.0.1"])
    )
    for issuer in ("https://identity.example.test:8443/realms/corp", "http://127.0.0.1:18784/realms/corp"):
        with pytest.raises(ServiceUnavailableException):
            directory.keycloak_origin(issuer)
    directory.settings.allowed_provider_origins = ["http://127.0.0.1:18784"]
    assert directory.keycloak_origin("http://127.0.0.1:18784/realms/corp") == (
        "http://127.0.0.1:18784",
        "corp",
    )
