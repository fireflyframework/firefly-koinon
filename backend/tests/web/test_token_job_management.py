# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from datetime import UTC, datetime, timedelta

from conftest import bearer

from koinon.jobs.service import JobService


def token_headers(client, scopes):
    response = client.post(
        "/api/v1/tokens",
        headers=bearer(),
        json={
            "name": "Job management integration",
            "tenant_id": "north",
            "scopes": scopes,
            "expires_at": (datetime.now(UTC) + timedelta(hours=1)).isoformat(),
        },
    )
    assert response.status_code == 201, response.text
    return {"Authorization": "Bearer " + response.json()["token"]}


def job(client, key):
    service = client.native_app.state.context.get_bean(JobService)
    return client.portal.call(service.submit, "north", client.workspace_id, "ingest", {}, key)


def test_advertised_job_management_scope_can_cancel_without_ingestion_permission(client):
    queued = job(client, "management-token")
    headers = token_headers(client, ["catalog:read", "jobs:manage"])
    response = client.post(f"/api/v1/tenants/north/jobs/{queued.id}/cancel", headers=headers)
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "cancelled"


def test_read_only_token_cannot_cancel_and_existing_ingestion_authority_still_can(client):
    queued = job(client, "read-vs-ingest")
    path = f"/api/v1/tenants/north/jobs/{queued.id}/cancel"
    assert client.post(path, headers=token_headers(client, ["catalog:read"])).status_code == 403
    response = client.post(path, headers=token_headers(client, ["ingest:write"]))
    assert response.status_code == 200, response.text
    assert (
        client.post(
            path.replace("/north/", "/south/"), headers=token_headers(client, ["jobs:manage", "catalog:read"])
        ).status_code
        == 403
    )


def test_job_management_token_loses_authority_when_user_role_changes(client):
    from koinon.catalog.repositories import MembershipRepository

    queued = job(client, "role-downgrade")
    headers = token_headers(client, ["catalog:read", "jobs:manage"])

    async def downgrade():
        repository = client.native_app.state.context.get_bean(MembershipRepository)
        member = await repository.find_by_id("admin")
        member.role = "viewer"
        await repository.save(member)

    client.portal.call(downgrade)
    path = f"/api/v1/tenants/north/jobs/{queued.id}/cancel"
    assert client.post(path, headers=headers).status_code == 403
    assert client.get(path.removesuffix("/cancel"), headers=headers).json()["status"] == "queued"
