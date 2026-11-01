# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Trusted identity and scope data feed fixed localized subjects and the shared native template."""

from datetime import timedelta
from uuid import uuid4
from zoneinfo import ZoneInfo

from pyfly.container import service

from koinon.catalog.service import CatalogService
from koinon.communications.crypto import CommunicationsCipher
from koinon.communications.dtos import EmailInvitationInput, EmailPreview
from koinon.communications.locale_service import CommunicationLocales
from koinon.communications.locales import subject_line, translate
from koinon.communications.recipients import RecipientService, recipient_unavailable
from koinon.communications.repositories import CommunicationPolicyRepository, OutboxRepository
from koinon.communications.settings import CommunicationsSettings, InstallationLinks
from koinon.communications.templates import EmailRenderer
from koinon.organization_branding.service import OrganizationBrandingService
from koinon.profiles.repositories import ProfileRepository
from koinon.profiles.service import profile_id
from koinon.security.authority import primary_authority


def _expiry(value, zone, locale):
    local = value.astimezone(ZoneInfo(zone))
    if locale.startswith("es"):
        months = (
            "enero",
            "febrero",
            "marzo",
            "abril",
            "mayo",
            "junio",
            "julio",
            "agosto",
            "septiembre",
            "octubre",
            "noviembre",
            "diciembre",
        )
        return f"{local.day} de {months[local.month - 1]} de {local.year} a las {local:%H:%M %Z}"
    return local.strftime("%B ") + str(local.day) + local.strftime(", %Y at %H:%M %Z")


@service(name="communications.content")
class CommunicationContent:
    def __init__(
        self,
        catalog: CatalogService,
        recipients: RecipientService,
        profiles: ProfileRepository,
        branding: OrganizationBrandingService,
        policies: CommunicationPolicyRepository,
        locales: CommunicationLocales,
        renderer: EmailRenderer,
        outbox: OutboxRepository,
        settings: CommunicationsSettings,
        links: InstallationLinks,
        cipher: CommunicationsCipher,
    ):
        self.catalog, self.recipients, self.profiles, self.branding = catalog, recipients, profiles, branding
        self.policies, self.locales, self.renderer, self.outbox = policies, locales, renderer, outbox
        self.settings, self.links, self.cipher = settings, links, cipher

    @primary_authority()
    async def _brand(self, tenant_id):
        row = await self.branding.settings.current(tenant_id)
        return (await self.branding._view(tenant_id, row)).branding

    async def preview_invitation(self, actor, tenant_id, body: EmailInvitationInput):
        prepared = await self.recipients.resolve(actor, tenant_id, body)
        return await self._preview_invitation(actor, tenant_id, body, prepared)

    @primary_authority()
    async def _preview_invitation(self, actor, tenant_id, body, prepared):
        await self.catalog.authorize(actor, tenant_id, "members:write", body.workspace_id)
        await self.recipients.ensure_current(prepared.provider, actor=actor, workspace_id=body.workspace_id)
        tenant = await self.catalog.tenant_repository.find_by_id(tenant_id)
        workspace = (
            await self.catalog.catalog_repository.find_by_id(body.workspace_id) if body.workspace_id else None
        )
        if workspace is not None and (
            workspace.tenant_id != tenant_id
            or workspace.kind != "workspace"
            or workspace.status == "archived"
        ):
            raise recipient_unavailable()
        owner = await self.recipients.known_subject(prepared.provider, prepared.person.external_subject)
        values = dict(
            display_name=prepared.person.display_name,
            email=prepared.person.email,
            message=body.message,
            organization_name=tenant.name,
            workspace_name=workspace.name if workspace else None,
        )
        return await self._invitation_values(
            tenant_id,
            str(uuid4()),
            actor,
            body.role,
            await self.outbox.clock() + timedelta(hours=body.expires_in_hours),
            values,
            owner,
        )

    @primary_authority()
    async def invitation(self, row):
        provider = await self.recipients.snapshot(row.tenant_id, row.provider_id)
        owner = await self.recipients.known_subject(provider, row.external_subject)
        values = self.cipher.open(row.tenant_id, "delivery", row.recipient_ciphertext)
        return await self._invitation_values(
            row.tenant_id, row.id, row.created_by, row.role, row.expires_at, values, owner
        )

    async def _invitation_values(self, tenant_id, identifier, actor, role, expiry, recipient, owner):
        brand = await self._brand(tenant_id)
        locale, origin = await self.locales.resolve(owner=owner, tenant_id=tenant_id)
        actor_profile = await self.profiles.find_by_id(profile_id(actor))
        recipient_profile = await self.profiles.find_by_id(profile_id(owner)) if owner else None
        actor_name = (
            actor_profile.display_name
            if actor_profile and actor_profile.display_name.strip()
            else translate(locale, "team_fallback", organization=recipient["organization_name"])
        )
        policy = await self.policies.find_by_id(tenant_id)
        senders = self.settings.sender_options()
        sender = next((value for value in senders if policy and value.id == policy.sender_id), None) or (
            senders[0] if len(senders) == 1 else None
        )
        scope = recipient.get("workspace_name") or recipient["organization_name"]
        paragraphs = [
            translate(locale, "invite_by", actor=actor_name, organization=recipient["organization_name"]),
            translate(locale, "invite_scope", scope=scope, role=translate(locale, "role_" + role)),
            translate(
                locale,
                "invite_expiry",
                expiry=_expiry(expiry, recipient_profile.time_zone if recipient_profile else "UTC", locale),
            ),
            translate(locale, "invite_sign_in"),
        ]
        if recipient.get("message"):
            paragraphs.append(recipient["message"])
        preview = EmailPreview(
            subject=subject_line(locale, product=brand.product_name, kind="invitation", scope=scope),
            sender_name=sender.display_name if sender else brand.product_name,
            recipient_display_name=recipient["display_name"],
            recipient_email=recipient["email"],
            heading=translate(locale, "invite_heading"),
            paragraphs=paragraphs,
            action_label=translate(locale, "invite_action"),
            footer=translate(locale, "invite_footer"),
            product_name=brand.product_name,
            accent_color=brand.palette.light.accent,
            branding=brand,
            organization_name=recipient["organization_name"],
            workspace_name=recipient.get("workspace_name"),
            effective_locale=locale,
            locale_origin=origin,
        )
        rendered = await self.renderer.render(
            preview,
            action_url=self.links.invitation_url(
                identifier, client_path=self.settings.acceptance_client_path
            ),
            locale=locale,
        )
        return preview.model_copy(
            update={"rendered_html": self.renderer.preview_html(rendered), "rendered_text": rendered.text}
        )

    @primary_authority()
    async def notice(self, event, person):
        brand = await self._brand(event.tenant_id)
        locale, origin = await self.locales.resolve(owner=event.owner_subject, tenant_id=event.tenant_id)
        values = event.event_json
        organization = (
            values.get("organization_name")
            or (await self.catalog.tenant_repository.find_by_id(event.tenant_id)).name
        )
        workspace = values.get("workspace_name")
        scope = workspace or organization
        kind = event.kind
        title = (
            "security_title"
            if kind == "security"
            else "welcome_heading"
            if kind == "welcome"
            else kind + "_title"
        )
        heading = translate(locale, title, product=brand.product_name)
        body_key = (
            "security_" + values.get("subtype", "")
            if kind == "security"
            else "welcome_description"
            if kind == "welcome"
            else kind + "_body"
        )
        paragraphs = [translate(locale, body_key)]
        if values.get("actor_name"):
            paragraphs.append(
                ("Realizado por: " if locale.startswith("es") else "Changed by: ") + values["actor_name"]
            )
        if values.get("label"):
            paragraphs.append(values["label"])
        if values.get("role"):
            paragraphs.append(
                translate(
                    locale, "invite_scope", scope=scope, role=translate(locale, "role_" + values["role"])
                )
            )
        if values.get("scopes"):
            paragraphs.append(
                ("Permisos: " if locale.startswith("es") else "Scopes: ") + ", ".join(values["scopes"])
            )
        footer_key = (
            "security_footer"
            if kind == "security"
            else "welcome_footer"
            if kind == "welcome"
            else kind + "_body"
        )
        subject_kind = "welcome" if kind == "welcome" else "security"
        subject_scope = organization + " / " + workspace if workspace else organization
        return EmailPreview(
            subject=subject_line(
                locale,
                product=brand.product_name,
                kind=subject_kind,
                scope=subject_scope,
                subtype=values.get("subtype") if kind == "security" else None,
            ),
            sender_name=brand.product_name,
            recipient_display_name=person.display_name,
            recipient_email=person.email,
            heading=heading,
            paragraphs=paragraphs,
            action_label=translate(locale, "welcome_action" if kind == "welcome" else "inbox"),
            footer=translate(locale, footer_key),
            product_name=brand.product_name,
            accent_color=brand.palette.light.accent,
            branding=brand,
            organization_name=organization,
            workspace_name=workspace,
            effective_locale=locale,
            locale_origin=origin,
        )

    @primary_authority()
    async def digest(self, event, person, summary, *, locale_override=None):
        brand = await self._brand(event.tenant_id)
        locale, origin = await self.locales.resolve(owner=event.owner_subject, tenant_id=event.tenant_id)
        if locale_override is not None:
            locale, origin = locale_override
        organization = event.event_json["organization_name"]
        cadence = event.event_json["cadence"]
        purpose = "administrative_digest" if summary.audience == "organization_administrators" else "digest"
        return EmailPreview(
            subject=subject_line(
                locale, product=brand.product_name, kind=purpose, scope=organization, cadence=cadence
            ),
            sender_name=brand.product_name,
            recipient_display_name=person.display_name,
            recipient_email=person.email,
            heading=translate(locale, purpose + "_heading"),
            paragraphs=[translate(locale, purpose + "_description")],
            action_label=translate(locale, "digest_action"),
            footer=translate(locale, "digest_footer"),
            product_name=brand.product_name,
            accent_color=brand.palette.light.accent,
            branding=brand,
            organization_name=organization,
            activity_summary=summary,
            effective_locale=locale,
            locale_origin=origin,
        )
