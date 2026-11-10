# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import asyncio
import hashlib

import httpx
import pytest
from koinon.integrations.content_sources.dtos import Account, SourceScope
from koinon.integrations.content_sources.errors import SourceError
from koinon.integrations.content_sources.microsoft import OneDriveSource
from koinon.integrations.content_sources.transport import SourceTransport, checked_hosts
from pyfly.client import HttpxClientAdapter
from test_remote_sources import Sink, Stream, Tokens, graph_item


async def test_transfer_has_separate_total_deadline_and_native_connect_read_limits():
    seen = []

    class SlowStream(Stream):
        async def __aiter__(self):
            await asyncio.sleep(0.05)
            yield b"abcdef"

    data = SlowStream([])

    def respond(request):
        seen.append(request)
        return httpx.Response(200, stream=data)

    transport = SourceTransport(
        Account("onedrive", "reader"),
        Tokens(),
        host="graph.microsoft.com",
        timeout=0.01,
        connect_timeout=0.2,
        read_timeout=0.3,
        transfer_timeout=1,
        http_client=HttpxClientAdapter(transport=httpx.MockTransport(respond)),
        owns_http_client=True,
    )
    try:
        measured, digest = await transport.transfer(
            "https://graph.microsoft.com/v1.0/drives/d/items/f/content", Sink(), max_bytes=6
        )
    finally:
        await transport.aclose()
    assert measured == 6 and digest == hashlib.sha256(b"abcdef").hexdigest() and data.closed
    assert seen[0].extensions["timeout"] == {"connect": 0.2, "read": 0.3, "write": 0.3, "pool": 0.2}


async def test_total_transfer_deadline_covers_redirect_and_closes_response():
    class SlowStream(Stream):
        async def __aiter__(self):
            await asyncio.Event().wait()
            yield b"unreachable"

    body = SlowStream([])

    def respond(request):
        if request.url.host == "graph.microsoft.com":
            return httpx.Response(302, headers={"location": "https://tenant.sharepoint.com/signed"})
        assert "authorization" not in request.headers
        return httpx.Response(200, stream=body)

    transport = SourceTransport(
        Account("onedrive", "reader"),
        Tokens(),
        host="graph.microsoft.com",
        timeout=1,
        transfer_timeout=0.05,
        download_hosts=frozenset({"tenant.sharepoint.com"}),
        http_client=HttpxClientAdapter(transport=httpx.MockTransport(respond)),
        owns_http_client=True,
    )
    try:
        with pytest.raises(SourceError, match="timeout"):
            await transport.transfer(
                "https://graph.microsoft.com/v1.0/drives/d/items/f/content",
                Sink(),
                max_bytes=6,
                redirects=True,
            )
    finally:
        await transport.aclose()
    assert body.closed


async def test_graph_content_can_stream_directly_without_any_redirect_hosts():
    body = Stream([b"abcdef"])

    def respond(request):
        assert request.url.host == "graph.microsoft.com"
        assert request.headers["authorization"] == "Bearer synthetic-delegated-token"
        return (
            httpx.Response(200, stream=body)
            if request.url.path.endswith("/content")
            else httpx.Response(200, json=graph_item())
        )

    async with OneDriveSource(
        SourceScope(Account("onedrive", "reader"), "drive"),
        Tokens(),
        http_client=HttpxClientAdapter(transport=httpx.MockTransport(respond)),
        owns_http_client=True,
    ) as source:
        item = await source.get_item("f1")
        receipt = await source.download(item, Sink(), max_bytes=6)
        assert receipt.size_bytes == 6 and body.closed


@pytest.mark.parametrize("host", ["*.sharepoint.com", "tenant..sharepoint.com", "-tenant.sharepoint.com"])
def test_download_hosts_are_literal_dns_names_not_wildcard_patterns(host):
    with pytest.raises(ValueError):
        checked_hosts(frozenset({host}))


async def test_composition_passes_installation_deadlines_and_exact_graph_hosts():
    from koinon.integrations.content_sources.browse import PersonalSourceBrowser
    from koinon.integrations.content_sources.settings import ContentSourceSettings

    settings = ContentSourceSettings(
        metadata_timeout_seconds=25,
        connect_timeout_seconds=8,
        read_timeout_seconds=45,
        transfer_timeout_seconds=600,
        microsoft_download_hosts=["tenant.sharepoint.com"],
    )
    browser = PersonalSourceBrowser(None, None, settings)
    account = Account("onedrive", "reader")
    async with browser._discovery(account, Tokens()) as discovery:
        assert discovery._http.timeout == 25 and discovery._http.connect_timeout == 8
    async with browser._source(SourceScope(account, "drive"), Tokens()) as source:
        assert source._http.transfer_timeout == 600 and source._http.read_timeout == 45
        assert source._http.download_hosts == frozenset({"tenant.sharepoint.com"})
    settings.transfer_timeout_seconds = float("inf")
    with pytest.raises(ValueError):
        browser._source(SourceScope(account, "drive"), Tokens())
