# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0


def test_new_inputs_reject_coercion_unknowns_and_unsafe_text():
    import pytest
    from pydantic import ValidationError

    from koinon.organization_people.dtos import (
        OrganizationPersonPatch,
        OrganizationProfileMappingInput,
        OrganizationUnitInput,
    )

    for values in (
        {"expected_revision": True},
        {"expected_revision": "1"},
        {"expected_revision": 1, "role": "admin"},
        {"expected_revision": 1, "manage_locally": "true"},
        {"expected_revision": 1, "job_title": "  "},
    ):
        with pytest.raises(ValidationError):
            OrganizationPersonPatch.model_validate(values)
    with pytest.raises(ValidationError):
        OrganizationProfileMappingInput.model_validate(
            {"expected_revision": 0, "enabled": "false", "fields": {}}
        )
    with pytest.raises(ValidationError):
        OrganizationUnitInput(name="Team", provider_id="provider")


def test_presentation_mapping_rejects_credential_claim_case_variants():
    import pytest
    from pydantic import ValidationError

    from koinon.organization_people.dtos import OrganizationProfileFields

    for claim in (
        "accessToken",
        "refresh_token",
        "password",
        "client_secret",
        "api_key",
        "authorization",
        "cookie",
        "privateKey",
        "user_password",
        "passwordHash",
    ):
        with pytest.raises(ValidationError):
            OrganizationProfileFields(job_title=claim)
    assert OrganizationProfileFields(job_title="koinon_jobTitle").job_title == "koinon_jobTitle"
    assert OrganizationProfileFields(job_title="secretariat_title").job_title == "secretariat_title"


def test_credential_tokens_embedded_inside_custom_claim_names_are_rejected():
    import pytest
    from pydantic import ValidationError

    from koinon.organization_people.dtos import OrganizationProfileFields

    for claim in (
        "custom_client_secret_value",
        "userAccessTokenValue",
        "oidcPrivateKeyData",
        "userPasswordHash",
    ):
        with pytest.raises(ValidationError):
            OrganizationProfileFields(job_title=claim)
    assert OrganizationProfileFields(job_title="secretariat_title").job_title == "secretariat_title"


def test_generic_secret_tokens_are_rejected_without_blocking_secretariat_names():
    import pytest
    from pydantic import ValidationError

    from koinon.organization_people.dtos import OrganizationProfileFields

    for claim in ("custom_secret_value", "user_secret", "userSecretValue", "USER_SECRET"):
        with pytest.raises(ValidationError):
            OrganizationProfileFields(job_title=claim)
    for claim in ("secretariat_title", "SecretaryJobTitle", "koinon_jobTitle"):
        assert OrganizationProfileFields(job_title=claim).job_title == claim


def test_output_revisions_fit_persisted_int32_and_read_update_sdk_contract():
    import pytest
    from pydantic import ValidationError

    from koinon.organization_people.dtos import (
        OrganizationDirectorySettings,
        OrganizationPerson,
        OrganizationProfileMapping,
        OrganizationUnit,
    )

    for model, values in (
        (OrganizationPerson, {"display_name": "Member"}),
        (OrganizationUnit, {"id": "id", "name": "Team", "kind": "team", "tenant_id": "north"}),
        (OrganizationDirectorySettings, {"tenant_id": "north"}),
        (OrganizationProfileMapping, {"tenant_id": "north", "provider_id": "provider"}),
    ):
        with pytest.raises(ValidationError):
            model(**values, revision=2147483648)
        assert model(**values, revision=2147483647).revision == 2147483647
    with pytest.raises(ValidationError):
        OrganizationUnit(id="id", name="Team", kind="team", tenant_id="north", revision=0)
