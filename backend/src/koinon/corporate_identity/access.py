# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from pyfly.container import bean, configuration
from pyfly.data.relational.sqlalchemy import transactional
from pyfly.data.transaction import current_unit_of_work

from koinon.catalog.ports import ManagedMembership, ManagedMembershipReader
from koinon.corporate_identity.member_projection import member_page, membership_rows
from koinon.corporate_identity.refresh import CorporateAccessRefresh
from koinon.corporate_identity.repositories import CorporateGrantRepository
from koinon.security.settings import OidcSettings


class CorporateMembershipReader:
    def __init__(self, grants: CorporateGrantRepository, oidc: OidcSettings, refresh: CorporateAccessRefresh):
        self.grants, self.oidc, self.refresh = grants, oidc, refresh

    async def load_managed_memberships(self, subject: str) -> list[ManagedMembership]:
        # Refresh before request units begin; never suspend a tenant lock for an independent FK write.
        if current_unit_of_work("primary") is None:
            await self.refresh.subject(subject)
        return await self._current(subject)

    @transactional(read_only=True)
    async def _current(self, subject: str) -> list[ManagedMembership]:
        rows = await self.grants.current(subject, self.oidc.issuer)
        return [
            ManagedMembership(
                id=grant.id,
                subject=grant.subject,
                tenant_id=grant.tenant_id,
                workspace_id=grant.workspace_id,
                role=grant.role,
                active=True,
                created_at=grant.observed_at,
                source_id=grant.provider_id,
                source_name=name,
                expires_at=grant.expires_at,
            )
            for grant, name in rows
        ]

    @transactional(read_only=True)
    async def effective_membership_page(self, tenant_id: str, **filters) -> dict:
        return await member_page(self.grants._require_session(), self.oidc.issuer, tenant_id, **filters)

    def effective_membership_rows(self):
        return membership_rows(self.oidc.issuer)


@configuration
class CorporateAccessConfiguration:
    @bean(name="identity.managed_memberships")
    def managed_memberships(
        self, grants: CorporateGrantRepository, oidc: OidcSettings, refresh: CorporateAccessRefresh
    ) -> ManagedMembershipReader:
        return CorporateMembershipReader(grants, oidc, refresh)
