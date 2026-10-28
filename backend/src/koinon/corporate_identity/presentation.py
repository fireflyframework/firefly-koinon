# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Initialize a new verified profile without replacing a person's saved preferences or photo."""

from pydantic import TypeAdapter
from pyfly.container import service

from koinon.corporate_identity.challenges import policy
from koinon.corporate_identity.directory import NativeCorporateDirectory
from koinon.corporate_identity.dtos import ProviderSettings
from koinon.corporate_identity.policy import verified_identity
from koinon.corporate_identity.repositories import CorporateProviderRepository
from koinon.corporate_identity.settings import IdentityCredentialStore
from koinon.profiles.service import ProfileService, profile_id
from koinon.security.settings import OidcSettings


@service(name="identity.presentation")
class CorporatePresentation:
    def __init__(
        self,
        providers: CorporateProviderRepository,
        directory: NativeCorporateDirectory,
        credentials: IdentityCredentialStore,
        profiles: ProfileService,
        oidc: OidcSettings,
    ):
        self.providers, self.directory, self.credentials = providers, directory, credentials
        self.profiles, self.oidc = profiles, oidc

    async def initialize(self, context):
        subject = f"{context.attributes['iss']}|{context.user_id}"
        existing = await self.profiles.profiles.find_by_id(profile_id(subject))
        await self.profiles.get(subject, context.attributes)
        if existing is not None:
            return
        providers = await self.providers.find_all(
            canonical_issuer=self.oidc.issuer,
            broker_alias=context.attributes.get("koinon_identity_provider"),
            status="active",
        )
        for provider in providers:
            try:
                identity = verified_identity(policy(provider), context.attributes)
                settings = TypeAdapter(ProviderSettings).validate_python(provider.settings_json)
                if settings.kind == "keycloak":
                    continue
                credential = (
                    self.credentials.decrypt(provider.tenant_id, provider.id, provider.secret_ciphertext)
                    if provider.secret_ciphertext
                    else None
                )
                token = await self.directory.acquire(settings, credential)
                content = await self.directory.avatar(settings, token, identity.external_subject)
                if content is not None:
                    await self.profiles.set_avatar(subject, content)
                    return
            except Exception:
                # A missing corporate photo must not prevent sign-in or replace saved preferences.
                continue
