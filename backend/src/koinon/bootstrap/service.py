# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import re
from datetime import timedelta
from urllib.parse import urlsplit
from uuid import UUID, uuid4

from pyfly.container import bean, configuration, service
from pyfly.data.relational.sqlalchemy import LockMode, transactional
from pyfly.data.transaction import Isolation
from pyfly.kernel import ConflictException
from pyfly.security.context import SecurityContext
from pyfly.security.oauth2.client import ClientRegistration
from starlette.requests import Request

from koinon.bootstrap.dtos import BootstrapSeedInput
from koinon.bootstrap.entities import BootstrapIdentityGrant
from koinon.bootstrap.ports import BootstrapLoginObserver
from koinon.bootstrap.repositories import BootstrapGrantRepository
from koinon.catalog.entities import AuditEvent, Membership, Tenant
from koinon.catalog.errors import AccessDenied
from koinon.catalog.repositories import AuditRepository, MembershipRepository, TenantRepository
from koinon.communications.ports import WelcomeAdmissionPort
from koinon.corporate_identity.policy import IdentityPolicy, verified_identity
from koinon.security.settings import OidcSettings


@service(name="bootstrap.grants")
class BootstrapGrants:
    def __init__(
        self,
        grants: BootstrapGrantRepository,
        tenants: TenantRepository,
        members: MembershipRepository,
        audits: AuditRepository,
        oidc: OidcSettings,
        welcome: WelcomeAdmissionPort,
    ):
        self.grants, self.tenants, self.members, self.audits, self.oidc, self.welcome = (
            grants,
            tenants,
            members,
            audits,
            oidc,
            welcome,
        )

    @transactional(datasource="primary", isolation=Isolation.SERIALIZABLE)
    async def seed(self, tenant_id: str, name: str, value: BootstrapSeedInput) -> int:
        if (
            not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}", tenant_id)
            or not name.strip()
            or len(name) > 160
        ):
            raise ValueError("Supply a new tenant identifier and name")
        if (
            value.issuer != self.oidc.issuer
            or value.client_id != self.oidc.client_id
            or value.issuer != f"https://login.microsoftonline.com/{value.entra_tenant_id}/v2.0"
        ):
            raise ValueError("Bootstrap identities must match the configured direct Entra issuer and client")
        now = await self.grants.clock()
        if any(row.expires_at <= now or row.expires_at > now + timedelta(days=7) for row in value.grants):
            raise ValueError("Bootstrap expiry must be in the next seven days")
        if await self.tenants.find_by_id(tenant_id) is not None:
            raise ValueError("Tenant already exists; use its authorized administration workflow")
        await self.tenants.save(Tenant(id=tenant_id, name=name.strip()))
        for row in value.grants:
            await self.grants.save(
                BootstrapIdentityGrant(
                    id=str(uuid4()),
                    tenant_id=tenant_id,
                    canonical_issuer=value.issuer,
                    native_client_id=value.client_id,
                    entra_tenant_id=str(value.entra_tenant_id),
                    object_id=str(row.object_id),
                    role=row.role,
                    expires_at=row.expires_at,
                    created_at=now,
                )
            )
        await self.audits.save(
            AuditEvent(
                id=str(uuid4()),
                tenant_id=tenant_id,
                subject="system:bootstrap",
                action="tenant.bootstrap.pending",
                details={"grant_count": len(value.grants)},
            )
        )
        return len(value.grants)

    async def observe_login(
        self, request: Request, registration: ClientRegistration, context: SecurityContext
    ) -> None:
        if (
            request.method != "GET"
            or request.url.path != urlsplit(self.oidc.redirect_uri).path
            or registration.client_id != self.oidc.client_id
            or registration.issuer_uri != self.oidc.issuer
            or registration.redirect_uri != self.oidc.redirect_uri
            or not context.is_authenticated
            or context.attributes.get("sub") != context.user_id
            or any(
                key in context.attributes for key in ("koinon_token", "koinon_token_id", "koinon_mcp_grant")
            )
        ):
            return
        claims = context.attributes
        policy = IdentityPolicy(
            "bootstrap",
            "entra",
            self.oidc.issuer,
            None,
            external_tenant_id=claims.get("tid"),
            identity_mode="direct",
            native_client_id=self.oidc.client_id,
        )
        try:
            identity = verified_identity(policy, claims)
        except AccessDenied:
            return
        await self._consume(identity.subject, str(UUID(claims["tid"])), identity.external_subject)

    @transactional(datasource="primary", isolation=Isolation.SERIALIZABLE)
    async def _consume(self, subject: str, tid: str, oid: str) -> None:
        now = await self.grants.clock()
        rows = await self.grants.pending(self.oidc.issuer, self.oidc.client_id, tid, oid, now)
        if len(rows) > 100:
            raise ConflictException(
                "Bootstrap enrollment exceeds its supported bound", code="BOOTSTRAP_LIMIT"
            )
        for row in rows:
            tenant = await self.tenants.find_by_id(row.tenant_id, lock=LockMode.PESSIMISTIC_WRITE)
            if tenant is None:
                raise RuntimeError("Bootstrap organization is unavailable")
            existing = [
                member
                for member in await self.members.find_all(subject=subject, tenant_id=row.tenant_id)
                if member.workspace_id is None
            ]
            if len(existing) > 1 or existing and (not existing[0].active or existing[0].role != row.role):
                raise ConflictException(
                    "Existing membership requires authorized review", code="BOOTSTRAP_MEMBERSHIP_CONFLICT"
                )
            member = (
                existing[0]
                if existing
                else Membership(id=str(uuid4()), subject=subject, tenant_id=row.tenant_id, role=row.role)
            )
            if not existing:
                await self.members.save(member)
            await self.welcome.admit(subject, row.tenant_id)
            await self.audits.save(
                AuditEvent(
                    id=str(uuid4()),
                    tenant_id=row.tenant_id,
                    subject=subject,
                    action="tenant.bootstrap.activated",
                    resource_id=member.id,
                    details={"bootstrap_grant_id": row.id},
                )
            )
            await self.grants.activate(row, subject, member.id, now)


@configuration
class BootstrapConfiguration:
    @bean(name="bootstrap.verified_login_observer")
    def observer(self, service: BootstrapGrants) -> BootstrapLoginObserver:
        return service
