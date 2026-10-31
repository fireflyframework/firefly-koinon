# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""In-process native RSA/JWKS to persisted CIAM evidence; no listener/provider calls."""

import importlib.util
import time
from pathlib import Path

import jwt

ROOT = Path(__file__).resolve().parents[3]
spec = importlib.util.spec_from_file_location(
    "ciam_signed_native_fixture", ROOT / "backend/tests/web/conftest.py"
)
native = importlib.util.module_from_spec(spec)
spec.loader.exec_module(native)
client = native.client


def test_signed_bearer_to_native_profile_binding_claims_and_same_token_dedup(client):
    from pyfly.data.relational.sqlalchemy import transactional

    from koinon.corporate_identity.entities import CorporateProvider
    from koinon.corporate_identity.repositories import CorporateProviderRepository
    from koinon.corporate_profiles.dtos import CorporateProfileSyncPolicy
    from koinon.corporate_profiles.repositories import CorporateProfileRepository
    from koinon.corporate_profiles.settings import CorporateProfileSettings
    from koinon.organization_people.dtos import OrganizationProfileFields, OrganizationProfileMappingInput
    from koinon.organization_people.service import OrganizationPeopleService

    context = client.native_app.state.context

    async def setup():
        context.get_bean(CorporateProfileSettings).worker_enabled = False
        provider = CorporateProvider(
            id="inert-native",
            tenant_id="north",
            kind="keycloak",
            name="Inert native connection",
            canonical_issuer=native.ISSUER,
            source_key="inert-native",
            status="active",
            settings_json={"kind": "keycloak", "issuer": native.ISSUER, "client_id": "browser"},
            created_by=native.ISSUER + "|admin",
            updated_by=native.ISSUER + "|admin",
        )
        await context.get_bean(CorporateProviderRepository).save(provider)
        await context.get_bean(OrganizationPeopleService).update_mapping(
            native.ISSUER + "|admin",
            "north",
            provider.id,
            OrganizationProfileMappingInput(
                expected_revision=0,
                enabled=True,
                fields=OrganizationProfileFields(job_title="job_title"),
                profile_sync=CorporateProfileSyncPolicy(
                    name_source="personal",
                    avatar_source="personal",
                    job_title_source="verified_claims",
                    unit_source="local",
                    manager_source="local",
                ),
            ),
        )

    client.portal.call(setup)
    original_get = context.get_bean(OrganizationPeopleService).get
    calls = []

    async def captured_get(*args, **kwargs):
        calls.append(args)
        return await original_get(*args, **kwargs)

    context.get_bean(OrganizationPeopleService).get = captured_get
    issued = int(time.time()) - 30

    def headers(iat, title):
        encoded = jwt.encode(
            {
                "iss": native.ISSUER,
                "sub": "viewer",
                "aud": "koinon-api",
                "iat": iat,
                "exp": int(time.time()) + 300,
                "job_title": title,
                "roles": ["admin"],
            },
            native.KEY,
            algorithm="RS256",
            headers={"kid": "local-key"},
        )
        return {"Authorization": "Bearer " + encoded}

    url = "/api/v1/tenants/north/organization/people/me"
    credential = headers(issued, "Native verified engineer")
    first = client.get(url, headers=credential)
    assert first.status_code == 200, (first.text, calls)
    assert first.json()["job_title"] == "Native verified engineer"
    second = client.get(url, headers=credential)
    assert second.status_code == 200 and second.json()["revision"] == first.json()["revision"]
    assert client.get("/api/v1/tenants/north/members", headers=credential).status_code == 403

    @transactional(read_only=True)
    async def state():
        row = await context.get_bean(CorporateProfileRepository).owner("north", native.ISSUER + "|viewer")
        return row.binding_revision, row.claims_observed_at.timestamp()

    assert client.portal.call(state) == (1, float(issued))
    cleared = client.get(url, headers=headers(issued + 1, None))
    assert cleared.status_code == 200 and cleared.json()["job_title"] is None
    assert cleared.json()["revision"] == first.json()["revision"] + 1
    assert client.portal.call(state) == (2, float(issued + 1))


def test_native_me_refresh_is_not_shadowed_by_person_refresh(client):
    from koinon.corporate_profiles.service import CorporateProfileService

    service = client.native_app.state.context.get_bean(CorporateProfileService)
    original = service.refresh_person
    calls = []

    async def captured(*args, **kwargs):
        calls.append(args)
        return await original(*args, **kwargs)

    service.refresh_person = captured
    response = client.post(
        "/api/v1/tenants/north/organization/people/me/profile-refresh",
        headers=native.bearer("viewer"),
        json={},
    )
    assert response.status_code == 202, (response.text, calls)
