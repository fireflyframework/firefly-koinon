# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from contextlib import asynccontextmanager

import httpx
import pytest
from koinon.integrations.content_sources.discovery import GoogleDriveDiscovery
from koinon.integrations.content_sources.errors import SourceError
from pyfly.client import HttpxClientAdapter
from test_connection_lifecycle import begin, complete
from test_connection_lifecycle import lifecycle as lifecycle


async def test_personal_browse_uses_reader_grant_and_opaque_bound_continuation(lifecycle, monkeypatch):
    from koinon.integrations.content_sources.browse import PersonalSourceBrowser

    connections, _, _, context = lifecycle
    start, state = await begin(connections)
    await complete(connections, start, state)
    browser = context.get_bean(PersonalSourceBrowser)
    seen = []

    def respond(request):
        seen.append(request)
        assert request.headers["authorization"] == "Bearer access-one"
        return httpx.Response(
            200,
            json={
                "drives": [{"id": "drive", "name": "Research"}],
                "nextPageToken": "private-provider-cursor",
            },
        )

    @asynccontextmanager
    async def discovery(account, tokens):
        async with GoogleDriveDiscovery(
            account,
            tokens,
            http_client=HttpxClientAdapter(transport=httpx.MockTransport(respond), trust_env=False),
            owns_http_client=True,
        ) as adapter:
            yield adapter

    monkeypatch.setattr(browser, "_discovery", discovery)
    page = await browser.drives("issuer|alice", "tenant", start.connection_id)
    assert page.items[0].id == "drive"
    assert page.next_cursor and "private-provider-cursor" not in page.next_cursor
    await browser.drives("issuer|alice", "tenant", start.connection_id, cursor=page.next_cursor)
    assert seen[1].url.params["pageToken"] == "private-provider-cursor"
    with pytest.raises(SourceError):
        await browser.drives("issuer|bob", "tenant", start.connection_id, cursor=page.next_cursor)
    other, state = await begin(connections)
    await complete(connections, other, state)
    with pytest.raises(SourceError):
        await browser.drives("issuer|alice", "tenant", other.connection_id, cursor=page.next_cursor)
    with pytest.raises(SourceError):
        await browser.drives(
            "issuer|alice", "tenant", start.connection_id, cursor=page.next_cursor[:-2] + "AA"
        )
    assert len(seen) == 2


async def test_disconnect_during_remote_browse_suppresses_returned_metadata(lifecycle, monkeypatch):
    from koinon.integrations.content_sources.browse import PersonalSourceBrowser

    connections, _, _, context = lifecycle
    start, state = await begin(connections)
    connected = await complete(connections, start, state)
    browser = context.get_bean(PersonalSourceBrowser)

    async def respond(request):
        await connections.disconnect("issuer|alice", "tenant", start.connection_id, connected.revision)
        return httpx.Response(200, json={"drives": [{"id": "private", "name": "No longer readable"}]})

    @asynccontextmanager
    async def discovery(account, tokens):
        async with GoogleDriveDiscovery(
            account,
            tokens,
            http_client=HttpxClientAdapter(transport=httpx.MockTransport(respond), trust_env=False),
            owns_http_client=True,
        ) as adapter:
            yield adapter

    monkeypatch.setattr(browser, "_discovery", discovery)
    with pytest.raises(SourceError):
        await browser.drives("issuer|alice", "tenant", start.connection_id)
