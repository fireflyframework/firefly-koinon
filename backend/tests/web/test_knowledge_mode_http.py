# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import pytest
from conftest import bearer
from test_organization_knowledge_http import body
from test_organization_knowledge_http import policy_client as policy_client


@pytest.fixture(autouse=True)
def mode_index_metadata(policy_client):
    from koinon.knowledge.indexes.repositories import KnowledgeIndexRepository

    policy_client.native_app.state.context.register_bean(KnowledgeIndexRepository)


ROOT = "/api/v1/tenants/north/knowledge/settings/transitions"


def test_mode_request_status_and_cancellation_have_real_revisioned_receipts(policy_client):
    client = policy_client
    assert client.get(ROOT + "/current").status_code == 401
    current = client.get(ROOT + "/current", headers=bearer())
    assert current.status_code == 200 and current.json() == {"transition": None}, current.text
    headers = {**bearer(), "Idempotency-Key": "http-mode"}
    requested = client.post(ROOT, headers=headers, json=body())
    assert requested.status_code == 202, requested.text
    record = requested.json()
    assert record["active_mode"] == "rlm" and record["requested_mode"] == "rag"
    assert record["status"] == "queued"
    replay = client.post(ROOT, headers=headers, json=body())
    assert replay.json()["id"] == record["id"]
    path = ROOT + "/" + record["id"]
    assert client.get(path, headers=bearer()).json() == record
    assert client.get(path + "/targets", headers=bearer()).json() == {"items": [], "next_cursor": None}
    assert client.get(path + "/targets?limit=201", headers=bearer()).status_code in (400, 422)
    assert client.get(path + "/recoveries", headers=bearer()).json() == {"items": [], "next_cursor": None}
    assert client.get(path + "/recoveries?limit=101", headers=bearer()).status_code in (400, 422)
    assert client.get(path + "/recoveries", headers=bearer("viewer")).status_code == 403
    assert client.post(path + "/cancel", headers=bearer(), json={"expected_revision": 99}).status_code == 409
    cancelled = client.post(
        path + "/cancel", headers=bearer(), json={"expected_revision": record["revision"]}
    )
    assert cancelled.status_code == 200, cancelled.text
    assert cancelled.json()["status"] == "cancelled"
    assert (
        client.post(
            path + "/retry", headers=bearer(), json={"expected_revision": cancelled.json()["revision"]}
        ).status_code
        == 409
    )
    active = client.get("/api/v1/tenants/north/knowledge/settings", headers=bearer()).json()
    assert active["documents"]["answer_mode"] == "rlm" and active["revision"] == 0


def test_mode_http_requires_admin_idempotency_and_exact_tenant(policy_client):
    client = policy_client
    for subject in ("viewer", "editor", "analyst", "outsider"):
        assert (
            client.post(
                ROOT, headers={**bearer(subject), "Idempotency-Key": "denied"}, json=body()
            ).status_code
            == 403
        )
        assert client.get(ROOT + "/current", headers=bearer(subject)).status_code == 403
    assert client.post(ROOT, headers=bearer(), json=body()).status_code == 400
    request = client.post(ROOT, headers={**bearer(), "Idempotency-Key": "tenant-bound"}, json=body()).json()
    foreign = ROOT.replace("/north/", "/south/") + "/" + request["id"]
    assert client.get(foreign, headers=bearer()).status_code == 403
    assert client.get(ROOT + "/missing", headers=bearer()).status_code == 403
