# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Current registration authority without a catalog service dependency."""

import hashlib
import json
import re

from pyfly.container import service
from pyfly.data.relational.sqlalchemy import LockMode
from pyfly.data.transaction import current_unit_of_work

from koinon.catalog.repositories import TenantRepository
from koinon.mcp_applications.repositories import McpOAuthClientRepository
from koinon.mcp_auth.settings import McpOAuthSettings
from koinon.security.authority import primary_authority


@service(name="mcp.applications.authority")
class McpOAuthClientAuthority:
    def __init__(
        self, repository: McpOAuthClientRepository, settings: McpOAuthSettings, tenants: TenantRepository
    ):
        self.repository, self.settings, self.tenants = repository, settings, tenants

    @primary_authority()
    async def resolve(self, identifier: str) -> dict:
        static = [value for value in self.settings.clients if value["client_id"] == identifier]
        rows = await self.repository.find_all(client_id=identifier)
        if len(static) + len(rows) != 1:
            raise ValueError("OAuth client is unavailable")
        if static:
            return dict(static[0])
        tenant_id = rows[0].tenant_id
        unit = current_unit_of_work("primary")
        lock = {"lock": LockMode.PESSIMISTIC_READ} if unit is not None and not unit.read_only else {}
        if lock:
            # Administration locks tenant before registration. Audit FK checks must not reverse it.
            tenant = await self.tenants.find_by_id(tenant_id, **lock)
            if tenant is None:
                raise ValueError("OAuth client organization is unavailable")
        row = await self.repository.find_by_id(rows[0].id, **lock)
        if row is None or not row.enabled or row.tenant_id != tenant_id or row.client_id != identifier:
            raise ValueError("OAuth client is unavailable")
        result = {
            "client_id": row.client_id,
            "name": row.name,
            "redirect_uris": list(row.redirect_uris),
            "scopes": list(row.scopes),
            "client_secret_hash": row.client_secret_hash,
        }
        encoded = json.dumps(result, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
        result["registration"] = {
            "id": row.id,
            "tenant_id": row.tenant_id,
            "revision": row.revision,
            "sha256": hashlib.sha256(encoded).hexdigest(),
        }
        return result

    @staticmethod
    def snapshot(client: dict) -> dict | None:
        return dict(client["registration"]) if "registration" in client else None

    @primary_authority()
    async def validate(self, client_id: str, tenant_id: str, snapshot: dict | None) -> dict:
        if snapshot is not None and (
            not isinstance(snapshot, dict)
            or set(snapshot) != {"id", "tenant_id", "revision", "sha256"}
            or type(snapshot["revision"]) is not int
            or not 1 <= snapshot["revision"] <= 2147483647
            or any(not isinstance(snapshot[key], str) or not snapshot[key] for key in ("id", "tenant_id"))
            or not isinstance(snapshot["sha256"], str)
            or not re.fullmatch(r"[0-9a-f]{64}", snapshot["sha256"])
        ):
            raise ValueError("OAuth registration pin is invalid")
        current = await self.resolve(client_id)
        actual = self.snapshot(current)
        if actual != snapshot or (actual is not None and actual["tenant_id"] != tenant_id):
            raise ValueError("OAuth registration is no longer current")
        return current

    async def validate_application(self, application):
        if application is None:
            raise ValueError("OAuth application is unavailable")
        return await self.validate(
            application.client_id, application.tenant_id, application.client_registration
        )
