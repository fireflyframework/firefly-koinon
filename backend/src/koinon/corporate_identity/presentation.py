# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Initialize personal preferences; corporate photos belong to tenant overlays."""

from pyfly.container import service

from koinon.corporate_identity.directory import NativeCorporateDirectory
from koinon.corporate_identity.repositories import CorporateProviderRepository
from koinon.corporate_identity.settings import IdentityCredentialStore
from koinon.profiles.service import ProfileService
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
        await self.profiles.get(subject, context.attributes)
