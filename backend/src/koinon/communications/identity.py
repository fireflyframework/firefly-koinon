# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Only the successful native OIDC login path can bind a canonical subject to directory identity."""

import json
from uuid import uuid4

from pyfly.container import bean, configuration, service
from pyfly.data.relational.sqlalchemy import transactional
from pyfly.kernel import ServiceUnavailableException
from sqlalchemy import select

from koinon.catalog.errors import AccessDenied
from koinon.communications.entities import RecipientIdentityRecord
from koinon.communications.ports import CommunicationIdentityObserver
from koinon.communications.recipients import RecipientService, recipient_unavailable
from koinon.communications.repositories import OutboxRepository, RecipientIdentityRepository
from koinon.communications.welcome import WelcomeAdmissions
from koinon.corporate_identity.challenges import policy
from koinon.corporate_identity.dtos import EntraSettings, GoogleWorkspaceSettings, KeycloakSettings
from koinon.corporate_identity.entities import CorporateProvider
from koinon.corporate_identity.policy import verified_identity
from koinon.corporate_identity.repositories import CorporateProviderRepository
from koinon.security.authority import primary_authority
from koinon.security.settings import OidcSettings


def immutable_identity_key(settings, external_subject):
    if isinstance(settings, EntraSettings):
        authority = str(settings.tenant_id)
    elif isinstance(settings, KeycloakSettings):
        authority = settings.issuer
    elif isinstance(settings, GoogleWorkspaceSettings):
        authority = settings.customer_id or ",".join(sorted(settings.hosted_domains))
    else:
        raise recipient_unavailable()
    return json.dumps([settings.kind, authority, external_subject], separators=(",", ":"))


@service(name="communications.identity_bindings")
class CommunicationIdentityBindings:
    def __init__(
        self,
        providers: CorporateProviderRepository,
        identities: RecipientIdentityRepository,
        recipients: RecipientService,
        welcomes: WelcomeAdmissions,
        outbox: OutboxRepository,
        oidc: OidcSettings,
    ):
        self.providers, self.identities, self.recipients, self.welcomes, self.outbox, self.oidc = (
            providers,
            identities,
            recipients,
            welcomes,
            outbox,
            oidc,
        )

    @primary_authority()
    async def _observations(self, context):
        if (
            not context.is_authenticated
            or context.attributes.get("sub") != context.user_id
            or context.attributes.get("iss") != self.oidc.issuer
            or any(name in context.attributes for name in ("koinon_token", "koinon_token_id"))
        ):
            raise recipient_unavailable()
        rows = list(
            await self.providers._require_session().scalars(
                select(CorporateProvider)
                .where(
                    CorporateProvider.canonical_issuer == self.oidc.issuer,
                    CorporateProvider.status == "active",
                    CorporateProvider.broker_alias == context.attributes.get("koinon_identity_provider"),
                )
                .order_by(CorporateProvider.id)
                .limit(101)
            )
        )
        if len(rows) > 100:
            raise recipient_unavailable()
        result = []
        for row in rows:
            try:
                identity = verified_identity(policy(row, self.oidc), context.attributes)
            except AccessDenied:
                continue
            result.append((identity, await self.recipients.snapshot(row.tenant_id, row.id)))
        return result

    async def observe_login(self, context):
        if not self.welcomes.events.settings.enabled:
            return
        try:
            observations = await self._observations(context)
        except ServiceUnavailableException:
            return
        for identity, provider in observations:
            try:
                observed = await self.recipients.observe(provider, identity.external_subject)
            except (AccessDenied, ServiceUnavailableException):
                continue
            await self._bind(identity, observed)

    @transactional
    async def _bind(self, identity, observed):
        await self.recipients.catalog._lock_tenant(observed.provider.tenant_id)
        await self.recipients.ensure_current(observed.provider)
        self_rows = await self.identities.find_all(
            tenant_id=observed.provider.tenant_id, provider_id=observed.provider.id, subject=identity.subject
        )
        external_rows = await self.identities.find_all(
            tenant_id=observed.provider.tenant_id,
            provider_id=observed.provider.id,
            external_subject=identity.external_subject,
        )
        if (
            self_rows
            and self_rows[0].external_subject != identity.external_subject
            or external_rows
            and external_rows[0].subject != identity.subject
        ):
            raise recipient_unavailable()
        now = await self.outbox.clock()
        row = (
            external_rows[0]
            if external_rows
            else RecipientIdentityRecord(
                id=str(uuid4()),
                tenant_id=observed.provider.tenant_id,
                provider_id=observed.provider.id,
                external_subject=identity.external_subject,
                subject=identity.subject,
            )
        )
        row.provider_revision, row.verified_at = observed.provider.revision, now
        await self.identities.save(row)
        key = immutable_identity_key(observed.provider.settings, identity.external_subject)
        await self.welcomes.bind(identity.subject, observed.provider.tenant_id, key)


@configuration
class CommunicationLoginConfiguration:
    @bean(name="communications.login_observer")
    def login_observer(self, bindings: CommunicationIdentityBindings) -> CommunicationIdentityObserver:
        return bindings
