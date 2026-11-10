# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Bounded delegated discovery; no installation identity or directory enumeration."""

from typing import Self
from urllib.parse import urlencode

from pyfly.client.ports.outbound import StreamingHttpClientPort

from koinon.integrations.content_sources.discovery_dtos import DiscoveryCursor, LocationPage, SourceLocation
from koinon.integrations.content_sources.dtos import Account, bounded
from koinon.integrations.content_sources.errors import SourceError
from koinon.integrations.content_sources.parsing import identifier, path_id, rows
from koinon.integrations.content_sources.ports import DelegatedTokenSource
from koinon.integrations.content_sources.transport import SourceTransport, checked_url


class _Discovery:
    host: str

    def __init__(
        self,
        account: Account,
        tokens: DelegatedTokenSource,
        *,
        http_client: StreamingHttpClientPort | None = None,
        owns_http_client: bool = False,
        timeout: float = 30,
        connect_timeout: float = 10,
        read_timeout: float = 30,
        transfer_timeout: float = 900,
    ):
        self.account = account
        self._http = SourceTransport(
            account,
            tokens,
            host=self.host,
            http_client=http_client,
            owns_http_client=owns_http_client,
            timeout=timeout,
            connect_timeout=connect_timeout,
            read_timeout=read_timeout,
            transfer_timeout=transfer_timeout,
        )

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *_):
        await self._http.aclose()

    def _resume(self, cursor: DiscoveryCursor | None, operation: str) -> str | None:
        if cursor is None:
            return None
        if cursor.account != self.account or cursor.operation != operation:
            raise SourceError("invalid_cursor")
        return cursor.token

    def _cursor(self, token, operation: str) -> DiscoveryCursor | None:
        if token is None:
            return None
        try:
            return DiscoveryCursor(self.account, operation, token)
        except (TypeError, ValueError):
            raise SourceError("invalid_response") from None


class GraphDiscovery(_Discovery):
    host = "graph.microsoft.com"

    def __init__(self, account: Account, tokens: DelegatedTokenSource, **kwargs):
        if account.provider not in {"sharepoint", "onedrive"}:
            raise ValueError("Microsoft delegated identity required")
        super().__init__(account, tokens, **kwargs)

    def _link(self, token: str, path: str) -> str:
        checked_url(token, host=self.host, path=path)
        return token

    async def _page(self, path, operation, kind, params, cursor):
        token = self._resume(cursor, operation)
        if token is not None:
            self._link(token, path)
        document = await self._http.json(token or "https://" + self.host + path + "?" + urlencode(params))
        next_cursor = self._cursor(document.get("@odata.nextLink"), operation)
        if next_cursor is not None:
            self._link(next_cursor.token, path)
        result = tuple(
            SourceLocation(
                identifier(row.get("id")),
                identifier(row.get("displayName" if kind == "site" else "name")),
                kind,
            )
            for row in rows(document.get("value"))
        )
        return LocationPage(result, next_cursor)

    async def sites(self, query: str, cursor: DiscoveryCursor | None = None) -> LocationPage:
        if self.account.provider != "sharepoint":
            raise SourceError("unsupported")
        bounded(query, limit=256)
        return await self._page("/v1.0/sites", "sites:" + query, "site", {"search": query}, cursor)

    async def drives(
        self,
        *,
        site_id: str | None = None,
        cursor: DiscoveryCursor | None = None,
    ) -> LocationPage:
        if self.account.provider == "sharepoint":
            if site_id is None:
                raise SourceError("unsupported")
            path = "/v1.0/sites/" + path_id(site_id) + "/drives"
        else:
            if site_id is not None:
                raise SourceError("unsupported")
            path = "/v1.0/me/drives"
        return await self._page(path, path, "drive", {"$top": 200}, cursor)


class GoogleDriveDiscovery(_Discovery):
    host = "www.googleapis.com"

    def __init__(self, account: Account, tokens: DelegatedTokenSource, **kwargs):
        if account.provider != "google_drive":
            raise ValueError("Google delegated identity required")
        super().__init__(account, tokens, **kwargs)

    async def drives(self, cursor: DiscoveryCursor | None = None) -> LocationPage:
        token = self._resume(cursor, "shared-drives")
        params = {"pageSize": 100, "useDomainAdminAccess": "false", "fields": "nextPageToken,drives(id,name)"}
        if token is not None:
            params["pageToken"] = token
        document = await self._http.json("https://" + self.host + "/drive/v3/drives?" + urlencode(params))
        return LocationPage(
            tuple(
                SourceLocation(identifier(row.get("id")), identifier(row.get("name")), "drive")
                for row in rows(document.get("drives"))
            ),
            self._cursor(document.get("nextPageToken"), "shared-drives"),
        )
