# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Account-scoped browse contract; no live provider or import claim."""

import httpx
import pytest
from koinon.integrations.content_sources.dtos import Account
from koinon.integrations.content_sources.errors import SourceError
from pyfly.client import HttpxClientAdapter


class Tokens:
    async def access_token(self, account):
        return "synthetic-" + account.subject


async def test_graph_browse_is_read_only_and_continuation_cannot_switch_account_or_site():
    from koinon.integrations.content_sources.discovery import GraphDiscovery

    first = Account("sharepoint", "reader", "tenant")
    seen = []

    def respond(request):
        seen.append(request)
        assert request.method == "GET"
        assert request.headers["authorization"] == "Bearer synthetic-reader"
        if request.url.path == "/v1.0/sites":
            assert request.url.params["search"] == "Research & Finance"
            return httpx.Response(200, json={"value": [{"id": "site-1", "displayName": "Research"}]})
        assert request.url.path == "/v1.0/sites/site-1/drives"
        return httpx.Response(
            200,
            json={
                "value": [{"id": "drive-1", "name": "Documents"}],
                "@odata.nextLink": "https://graph.microsoft.com/v1.0/sites/site-1/drives?$skiptoken=next",
            },
        )

    client = HttpxClientAdapter(transport=httpx.MockTransport(respond), trust_env=False)
    async with GraphDiscovery(first, Tokens(), http_client=client, owns_http_client=True) as browse:
        sites = await browse.sites("Research & Finance")
        assert [(site.id, site.name) for site in sites.items] == [("site-1", "Research")]
        page = await browse.drives(site_id="site-1")
        assert [(drive.id, drive.name) for drive in page.items] == [("drive-1", "Documents")]
        with pytest.raises(SourceError, match="invalid_cursor"):
            await browse.drives(site_id="site-2", cursor=page.next_cursor)
        other = GraphDiscovery(Account("sharepoint", "other", "tenant"), Tokens(), http_client=client)
        with pytest.raises(SourceError, match="invalid_cursor"):
            await other.drives(site_id="site-1", cursor=page.next_cursor)
        assert len(seen) == 2


async def test_onedrive_browse_cannot_search_sharepoint_or_supply_foreign_user():
    from koinon.integrations.content_sources.discovery import GraphDiscovery

    def respond(request):
        assert request.url.path == "/v1.0/me/drives"
        return httpx.Response(200, json={"value": [{"id": "personal", "name": "My files"}]})

    async with GraphDiscovery(
        Account("onedrive", "reader", "consumers"),
        Tokens(),
        http_client=HttpxClientAdapter(transport=httpx.MockTransport(respond), trust_env=False),
        owns_http_client=True,
    ) as browse:
        assert (await browse.drives()).items[0].id == "personal"
        with pytest.raises(SourceError, match="unsupported"):
            await browse.sites("company")
        with pytest.raises(SourceError, match="unsupported"):
            await browse.drives(site_id="foreign")


async def test_google_shared_drive_browse_does_not_request_domain_admin_access():
    from koinon.integrations.content_sources.discovery import GoogleDriveDiscovery

    def respond(request):
        assert request.method == "GET"
        assert request.url.path == "/drive/v3/drives"
        assert request.url.params["useDomainAdminAccess"] == "false"
        assert request.url.params["pageSize"] == "100"
        return httpx.Response(
            200, json={"drives": [{"id": "shared-1", "name": "Evidence"}], "nextPageToken": "next"}
        )

    async with GoogleDriveDiscovery(
        Account("google_drive", "reader"),
        Tokens(),
        http_client=HttpxClientAdapter(transport=httpx.MockTransport(respond), trust_env=False),
        owns_http_client=True,
    ) as browse:
        page = await browse.drives()
        assert page.items[0].id == "shared-1"
        assert page.next_cursor.account == Account("google_drive", "reader")


@pytest.mark.parametrize(
    "url",
    [
        "https://attacker.example/sites/site-1/drives?token=private",
        "https://graph.microsoft.com/v1.0/sites/site-2/drives?token=private",
        "https://graph.microsoft.com/v1.0/me/messages?token=private",
    ],
)
async def test_graph_discovery_rejects_provider_supplied_cross_resource_continuation(url):
    from koinon.integrations.content_sources.discovery import GraphDiscovery

    async with GraphDiscovery(
        Account("sharepoint", "reader", "tenant"),
        Tokens(),
        http_client=HttpxClientAdapter(
            transport=httpx.MockTransport(
                lambda request: httpx.Response(
                    200,
                    json={"value": [], "@odata.nextLink": url},
                )
            ),
            trust_env=False,
        ),
        owns_http_client=True,
    ) as browse:
        with pytest.raises(SourceError, match="unsafe_url"):
            await browse.drives(site_id="site-1")


@pytest.mark.parametrize("provider", ["sharepoint", "onedrive"])
async def test_graph_root_resolves_stable_item_id_without_weakening_item_lookup(provider):
    from koinon.integrations.content_sources.dtos import SourceScope
    from koinon.integrations.content_sources.microsoft import OneDriveSource, SharePointSource

    def respond(request):
        assert request.method == "GET" and request.url.path == "/v1.0/drives/drive-1/root"
        return httpx.Response(
            200,
            json={
                "id": "stable-root",
                "name": "Documents",
                "folder": {},
                "parentReference": {"driveId": "drive-1"},
            },
        )

    adapter = SharePointSource if provider == "sharepoint" else OneDriveSource
    async with adapter(
        SourceScope(Account(provider, "reader", "tenant"), "drive-1"),
        Tokens(),
        http_client=HttpxClientAdapter(transport=httpx.MockTransport(respond), trust_env=False),
        owns_http_client=True,
    ) as source:
        root = await source.root()
        assert root.item_id == "stable-root" and root.kind == "folder"


@pytest.mark.parametrize("drive", ["my-drive", "shared-1"])
async def test_google_root_alias_only_resolved_by_explicit_root_operation(drive):
    from koinon.integrations.content_sources.dtos import SourceScope
    from koinon.integrations.content_sources.google_drive import GoogleDriveSource

    def respond(request):
        assert request.method == "GET"
        assert request.url.path == "/drive/v3/files/" + ("root" if drive == "my-drive" else drive)
        document = {
            "id": "stable-root" if drive == "my-drive" else drive,
            "name": "My files",
            "mimeType": "application/vnd.google-apps.folder",
        }
        if drive != "my-drive":
            document["driveId"] = drive
        return httpx.Response(200, json=document)

    async with GoogleDriveSource(
        SourceScope(Account("google_drive", "reader"), drive),
        Tokens(),
        http_client=HttpxClientAdapter(transport=httpx.MockTransport(respond), trust_env=False),
        owns_http_client=True,
    ) as source:
        root = await source.root()
        assert root.item_id == ("stable-root" if drive == "my-drive" else drive)
        if drive == "my-drive":
            with pytest.raises(SourceError, match="unavailable"):
                await source.get_item("root")
