# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import pytest
from pydantic import ValidationError

from koinon.organization_people.dtos import OrganizationProfileMappingInput


def test_mapping_accepts_explicit_typed_corporate_profile_policy():
    body = OrganizationProfileMappingInput.model_validate(
        {
            "expected_revision": 0,
            "enabled": True,
            "fields": {},
            "profile_sync": {
                "interval_seconds": 900,
                "manager_source": "verified_claims",
                "allow_personal_overrides": True,
            },
        }
    )
    assert body.profile_sync.interval_seconds == 900
    assert body.profile_sync.manager_source == "verified_claims"
    assert body.profile_sync.allow_personal_overrides is True


def test_legacy_mapping_distinguishes_policy_omission_from_explicit_null():
    base = {"expected_revision": 0, "enabled": True, "fields": {}}
    omitted = OrganizationProfileMappingInput.model_validate(base)
    cleared = OrganizationProfileMappingInput.model_validate({**base, "profile_sync": None})
    assert "profile_sync" not in omitted.model_fields_set
    assert "profile_sync" in cleared.model_fields_set
    assert cleared.profile_sync is None


@pytest.mark.parametrize(
    "bad",
    [
        {"interval_seconds": True},
        {"interval_seconds": 299},
        {"interval_seconds": 86401},
        {"allow_personal_overrides": "true"},
        {"unknown": 1},
    ],
)
def test_profile_policy_rejects_invalid_admin_input(bad):
    from koinon.corporate_profiles.dtos import CorporateProfileSyncPolicy

    with pytest.raises(ValidationError):
        CorporateProfileSyncPolicy.model_validate(bad)


@pytest.mark.parametrize(
    "name", ["userAccessTokenValue", "custom_secret_value", "password", "email", "groups"]
)
def test_keycloak_profile_attributes_cannot_select_credentials_or_identity(name):
    from koinon.corporate_profiles.dtos import KeycloakProfileAttributes

    with pytest.raises(ValidationError):
        KeycloakProfileAttributes(job_title=name)


def test_presentation_patch_schema_optional_fields_do_not_advertise_null():
    from koinon.corporate_profiles.dtos import OrganizationPresentationInput

    schema = OrganizationPresentationInput.model_json_schema()
    for name in ("name_mode", "avatar_mode"):
        assert '"type": "null"' not in __import__("json").dumps(schema["properties"][name])
        with pytest.raises(ValidationError):
            OrganizationPresentationInput.model_validate({"expected_revision": 0, name: None})
