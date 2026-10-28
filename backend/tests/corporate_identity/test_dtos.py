# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import pytest
from pydantic import ValidationError

from koinon.corporate_identity.dtos import IdentityProviderInput, IdentityProviderPatch


def test_provider_inputs_are_typed_and_secrets_are_redacted():
    value = IdentityProviderInput(
        kind="entra",
        name="Corporate sign-in",
        broker_alias="north-entra",
        settings={
            "kind": "entra",
            "tenant_id": "11111111-1111-1111-1111-111111111111",
            "client_id": "client",
        },
        credential={"kind": "entra", "secret": "not-a-real-secret"},
    )
    assert "not-a-real-secret" not in repr(value)
    assert "not-a-real-secret" not in value.model_dump_json()
    for changes in (
        {"kind": "google_workspace"},
        {"settings": {"kind": "entra", "tenant_id": "common", "client_id": "client"}},
        {"unexpected": "value"},
        {"broker_alias": "../other"},
    ):
        with pytest.raises(ValidationError):
            IdentityProviderInput.model_validate({**value.model_dump(), **changes})


def test_google_domain_policy_is_explicit_and_patch_distinguishes_clear_from_omission():
    value = IdentityProviderInput(
        kind="google_workspace",
        name="Workspace",
        broker_alias="north-google",
        settings={"kind": "google_workspace", "client_id": "client", "hosted_domains": ["Example.test"]},
    )
    assert value.settings.hosted_domains == ["example.test"]
    for domain in ("*", "@example.test", "https://example.test", "example.test/path", ""):
        with pytest.raises(ValidationError):
            IdentityProviderInput.model_validate(
                {
                    **value.model_dump(),
                    "settings": {
                        "kind": "google_workspace",
                        "client_id": "client",
                        "hosted_domains": [domain],
                    },
                }
            )
    omitted = IdentityProviderPatch(expected_revision=1, name="New name")
    cleared = IdentityProviderPatch(expected_revision=1, credential=None)
    assert "credential" not in omitted.model_fields_set
    assert "credential" in cleared.model_fields_set and cleared.credential is None


def test_patch_rejects_blank_or_control_character_names():
    for value in ("   ", "Hidden\ncontrol"):
        with pytest.raises(ValidationError):
            IdentityProviderPatch(expected_revision=1, name=value)


def test_google_directory_credentials_do_not_require_an_unused_broker_client_secret():
    from koinon.corporate_identity.dtos import GoogleCredential

    credential = GoogleCredential(
        kind="google_workspace",
        service_account_email="directory@fixture.invalid",
        private_key="synthetic-only-not-a-key",
        delegated_admin="admin@fixture.invalid",
    )
    assert credential.secret is None
    assert "secret" not in credential.model_dump(exclude_none=True)
    assert "synthetic-only-not-a-key" not in repr(credential)
