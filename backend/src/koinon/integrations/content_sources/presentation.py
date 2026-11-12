# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Authorized installation and mapping presentation without credential disclosure."""

import asyncio

from pyfly.container import Container, service

from koinon.catalog.ancestry import validated_ancestry
from koinon.catalog.errors import AccessDenied
from koinon.catalog.service import PARENTS, CatalogService
from koinon.integrations.content_sources.api_dtos import (
    SourceCapabilitiesOutput,
    SourceFormatCapability,
    SourceProvider,
    SourceProviderCapability,
    SourceScheduleCapability,
    SourceValidationLimits,
)
from koinon.integrations.content_sources.errors import SourceError
from koinon.integrations.content_sources.mapping_dtos import VALIDATION_MAX_LIFETIME_SECONDS
from koinon.integrations.content_sources.registrations import SourceRegistrations
from koinon.integrations.content_sources.settings import ContentSourceSettings
from koinon.integrations.content_sources.sync_dtos import (
    SourceDestinationPresentation,
    SourceDestinationSegment,
    SourceRootPresentation,
)
from koinon.knowledge.bulk.upload_formats import upload_formats
from koinon.security.authority import primary_authority

_PROVIDERS: dict[SourceProvider, str] = {
    "sharepoint": "SharePoint",
    "onedrive": "OneDrive",
    "google_drive": "Google Drive",
}
_SYNC_DEPENDENCIES = (
    "content_sources.mappings",
    "content_sources.policies",
    "content_sources.policy_service",
    "content_sources.publication_writer",
    "content_sources.scheduler",
    "content_sources.worker",
    "content_sources.files",
    "content_sources.folders",
)


@service(name="content_sources.presentation")
class SourcePresentation:
    def __init__(self, container: Container, settings: ContentSourceSettings, catalog: CatalogService):
        self.container, self.settings, self.catalog = container, settings, catalog

    def synchronization_available(self) -> bool:
        return bool(
            self.settings.enabled
            and self.settings.synchronization_enabled
            and all(self.container.contains(name) for name in _SYNC_DEPENDENCIES)
        )

    async def source_root(self, actor, tenant, mapping, policy, connections, browser):
        # Import locally: lifecycle consumes this presentation service, not its authority.
        from koinon.integrations.content_sources.dtos import Account, RemoteItem, SourceScope
        from koinon.integrations.content_sources.lifecycle import _no_remote_unit
        from koinon.integrations.content_sources.mapping_ancestry import FolderAncestry
        from koinon.integrations.content_sources.read_authority import source_authority
        from koinon.integrations.content_sources.reader_access import _OperationToken

        _no_remote_unit()
        account = Account(mapping.provider, mapping.external_subject, mapping.external_tenant)
        scope = SourceScope(account, mapping.drive_id)
        grant = await connections.read_grant(actor, tenant, mapping.connection_id, account)
        try:
            async with (
                asyncio.timeout(120),
                browser._source(scope, _OperationToken(account, grant.token)) as adapter,
            ):
                items = {}

                class DisplayFolders:
                    async def root(self) -> RemoteItem:
                        item = await adapter.root()
                        items[item.item_id] = item
                        return item

                    async def get_item(self, item_id: str) -> RemoteItem:
                        item = await adapter.get_item(item_id)
                        items[item.item_id] = item
                        return item

                reader = DisplayFolders()
                before = await FolderAncestry(reader, scope).capture((mapping.root_id,))
                captured = dict(items)
                after = await FolderAncestry(reader, scope).capture((mapping.root_id,))
                if before != after or captured != items:
                    raise SourceError("authority_changed")
                path = (mapping.root_id, *before.ancestors(mapping.root_id))
                if path != tuple(policy.root_ancestry_json):
                    raise SourceError("authority_changed")
                result = SourceRootPresentation(
                    name=items[mapping.root_id].name,
                    relative_path=[items[identifier].name for identifier in reversed(path)],
                )
        except TimeoutError:
            raise SourceError("timeout") from None
        await connections.confirm_read_grant(actor, tenant, mapping.connection_id, grant)
        async with primary_authority(fresh=True):
            connection = await connections.connections.owned(tenant, actor, mapping.connection_id)
            if connection is None or connection.revision != grant.revision:
                raise SourceError("authority_changed")
            authority, digest = source_authority(connection)
            if digest != policy.authority_sha256 or authority != policy.policy_json.get("authority"):
                raise SourceError("authority_changed")
        return result, grant.revision

    async def destination(self, actor, tenant, destination):
        async def read(identifier):
            return await self.catalog.get(actor, tenant, identifier)

        parent = await read(destination.parent_id)
        chain = await validated_ancestry(parent, read, PARENTS)
        if len(chain) < 3 or (chain[-1].id, chain[-2].id) != (
            destination.workspace_id,
            destination.project_id,
        ):
            raise AccessDenied("Source destination changed.", code="ACCESS_DENIED")
        return SourceDestinationPresentation(
            segments=[
                SourceDestinationSegment(id=item.id, kind=item.kind, name=item.name)
                for item in reversed(chain)
            ]
        )

    async def capabilities(self, actor: str, tenant: str) -> SourceCapabilitiesOutput:
        await self.catalog._refresh_managed_memberships(actor)
        async with primary_authority(fresh=True):
            memberships = await self.catalog.memberships(actor)
            grant = await self.catalog.restriction.grant(actor) if self.catalog.restriction else None
            for workspace in {row.workspace_id for row in memberships if row.tenant_id == tenant}:
                if "catalog:read" in self.catalog._resolved_permissions(
                    memberships, tenant, workspace, grant
                ):
                    await self.catalog._validate_workspace(tenant, workspace)
                    break
            else:
                raise AccessDenied("Source capabilities require organization access.", code="ACCESS_DENIED")
        self.settings.synchronization_options()
        accounts = bool(self.settings.enabled and self.container.contains("content_sources.connections"))
        registrations = SourceRegistrations(self.settings)
        providers = []
        for provider, label in _PROVIDERS.items():
            reason = "disabled" if not accounts else None
            if reason is None:
                try:
                    registrations.get(provider)
                except SourceError:
                    reason = "not_configured"
            providers.append(
                SourceProviderCapability(
                    provider=provider,
                    display_name=label,
                    consent_available=reason is None,
                    unavailable_reason=reason,
                )
            )
        formats = [
            SourceFormatCapability(extension=extension, mode=value.mode)
            for value in upload_formats()
            if value.available
            for extension in value.extensions
        ]
        return SourceCapabilitiesOutput(
            accounts_available=accounts,
            synchronization_available=self.synchronization_available(),
            providers=providers,
            modes=sorted({value.mode for value in formats}),
            formats=formats,
            schedule=SourceScheduleCapability(
                min_interval_seconds=self.settings.sync_min_interval_seconds,
                max_interval_seconds=self.settings.sync_max_interval_seconds,
            ),
            validation_limits=SourceValidationLimits(
                max_scan_items=self.settings.sync_max_scan_items,
                max_active_per_owner=self.settings.sync_validation_max_active_per_owner,
                max_active_per_tenant=self.settings.sync_validation_max_active_per_tenant,
                max_records_per_tenant=self.settings.sync_validation_max_records_per_tenant,
                max_retained_bytes_per_tenant=self.settings.sync_validation_max_retained_bytes_per_tenant,
                max_lifetime_seconds=VALIDATION_MAX_LIFETIME_SECONDS,
            ),
        )
