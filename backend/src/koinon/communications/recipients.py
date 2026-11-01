# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Fresh directory observations outside units, followed by current primary authority checks."""

from dataclasses import dataclass, field
from datetime import UTC, datetime

from pydantic import TypeAdapter
from pyfly.container import service
from pyfly.kernel import ConflictException, InvalidRequestException

from koinon.catalog.errors import AccessDenied
from koinon.catalog.service import CatalogService
from koinon.communications.crypto import RecipientReferences
from koinon.communications.directory import DirectoryPerson, RecipientDirectory
from koinon.communications.dtos import (
    DirectoryRecipient,
    DirectoryRecipientPage,
    EmailInvitationInput,
    RecipientProvider,
    RecipientProviderPage,
)
from koinon.communications.repositories import RecipientIdentityRepository
from koinon.communications.settings import CommunicationsSettings
from koinon.corporate_identity.challenges import policy as identity_policy
from koinon.corporate_identity.dtos import (
    EntraSettings,
    KeycloakSettings,
    ProviderCredential,
    ProviderSettings,
)
from koinon.corporate_identity.entities import CorporateProvider
from koinon.corporate_identity.policy import IdentityPolicy, verified_identity
from koinon.corporate_identity.repositories import CorporateProviderRepository
from koinon.corporate_identity.settings import IdentityCredentialStore
from koinon.security.authority import primary_authority
from koinon.security.settings import OidcSettings
from koinon.web.pagination import sql_page


def recipient_unavailable():
    return AccessDenied("This invitation or recipient is unavailable", code="EMAIL_INVITATION_UNAVAILABLE")


@dataclass(frozen=True, slots=True)
class ProviderSnapshot:
    id: str
    tenant_id: str
    revision: int
    name: str
    policy: IdentityPolicy
    settings: ProviderSettings
    credential: ProviderCredential | None = field(repr=False)


@dataclass(frozen=True, slots=True)
class PreparedRecipient:
    provider: ProviderSnapshot
    person: DirectoryPerson
    observed_at: datetime


@service(name="communications.recipients")
class RecipientService:
    def __init__(
        self,
        catalog: CatalogService,
        providers: CorporateProviderRepository,
        credentials: IdentityCredentialStore,
        directory: RecipientDirectory,
        references: RecipientReferences,
        oidc: OidcSettings,
        settings: CommunicationsSettings,
        identities: RecipientIdentityRepository,
    ):
        self.catalog, self.providers, self.credentials = catalog, providers, credentials
        self.directory, self.references, self.oidc, self.settings, self.identities = (
            directory,
            references,
            oidc,
            settings,
            identities,
        )

    @primary_authority()
    async def snapshot(self, tenant_id, provider_id, *, actor=None, workspace_id=None):
        if actor is not None:
            await self.catalog.authorize(actor, tenant_id, "members:write", workspace_id)
        row = await self.providers.find_by_id(provider_id)
        if (
            row is None
            or row.tenant_id != tenant_id
            or row.status != "active"
            or row.canonical_issuer != self.oidc.issuer
        ):
            raise recipient_unavailable()
        settings = TypeAdapter(ProviderSettings).validate_python(row.settings_json)
        direct_entra = isinstance(settings, EntraSettings) and settings.identity_mode == "direct"
        if (
            isinstance(settings, EntraSettings)
            and settings.identity_mode == "direct"
            and (
                row.broker_alias is not None
                or self.oidc.issuer != f"https://login.microsoftonline.com/{settings.tenant_id}/v2.0"
                or settings.client_id != self.oidc.client_id
            )
        ):
            raise recipient_unavailable()
        if (
            settings.kind != row.kind
            or not direct_entra
            and (
                row.broker_alias is None
                and (
                    not isinstance(settings, KeycloakSettings)
                    or settings.issuer != self.oidc.issuer
                    or settings.client_id != self.oidc.client_id
                )
            )
        ):
            raise recipient_unavailable()
        credential = (
            self.credentials.decrypt(tenant_id, provider_id, row.secret_ciphertext)
            if row.secret_ciphertext
            else None
        )
        policy = identity_policy(row, self.oidc)
        return ProviderSnapshot(row.id, row.tenant_id, row.revision, row.name, policy, settings, credential)

    async def ensure_current(self, snapshot, *, actor=None, workspace_id=None):
        current = await self.snapshot(snapshot.tenant_id, snapshot.id, actor=actor, workspace_id=workspace_id)
        if (
            current.revision != snapshot.revision
            or current.policy != snapshot.policy
            or current.settings != snapshot.settings
        ):
            raise recipient_unavailable()
        return current

    @staticmethod
    def require_identity(actor, claims, provider, external_subject):
        try:
            identity = verified_identity(provider.policy, claims)
            if identity.subject != actor or identity.external_subject != external_subject:
                raise recipient_unavailable()
        except Exception:
            raise recipient_unavailable() from None

    @primary_authority()
    async def known_subject(self, provider, external_subject):
        rows = await self.identities.find_all(
            tenant_id=provider.tenant_id, provider_id=provider.id, external_subject=external_subject
        )
        if rows:
            return rows[0].subject
        # In a direct native realm, directory id is the OIDC sub by the existing verified identity policy.
        if provider.policy.kind == "keycloak" and provider.policy.broker_alias is None:
            return provider.policy.canonical_issuer + "|" + external_subject
        return None

    @primary_authority()
    async def exact_membership(self, provider, external_subject, workspace_id):
        subject = await self.known_subject(provider, external_subject)
        if not subject:
            return False
        rows = await self.catalog.membership_repository.find_all(
            tenant_id=provider.tenant_id, subject=subject, workspace_id=workspace_id, active=True
        )
        return bool(rows)

    async def observe(self, provider, external_subject):
        person = await self.directory.read(
            provider.settings,
            provider.credential,
            external_subject,
            allow_entra_guests=self.settings.allow_entra_guests,
        )
        if person.delivery_address_status != "verified_directory" or person.email is None:
            raise recipient_unavailable()
        await self.ensure_current(provider)
        return PreparedRecipient(provider, person, datetime.now(UTC))

    async def resolve(self, actor, tenant_id, body: EmailInvitationInput):
        binding = self.references.open(body.recipient_ref, actor=actor, tenant_id=tenant_id)
        provider = await self.snapshot(
            tenant_id, binding.provider_id, actor=actor, workspace_id=body.workspace_id
        )
        if provider.revision != binding.provider_revision:
            raise recipient_unavailable()
        prepared = await self.observe(provider, binding.external_subject)
        if await self.exact_membership(provider, prepared.person.external_subject, body.workspace_id):
            raise ConflictException(
                "This person already has a role assignment in the exact scope", code="MEMBERSHIP_EXISTS"
            )
        return prepared

    @primary_authority()
    async def providers_page(self, actor, tenant_id, *, workspace_id=None, page=1, page_size=20):
        await self.catalog.authorize(actor, tenant_id, "members:write", workspace_id)
        if type(page_size) is not int or not 1 <= page_size <= 20:
            raise InvalidRequestException(
                "Choose a provider page size from one to twenty", code="INVALID_PAGE"
            )
        rows = await sql_page(
            CorporateProvider,
            [
                CorporateProvider.tenant_id == tenant_id,
                CorporateProvider.canonical_issuer == self.oidc.issuer,
                CorporateProvider.status == "active",
            ],
            page=page,
            page_size=page_size,
            sorts=("created_at",),
        )
        return RecipientProviderPage(
            **{
                **rows,
                "items": [RecipientProvider(id=row.id, display_name=row.name) for row in rows["items"]],
            }
        )

    async def search(self, actor, tenant_id, *, provider_id=None, q, workspace_id=None, after=None, limit=20):
        if provider_id is None:
            choices = await self.providers_page(actor, tenant_id, workspace_id=workspace_id, page_size=2)
            if choices.total != 1:
                raise InvalidRequestException(
                    "Select an explicit active identity provider", code="RECIPIENT_PROVIDER_REQUIRED"
                )
            provider_id = choices.items[0].id
        provider = await self.snapshot(tenant_id, provider_id, actor=actor, workspace_id=workspace_id)
        cursor = None
        if after:
            try:
                value = self.references.cipher.open(tenant_id, "directory_cursor", after)
                if (value["actor"], value["provider"], value["revision"], value["q"], value["workspace"]) != (
                    actor,
                    provider_id,
                    provider.revision,
                    q,
                    workspace_id,
                ) or not 0 <= datetime.now(UTC).timestamp() - value["issued_at"] < 300:
                    raise ValueError()
                cursor = value["cursor"]
            except Exception:
                raise InvalidRequestException(
                    "Search the current directory again", code="RECIPIENT_CURSOR_UNAVAILABLE"
                ) from None
        people, following = await self.directory.search(
            provider.settings,
            provider.credential,
            q=q,
            limit=limit,
            after=cursor,
            allow_entra_guests=self.settings.allow_entra_guests,
        )
        await self.ensure_current(provider, actor=actor, workspace_id=workspace_id)
        items = []
        for person in people:
            eligible = person.delivery_address_status == "verified_directory"
            existing = (
                await self.exact_membership(provider, person.external_subject, workspace_id)
                if eligible
                else False
            )
            reference = (
                self.references.issue(
                    actor=actor,
                    tenant_id=tenant_id,
                    provider_id=provider.id,
                    provider_revision=provider.revision,
                    external_subject=person.external_subject,
                )
                if eligible
                else None
            )
            items.append(
                DirectoryRecipient(
                    recipient_ref=reference,
                    display_name=person.display_name,
                    email=person.email,
                    provider_label=provider.name,
                    delivery_address_status=person.delivery_address_status,
                    eligibility="already_has_access"
                    if existing
                    else "eligible"
                    if eligible
                    else "unavailable",
                    eligibility_reason="MEMBERSHIP_EXISTS" if existing else person.reason,
                )
            )
        next_cursor = (
            self.references.cipher.seal(
                tenant_id,
                "directory_cursor",
                dict(
                    actor=actor,
                    provider=provider_id,
                    revision=provider.revision,
                    q=q,
                    workspace=workspace_id,
                    cursor=following,
                    issued_at=datetime.now(UTC).timestamp(),
                ),
            )
            if following
            else None
        )
        return DirectoryRecipientPage(items=items, next_cursor=next_cursor)
