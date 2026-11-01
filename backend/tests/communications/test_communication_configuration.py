# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import pytest

from koinon.communications.settings import CommunicationsSettings, InstallationLinks
from koinon.operations.configuration import environment_configuration


@pytest.mark.parametrize(
    "url",
    [
        "https://user:password@brain.test",
        "https://brain.test/path",
        "https://brain.test?other=1",
        "https://brain.test/#fragment",
        "http://brain.test",
        "//brain.test",
        "https://brain.test\\other",
    ],
)
def test_public_origin_requires_exact_operator_https_origin(url):
    with pytest.raises(ValueError):
        InstallationLinks(public_url=url)


def test_native_acceptance_is_default_and_never_uses_request_host():
    links = InstallationLinks(public_url="https://brain.test/")
    assert (
        links.invitation_url("11111111-1111-1111-1111-111111111111")
        == "https://brain.test/auth/invitations/email/11111111-1111-1111-1111-111111111111"
    )
    with pytest.raises(ValueError):
        links.invitation_url("../../other")
    with pytest.raises(ValueError):
        InstallationLinks().invitation_url("11111111-1111-1111-1111-111111111111")


def test_actual_environment_alias_sets_typed_canonical_origin(monkeypatch):
    monkeypatch.setenv("KOINON_OIDC_ISSUER", "https://identity.test/realms/people")
    monkeypatch.setenv("KOINON_PUBLIC_URL", "https://brain.test")
    monkeypatch.setenv("PYFLY_DATA_RELATIONAL_URL", "sqlite+aiosqlite:///:memory:")
    assert environment_configuration()["koinon"]["public_url"] == "https://brain.test"


def test_verified_sender_choices_cannot_inject_headers_or_duplicate_ids():
    choice = dict(id="main", display_name="Knowledge team", address="team@example.test")
    settings = CommunicationsSettings(verified_senders=[choice])
    assert settings.sender_options()[0].address == "team@example.test"
    for senders in (
        [{**choice, "address": "team@example.test\r\nBcc:other@example.test"}],
        [choice, choice],
        [{**choice, "verified": True}],
        [{**choice, "display_name": "Team\r\nOther"}],
    ):
        with pytest.raises(ValueError):
            CommunicationsSettings(verified_senders=senders)
