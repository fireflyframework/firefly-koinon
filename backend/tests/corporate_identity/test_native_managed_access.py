# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from datetime import UTC, datetime, timedelta

from test_identity_provider_http import native

from koinon.corporate_identity.entities import CorporateGrant, CorporateMapping, CorporateProvider
from koinon.corporate_identity.repositories import (
    CorporateGrantRepository,
    CorporateMappingRepository,
    CorporateProviderRepository,
)

client = native.client


def test_native_http_context_reads_a_late_bound_managed_port(client):
    # Controlled stored policy isolates native DI/read authorization; real SSO is qualified separately.
    async def policy():
        context = client.native_app.state.context
        await context.get_bean(CorporateProviderRepository).save(
            CorporateProvider(
                id="late-provider",
                tenant_id="north",
                kind="keycloak",
                name="Corporate research",
                canonical_issuer=native.ISSUER,
                source_key="@realm",
                settings_json={"kind": "keycloak", "issuer": native.ISSUER, "client_id": "browser"},
                status="active",
                revision=1,
                policy_revision=1,
                created_by=native.ISSUER + "|admin",
                updated_by=native.ISSUER + "|admin",
            )
        )
        await context.get_bean(CorporateMappingRepository).save(
            CorporateMapping(
                id="late-mapping",
                tenant_id="north",
                provider_id="late-provider",
                group_id="research",
                group_name="Research",
                role="editor",
                enabled=True,
                revision=1,
            )
        )
        now = datetime.now(UTC)
        await context.get_bean(CorporateGrantRepository).save(
            CorporateGrant(
                id="late-grant",
                tenant_id="north",
                provider_id="late-provider",
                mapping_id="late-mapping",
                subject=native.ISSUER + "|new-corporate",
                external_subject="new-corporate",
                role="editor",
                policy_revision=1,
                mapping_revision=1,
                active=True,
                observed_at=now,
                expires_at=now + timedelta(seconds=60),
            )
        )

    client.portal.call(policy)
    response = client.get("/api/v1/context", headers=native.bearer("new-corporate"))
    assert response.status_code == 200, response.text
    assert any(
        tenant["id"] == "north" and "catalog:write" in tenant["permissions"]
        for tenant in response.json()["tenants"]
    )
    rows = client.get("/api/v1/tenants/north/members?role=editor", headers=native.bearer())
    assert rows.status_code == 200, rows.text
    assert any(row["managed"] and row["source_name"] == "Corporate research" for row in rows.json()["items"])
