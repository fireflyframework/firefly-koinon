# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Enabled installation mutations must never silently omit durable account notices."""

from pyfly.container import Container, service

from koinon.authorized_applications.service import AuthorizedApplicationService
from koinon.catalog.ports import MembershipEventRecorder
from koinon.catalog.service import CatalogService
from koinon.communications.ports import (
    AccountEventRecorder,
    CommunicationIdentityObserver,
    WelcomeAdmissionPort,
)
from koinon.communications.settings import CommunicationsSettings
from koinon.mcp_applications.service import McpOAuthClientRegistry
from koinon.tokens.service import PersonalTokenService


@service(name="communications.preflight")
class CommunicationsPreflight:
    def __init__(self, container: Container, settings: CommunicationsSettings):
        self.container, self.settings = container, settings

    async def start(self):
        if not self.settings.enabled:
            return
        self.container.resolve(MembershipEventRecorder)
        self.container.resolve(AccountEventRecorder)
        self.container.resolve(CommunicationIdentityObserver)
        self.container.resolve(WelcomeAdmissionPort)
        catalog = self.container.resolve(CatalogService)
        if catalog.membership_events is None or any(
            self.container.resolve(kind).events is None
            for kind in (PersonalTokenService, AuthorizedApplicationService, McpOAuthClientRegistry)
        ):
            raise RuntimeError(
                "Enabled communications requires atomic event recorder bindings "
                "on every account mutation service"
            )

    async def stop(self):
        pass
