# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import pytest

from koinon.communications.locales import effective_locale, translate


def test_explicit_notification_locale_then_organization_then_installation_then_default():
    assert effective_locale(user="es-MX", organization="en-US", installation="en-US") == ("es-MX", "user")
    assert effective_locale(organization="es-ES", installation="en-US") == ("es-ES", "organization")
    assert effective_locale(installation="es-ES") == ("es-ES", "installation")
    assert effective_locale() == ("en-US", "default")
    with pytest.raises(ValueError):
        effective_locale(user="unknown")


def test_catalog_covers_every_product_message_in_both_languages_without_translating_fixed_attribution():
    for locale in ("en-US", "es-ES"):
        for key in (
            "invite_heading",
            "invite_action",
            "invite_footer",
            "digest_heading",
            "digest_action",
            "digest_footer",
            "preferences",
            "accept",
            "decline",
            "access_granted_title",
            "role_changed_title",
            "access_removed_title",
            "security_title",
            "security_token_created",
            "security_token_revoked",
            "security_application_granted",
            "security_application_revoked",
            "security_client_registered",
            "security_client_revoked",
            "security_client_secret_rotated",
            "mcp_summary_unavailable",
        ):
            value = translate(locale, key, product="Example", actor="Team", organization="Organization")
            assert value and "{" not in value
    assert translate("es-ES", "accept") == "Aceptar"
    assert translate("en-US", "accept") == "Accept"
