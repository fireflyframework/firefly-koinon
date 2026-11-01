# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from pyfly.container import component

from koinon.communications.locales import effective_locale
from koinon.communications.repositories import CommunicationPolicyRepository, NotificationPreferenceRepository
from koinon.communications.settings import CommunicationsSettings
from koinon.security.authority import primary_authority


@component(name="communications.locales")
class CommunicationLocales:
    def __init__(
        self,
        preferences: NotificationPreferenceRepository,
        policies: CommunicationPolicyRepository,
        settings: CommunicationsSettings,
    ):
        self.preferences, self.policies, self.settings = preferences, policies, settings

    @primary_authority()
    async def resolve(self, *, owner=None, tenant_id=None):
        preference = await self.preferences.find_by_id(owner) if owner else None
        policy = await self.policies.find_by_id(tenant_id) if tenant_id else None
        return effective_locale(
            user=preference.notification_locale if preference else None,
            organization=policy.default_locale if policy else None,
            installation=self.settings.default_locale,
        )
