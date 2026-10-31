# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from datetime import UTC, datetime

from pyfly.container import Provider, service
from pyfly.security.context import SecurityContext
from pyfly.security.context_holder import SecurityContextHolder

from koinon.catalog.errors import AccessDenied
from koinon.catalog.service import ROLE_PERMISSIONS, CatalogService
from koinon.evidence.dtos import SourceReference
from koinon.evidence.ports import SourceResolverPort, TransitiveSourceResolverPort
from koinon.tokens.repositories import PersonalTokenRepository


def unavailable():
    return AccessDenied("This evidence is unavailable in the selected context", code="EVIDENCE_UNAVAILABLE")


@service(name="evidence.access")
class EvidenceAccess:
    def __init__(
        self,
        catalog: CatalogService,
        tokens: PersonalTokenRepository,
        sources: Provider[SourceResolverPort | None] | None = None,
    ):
        self.catalog, self.tokens = catalog, tokens
        self.sources = sources

    async def _owner_memberships(self, subject):
        rows = list(await self.catalog.membership_repository.find_all(subject=subject, active=True))
        if self.catalog.managed_memberships is not None:
            rows.extend(await self.catalog.managed_memberships.load_managed_memberships(subject))
        return rows

    async def _chain(self, tenant_id, identifier):
        rows, seen = [], set()
        while identifier is not None:
            if identifier in seen or len(seen) >= 16:
                raise unavailable()
            seen.add(identifier)
            matches = await self.catalog.catalog_repository.find_all(id=identifier, tenant_id=tenant_id)
            if not matches or matches[0].status == "archived":
                raise unavailable()
            row = matches[0]
            rows.append(row)
            identifier = row.parent_id
        return rows

    async def _token(self, identifier, owner, tenant_id):
        row = await self.tokens.find_by_id(identifier)
        if (
            row is None
            or row.subject != owner
            or row.tenant_id != tenant_id
            or row.revoked_at is not None
            or row.expires_at <= datetime.now(UTC)
        ):
            raise unavailable()
        restriction = getattr(self.catalog, "restriction", None)
        if restriction is not None:
            issuer, _, sub = owner.partition("|")
            with SecurityContextHolder.using(
                SecurityContext(
                    user_id=sub, attributes={"iss": issuer, "sub": sub, "koinon_token_id": identifier}
                )
            ):
                verified = await restriction.grant(owner)
                if verified is None or verified.id != identifier:
                    raise unavailable()
        elif getattr(row, "purpose", None) == "application":
            raise unavailable()
        return row

    async def check(
        self,
        subject: str,
        tenant_id: str,
        sources: tuple[SourceReference, ...],
        *,
        permission: str,
        owner_subject: str | None = None,
        originating_token_ids: tuple[str, ...] = (),
        creator_token_id: str | None = None,
        creator_permission: str | None = None,
    ):
        if permission in {"shares:read", "shares:write", "exports:read", "exports:write"} and any(
            source.kind == "knowledge_version" for source in sources
        ):
            resolver = self.sources.get() if self.sources else None
            if not isinstance(resolver, TransitiveSourceResolverPort):
                raise AccessDenied(
                    "Knowledge source permissions cannot be verified",
                    code="CURATED_TRANSITIVE_AUTHORITY_UNQUALIFIED",
                )
            roots = await resolver.resolve_bounds(subject, tenant_id, sources)
            sources = tuple({source.id: source for source in (*sources, *roots)}.values())
        owner = owner_subject or subject
        memberships = [row for row in await self._owner_memberships(owner) if row.tenant_id == tenant_id]
        if not memberships:
            raise unavailable()
        origins = [
            await self._token(identifier, owner, tenant_id) for identifier in set(originating_token_ids)
        ]
        if any("catalog:read" not in token.scopes for token in origins):
            raise unavailable()
        creator = await self._token(creator_token_id, owner, tenant_id) if creator_token_id else None
        if creator is not None and (
            creator_permission not in creator.scopes or "catalog:read" not in creator.scopes
        ):
            raise unavailable()
        admitted = set()
        for source in sources:
            if source.asset_id in admitted:
                continue
            admitted.add(source.asset_id)
            entry = await self.catalog.get(subject, tenant_id, source.asset_id)
            await self.catalog.authorize(subject, tenant_id, permission, entry.workspace_id)
            chain = await self._chain(tenant_id, source.asset_id)
            if not any(
                (member.workspace_id is None or member.workspace_id == entry.workspace_id)
                and "catalog:read" in ROLE_PERMISSIONS.get(member.role, ())
                for member in memberships
            ):
                raise unavailable()
            if creator is not None and (
                (creator.workspace_ids is not None and entry.workspace_id not in creator.workspace_ids)
                or (creator.asset_ids is not None and not any(row.id in creator.asset_ids for row in chain))
            ):
                raise unavailable()
        if not admitted:
            await self.catalog.authorize(subject, tenant_id, permission)
            if not any(member.workspace_id is None for member in memberships):
                raise unavailable()
            if creator is not None and (creator.workspace_ids is not None or creator.asset_ids is not None):
                raise unavailable()

    async def management(self, subject, tenant_id, sources, *, permission):
        if not sources:
            await self.catalog.authorize(subject, tenant_id, permission)
        for source in sources:
            matches = await self.catalog.catalog_repository.find_all(id=source.asset_id, tenant_id=tenant_id)
            if not matches:
                await self.catalog.authorize(subject, tenant_id, permission)
                continue
            entry = matches[0]
            await self.catalog.authorize(subject, tenant_id, permission, entry.workspace_id)
            if self.catalog.restriction:
                await self.catalog.restriction.resource(subject, entry)
