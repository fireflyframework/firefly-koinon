# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import httpx
import pytest

from koinon_sdk import KoinonClient


async def test_organization_self_preserves_unassigned_identity_without_a_write():
    requests = []

    def handle(request):
        requests.append(request)
        return httpx.Response(200, json={"display_name": "Alex Morgan", "id": None, "revision": 0})

    async with KoinonClient(
        "https://knowledge.test/api/v1",
        token_provider=lambda: "directory-reader",
        transport=httpx.MockTransport(handle),
    ) as client:
        person = await client.organization_person_self("north/office", workspace_id="shared space")
    assert person.id is None and person.revision == 0 and person.job_title is None
    assert len(requests) == 1 and requests[0].method == "GET"
    assert requests[0].url.raw_path.startswith(b"/api/v1/tenants/north%2Foffice/organization/people/me?")
    assert dict(requests[0].url.params) == {"workspace_id": "shared space"}


async def test_organization_directory_preserves_explicit_filters_and_typed_people():
    requests = []

    def handle(request):
        requests.append(request)
        return httpx.Response(
            200,
            json={
                "items": [{"id": "person", "display_name": "Alex Morgan", "job_title": "Engineer"}],
                "total": 1,
                "page": 2,
                "page_size": 10,
                "pages": 1,
            },
        )

    async with KoinonClient(
        "https://knowledge.test/api/v1",
        token_provider=lambda: "directory-reader",
        transport=httpx.MockTransport(handle),
    ) as client:
        result = await client.organization_people(
            "north", workspace_id="shared", q="Alex", unassigned=False, page=2, page_size=10
        )
    assert result.items[0].job_title == "Engineer" and result.page == 2
    assert dict(requests[0].url.params) == {
        "workspace_id": "shared",
        "q": "Alex",
        "unassigned": "false",
        "page": "2",
        "page_size": "10",
    }


async def test_organization_writes_and_hierarchy_helpers_keep_nulls_and_revisions():
    import json

    from koinon_sdk import (
        OrganizationDirectorySettingsInput,
        OrganizationPersonCreate,
        OrganizationPersonPatch,
        OrganizationProfileFields,
        OrganizationProfileMappingInput,
        OrganizationUnitInput,
        OrganizationUnitPatch,
    )

    requests = []
    unit = {"id": "unit", "tenant_id": "north", "name": "Engineering", "kind": "department", "revision": 3}

    def handle(request):
        requests.append(request)
        path = request.url.path
        if request.method == "DELETE":
            return httpx.Response(204)
        if path.endswith("/avatar"):
            return httpx.Response(304, headers={"ETag": '"photo"'})
        if "/profile-mappings/" in path:
            return httpx.Response(200, json={"tenant_id": "north", "provider_id": "provider", "fields": {}})
        if path.endswith("/directory-settings"):
            return httpx.Response(
                200, json={"tenant_id": "north", "revision": 1, "visibility": "administrators"}
            )
        if path.endswith("/units") and request.method == "GET":
            return httpx.Response(
                200, json={"items": [unit], "total": 1, "page": 1, "page_size": 25, "pages": 1}
            )
        if "/units" in path:
            return httpx.Response(200, json=unit)
        if path.endswith("/reports"):
            return httpx.Response(200, json={"items": [], "total": 0, "page": 1, "page_size": 25, "pages": 0})
        return httpx.Response(200, json={"id": "person", "display_name": "Alex Morgan", "revision": 4})

    async with KoinonClient(
        "https://knowledge.test/api/v1",
        token_provider=lambda: "directory-admin",
        transport=httpx.MockTransport(handle),
    ) as client:
        await client.create_organization_person(
            "north", OrganizationPersonCreate(profile_id="profile", job_title="Engineer")
        )
        await client.organization_person("north", "person/one", workspace_id="shared")
        await client.update_organization_person(
            "north", "person/one", OrganizationPersonPatch(expected_revision=4, manager_id=None)
        )
        photo = await client.organization_person_avatar(
            "north", "person/one", workspace_id="shared", if_none_match='"photo"'
        )
        reports = await client.organization_person_reports(
            "north", "person/one", workspace_id="shared", page=1
        )
        units = await client.organization_units("north", parent_id="division")
        await client.create_organization_unit("north", OrganizationUnitInput(name="Engineering"))
        await client.update_organization_unit(
            "north", "unit/one", OrganizationUnitPatch(expected_revision=3, parent_id=None)
        )
        await client.delete_organization_unit("north", "unit/one", expected_revision=3)
        await client.organization_directory_settings("north")
        await client.update_organization_directory_settings(
            "north", OrganizationDirectorySettingsInput(expected_revision=1, visibility="administrators")
        )
        await client.organization_profile_mapping("north", "provider/one")
        await client.update_organization_profile_mapping(
            "north",
            "provider/one",
            OrganizationProfileMappingInput(
                expected_revision=0, enabled=True, fields=OrganizationProfileFields(job_title="job_title")
            ),
        )
    assert len(requests) == 13
    assert json.loads(requests[2].content) == {"expected_revision": 4, "manager_id": None}
    assert requests[2].url.raw_path.endswith(b"/people/person%2Fone")
    assert photo.not_modified and photo.etag == '"photo"'
    assert requests[3].headers["if-none-match"] == '"photo"'
    assert reports.items == [] and units.items[0].name == "Engineering"
    assert json.loads(requests[7].content) == {"expected_revision": 3, "parent_id": None}
    assert dict(requests[8].url.params) == {"expected_revision": "3"}
    assert requests[11].url.raw_path.endswith(b"/profile-mappings/provider%2Fone")
    assert requests[12].method == "PUT"


def test_organization_inputs_reject_role_fields_and_coerced_revisions():
    from pydantic import ValidationError

    from koinon_sdk import OrganizationPersonPatch

    with pytest.raises(ValidationError):
        OrganizationPersonPatch(expected_revision=True)
    with pytest.raises(ValidationError):
        OrganizationPersonPatch.model_validate({"expected_revision": 1, "roles": ["admin"]})
