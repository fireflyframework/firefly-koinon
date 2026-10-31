# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import json

import httpx
import pytest

from koinon_sdk import KoinonClient

METHODS = (
    "mcp_oauth_clients_readiness",
    "mcp_oauth_clients",
    "create_mcp_oauth_client",
    "mcp_oauth_client",
    "update_mcp_oauth_client",
    "rotate_mcp_oauth_client_secret",
    "organization_mcp_connection",
)


@pytest.mark.parametrize("name", METHODS)
def test_all_organization_oauth_operations_are_explicit_and_typed(name):
    assert callable(getattr(KoinonClient, name, None))


async def test_registry_operations_preserve_tenant_revision_filters_and_one_time_credentials():
    from koinon_sdk import McpOAuthClientInput, McpOAuthClientPatch, McpOAuthClientRevision

    value = {
        "id": "row/one",
        "tenant_id": "north/team",
        "client_id": "koinon_org_owned",
        "name": "Research client",
        "client_type": "confidential",
        "redirect_uris": ["https://client.example/callback"],
        "scopes": ["catalog:read", "knowledge:search"],
        "enabled": True,
        "revision": 2,
        "created_at": "2026-10-29T00:00:00Z",
        "updated_at": "2026-10-29T01:00:00Z",
        "created_by": "issuer|admin",
        "updated_by": "issuer|admin",
    }
    descriptor = {
        "enabled": True,
        "endpoint": "https://organization.example/mcp",
        "authentication": ["oauth"],
        "oauth_enabled": True,
        "oauth_registration": "pre_registered",
        "supported_scopes": ["catalog:read"],
        "tools": [],
        "review": {"supported": True},
    }
    seen = []

    def handle(request):
        body = json.loads(request.content) if request.content else None
        seen.append(
            (request.method, request.url.raw_path.decode().split("?")[0], dict(request.url.params), body)
        )
        if request.url.path.endswith("/connection"):
            response = descriptor
        elif request.url.path.endswith("/readiness"):
            response = {
                "ready": True,
                "endpoint_enabled": True,
                "oauth_enabled": True,
                "encryption_configured": True,
                "missing_configuration": [],
            }
        elif request.method == "POST":
            response = {"client": value, "client_secret": "owned-secret-once"}
        elif request.url.path.endswith("/oauth-clients"):
            response = {"items": [value], "total": 1, "page": 2, "page_size": 10, "pages": 2}
        else:
            response = value
        return httpx.Response(200, json=response)

    async with KoinonClient(
        "https://organization.example/api/v1",
        token_provider=lambda: "owned-identity",
        transport=httpx.MockTransport(handle),
    ) as client:
        assert (await client.mcp_connection()).enabled
        assert (await client.organization_mcp_connection("north/team")).enabled
        assert (await client.mcp_oauth_clients_readiness("north/team")).ready
        page = await client.mcp_oauth_clients(
            "north/team",
            q="Research",
            status="enabled",
            page=2,
            page_size=10,
            sort="updated_at",
            order="desc",
        )
        assert page.items[0].client_id == "koinon_org_owned"
        issued = await client.create_mcp_oauth_client(
            "north/team",
            McpOAuthClientInput(
                name="Research client",
                client_type="confidential",
                redirect_uris=["https://client.example/callback"],
                scopes=["catalog:read", "knowledge:search"],
            ),
        )
        assert issued.client_secret == "owned-secret-once"
        assert "owned-secret-once" not in repr(issued)
        detail = await client.mcp_oauth_client("north/team", "row/one")
        assert "client_secret" not in detail.model_dump()
        await client.update_mcp_oauth_client(
            "north/team", "row/one", McpOAuthClientPatch(expected_revision=1, enabled=False)
        )
        await client.rotate_mcp_oauth_client_secret(
            "north/team", "row/one", McpOAuthClientRevision(expected_revision=2)
        )
    prefix = "/api/v1/tenants/north%2Fteam/mcp"
    assert [row[:2] for row in seen] == [
        ("GET", "/api/v1/mcp/connection"),
        ("GET", prefix + "/connection"),
        ("GET", prefix + "/oauth-clients/readiness"),
        ("GET", prefix + "/oauth-clients"),
        ("POST", prefix + "/oauth-clients"),
        ("GET", prefix + "/oauth-clients/row%2Fone"),
        ("PATCH", prefix + "/oauth-clients/row%2Fone"),
        ("POST", prefix + "/oauth-clients/row%2Fone/rotate-secret"),
    ]
    assert seen[3][2] == {
        "q": "Research",
        "status": "enabled",
        "page": "2",
        "page_size": "10",
        "sort": "updated_at",
        "order": "desc",
    }
    assert seen[6][3] == {"expected_revision": 1, "enabled": False}
    assert seen[7][3] == {"expected_revision": 2}


def test_oauth_inputs_reject_unsupported_scopes_injected_secrets_and_noninteger_revisions():
    from pydantic import ValidationError

    from koinon_sdk import McpOAuthClientInput, McpOAuthClientRevision

    values = {
        "name": "Client",
        "client_type": "public",
        "redirect_uris": ["https://client.example/callback"],
        "scopes": ["catalog:read"],
    }
    for changes in ({"scopes": ["identity:manage"]}, {"client_secret": "injected"}, {"tenant_id": "other"}):
        with pytest.raises(ValidationError):
            McpOAuthClientInput.model_validate({**values, **changes})
    for revision in (True, "1", 0):
        with pytest.raises(ValidationError):
            McpOAuthClientRevision(expected_revision=revision)
