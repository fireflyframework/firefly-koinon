# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import base64
from copy import deepcopy
from datetime import UTC, datetime, timedelta

import pytest
from fixture_readiness import OwnedReadiness
from pyfly.container.scanner import scan_package
from pyfly.context import ApplicationContext
from pyfly.core import Config
from pyfly.data.transaction import current_unit_of_work
from pyfly.kernel import ConflictException, InvalidRequestException, ServiceUnavailableException
from pyfly.security.context import SecurityContext
from pyfly.security.context_holder import SecurityContextHolder

import koinon.jobs.entities  # noqa: F401 -- declare the queue FK target for native metadata fixtures
from koinon.bootstrap.repositories import BootstrapGrantRepository
from koinon.catalog.entities import Membership, Tenant
from koinon.catalog.errors import AccessDenied
from koinon.catalog.repositories import MembershipRepository, TenantRepository
from koinon.catalog.service import CatalogService
from koinon.communications.administration import CommunicationsAdministration
from koinon.communications.bootstrap_contacts import BootstrapContacts
from koinon.communications.configuration import CommunicationsConfiguration
from koinon.communications.content import CommunicationContent
from koinon.communications.crypto import CommunicationsCipher, RecipientReferences
from koinon.communications.delivery import EmailDispatcher
from koinon.communications.digest import DigestScheduler
from koinon.communications.directory import RecipientDirectory, normalize_recipient
from koinon.communications.dtos import EmailInvitationInput
from koinon.communications.events import CommunicationEvents
from koinon.communications.identity import CommunicationIdentityBindings
from koinon.communications.inbox import NotificationService
from koinon.communications.invitations import EmailInvitationService
from koinon.communications.locale_service import CommunicationLocales
from koinon.communications.outbox import CommunicationOutbox
from koinon.communications.readiness import EmailReadiness
from koinon.communications.recipients import RecipientService
from koinon.communications.repositories import (
    BootstrapContactRepository,
    CommunicationPolicyRepository,
    EmailInvitationRepository,
    NotificationPreferenceRepository,
    NotificationRepository,
    OutboxRepository,
    RecipientIdentityRepository,
)
from koinon.communications.settings import CommunicationsSettings, InstallationLinks
from koinon.communications.submission import EmailSubmission
from koinon.communications.templates import EmailRenderer
from koinon.communications.welcome import WelcomeAdmissions
from koinon.corporate_identity.entities import CorporateProvider
from koinon.corporate_identity.repositories import CorporateProviderRepository
from koinon.corporate_identity.settings import IdentityCredentialStore, IdentitySettings
from koinon.organization_branding.repositories import OrganizationBrandingRepository
from koinon.organization_branding.service import OrganizationBrandingService
from koinon.profiles.repositories import ProfileRepository
from koinon.security.settings import OidcSettings
from koinon.tokens.authorization import TokenRestriction
from koinon.tokens.entities import PersonalToken
from koinon.tokens.repositories import PersonalTokenRepository

ACTOR = "https://issuer.test|admin"
PERSON = "https://issuer.test|person"


class OwnedDirectory:
    def __init__(self):
        self.raw = dict(
            id="person", enabled=True, emailVerified=True, email="person@example.test", firstName="Person"
        )
        self.reads = 0

    async def read(self, settings, credential, external_subject, **kwargs):
        assert current_unit_of_work("primary") is None
        self.reads += 1
        return normalize_recipient(settings, external_subject, deepcopy(self.raw))

    async def search(self, settings, credential, **kwargs):
        return [await self.read(settings, credential, self.raw["id"])], None


@pytest.fixture
async def email_context(tmp_path):
    context = ApplicationContext(
        Config(
            {
                "pyfly": {
                    "banner": {"mode": "off"},
                    "data": {
                        "relational": {
                            "enabled": True,
                            "ddl-auto": "create",
                            "url": f"sqlite+aiosqlite:///{tmp_path / 'email.db'}",
                        }
                    },
                }
            }
        )
    )
    scan_package("koinon.catalog", context.container)
    settings = CommunicationsSettings(
        enabled=True,
        verified_senders=[dict(id="main", display_name="Knowledge team", address="team@example.test")],
    )
    native = OwnedDirectory()
    for kind, value in (
        (CommunicationsSettings, settings),
        (IdentitySettings, IdentitySettings(master_key=base64.urlsafe_b64encode(b"k" * 32).decode())),
        (InstallationLinks, InstallationLinks(public_url="https://brain.test")),
        (RecipientDirectory, native),
        (
            OidcSettings,
            OidcSettings(
                issuer="https://issuer.test",
                jwks_uri="https://issuer.test/jwks",
                authorization_uri="https://issuer.test/authorize",
                token_uri="https://issuer.test/token",
                redirect_uri="https://brain.test/login/oauth2/code/koinon",
                client_id="client",
                api_audience="api",
            ),
        ),
    ):
        context.container.register_instance(kind, value)
    context.container.register_instance(EmailReadiness, OwnedReadiness())
    for kind in (
        BootstrapContacts,
        BootstrapContactRepository,
        BootstrapGrantRepository,
        CommunicationsAdministration,
        NotificationService,
        CommunicationOutbox,
        EmailDispatcher,
        EmailSubmission,
        DigestScheduler,
        WelcomeAdmissions,
        CommunicationIdentityBindings,
        CommunicationContent,
        CommunicationLocales,
        EmailRenderer,
        ProfileRepository,
        NotificationPreferenceRepository,
        OrganizationBrandingRepository,
        OrganizationBrandingService,
        CommunicationPolicyRepository,
        NotificationRepository,
        OutboxRepository,
        CommunicationEvents,
        CommunicationsConfiguration,
        CorporateProviderRepository,
        IdentityCredentialStore,
        CommunicationsCipher,
        RecipientReferences,
        RecipientService,
        EmailInvitationRepository,
        RecipientIdentityRepository,
        EmailInvitationService,
        PersonalTokenRepository,
        TokenRestriction,
    ):
        context.register_bean(kind)
    await context.start()
    try:
        for tenant in ("north", "south"):
            await context.get_bean(TenantRepository).save(Tenant(id=tenant, name=tenant))
            await context.get_bean(MembershipRepository).save(
                Membership(id=tenant + "-admin", subject=ACTOR, tenant_id=tenant, role="admin")
            )
        await context.get_bean(CorporateProviderRepository).save(
            CorporateProvider(
                id="provider",
                tenant_id="north",
                kind="keycloak",
                name="People",
                canonical_issuer="https://issuer.test",
                broker_alias=None,
                source_key="@realm",
                settings_json={"kind": "keycloak", "issuer": "https://issuer.test", "client_id": "client"},
                revision=1,
                status="active",
                created_by=ACTOR,
                updated_by=ACTOR,
            )
        )
        yield context, native
    finally:
        await context.stop()


def claims(subject="person"):
    return {"iss": "https://issuer.test", "sub": subject}


async def draft(context, *, workspace_id=None):
    page = await context.get_bean(RecipientService).search(
        ACTOR, "north", provider_id="provider", q="Person", workspace_id=workspace_id
    )
    return EmailInvitationInput(
        recipient_ref=page.items[0].recipient_ref, role="viewer", workspace_id=workspace_id
    )


async def test_email_invitation_is_recipient_bound_uuid_not_bearer_and_replay_is_readonly(email_context):
    context, directory = email_context
    service = context.get_bean(EmailInvitationService)
    body = await draft(context)
    invitation = await service.create(ACTOR, "north", body, "create-one")
    assert "token" not in invitation.model_dump() and invitation.recipient_email == "person@example.test"
    reads = directory.reads
    assert (await service.create(ACTOR, "north", body, "create-one")).id == invitation.id
    assert directory.reads == reads
    with pytest.raises(AccessDenied):
        await service.review("https://issuer.test|other", invitation.id, claims("other"))
    with pytest.raises(AccessDenied):
        await service.accept(
            "https://other.test|person", invitation.id, {"iss": "https://other.test", "sub": "person"}
        )
    member = await service.accept(PERSON, invitation.id, claims())
    assert member.subject == PERSON and member.role == "viewer" and member.workspace_id is None
    await context.get_bean(CatalogService).update_member(ACTOR, "north", member.id, active=False)
    with pytest.raises(ConflictException):
        await service.accept(PERSON, invitation.id, claims())
    assert not (await context.get_bean(MembershipRepository).find_by_id(member.id)).active
    assert (await service.review(PERSON, invitation.id, claims())).status == "accepted"


async def test_current_inviter_provider_and_recipient_account_must_still_be_eligible(email_context):
    context, directory = email_context
    service = context.get_bean(EmailInvitationService)
    invitation = await service.create(ACTOR, "north", await draft(context), "create-two")
    directory.raw["enabled"] = False
    with pytest.raises(AccessDenied):
        await service.accept(PERSON, invitation.id, claims())
    directory.raw["enabled"] = True
    await context.get_bean(MembershipRepository).save(
        Membership(id="second-admin", subject="https://issuer.test|second", tenant_id="north", role="admin")
    )
    await context.get_bean(CatalogService).update_member(
        "https://issuer.test|second", "north", "north-admin", active=False
    )
    with pytest.raises(AccessDenied):
        await service.accept(PERSON, invitation.id, claims())
    assert not await context.get_bean(MembershipRepository).find_all(subject=PERSON)


async def test_decline_and_revoke_never_create_access_and_resend_has_server_cooldown(email_context):
    context, _ = email_context
    service = context.get_bean(EmailInvitationService)
    invitation = await service.create(ACTOR, "north", await draft(context), "create-three")
    with pytest.raises(ConflictException):
        await service.resend(ACTOR, "north", invitation.id)
    assert (await service.decline(PERSON, invitation.id, claims())).status == "declined"
    with pytest.raises(ConflictException):
        await service.accept(PERSON, invitation.id, claims())
    second = await service.create(ACTOR, "north", await draft(context), "create-four")
    await service.revoke(ACTOR, "north", second.id)
    assert (await service.review(PERSON, second.id, claims())).status == "revoked"
    assert not await context.get_bean(MembershipRepository).find_all(subject=PERSON)


async def test_exact_duplicate_is_rejected_but_additional_workspace_grant_is_allowed(email_context):
    context, _ = email_context
    await context.get_bean(CatalogService).create_member(ACTOR, "north", subject=PERSON, role="viewer")
    with pytest.raises(ConflictException):
        await context.get_bean(EmailInvitationService).create(
            ACTOR, "north", await draft(context), "duplicate"
        )
    space = await context.get_bean(CatalogService).create(ACTOR, "north", kind="workspace", name="Research")
    invitation = await context.get_bean(EmailInvitationService).create(
        ACTOR, "north", await draft(context, workspace_id=space.id), "additional"
    )
    member = await context.get_bean(EmailInvitationService).accept(PERSON, invitation.id, claims())
    assert member.workspace_id == space.id


@pytest.mark.parametrize("lost", ["revoked", "expired", "scope"])
async def test_pending_pat_invitation_cannot_escape_origin_credential_revocation_or_ceiling(
    email_context, lost
):
    context, _ = email_context
    tokens = context.get_bean(PersonalTokenRepository)
    token = PersonalToken(
        id="a" * 32,
        subject=ACTOR,
        tenant_id="north",
        name="Owned test fixture",
        token_hash="0" * 64,
        prefix="fixture",
        scopes=["members:write"],
        expires_at=datetime.now(UTC) + timedelta(hours=1),
    )
    await tokens.save(token)
    security_token = SecurityContextHolder.set_context(
        SecurityContext(
            user_id="admin",
            attributes={"iss": "https://issuer.test", "sub": "admin", "koinon_token_id": token.id},
        )
    )
    try:
        invitation = await context.get_bean(EmailInvitationService).create(
            ACTOR, "north", await draft(context), "pat-create"
        )
    finally:
        SecurityContextHolder.reset_context(security_token)
    if lost == "revoked":
        token.revoked_at = datetime.now(UTC)
    elif lost == "expired":
        token.expires_at = datetime.now(UTC) - timedelta(seconds=1)
    else:
        token.scopes = ["profile:read"]
    await tokens.save(token)
    review = await context.get_bean(EmailInvitationService).review(PERSON, invitation.id, claims())
    assert not review.can_accept and review.action_reasons["accept"] in {
        "origin_token_revoked",
        "origin_token_expired",
        "origin_scope_changed",
    }
    with pytest.raises(AccessDenied):
        await context.get_bean(EmailInvitationService).accept(PERSON, invitation.id, claims())
    assert not await context.get_bean(MembershipRepository).find_all(subject=PERSON)


async def test_invitation_outbox_failure_rolls_back_intention(email_context, monkeypatch):
    context, _ = email_context
    body = await draft(context)

    async def fail(*args, **kwargs):
        raise RuntimeError("fixture outbox failure")

    monkeypatch.setattr(context.get_bean(OutboxRepository), "save", fail)
    with pytest.raises(RuntimeError, match="fixture outbox failure"):
        await context.get_bean(EmailInvitationService).create(ACTOR, "north", body, "rollback")
    assert not await context.get_bean(EmailInvitationRepository).find_all(tenant_id="north")


async def test_members_inviter_gets_only_bounded_provider_choices_and_no_arbitrary_default(email_context):
    context, _ = email_context
    recipients = context.get_bean(RecipientService)
    options = await recipients.providers_page(ACTOR, "north")
    assert options.items[0].model_dump() == {"id": "provider", "display_name": "People"}
    assert len((await recipients.search(ACTOR, "north", q="Person")).items) == 1
    row = await context.get_bean(CorporateProviderRepository).find_by_id("provider")
    second = CorporateProvider(
        id="provider-two",
        tenant_id="north",
        kind=row.kind,
        name="Other people",
        canonical_issuer=row.canonical_issuer,
        broker_alias="other",
        source_key="other",
        settings_json=row.settings_json,
        revision=1,
        status="active",
        created_by=ACTOR,
        updated_by=ACTOR,
    )
    await context.get_bean(CorporateProviderRepository).save(second)
    with pytest.raises(InvalidRequestException) as error:
        await recipients.search(ACTOR, "north", q="Person")
    assert error.value.code == "RECIPIENT_PROVIDER_REQUIRED"


async def test_email_create_requires_real_ready_channel_even_when_brand_and_sender_are_present(email_context):
    context, _ = email_context
    context.get_bean(EmailReadiness).state = "not_configured"
    with pytest.raises(ServiceUnavailableException):
        await context.get_bean(EmailInvitationService).create(
            ACTOR, "north", await draft(context), "disabled"
        )
    assert not await context.get_bean(EmailInvitationRepository).find_all(tenant_id="north")
