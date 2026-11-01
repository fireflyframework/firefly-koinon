# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from pyfly.container import Container
from pyfly.core import Config
from pyfly.notifications.capabilities import EmailProviderCapabilities
from pyfly.notifications.ports import EmailProvider
from pyfly.notifications.providers.dummy import DummyEmailProvider
from pyfly.notifications.services import DefaultEmailService

from koinon.communications.readiness import EmailReadiness
from koinon.communications.settings import CommunicationsSettings, InstallationLinks


class OwnedProvider:
    name = "owned-fixture"
    capabilities = EmailProviderCapabilities(real_delivery=True, inline_cid=True)

    async def send(self, message):
        raise AssertionError("Readiness must never dispatch")


def readiness(provider=None):
    container = Container()
    if provider is not None:
        container.register_instance(EmailProvider, provider)
        container.register_instance(DefaultEmailService, DefaultEmailService(provider))
    settings = CommunicationsSettings(
        enabled=True, verified_senders=[dict(id="main", display_name="Team", address="team@example.test")]
    )
    return EmailReadiness(
        container,
        settings,
        InstallationLinks(public_url="https://brain.test"),
        Config({"pyfly": {"notifications": {"enabled": True}}}),
    )


def test_absent_dummy_and_undeclared_providers_never_count_as_real_delivery_ready():
    assert readiness().observe().state == "not_configured"
    assert readiness(DummyEmailProvider()).observe().state == "not_configured"
    provider = OwnedProvider()
    provider.capabilities = EmailProviderCapabilities()
    assert readiness(provider).observe().state == "not_configured"


def test_declared_real_cid_transport_and_verified_sender_only_claim_configuration_not_delivery():
    result = readiness(OwnedProvider()).observe()
    assert result.state == "ready" and result.sender_address == "team@example.test"
    assert result.acceptance_base == "https://brain.test/auth/invitations/email"
    assert result.sender_options[0].id == "main"
    assert readiness(OwnedProvider()).observe(sender_id="other").state == "not_configured"


def test_explicit_disabled_native_channel_wins_over_an_available_provider_binding():
    service = readiness(OwnedProvider())
    service.config = Config({"pyfly": {"notifications": {"enabled": False}}})
    assert service.observe().state == "not_configured"
    assert any(issue.code == "EMAIL_DISABLED" for issue in service.observe().issues)
