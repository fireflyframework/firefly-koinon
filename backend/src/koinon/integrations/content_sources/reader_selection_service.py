# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Reader choices are preferences; every consumption still checks current authority."""

import hashlib
import json

from pyfly.container import service
from sqlalchemy import select

from koinon.catalog.errors import AccessDenied
from koinon.catalog.service import CatalogService
from koinon.integrations.content_sources.entities import PersonalSourceConnection
from koinon.integrations.content_sources.errors import SourceError
from koinon.integrations.content_sources.lifecycle import _no_remote_unit
from koinon.integrations.content_sources.read_dtos import ReaderSelectionSnapshot, validate_selections
from koinon.integrations.content_sources.reader_selection_repository import SourceReaderSelectionRepository
from koinon.security.authority import primary_authority


@service(name="content_sources.reader_selection")
class SourceReaderSelections:
    def __init__(self, records: SourceReaderSelectionRepository, catalog: CatalogService):
        self.records, self.catalog = records, catalog

    async def _authorize(self, actor, tenant):
        await self.catalog._refresh_managed_memberships(actor)
        async with primary_authority(fresh=True):
            memberships = await self.catalog.memberships(actor)
            grant = await self.catalog.restriction.grant(actor) if self.catalog.restriction else None
            for workspace in {row.workspace_id for row in memberships if row.tenant_id == tenant}:
                if "catalog:read" in self.catalog._resolved_permissions(
                    memberships, tenant, workspace, grant
                ):
                    await self.catalog._validate_workspace(tenant, workspace)
                    return
        raise AccessDenied("Source choices require current organization access", code="ACCESS_DENIED")

    async def get(self, actor, tenant):
        _no_remote_unit()
        await self._authorize(actor, tenant)
        async with primary_authority(fresh=True):
            return await self.records.snapshot(tenant, actor)

    async def replace(self, actor, tenant, request):
        _no_remote_unit()
        await self._authorize(actor, tenant)
        payload = request.model_dump(mode="json", exclude={"operation_id"})
        payload["connections"] = sorted(
            payload["connections"],
            key=lambda value: (value["provider"], value["external_tenant"] or "", value["connection_id"]),
        )
        digest = hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        async with primary_authority(read_only=False):
            return await self.records.replace(actor, tenant, request, digest)

    async def resolve(self, actor, tenant, overrides=None):
        if overrides is not None:
            validate_selections(tuple(overrides))
            await self._authorize(actor, tenant)
            async with primary_authority(fresh=True):
                await self.records.validate_owned(actor, tenant, overrides)
            return ReaderSelectionSnapshot(tuple(overrides), None)
        value = await self.get(actor, tenant)
        return ReaderSelectionSnapshot(value.connections, value.revision)

    async def confirm(self, actor, tenant, snapshot):
        _no_remote_unit()
        await self._authorize(actor, tenant)
        async with primary_authority(fresh=True):
            await self.confirm_local(actor, tenant, snapshot)

    async def lock_confirm(self, actor, tenant, snapshot):
        if snapshot.revision is not None:
            await self.records.lock_revision(tenant, actor, snapshot.revision)
        await self.records._require_session().execute(
            select(PersonalSourceConnection.id)
            .where(
                PersonalSourceConnection.tenant_id == tenant,
                PersonalSourceConnection.owner == actor,
                PersonalSourceConnection.id.in_([item.connection_id for item in snapshot.connections]),
            )
            .order_by(PersonalSourceConnection.id)
            .with_for_update()
        )
        await self.confirm_local(actor, tenant, snapshot)

    async def confirm_local(self, actor, tenant, snapshot):
        if snapshot.revision is not None:
            current = await self.records.snapshot(tenant, actor)
            if current.revision != snapshot.revision or set(current.connections) != set(snapshot.connections):
                raise SourceError("authority_changed")
        await self.records.validate_owned(actor, tenant, snapshot.connections)
