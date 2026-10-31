# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import pytest

from koinon.corporate_identity.dtos import EntraSettings, GoogleWorkspaceSettings, KeycloakSettings
from koinon.corporate_profiles.dtos import CorporateProfileSyncPolicy, KeycloakProfileAttributes

OID = "22222222-2222-4222-8222-222222222222"
TID = "11111111-1111-4111-8111-111111111111"


def test_entra_normalizes_directory_fields_and_refuses_app_only_manager():
    from koinon.corporate_profiles.normalization import normalize_user

    settings = EntraSettings(kind="entra", tenant_id=TID, client_id="client")
    result = normalize_user(
        settings,
        CorporateProfileSyncPolicy(manager_source="directory"),
        OID,
        {
            "id": OID,
            "accountEnabled": True,
            "displayName": "Member",
            "jobTitle": "Engineer",
            "department": "Platform",
        },
    )
    assert result.fields["job_title"].value == "Engineer"
    assert result.fields["department"].value == "Platform"
    assert result.fields["manager"].status == "unsupported"
    assert result.fields["manager"].code == "PROFILE_MANAGER_APP_UNSUPPORTED"


def test_google_uses_one_primary_organization_and_only_provider_manager_relation():
    from koinon.corporate_profiles.normalization import normalize_user

    settings = GoogleWorkspaceSettings(
        kind="google_workspace", client_id="client", hosted_domains=["example.org"], customer_id="C001"
    )
    raw = {
        "id": "user123",
        "customerId": "C001",
        "suspended": False,
        "name": {"fullName": "Member"},
        "organizations": [{"primary": True, "title": "Lead", "department": "Engineering"}],
        "relations": [{"type": "manager", "value": "manager@example.org"}],
    }
    result = normalize_user(settings, CorporateProfileSyncPolicy(manager_source="directory"), "user123", raw)
    assert result.fields["job_title"].value == "Lead"
    assert result.manager_lookup == "manager@example.org"
    assert result.customer_id == "C001"
    raw["organizations"].append({"primary": True, "title": "Wrong"})
    assert (
        normalize_user(settings, CorporateProfileSyncPolicy(), "user123", raw).fields["job_title"].status
        == "unavailable"
    )


@pytest.mark.parametrize("field,value", [("id", "someone_else"), ("customerId", "C002"), ("suspended", True)])
def test_google_rejects_wrong_identity_customer_and_inactive_user(field, value):
    from koinon.corporate_profiles.normalization import ProfileObservationError, normalize_user

    settings = GoogleWorkspaceSettings(
        kind="google_workspace", client_id="client", hosted_domains=["example.org"], customer_id="C001"
    )
    raw = {"id": "user123", "customerId": "C001", "suspended": False, "name": {"fullName": "Member"}}
    raw[field] = value
    with pytest.raises(ProfileObservationError):
        normalize_user(settings, CorporateProfileSyncPolicy(), "user123", raw)


def test_keycloak_multivalued_attributes_do_not_win_by_array_order():
    from koinon.corporate_profiles.normalization import normalize_user

    settings = KeycloakSettings(
        kind="keycloak", issuer="https://identity.example/realms/company", client_id="client"
    )
    config = CorporateProfileSyncPolicy(
        keycloak_attributes=KeycloakProfileAttributes(
            job_title="jobTitle", department="department", manager="managerId"
        ),
        manager_source="directory",
    )
    result = normalize_user(
        settings,
        config,
        "user",
        {
            "id": "user",
            "enabled": True,
            "firstName": "First",
            "lastName": "Last",
            "attributes": {
                "jobTitle": ["Wrong", "Other"],
                "department": ["Operations"],
                "managerId": ["manager"],
            },
        },
    )
    assert result.fields["display_name"].value == "First Last"
    assert result.fields["job_title"].status == "unavailable"
    assert result.fields["department"].value == "Operations"
    assert result.fields["manager"].value == "manager"
