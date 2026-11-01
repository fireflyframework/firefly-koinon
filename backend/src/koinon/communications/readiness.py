# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Declared native transport and verified operator sender configuration; never mailbox proof."""

from pyfly.config.properties.data import parse_bool
from pyfly.container import Container, component
from pyfly.container.exceptions import NoSuchBeanError
from pyfly.core import Config
from pyfly.kernel import ServiceUnavailableException
from pyfly.notifications.capabilities import email_capabilities
from pyfly.notifications.ports import EmailProvider
from pyfly.notifications.services import DefaultEmailService

from koinon.communications.dtos import CommunicationCapabilities, CommunicationIssue, VerifiedSenderOption
from koinon.communications.locales import effective_locale
from koinon.communications.settings import CommunicationsSettings, InstallationLinks


@component(name="communications.email_readiness")
class EmailReadiness:
    def __init__(
        self, container: Container, settings: CommunicationsSettings, links: InstallationLinks, config: Config
    ):
        self.container, self.settings, self.links, self.config = container, settings, links, config

    def observe(self, *, sender_id=None, organization_locale=None):
        options = self.settings.sender_options()
        chosen = (
            next((item for item in options if item.id == sender_id), None)
            if sender_id
            else options[0]
            if len(options) == 1
            else None
        )
        issues = []
        provider_label = ""
        if self.settings.enabled:
            if not self.links.public_url:
                issues.append(
                    CommunicationIssue(
                        code="PUBLIC_ORIGIN_REQUIRED",
                        explanation="Configure the canonical public HTTPS origin.",
                    )
                )
            if chosen is None:
                issues.append(
                    CommunicationIssue(
                        code="VERIFIED_SENDER_REQUIRED",
                        explanation="Select an operator-verified sender identity.",
                    )
                )
            try:
                if not parse_bool(
                    self.config.get("pyfly.notifications.enabled", False), "notifications.enabled"
                ):
                    issues.append(
                        CommunicationIssue(
                            code="EMAIL_DISABLED", explanation="The installation email channel is disabled."
                        )
                    )
                    raise NoSuchBeanError(bean_type=EmailProvider)
                provider = self.container.resolve(EmailProvider)
                self.container.resolve(DefaultEmailService)
                caps = email_capabilities(provider)
                if not caps.real_delivery or not caps.inline_cid:
                    raise NoSuchBeanError(bean_type=EmailProvider)
                provider_label = provider.name
            except NoSuchBeanError:
                issues.append(
                    CommunicationIssue(
                        code="REAL_EMAIL_TRANSPORT_REQUIRED",
                        explanation=(
                            "Configure a native email transport with real delivery and inline image support."
                        ),
                    )
                )
        state = "disabled" if not self.settings.enabled else "not_configured" if issues else "ready"
        locale, origin = effective_locale(
            organization=organization_locale, installation=self.settings.default_locale
        )
        return CommunicationCapabilities(
            state=state,
            provider_label=provider_label,
            sender_name=chosen.display_name if chosen else "",
            sender_address=chosen.address if chosen else "",
            sender_options=[VerifiedSenderOption(**item.model_dump()) for item in options],
            public_address_configured=bool(self.links.public_url),
            public_url=self.links.public_url or None,
            acceptance_base=self.links.public_url + self.settings.acceptance_client_path
            if self.links.public_url
            else None,
            issues=issues,
            effective_locale=locale,
            locale_origin=origin,
        )

    def require_ready(self, *, sender_id=None):
        observation = self.observe(sender_id=sender_id)
        if observation.state != "ready":
            raise ServiceUnavailableException(
                "Email delivery configuration is not ready", code="COMMUNICATIONS_NOT_READY"
            )
        return observation
