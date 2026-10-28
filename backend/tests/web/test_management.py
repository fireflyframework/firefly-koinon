# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from conftest import ISSUER, bearer


def test_signed_native_identity_and_context(client):
    assert client.get("/api/v1/context").status_code == 401
    response = client.get("/api/v1/context", headers=bearer())
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["subject"] == f"{ISSUER}|admin"
    assert [tenant["id"] for tenant in body["tenants"]] == ["north"]
    assert body["workspaces"][0]["id"] == client.workspace_id
    assert client.get("/api/v1/tenants/south/catalog", headers=bearer()).status_code == 403


def test_catalog_crud_roles_and_ancestry(client):
    url = "/api/v1/tenants/north/catalog"
    assert (
        client.post(
            url,
            headers=bearer("viewer"),
            json={"kind": "project", "name": "P", "parent_id": client.workspace_id},
        ).status_code
        == 403
    )
    response = client.post(
        url,
        headers=bearer("editor"),
        json={
            "kind": "project",
            "name": "Quarterly",
            "parent_id": client.workspace_id,
            "metadata": {"purpose": "analysis"},
        },
    )
    assert response.status_code == 201, response.text
    project = response.json()
    assert project["workspace_id"] == client.workspace_id
    assert project["metadata"] == {"purpose": "analysis"}
    entry_url = url + "/" + project["id"]
    assert client.get(entry_url, headers=bearer("viewer")).status_code == 200
    assert (
        client.patch(entry_url, headers=bearer("editor"), json={"name": "Renamed"}).json()["name"]
        == "Renamed"
    )
    assert client.patch(entry_url, headers=bearer(), json={"tenant_id": "south"}).status_code == 422
    assert (
        client.get("/api/v1/tenants/south/catalog/" + project["id"], headers=bearer("outsider")).status_code
        == 403
    )
    assert (
        client.post(
            url,
            headers=bearer(),
            json={"kind": "dataset", "name": "Orphan", "parent_id": client.workspace_id},
        ).status_code
        == 400
    )
    assert client.delete(entry_url, headers=bearer("editor")).status_code == 204


def test_memberships_last_admin_and_revocation(client):
    url = "/api/v1/tenants/north/members"
    assert client.get(url, headers=bearer("editor")).status_code == 403
    assert client.delete(url + "/admin", headers=bearer()).status_code == 409
    response = client.post(url, headers=bearer(), json={"subject": f"{ISSUER}|new-user", "role": "viewer"})
    assert response.status_code == 201, response.text
    member = response.json()
    assert client.get("/api/v1/tenants/north/catalog", headers=bearer("new-user")).status_code == 200
    assert client.delete(url + "/" + member["id"], headers=bearer()).status_code == 204
    assert client.get("/api/v1/tenants/north/catalog", headers=bearer("new-user")).status_code == 403
    assert (
        client.post(
            url, headers=bearer(), json={"subject": "email@example.test", "role": "admin"}
        ).status_code
        == 400
    )


def test_health_readiness_capabilities_and_audit_are_honest(client):
    assert client.get("/health").json()["status"] == "up"
    assert client.get("/ready").status_code == 200
    body = client.get("/api/v1/capabilities", headers=bearer()).json()
    assert body["catalog"]["ready"]
    assert not body["agentic"]["verified"]
    assert client.get("/api/v1/tenants/north/audit", headers=bearer("viewer")).status_code == 403
    events = client.get("/api/v1/tenants/north/audit", headers=bearer()).json()["items"]
    assert any(event["action"] == "catalog.created" for event in events)


def test_workspace_scope_cannot_be_spoofed_and_nonempty_parent_is_preserved(client):
    url = "/api/v1/tenants/north/catalog"
    workspace = client.post(url, headers=bearer(), json={"kind": "workspace", "name": "Other"}).json()
    response = client.get(
        url, headers=bearer(), params={"parent_id": client.workspace_id, "workspace_id": workspace["id"]}
    )
    assert response.status_code == 400
    project = client.post(
        url, headers=bearer(), json={"kind": "project", "name": "Child", "parent_id": client.workspace_id}
    ).json()
    assert client.delete(url + "/" + client.workspace_id, headers=bearer()).status_code == 409
    assert (
        client.post(
            "/api/v1/tenants/north/members",
            headers=bearer(),
            json={
                "subject": f"{ISSUER}|scoped",
                "role": "editor",
                "workspace_id": project["id"],
            },
        ).status_code
        == 400
    )
    membership = client.post(
        "/api/v1/tenants/north/members",
        headers=bearer(),
        json={
            "subject": f"{ISSUER}|scoped",
            "role": "editor",
            "workspace_id": client.workspace_id,
        },
    )
    assert membership.status_code == 201
    assert (
        client.get(url, headers=bearer("scoped"), params={"workspace_id": workspace["id"]}).status_code == 403
    )
    assert (
        client.get(url, headers=bearer("scoped"), params={"workspace_id": client.workspace_id}).status_code
        == 200
    )


def test_admin_can_handover_but_cannot_remove_final_admin(client):
    url = "/api/v1/tenants/north/members"
    response = client.post(url, headers=bearer(), json={"subject": f"{ISSUER}|replacement", "role": "admin"})
    assert response.status_code == 201
    assert (
        client.patch(url + "/admin", headers=bearer("replacement"), json={"role": "viewer"}).status_code
        == 200
    )
    assert client.delete(url + "/" + response.json()["id"], headers=bearer("replacement")).status_code == 409
    assert client.get(url, headers=bearer()).status_code == 403


def test_job_listing_and_cancellation_validate_actual_resource_scope(client):
    from koinon.catalog.service import CatalogService
    from koinon.jobs.service import JobService

    context = client.native_app.state.context

    async def jobs():
        service = context.get_bean(JobService)
        catalog = context.get_bean(CatalogService)
        other = await catalog.create(f"{ISSUER}|outsider", "south", kind="workspace", name="Other tenant")
        owned = await service.submit("north", client.workspace_id, "ingest", {"blob": "owned"}, "own-job")
        victim = await service.submit("south", other.id, "ingest", {"blob": "private"}, "other-job")
        return owned.id, victim.id

    owned, victim = client.portal.call(jobs)
    url = "/api/v1/tenants/north/jobs"
    listed = client.get(url, headers=bearer("viewer"))
    assert listed.status_code == 200
    assert [job["id"] for job in listed.json()["items"]] == [owned]
    fetched = client.get(url + "/" + owned, headers=bearer("viewer"))
    assert fetched.status_code == 200, fetched.text
    assert fetched.json()["id"] == owned
    assert "payload" not in fetched.json()
    assert client.get(url + "/" + victim, headers=bearer()).status_code == 403
    assert client.get(url + "/missing", headers=bearer()).status_code == 403
    assert client.get(url + "/" + owned, headers=bearer("outsider")).status_code == 403
    assert client.post(url + "/" + victim + "/cancel", headers=bearer()).status_code == 403
    assert client.post(url + "/" + owned + "/cancel", headers=bearer("viewer")).status_code == 403
    cancelled = client.post(url + "/" + owned + "/cancel", headers=bearer("editor"))
    assert cancelled.status_code == 200, cancelled.text
    assert cancelled.json()["status"] == "cancelled"
    audit = client.get("/api/v1/tenants/north/audit", headers=bearer()).json()["items"]
    assert any(event["action"] == "job.cancelled" for event in audit)


def test_native_problem_details_expose_actionable_code_and_support_reference(client):
    response = client.post(
        "/api/v1/tenants/north/catalog",
        headers=bearer("viewer"),
        json={"kind": "workspace", "name": "Denied"},
    )
    assert response.status_code == 403
    assert response.headers["content-type"].startswith("application/problem+json")
    body = response.json()
    assert body["code"] == "ACCESS_DENIED" and body["detail"]
    assert body["transactionId"]


def test_job_detail_honors_workspace_membership_within_same_organization(client):
    from koinon.catalog.service import CatalogService
    from koinon.jobs.service import JobService

    async def setup():
        context = client.native_app.state.context
        catalog = context.get_bean(CatalogService)
        service = context.get_bean(JobService)
        workspace = await catalog.create(f"{ISSUER}|admin", "north", kind="workspace", name="Private")
        visible = await service.submit("north", client.workspace_id, "ingest", {}, "visible")
        hidden = await service.submit("north", workspace.id, "ingest", {"private": True}, "hidden")
        return visible.id, hidden.id

    visible, hidden = client.portal.call(setup)
    member = client.post(
        "/api/v1/tenants/north/members",
        headers=bearer(),
        json={
            "subject": f"{ISSUER}|job-reader",
            "role": "viewer",
            "workspace_id": client.workspace_id,
        },
    )
    assert member.status_code == 201, member.text
    base = "/api/v1/tenants/north/jobs"
    assert client.get(base + "/" + visible, headers=bearer("job-reader")).status_code == 200
    assert client.get(base + "/" + hidden, headers=bearer("job-reader")).status_code == 403
    assert [job["id"] for job in client.get(base, headers=bearer("job-reader")).json()["items"]] == [visible]
