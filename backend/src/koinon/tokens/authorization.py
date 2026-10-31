# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from datetime import UTC, datetime

from pyfly.container import service
from pyfly.security.context_holder import SecurityContextHolder

from koinon.authorized_applications.entities import credential_matches
from koinon.authorized_applications.repositories import AuthorizedApplicationRepository
from koinon.catalog.errors import AccessDenied
from koinon.catalog.repositories import CatalogRepository
from koinon.mcp_applications.authority import McpOAuthClientAuthority
from koinon.tokens.repositories import PersonalTokenRepository


@service(name="tokens.restrictions")
class TokenRestriction:
    def __init__(
        self,
        tokens: PersonalTokenRepository,
        entries: CatalogRepository,
        applications: AuthorizedApplicationRepository | None = None,
        registrations: McpOAuthClientAuthority | None = None,
    ):
        self.tokens, self.entries = tokens, entries
        self.applications = applications
        self.registrations = registrations

    async def grant(self, subject: str):
        context = SecurityContextHolder.get_context()
        token_id = context.attributes.get("koinon_token_id") if context else None
        if not token_id:
            return None
        row = await self.tokens.find_by_id(token_id)
        if (
            row is None
            or row.subject != subject
            or row.revoked_at is not None
            or row.expires_at <= datetime.now(UTC)
        ):
            raise AccessDenied("This API token is no longer valid", code="TOKEN_UNAVAILABLE")
        if row.purpose == "application":
            application = (
                await self.applications.find_by_id(row.authorized_application_id)
                if self.applications
                else None
            )
            if application is None or not credential_matches(application, row, datetime.now(UTC)):
                raise AccessDenied("This application connection is no longer valid", code="TOKEN_UNAVAILABLE")
            if application.client_registration is not None:
                try:
                    if self.registrations is None:
                        raise ValueError("OAuth registration authority is unavailable")
                    await self.registrations.validate_application(application)
                except ValueError:
                    raise AccessDenied(
                        "This OAuth application registration is no longer valid", code="TOKEN_UNAVAILABLE"
                    ) from None
        return row

    async def resource(self, subject: str, entry, *, write=False):
        grant = await self.grant(subject)
        if grant is None:
            return
        if grant.tenant_id != entry.tenant_id or (
            grant.workspace_ids is not None and entry.workspace_id not in grant.workspace_ids
        ):
            raise AccessDenied("Resource exceeds the API token scope", code="TOKEN_SCOPE_DENIED")
        if grant.asset_ids is None:
            return
        if not write and entry.id in (grant.resource_ids or []):
            return
        current, seen = entry, set()
        while current is not None and len(seen) < 16 and current.id not in seen:
            if current.id in grant.asset_ids:
                return
            seen.add(current.id)
            current = await self.entries.find_by_id(current.parent_id) if current.parent_id else None
        raise AccessDenied("Resource exceeds the API token scope", code="TOKEN_SCOPE_DENIED")
