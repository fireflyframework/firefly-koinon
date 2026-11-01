# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Organization-wide diagnostics retain current native membership and credential ceilings."""

import json
from dataclasses import dataclass, field
from hashlib import sha256

from pyfly.container import service

from koinon.catalog.errors import AccessDenied
from koinon.catalog.service import CatalogService
from koinon.security.authority import primary_authority


@dataclass(frozen=True, slots=True)
class PlatformAuthority:
    fingerprint: str = field(repr=False)


@service(name="platform.authority")
class PlatformAccess:
    def __init__(self, catalog: CatalogService):
        self.catalog = catalog

    @primary_authority()
    async def resolve(self, subject: str, tenant_id: str) -> PlatformAuthority:
        memberships = [
            row
            for row in await self.catalog.memberships(subject)
            if row.tenant_id == tenant_id and row.active
        ]
        grant = await self.catalog.restriction.grant(subject) if self.catalog.restriction else None
        if not any(row.role == "admin" and row.workspace_id is None for row in memberships) or (
            grant is not None
            and (
                grant.tenant_id != tenant_id
                or not {"catalog:read", "audit:read"} <= set(grant.scopes)
                or grant.workspace_ids is not None
                or grant.asset_ids is not None
                or grant.resource_ids is not None
            )
        ):
            raise AccessDenied(
                "Current organization administrator access is required", code="PLATFORM_ADMIN_REQUIRED"
            )
        await self.catalog.authorize(subject, tenant_id, "catalog:read")
        await self.catalog.authorize(subject, tenant_id, "audit:read")
        stamp = {
            "memberships": sorted((row.id, row.role, row.workspace_id or "") for row in memberships),
            "credential": None
            if grant is None
            else {
                "id": grant.id,
                "tenant_id": grant.tenant_id,
                "scopes": sorted(grant.scopes),
                "expires_at": grant.expires_at.isoformat(),
            },
        }
        return PlatformAuthority(
            sha256(json.dumps(stamp, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        )
