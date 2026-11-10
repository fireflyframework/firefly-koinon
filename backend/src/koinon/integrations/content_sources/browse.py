# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Personal source browsing with current authority and opaque scoped continuation."""

import base64
import json
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime, timedelta

from pyfly.container import service

from koinon.integrations.content_sources.credentials import SourceCredentialVault
from koinon.integrations.content_sources.discovery import GoogleDriveDiscovery, GraphDiscovery
from koinon.integrations.content_sources.discovery_dtos import DiscoveryCursor, SourceLocation
from koinon.integrations.content_sources.dtos import Account, Cursor, RemoteItem, SourceScope, bounded
from koinon.integrations.content_sources.errors import SourceError
from koinon.integrations.content_sources.google_drive import GoogleDriveSource
from koinon.integrations.content_sources.lifecycle import SourceConnectionService, SourceReadGrant
from koinon.integrations.content_sources.microsoft import OneDriveSource, SharePointSource
from koinon.integrations.content_sources.parsing import path_id
from koinon.integrations.content_sources.settings import ContentSourceSettings


@dataclass(frozen=True, slots=True)
class Locations:
    items: tuple[SourceLocation, ...]
    next_cursor: str | None = field(repr=False)


@dataclass(frozen=True, slots=True)
class FolderItems:
    folder: RemoteItem
    items: tuple[RemoteItem, ...]
    next_cursor: str | None = field(repr=False)


class _ReaderTokens:
    def __init__(
        self, connections: SourceConnectionService, actor: str, tenant: str, identifier: str, account: Account
    ):
        self.connections, self.actor, self.tenant = connections, actor, tenant
        self.identifier, self.account = identifier, account
        self.grant: SourceReadGrant | None = None

    async def access_token(self, account: Account) -> str:
        if account != self.account:
            raise SourceError("access_denied")
        grant = self.grant
        if grant is None:
            grant = await self.connections.read_grant(self.actor, self.tenant, self.identifier, account)
            self.grant = grant
        return grant.token


@service(name="content_sources.browser")
class PersonalSourceBrowser:
    def __init__(
        self,
        connections: SourceConnectionService,
        vault: SourceCredentialVault,
        settings: ContentSourceSettings,
    ):
        self.connections, self.vault = connections, vault
        self.settings = settings

    def _discovery(self, account, tokens):
        adapter = GoogleDriveDiscovery if account.provider == "google_drive" else GraphDiscovery
        return adapter(account, tokens, **self.settings.transport_options())

    def _source(self, scope, tokens):
        adapters = {
            "google_drive": GoogleDriveSource,
            "onedrive": OneDriveSource,
            "sharepoint": SharePointSource,
        }
        options = self.settings.transport_options()
        if scope.account.provider == "google_drive":
            return GoogleDriveSource(scope, tokens, **options)
        return adapters[scope.account.provider](
            scope, tokens, **options, download_hosts=frozenset(self.settings.microsoft_download_hosts)
        )

    async def _reader(self, actor, tenant, identifier):
        connection = await self.connections.connected(actor, tenant, identifier)
        if connection.account is None:
            raise SourceError("reconnect_required")
        tokens = _ReaderTokens(self.connections, actor, tenant, identifier, connection.account)
        await tokens.access_token(connection.account)
        return connection.account, tokens

    async def _confirm(self, actor, tenant, identifier, account, tokens):
        current = await self.connections.connected(actor, tenant, identifier)
        if current.account != account or tokens.grant is None:
            raise SourceError("access_denied")
        await self.connections.confirm_read_grant(actor, tenant, identifier, tokens.grant)

    @staticmethod
    def _authority(tokens):
        grant = tokens.grant
        if grant is None:
            raise SourceError("access_denied")
        return [grant.revision, grant.config_fingerprint, list(grant.scopes)]

    def _open(self, actor, tenant, identifier, account, operation, cursor, tokens):
        if cursor is None:
            return None
        try:
            encoded = bounded(cursor, limit=65536).encode("ascii")
            envelope = base64.b64decode(encoded, altchars=b"-_", validate=True)
            value = self.vault.decrypt(tenant, actor, identifier, "browse-cursor", envelope)
            if (
                value["operation"] != operation
                or value["account"] != asdict(account)
                or value["authority"] != self._authority(tokens)
                or value["expires_at"] <= datetime.now(UTC).timestamp()
            ):
                raise ValueError
            return bounded(value["token"], limit=16384)
        except Exception:
            raise SourceError("invalid_cursor") from None

    def _seal(self, actor, tenant, identifier, account, operation, token, tokens):
        if token is None:
            return None
        envelope = self.vault.encrypt(
            tenant,
            actor,
            identifier,
            "browse-cursor",
            {
                "account": asdict(account),
                "authority": self._authority(tokens),
                "operation": operation,
                "token": token,
                "expires_at": (datetime.now(UTC) + timedelta(minutes=15)).timestamp(),
            },
        )
        return base64.urlsafe_b64encode(envelope).decode("ascii")

    async def sites(self, actor: str, tenant: str, identifier: str, query: str, *, cursor: str | None = None):
        account, tokens = await self._reader(actor, tenant, identifier)
        if account.provider != "sharepoint":
            raise SourceError("unsupported")
        operation = "sites:" + bounded(query, limit=256)
        token = self._open(actor, tenant, identifier, account, operation, cursor, tokens)
        continuation = DiscoveryCursor(account, operation, token) if token else None
        async with self._discovery(account, tokens) as adapter:
            if not isinstance(adapter, GraphDiscovery):
                raise SourceError("unsupported")
            page = await adapter.sites(query, continuation)
        await self._confirm(actor, tenant, identifier, account, tokens)
        return Locations(
            page.items,
            self._seal(
                actor,
                tenant,
                identifier,
                account,
                operation,
                page.next_cursor.token if page.next_cursor else None,
                tokens,
            ),
        )

    async def drives(
        self,
        actor: str,
        tenant: str,
        identifier: str,
        *,
        site_id: str | None = None,
        cursor: str | None = None,
    ):
        account, tokens = await self._reader(actor, tenant, identifier)
        if account.provider == "google_drive":
            if site_id is not None:
                raise SourceError("unsupported")
            operation = "shared-drives"
        elif account.provider == "sharepoint":
            if site_id is None:
                raise SourceError("unsupported")
            operation = "/v1.0/sites/" + path_id(bounded(site_id)) + "/drives"
        else:
            if site_id is not None:
                raise SourceError("unsupported")
            operation = "/v1.0/me/drives"
        token = self._open(actor, tenant, identifier, account, operation, cursor, tokens)
        continuation = DiscoveryCursor(account, operation, token) if token else None
        async with self._discovery(account, tokens) as adapter:
            if isinstance(adapter, GoogleDriveDiscovery):
                page = await adapter.drives(continuation)
            else:
                page = await adapter.drives(site_id=site_id, cursor=continuation)
        await self._confirm(actor, tenant, identifier, account, tokens)
        return Locations(
            page.items,
            self._seal(
                actor,
                tenant,
                identifier,
                account,
                operation,
                page.next_cursor.token if page.next_cursor else None,
                tokens,
            ),
        )

    async def children(
        self,
        actor: str,
        tenant: str,
        identifier: str,
        drive_id: str,
        *,
        folder_id: str | None = None,
        cursor: str | None = None,
    ):
        account, tokens = await self._reader(actor, tenant, identifier)
        scope = SourceScope(account, drive_id)
        async with self._source(scope, tokens) as adapter:
            folder = await adapter.root() if folder_id is None else await adapter.get_item(folder_id)
            if folder.kind != "folder":
                raise SourceError("unsupported")
            operation = "children:" + folder.item_id
            bound_operation = json.dumps([drive_id, operation], separators=(",", ":"))
            token = self._open(actor, tenant, identifier, account, bound_operation, cursor, tokens)
            continuation = Cursor(scope, operation, token) if token else None
            page = await adapter.children(folder.item_id, continuation)
        await self._confirm(actor, tenant, identifier, account, tokens)
        return FolderItems(
            folder,
            page.items,
            self._seal(
                actor,
                tenant,
                identifier,
                account,
                bound_operation,
                page.next_cursor.token if page.next_cursor else None,
                tokens,
            ),
        )
