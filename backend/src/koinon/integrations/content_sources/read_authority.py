# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Fresh reader-owned source authority, with no reusable positive grant."""

import hashlib
import json
from collections import defaultdict
from dataclasses import dataclass, replace

from pyfly.container import Provider, service

from koinon.catalog.service import CatalogService
from koinon.integrations.content_sources.errors import SourceError
from koinon.integrations.content_sources.lifecycle import _no_remote_unit
from koinon.integrations.content_sources.read_dtos import (
    LocalFolderSourcePin,
    LocalSourcePin,
    ReaderSourceSelection,
    validate_selections,
)
from koinon.integrations.content_sources.read_native import SourceReadNative
from koinon.integrations.content_sources.read_repository import SourceReadRepository
from koinon.integrations.content_sources.reader_access import PersonalSourceAccess
from koinon.security.authority import primary_authority


def source_authority(connection):
    """Stable reviewed identity and scopes; refresh revisions remain execution fences."""
    names = ("tenant_id", "owner", "provider", "external_subject", "issuer", "config_fingerprint")
    payload = {name: getattr(connection, name, None) for name in names}
    payload["connection_id"] = getattr(connection, "id", None)
    if any(not isinstance(value, str) or not value or value != value.strip() for value in payload.values()):
        raise SourceError("authority_changed")
    external_tenant = getattr(connection, "external_tenant", None)
    if external_tenant is not None and (
        not isinstance(external_tenant, str)
        or not external_tenant
        or external_tenant != external_tenant.strip()
    ):
        raise SourceError("authority_changed")
    scopes = getattr(connection, "scopes", None)
    if not isinstance(scopes, (list, tuple)) or any(
        not isinstance(scope, str) or not scope or any(ord(char) < 33 or ord(char) > 126 for char in scope)
        for scope in scopes
    ):
        raise SourceError("authority_changed")
    payload.update(
        schema="koinon.source-authority.v1", external_tenant=external_tenant, scopes=sorted(set(scopes))
    )
    encoded = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
    ).encode("utf-8")
    return payload, hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True, slots=True)
class _LocalComparison:
    pins: tuple
    origins: tuple
    connections: tuple
    archived_target: str | None = None


@service(name="content_sources.read_authority")
class SourceReadAuthority:
    def __init__(
        self,
        records: SourceReadRepository,
        remote: Provider[PersonalSourceAccess | None],
        catalog: CatalogService,
        native: Provider[SourceReadNative | None] | None = None,
    ):
        self.records, self.remote, self.catalog = records, remote, catalog
        self.native = native

    async def _snapshot(self, actor, tenant, pins, *, refresh=True, archived_target=None):
        if refresh:
            await self.catalog._refresh_managed_memberships(actor)
        normalized = tuple(pins)
        if self.native is not None:
            async with primary_authority(fresh=True):
                extractions = await self.records.expected_extractions(tenant, pins)
            native = self.native.get()
            values = []
            for pin in pins:
                if isinstance(pin, LocalFolderSourcePin):
                    values.append(pin)
                    continue
                expected = extractions.get(
                    (pin.asset_id, pin.native_workspace_id, pin.native_source_id, pin.version_id)
                )
                if expected is not None:
                    if native is None:
                        raise SourceError("unavailable")
                    await native.document_extraction(actor, tenant, pin, expected)
                    pin = replace(pin, extraction_id=expected)
                values.append(pin)
            normalized = tuple(values)
        async with primary_authority(fresh=True):
            for identifier in dict.fromkeys(
                pin.folder_id if isinstance(pin, LocalFolderSourcePin) else pin.asset_id for pin in pins
            ):
                entry = await self.catalog.get_identity(actor, tenant, identifier)
                seen = set()
                while entry is not None:
                    if (
                        entry.id in seen
                        or len(seen) >= 16
                        or (entry.status == "archived" and entry.id != archived_target)
                    ):
                        raise SourceError("access_denied")
                    seen.add(entry.id)
                    entry = (
                        await self.catalog.get_identity(actor, tenant, entry.parent_id)
                        if entry.parent_id
                        else None
                    )
            return await self.records.resolve(tenant, normalized)

    async def check(
        self,
        actor: str,
        tenant: str,
        pins: tuple[LocalSourcePin | LocalFolderSourcePin, ...],
        reader_connections: tuple[ReaderSourceSelection, ...],
    ) -> None:
        await self._check(actor, tenant, pins, reader_connections)

    async def _check(self, actor, tenant, pins, reader_connections, *, archived_target=None):
        _no_remote_unit()
        validate_selections(reader_connections)
        if len(pins) > 1000:
            raise SourceError("size_exceeded")
        if not pins:
            return _LocalComparison((), (), ())
        origins = await self._snapshot(actor, tenant, pins, archived_target=archived_target)
        selected = {
            (choice.provider, choice.external_tenant): choice.connection_id for choice in reader_connections
        }
        groups = defaultdict(list)
        for origin in origins:
            identifier = selected.get((origin.target.provider, origin.target.external_tenant))
            if identifier is None:
                raise SourceError("reconnect_required")
            groups[identifier].append(origin.target)
        revisions = {}
        remote = self.remote.get() if isinstance(self.remote, Provider) else self.remote
        if groups and remote is None:
            raise SourceError("unavailable")
        for origin in origins:
            if origin.config_fingerprint and (
                remote is None
                or remote.connections.registrations.get(origin.target.provider).fingerprint
                != origin.config_fingerprint
            ):
                raise SourceError("authority_changed")
        for identifier, targets in groups.items():
            if remote is None:
                raise SourceError("unavailable")
            targets = list(dict.fromkeys(targets))
            for start in range(0, len(targets), 100):
                observations = await remote.check(
                    actor, tenant, identifier, tuple(targets[start : start + 100])
                )
                if len(observations) != len(targets[start : start + 100]):
                    raise SourceError("unavailable")
                observed = {value.connection_revision for value in observations}
                if len(observed) != 1 or (identifier in revisions and revisions[identifier] not in observed):
                    raise SourceError("authority_changed")
                revisions[identifier] = observations[0].connection_revision
        if await self._snapshot(actor, tenant, pins, archived_target=archived_target) != origins:
            raise SourceError("authority_changed")
        async with primary_authority(fresh=True):
            connections = await self.records.check_connections(actor, tenant, revisions)
        return _LocalComparison(tuple(pins), origins, connections, archived_target)

    async def _lock_comparisons(self, actor, tenant, comparisons):
        await self.records.lock_origins(
            tenant,
            tuple(origin for comparison in comparisons for origin in comparison.origins),
            tuple(connection for comparison in comparisons for connection in comparison.connections),
        )
        for comparison in comparisons:
            await self._compare(actor, tenant, comparison)

    async def _compare(self, actor, tenant, comparison):
        """Compare one operation's observations inside its write unit; never contact a provider."""
        if (
            await self._snapshot(
                actor, tenant, comparison.pins, refresh=False, archived_target=comparison.archived_target
            )
            != comparison.origins
        ):
            raise SourceError("authority_changed")
        revisions = {row[0]: row[1] for row in comparison.connections}
        current = await self.records.check_connections(actor, tenant, revisions)
        if current != comparison.connections:
            raise SourceError("authority_changed")
        remote = self.remote.get() if isinstance(self.remote, Provider) else self.remote
        for row in current:
            if remote is None or remote.connections.registrations.get(row[2]).fingerprint != row[3]:
                raise SourceError("authority_changed")
