# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Preview actual past personal observations without changing preferences or queuing delivery."""

from types import SimpleNamespace
from uuid import uuid4

from pyfly.container import service
from pyfly.kernel import InvalidRequestException, ServiceUnavailableException

from koinon.activity.ports import ActivitySummaryReader
from koinon.catalog.service import CatalogService
from koinon.communications.content import CommunicationContent
from koinon.communications.dtos import ActivityEmailPreviewInput
from koinon.communications.locales import effective_locale
from koinon.communications.recipients import RecipientService, recipient_unavailable
from koinon.communications.repositories import (
    CommunicationPolicyRepository,
    OutboxRepository,
    RecipientIdentityRepository,
)
from koinon.communications.settings import CommunicationsSettings, InstallationLinks
from koinon.communications.templates import EmailRenderer
from koinon.security.authority import primary_authority


@service(name="communications.activity_preview")
class ActivityEmailPreviewService:
    def __init__(
        self,
        content: CommunicationContent,
        recipients: RecipientService,
        identities: RecipientIdentityRepository,
        outbox: OutboxRepository,
        policies: CommunicationPolicyRepository,
        settings: CommunicationsSettings,
        links: InstallationLinks,
        renderer: EmailRenderer,
        catalog: CatalogService,
        summaries: ActivitySummaryReader | None = None,
    ):
        self.content, self.recipients, self.identities, self.outbox, self.policies = (
            content,
            recipients,
            identities,
            outbox,
            policies,
        )
        self.settings, self.links, self.renderer, self.catalog, self.summaries = (
            settings,
            links,
            renderer,
            catalog,
            summaries,
        )

    @primary_authority()
    async def _target(self, owner, body):
        if body.window.end_at > await self.outbox.clock():
            raise InvalidRequestException(
                "Preview an observed past activity window", code="ACTIVITY_PREVIEW_FUTURE"
            )
        if body.preferences.digest == "off":
            raise InvalidRequestException(
                "Choose a cadence for the email preview", code="ACTIVITY_PREVIEW_CADENCE"
            )
        rows = await self.identities.find_all(tenant_id=body.tenant_id, subject=owner)
        if len(rows) != 1:
            raise recipient_unavailable()
        row = rows[0]
        provider = await self.recipients.snapshot(body.tenant_id, row.provider_id)
        if provider.revision != row.provider_revision:
            raise recipient_unavailable()
        tenant = await self.catalog.tenant_repository.find_by_id(body.tenant_id)
        policy = await self.policies.find_by_id(body.tenant_id)
        locale = effective_locale(
            user=body.preferences.notification_locale,
            organization=policy.default_locale if policy else None,
            installation=self.settings.default_locale,
        )
        return provider, row.external_subject, tenant.name, locale

    async def preview(self, owner, body: ActivityEmailPreviewInput):
        body = ActivityEmailPreviewInput.model_validate(body)
        if self.summaries is None:
            raise ServiceUnavailableException(
                "Activity observations are not configured", code="ACTIVITY_SUMMARIES_UNAVAILABLE"
            )
        provider, external, organization, locale = await self._target(owner, body)
        summary = await self.summaries.personal(owner, body.tenant_id, body.window)
        observed = await self.recipients.observe(provider, external)
        event = SimpleNamespace(
            id=str(uuid4()),
            tenant_id=body.tenant_id,
            owner_subject=owner,
            event_json=dict(organization_name=organization, cadence=body.preferences.digest),
        )
        value = await self.content.digest(event, observed.person, summary, locale_override=locale)
        rendered = await self.renderer.render(
            value,
            action_url=self.links.public_url + "/auth/notifications/preferences",
            preferences_url=self.links.public_url + "/auth/notifications/preferences",
            locale=value.effective_locale,
        )
        return value.model_copy(
            update={"rendered_html": self.renderer.preview_html(rendered), "rendered_text": rendered.text}
        )
