# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Current membership and credential ceilings for content-free activity summaries."""

import json
from dataclasses import dataclass, field
from hashlib import sha256

from pyfly.container import service

from koinon.catalog.errors import AccessDenied
from koinon.catalog.service import ROLE_PERMISSIONS, CatalogService


@dataclass(frozen=True, slots=True)
class ActivityAuthority:
    workspace_ids: tuple[str, ...] | None
    asset_limited: bool
    fingerprint: str = field(repr=False)


@service(name="activity.authority")
class ActivityAccess:
    def __init__(self, catalog: CatalogService):
        self.catalog = catalog

    async def resolve(self, subject: str, tenant_id: str, *, administrative: bool) -> ActivityAuthority:
        memberships = [
            row
            for row in await self.catalog.memberships(subject)
            if row.tenant_id == tenant_id and row.active
        ]
        readable = [row for row in memberships if "activity:read" in ROLE_PERMISSIONS.get(row.role, ())]
        grant = await self.catalog.restriction.grant(subject) if self.catalog.restriction else None
        if (
            not readable
            or grant is not None
            and (grant.tenant_id != tenant_id or not {"activity:read", "catalog:read"} <= set(grant.scopes))
        ):
            raise AccessDenied(
                "Activity is not accessible in the selected context", code="ACTIVITY_ACCESS_DENIED"
            )
        workspaces = (
            None
            if any(row.workspace_id is None for row in readable)
            else tuple(sorted({row.workspace_id for row in readable if row.workspace_id is not None}))
        )
        if grant is not None and grant.workspace_ids is not None:
            workspaces = tuple(
                sorted(
                    set(grant.workspace_ids)
                    if workspaces is None
                    else set(workspaces) & set(grant.workspace_ids)
                )
            )
        asset_limited = grant is not None and grant.asset_ids is not None
        if administrative and (
            not any(row.role == "admin" and row.workspace_id is None for row in memberships)
            or workspaces is not None
            or asset_limited
            or grant is not None
            and "audit:read" not in grant.scopes
        ):
            raise AccessDenied(
                "Organization activity requires current administrator access", code="ACTIVITY_ADMIN_REQUIRED"
            )
        stamp = dict(
            memberships=sorted((row.id, row.role, row.workspace_id or "") for row in memberships),
            grant=None
            if grant is None
            else dict(
                id=grant.id,
                scopes=sorted(grant.scopes),
                workspaces=grant.workspace_ids,
                assets=grant.asset_ids,
                resources=grant.resource_ids,
                expires_at=grant.expires_at.isoformat(),
            ),
        )
        fingerprint = sha256(json.dumps(stamp, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        return ActivityAuthority(workspaces, asset_limited, fingerprint)
