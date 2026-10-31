# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import json

import httpx
import pytest
from pydantic import ValidationError

from koinon_sdk import (
    CorporateProfileRefreshInput,
    CorporateProfileSyncPolicy,
    KoinonClient,
    OrganizationPresentationInput,
    OrganizationProfileFields,
    OrganizationProfileMappingInput,
)


async def test_tenant_presentation_is_read_without_changing_the_personal_profile():
    requests = []

    def handle(request):
        requests.append(request)
        return httpx.Response(
            200,
            json={
                "tenant_id": "north/office",
                "display_name": "Alex Rivera",
                "revision": 2,
                "name_source": "organization",
                "avatar_source": "organization",
                "status": "current",
            },
        )

    async with KoinonClient(
        "https://knowledge.test/api/v1",
        token_provider=lambda: "profile-reader",
        transport=httpx.MockTransport(handle),
    ) as client:
        value = await client.organization_presentation("north/office", workspace_id="shared space")
    assert value.display_name == "Alex Rivera" and value.revision == 2
    assert len(requests) == 1 and requests[0].method == "GET"
    assert requests[0].url.raw_path.startswith(
        b"/api/v1/tenants/north%2Foffice/organization/people/me/presentation?"
    )
    assert dict(requests[0].url.params) == {"workspace_id": "shared space"}


async def test_profile_preferences_and_refresh_keep_revisions_and_empty_admission_body():
    requests = []

    def handle(request):
        requests.append(request)
        if request.method == "PATCH":
            return httpx.Response(200, json={"tenant_id": "north", "revision": 4})
        return httpx.Response(202, json={"tenant_id": "north", "status": "queued"})

    async with KoinonClient(
        "https://knowledge.test/api/v1",
        token_provider=lambda: "profile-writer",
        transport=httpx.MockTransport(handle),
    ) as client:
        updated = await client.update_organization_presentation(
            "north", OrganizationPresentationInput(expected_revision=3, avatar_mode="personal"),
            workspace_id="shared",
        )
        queued = await client.refresh_organization_profile("north", workspace_id="shared")
        await client.refresh_organization_person_profile("north", "person/one")
    assert updated.revision == 4 and queued.status == "queued"
    assert [request.method for request in requests] == ["PATCH", "POST", "POST"]
    assert json.loads(requests[0].content) == {"expected_revision": 3, "avatar_mode": "personal"}
    assert dict(requests[1].url.params) == {"workspace_id": "shared"}
    assert requests[1].content == requests[2].content == b"{}"
    assert requests[2].url.raw_path.endswith(b"/person%2Fone/profile-refresh")


def test_profile_inputs_reject_null_preferences_and_upstream_identity_injection():
    with pytest.raises(ValidationError):
        OrganizationPresentationInput.model_validate({"expected_revision": 0, "name_mode": None})
    with pytest.raises(ValidationError):
        OrganizationPresentationInput(expected_revision=0)
    with pytest.raises(ValidationError):
        CorporateProfileRefreshInput.model_validate({"upstream_user_id": "another-user"})


def test_mapping_policy_preserves_omission_and_explicit_disable():
    common = {"expected_revision": 0, "enabled": True, "fields": OrganizationProfileFields()}
    omitted = OrganizationProfileMappingInput(**common).model_dump(mode="json", exclude_unset=True)
    disabled = OrganizationProfileMappingInput(**common, profile_sync=None).model_dump(
        mode="json", exclude_unset=True
    )
    enabled = OrganizationProfileMappingInput(
        **common, profile_sync=CorporateProfileSyncPolicy()
    ).model_dump(mode="json", exclude_unset=True)
    assert "profile_sync" not in omitted
    assert disabled["profile_sync"] is None
    assert enabled["profile_sync"] == {}
